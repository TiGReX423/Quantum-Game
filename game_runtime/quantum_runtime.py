
import math
import random

import pygame

from settings import CAMERA_RAY_COUNT, CAMERA_RAY_STEP
from game_utils import angle_to, angle_diff


class QuantumRuntimeMixin:
    def quantum_button_key(self, button):
        return button.get("id") or f"{button['rect'].x}:{button['rect'].y}"

    def quantum_choice_value(self, session_seed, group_id, cam_uid, button_key):
        group_hash = sum(ord(ch) for ch in str(group_id))
        button_hash = sum(ord(ch) for ch in str(button_key))
        return (int(session_seed) * 1103515245 + group_hash * 97531 + int(cam_uid) * 2654435761 + button_hash * 19349663) & 0xFFFFFFFF

    def quantum_wall_key(self, wall):
        return f"{wall['layer']}:{wall['x']}:{wall['y']}"

    def get_quantum_button_state(self, state, button):
        return state.setdefault("button_states", {}).get(id(button), "unresolved")

    def set_quantum_button_state(self, state, button, value):
        state.setdefault("button_states", {})[id(button)] = value

    def reset_quantum_button_group(self, state, buttons):
        state["mode"] = "classical"
        state["collapsed_state"] = ""
        state["button_states"] = {}
        state["session_seed"] = None
        for button in buttons:
            button["collapsed_out"] = False
            button["pressed_once"] = False
            button["active"] = False
            button["observable"] = False
            button["occupied_now"] = False

    def reset_quantum_wall_group(self, state, walls):
        state["session_seed"] = None
        state["wall_states"] = {}
        for wall in walls:
            wall["active"] = True
            wall["collapsed_out"] = False
            wall["observed"] = False
            wall["resolved_state"] = "unresolved"

    def build_quantum_wall_states(self, state, group_id, walls, cameras):
        ordered_walls = sorted(walls, key=lambda wall: (wall["x"], wall["y"], wall["layer"]))
        unresolved = list(ordered_walls)
        wall_states = {id(wall): "unresolved" for wall in ordered_walls}
        classical_wall = None

        for cam in sorted(cameras, key=lambda camera: camera.get("uid", 0)):
            visible = [wall for wall in unresolved if self.camera_sees_rect(cam, wall["rect"], ignore_rect=wall["rect"])]
            visible.sort(key=lambda wall: (wall["x"], wall["y"], wall["layer"]))
            for wall in visible:
                if wall not in unresolved:
                    continue
                if len(unresolved) <= 1:
                    classical_wall = unresolved[0]
                    break
                roll = self.quantum_choice_value(
                    state["session_seed"],
                    group_id,
                    cam.get("uid", 0),
                    self.quantum_wall_key(wall),
                )
                if roll % 2 == 0:
                    classical_wall = wall
                    break
                unresolved.remove(wall)
                wall_states[id(wall)] = "disappeared"
            if classical_wall is not None:
                break

        if classical_wall is None and len(unresolved) == 1:
            classical_wall = unresolved[0]

        if classical_wall is not None:
            for wall in ordered_walls:
                wall_states[id(wall)] = "classical" if wall is classical_wall else "disappeared"

        state["wall_states"] = wall_states

    def build_quantum_button_states(self, state, group_id, buttons, cameras):
        ordered_buttons = sorted(buttons, key=lambda button: button["rect"].centerx)
        unresolved = list(ordered_buttons)
        button_states = {id(button): "unresolved" for button in ordered_buttons}
        classical_button = None

        for cam in sorted(cameras, key=lambda camera: camera.get("uid", 0)):
            visible = [button for button in unresolved if self.camera_sees_rect(cam, button["rect"])]
            visible.sort(key=lambda button: button["rect"].centerx)
            for button in visible:
                if button not in unresolved:
                    continue
                if len(unresolved) <= 1:
                    classical_button = unresolved[0]
                    break
                roll = self.quantum_choice_value(
                    state["session_seed"],
                    group_id,
                    cam.get("uid", 0),
                    self.quantum_button_key(button),
                )
                if roll % 2 == 0:
                    classical_button = button
                    break
                unresolved.remove(button)
                button_states[id(button)] = "disappeared"
            if classical_button is not None:
                break

        if classical_button is None and len(unresolved) == 1:
            classical_button = unresolved[0]

        if classical_button is not None:
            for button in ordered_buttons:
                button_states[id(button)] = "classical" if button is classical_button else "disappeared"

        state["button_states"] = button_states

    def refresh_quantum_buttons(self):
        actor_rects = [self.player.rect] + [box["rect"] for box in self.boxes]

        for button in self.quantum_buttons:
            button["observable"] = False
            button["occupied_now"] = False
            button["active"] = False

        cameras = [cam for cam in self.placed_cameras if not cam["removed"]]
        for group_id, buttons in self.quantum_groups.items():
            state = self.quantum_group_state.setdefault(
                group_id,
                {
                    "was_observed": False,
                    "mode": "classical",
                    "observer_signature": 0,
                    "collapsed_state": "",
                    "collapse_mode": self.get_quantum_collapse_mode(buttons),
                    "button_states": {},
                    "session_seed": None,
                },
            )

            visible_pairs = []
            for button in buttons:
                if button["removed"]:
                    continue
                for cam in cameras:
                    if self.camera_sees_rect(cam, button["rect"]):
                        dist = math.hypot(
                            cam["rect"].centerx - button["rect"].centerx,
                            cam["rect"].centery - button["rect"].centery,
                        )
                        visible_pairs.append((dist, button, cam))
                        break

            observed_now = bool(visible_pairs)
            state["was_observed"] = observed_now

            target_ids = {
                target_id
                for button in buttons
                for target_id in self.parse_target_ids(button.get("target_id", ""))
            }
            if not observed_now:
                self.reset_quantum_button_group(state, buttons)
                for target_id in target_ids:
                    self.set_button_target_state(target_id, False)
                continue

            if state.get("session_seed") is None:
                state["session_seed"] = random.randrange(1, 1 << 30)

            observing_cameras = []
            for _dist, _button, cam in visible_pairs:
                if cam not in observing_cameras:
                    observing_cameras.append(cam)

            self.build_quantum_button_states(state, group_id, buttons, observing_cameras)

            any_pressed = False
            for button in buttons:
                button["scanned"] = True
                current_state = self.get_quantum_button_state(state, button)
                button["collapsed_out"] = current_state == "disappeared"
                button["observable"] = current_state == "classical"
                if button["removed"] or button.get("collapsed_out", False):
                    button["active"] = False
                    button["occupied_now"] = False
                    continue
                button["occupied_now"] = any(button["rect"].colliderect(rect) for rect in actor_rects)
                if current_state == "classical" and button["occupied_now"]:
                    button["pressed_once"] = True
                button["active"] = current_state == "classical" and button.get("pressed_once", False)
                if button["active"]:
                    any_pressed = True

            for target_id in target_ids:
                if any_pressed:
                    self.set_button_target_state(target_id, True)
                else:
                    self.set_button_target_state(target_id, False)

    def refresh_quantum_walls(self):
        if not self.quantum_wall_groups:
            return

        cameras = [cam for cam in self.placed_cameras if not cam["removed"]]
        changed = False
        for group_id, walls in self.quantum_wall_groups.items():
            state = self.quantum_wall_state.setdefault(group_id, {"session_seed": None, "wall_states": {}})
            visible_pairs = []
            for wall in walls:
                wall["observed"] = False
                for cam in cameras:
                    if self.camera_sees_rect(cam, wall["rect"], ignore_rect=wall["rect"]):
                        wall["observed"] = True
                        dist = math.hypot(
                            cam["rect"].centerx - wall["rect"].centerx,
                            cam["rect"].centery - wall["rect"].centery,
                        )
                        visible_pairs.append((dist, wall, cam))
                        break

            if not visible_pairs:
                for wall in walls:
                    if not wall.get("active", True) or wall.get("collapsed_out", False):
                        changed = True
                self.reset_quantum_wall_group(state, walls)
                continue

            mode = next((wall.get("subtype", "") for wall in walls if wall.get("subtype")), "single_only")
            if mode == "single_only":
                if state.get("session_seed") is None:
                    state["session_seed"] = random.randrange(1, 1 << 30)
                observing_cameras = []
                for _dist, _wall, cam in visible_pairs:
                    if cam not in observing_cameras:
                        observing_cameras.append(cam)
                self.build_quantum_wall_states(state, group_id, walls, observing_cameras)
                for wall in walls:
                    wall_state = state["wall_states"].get(id(wall), "unresolved")
                    active = wall_state != "disappeared"
                    if wall.get("active", True) != active:
                        changed = True
                    wall["active"] = active
                    wall["collapsed_out"] = wall_state == "disappeared"
                    wall["resolved_state"] = wall_state
            else:
                state["session_seed"] = None
                sorted_walls = sorted(walls, key=lambda wall: (wall["x"], wall["y"]))
                cam = min(visible_pairs, key=lambda item: item[0])[2]
                signature = self.compute_observer_signature(group_id, cam, len(sorted_walls))
                collapsed_state = self.build_quantum_collapsed_state(mode, len(sorted_walls), signature)
                for wall, bit in zip(sorted_walls, collapsed_state):
                    active = bit == "1"
                    if wall.get("active", True) != active:
                        changed = True
                    wall["active"] = active
                    wall["collapsed_out"] = not active
                    wall["resolved_state"] = "classical" if active else "disappeared"

        if changed:
            self.door_state_version += 1
            self.invalidate_ray_cache()

    def get_quantum_collapse_mode(self, buttons):
        for button in buttons:
            subtype = button.get("subtype") or button.get("props", {}).get("subtype", "")
            if subtype:
                return subtype
        return "single_or_none"

    def get_unresolved_quantum_buttons(self, buttons):
        unresolved = [
            button
            for button in buttons
            if not button.get("removed", False)
        ]
        return sorted(unresolved, key=lambda button: button["rect"].centerx)

    def build_quantum_basis_states(self, count):
        if count <= 0:
            return []

        full_state = "1" * count
        vanished_all = "0" * count
        states = [full_state]
        for index in range(count):
            mask = ["1"] * count
            mask[index] = "0"
            states.append("".join(mask))
        states.append(vanished_all)
        return states

    def compute_observer_signature(self, group_id, cam, remaining_count):
        angle = int(round(cam["angle"] * 10))
        group_hash = sum(ord(ch) for ch in group_id)
        return (
            (cam["rect"].centerx * 73856093)
            ^ (cam["rect"].centery * 19349663)
            ^ (angle * 83492791)
            ^ (remaining_count * 2654435761)
            ^ (group_hash * 97531)
        ) & 0xFFFFFFFF

    def build_quantum_collapsed_state(self, collapse_mode, unresolved_count, signature):
        if unresolved_count <= 0:
            return ""

        collapse_mode = {
            "one_stays": "single_only",
            "one_or_none": "single_or_none",
            "one_vanishes": "pair_only",
            "one_vanishes_or_none": "pair_or_none",
        }.get(collapse_mode, collapse_mode)

        if collapse_mode == "single_only":
            survivor_index = signature % unresolved_count
            return "".join("1" if idx == survivor_index else "0" for idx in range(unresolved_count))

        if collapse_mode == "single_or_none":
            bucket = signature % (unresolved_count + 2)
            if bucket == unresolved_count + 1:
                return "0" * unresolved_count
            survivor_index = bucket % unresolved_count
            return "".join("1" if idx == survivor_index else "0" for idx in range(unresolved_count))

        if collapse_mode == "pair_only":
            if unresolved_count <= 1:
                return "1" * unresolved_count
            collapsed_index = signature % unresolved_count
            return "".join("0" if idx == collapsed_index else "1" for idx in range(unresolved_count))

        if collapse_mode == "pair_or_none":
            if unresolved_count <= 1:
                return "1" * unresolved_count
            if signature % 5 == 0:
                return "0" * unresolved_count
            collapsed_index = signature % unresolved_count
            return "".join("0" if idx == collapsed_index else "1" for idx in range(unresolved_count))

        if collapse_mode == "all_or_none":
            return "0" * unresolved_count if signature % 4 == 0 else "1" * unresolved_count

        return "1" * unresolved_count

    def collapse_quantum_group(self, group_id, buttons, cam=None, visible_pairs=None):
        unresolved = self.get_unresolved_quantum_buttons(buttons)
        count = len(unresolved)
        if count <= 0:
            return

        state = self.quantum_group_state.setdefault(group_id, {})
        state["collapse_mode"] = self.get_quantum_collapse_mode(buttons)
        visible_pairs = visible_pairs or []
        closest_button = min(visible_pairs, key=lambda item: item[0])[1] if visible_pairs else None

        if closest_button in unresolved and state["collapse_mode"] == "single_only":
            collapsed_state = "".join("1" if button is closest_button else "0" for button in unresolved)
            signature = 0
        else:
            if cam is None and visible_pairs:
                cam = min(visible_pairs, key=lambda item: item[0])[2]
            signature = self.compute_observer_signature(group_id, cam, count) if cam else count
            collapsed_state = self.build_quantum_collapsed_state(state["collapse_mode"], count, signature)

        for button, bit in zip(unresolved, collapsed_state):
            button["collapsed_out"] = (bit == "0")
            button["observable"] = (bit == "1")

        state["mode"] = "collapsed"
        state["observer_signature"] = signature
        state["collapsed_state"] = collapsed_state

    def camera_sees_rect(self, cam, rect, ignore_rect=None):
        target = rect.center
        origin = cam["rect"].center
        max_distance = cam["range_tiles"] * self.tile_size
        distance = math.hypot(target[0] - origin[0], target[1] - origin[1])
        if distance > max_distance:
            return False

        target_angle = angle_to(origin, target)
        if angle_diff(target_angle, cam["angle"]) > cam["fov"] / 2:
            return False

        return not self.line_blocked(origin, target, ignore_rect=ignore_rect)

    def line_blocked(self, start, end, ignore_rect=None):
        blockers = self.all_blocking_rects_for_rays()
        line = (start, end)
        for rect in blockers:
            if ignore_rect is not None and rect == ignore_rect:
                continue
            if rect.clipline(line):
                return True
        return False

    def raycast_to_wall(self, origin, angle_deg, max_distance, step_size=None):
        blockers = self.all_blocking_rects_for_rays()
        step_size = max(1, int(step_size or CAMERA_RAY_STEP))
        angle_rad = math.radians(angle_deg)
        dx = math.cos(angle_rad) * step_size
        dy = math.sin(angle_rad) * step_size

        x = origin[0]
        y = origin[1]
        travelled = 0

        while travelled < max_distance:
            x += dx
            y += dy
            travelled += step_size

            point = (int(x), int(y))
            if point[0] < 0 or point[1] < 0 or point[0] >= self.world_width or point[1] >= self.world_height:
                break

            if any(rect.collidepoint(point) for rect in blockers):
                x -= dx
                y -= dy
                break

        return (int(x), int(y))

    def get_camera_cone_points(self, cam):
        is_preview = bool(cam.get("preview", False))
        if cam.get("id") == "placed_camera":
            cache_key = (
                cam["rect"].x,
                cam["rect"].y,
                cam["angle"],
                cam["range_tiles"],
                cam["fov"],
                self.door_state_version,
            )
            cached = self.camera_cone_cache.get(cache_key)
            if cached is not None:
                return cached
        elif is_preview:
            quantized_angle = int(round(cam["angle"] / 6.0)) * 6
            cache_key = (
                "preview",
                cam["rect"].x,
                cam["rect"].y,
                quantized_angle,
                cam["range_tiles"],
                cam["fov"],
                self.door_state_version,
            )
            cached = self.camera_cone_cache.get(cache_key)
            if cached is not None:
                return cached

        origin = cam["rect"].center
        max_distance = cam["range_tiles"] * self.tile_size
        half_fov = cam["fov"] / 2
        ray_count = max(8, CAMERA_RAY_COUNT // 3) if is_preview else CAMERA_RAY_COUNT
        step_size = CAMERA_RAY_STEP * 2 if is_preview else CAMERA_RAY_STEP

        points = [origin]
        for i in range(ray_count + 1):
            angle = cam["angle"] - half_fov + (i / ray_count) * cam["fov"]
            points.append(self.raycast_to_wall(origin, angle, max_distance, step_size=step_size))

        if cam.get("id") == "placed_camera" or is_preview:
            self.camera_cone_cache[cache_key] = points
        return points

    def update_camera_follow(self, force=False):
        player_view_rect = pygame.Rect(
            self.player.rect.x - self.camera_x,
            self.player.rect.y - self.camera_y,
            self.player.rect.width,
            self.player.rect.height,
        )

        if force:
            self.camera_x = self.player.rect.centerx - self.viewport_width // 2
            self.camera_y = self.player.rect.centery - self.viewport_height // 2
        else:
            if player_view_rect.left < self.view_frame.left:
                self.camera_x = self.player.rect.left - self.view_frame.left
            elif player_view_rect.right > self.view_frame.right:
                self.camera_x = self.player.rect.right - self.view_frame.right

            if player_view_rect.top < self.view_frame.top:
                self.camera_y = self.player.rect.top - self.view_frame.top
            elif player_view_rect.bottom > self.view_frame.bottom:
                self.camera_y = self.player.rect.bottom - self.view_frame.bottom

        max_camera_x = max(0, self.world_width - self.viewport_width)
        max_camera_y = max(0, self.world_height - self.viewport_height)

        self.camera_x = max(0, min(int(self.camera_x), max_camera_x))
        self.camera_y = max(0, min(int(self.camera_y), max_camera_y))
