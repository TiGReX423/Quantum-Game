
import math
import os

import pygame

from game_constants import PERSISTENT_MESSAGE_FRAMES
from game_text import HOVER_HINTS, MESSAGES, TUTORIAL_PAGES
from game_utils import load_image, angle_to
from settings import *


class WorldRuntimeMixin:
    def screen_to_world_view(self, pos):
        return (int(pos[0] / self.zoom), int(pos[1] / self.zoom))

    def world_to_screen(self, x, y):
        return x - self.camera_x, y - self.camera_y

    def get_player_center(self):
        return self.player.rect.centerx, self.player.rect.centery

    def set_message(self, text, frames=MESSAGE_TIME):
        self.message = text
        self.message_timer = frames

    def is_close_enough(self, rect, extra=INTERACT_DISTANCE):
        px, py = self.get_player_center()
        cx, cy = rect.center
        return math.hypot(px - cx, py - cy) <= extra

    def can_interact_with(self, obj):
        if obj is None or obj.get("removed"):
            return False
        rect = obj.get("rect")
        if rect is None:
            return False
        return self.is_close_enough(rect)

    def should_draw_hand_cursor(self):
        if self.note_open_id or self.camera_place_mode:
            return False
        return self.can_interact_with(self.hovered_object)

    def get_slot_label(self, slot_id):
        if slot_id == 1 and self.inventory["camera"] > 0:
            return "Camera"
        if slot_id == 2 and self.inventory["watering_can"] > 0:
            return "Watering can"
        return "Empty"

    def get_equipped_item_kind(self):
        if self.selected_slot == 1 and self.inventory["camera"] > 0:
            return "camera"
        if self.selected_slot == 2 and self.inventory["watering_can"] > 0:
            return "watering_can"
        return ""

    def is_walkable_cell(self, tx, ty):
        if tx < 0 or ty < 0 or ty >= len(self.walkable_map) or tx >= len(self.walkable_map[ty]):
            return False
        return self.walkable_map[ty][tx] == "1"

    def active_quantum_wall_at_cell(self, tx, ty):
        tile = self.quantum_wall_at(tx, ty)
        return bool(tile and tile.get("active", True))

    def inactive_quantum_wall_at_cell(self, tx, ty):
        tile = self.quantum_wall_at(tx, ty)
        return bool(tile and not tile.get("active", True))

    def active_target_wall_at_cell(self, tx, ty):
        tile = self.target_wall_at(tx, ty)
        return bool(tile and tile.get("active", True))

    def inactive_target_wall_at_cell(self, tx, ty):
        tile = self.target_wall_at(tx, ty)
        return bool(tile and not tile.get("active", True))

    def rect_in_walkable(self, rect):
        # Movement checks use a few sample points near the feet so the player
        # can slide along corners while still respecting the walkable map.
        feet_points = [
            (rect.left + 4, rect.bottom - 2),
            (rect.centerx, rect.bottom - 2),
            (rect.right - 4, rect.bottom - 2),
        ]
        for px, py in feet_points:
            tx = int(px) // self.tile_size
            ty = int(py) // self.tile_size

            if self.active_quantum_wall_at_cell(tx, ty):
                return False
            if self.active_target_wall_at_cell(tx, ty):
                return False

            if (
                not self.is_walkable_cell(tx, ty)
                and not self.point_on_active_bridge(px, py)
                and not self.inactive_quantum_wall_at_cell(tx, ty)
                and not self.inactive_target_wall_at_cell(tx, ty)
            ):
                return False
        return True

    def point_on_inactive_quantum_wall(self, px, py):
        tx = int(px) // self.tile_size
        ty = int(py) // self.tile_size
        return self.inactive_quantum_wall_at_cell(tx, ty)

    def point_on_active_bridge(self, px, py):
        point = (int(px), int(py))
        for bridge in self.bridges:
            if bridge.get("removed") or not bridge.get("active", False):
                continue
            if bridge["rect"].collidepoint(point):
                return True
        for bridge in self.bridge_tiles:
            if bridge.get("removed") or not bridge.get("active", False):
                continue
            if bridge["rect"].collidepoint(point):
                return True
        return False

    def get_world_bounds(self):
        return pygame.Rect(0, 0, self.world_width, self.world_height)

    def collides_with_solid(self, rect, ignore_box=None, include_closed_doors=True):
        if include_closed_doors:
            for door in self.doors:
                if door["removed"]:
                    continue
                if rect.colliderect(door["rect"]):
                    return True

        for wall in self.quantum_wall_tiles:
            if wall.get("active", True) and rect.colliderect(wall["rect"]):
                return True

        for wall in self.target_wall_tiles:
            if wall.get("active", True) and rect.colliderect(wall["rect"]):
                return True

        for box in self.boxes:
            if box is ignore_box:
                continue
            if rect.colliderect(box["rect"]):
                return True

        return False

    def all_blocking_rects_for_rays(self):
        if self.blocking_rects_cache_version != self.door_state_version:
            rects = list(self.static_blocking_rects)
            for door in self.doors:
                if not door["removed"]:
                    rects.append(door["rect"])
            for wall in self.quantum_wall_tiles:
                if wall.get("active", True):
                    rects.append(wall["rect"])
            for wall in self.target_wall_tiles:
                if wall.get("active", True):
                    rects.append(wall["rect"])
            self.blocking_rects_cache = rects
            self.blocking_rects_cache_version = self.door_state_version
        return self.blocking_rects_cache

    def find_clicked_object(self, mouse_pos, objects):
        mouse_x, mouse_y = self.screen_to_world_view(mouse_pos)
        world_pos = (mouse_x + self.camera_x, mouse_y + self.camera_y)
        for obj in reversed(objects):
            if obj.get("removed"):
                continue
            if self.point_hits_object(world_pos, obj):
                return obj
        return None

    def find_clicked_cleanup_object(self, mouse_pos):
        mouse_x, mouse_y = self.screen_to_world_view(mouse_pos)
        world_pos = (mouse_x + self.camera_x, mouse_y + self.camera_y)
        nearest = None
        nearest_dist = math.inf
        for obj in reversed(self.cleanup_objects):
            if obj.get("removed"):
                continue
            hit = self.point_hits_object(world_pos, obj)
            rect = obj.get("rect")
            if not hit and rect is not None:
                expanded = rect.inflate(10, 10)
                hit = expanded.collidepoint(world_pos)
            if not hit:
                continue
            dist = math.hypot(world_pos[0] - obj["rect"].centerx, world_pos[1] - obj["rect"].centery)
            if dist < nearest_dist:
                nearest = obj
                nearest_dist = dist
        return nearest

    def find_nearest_cleanup_object(self):
        player_center = self.get_player_center()
        nearest = None
        nearest_dist = math.inf
        for obj in self.cleanup_objects:
            if obj.get("removed"):
                continue
            rect = obj.get("rect")
            if rect is None:
                continue
            dist = math.hypot(player_center[0] - rect.centerx, player_center[1] - rect.centery)
            if dist <= INTERACT_DISTANCE and dist < nearest_dist:
                nearest = obj
                nearest_dist = dist
        return nearest

    def get_object_draw_world_position(self, obj, image=None):
        image = image if image is not None else obj["image"]
        draw_x = obj["x"] if "x" in obj else obj["rect"].x
        draw_y = obj["y"] if "y" in obj else obj["rect"].y
        draw_y -= self.get_special_interaction_lift(obj)
        return draw_x, draw_y

    def point_hits_object(self, world_pos, obj):
        image = obj["image"]
        draw_x, draw_y = self.get_object_draw_world_position(obj, image)
        local_x = int(world_pos[0] - draw_x)
        local_y = int(world_pos[1] - draw_y)

        if 0 <= local_x < image.get_width() and 0 <= local_y < image.get_height():
            mask = obj.get("mask")
            if mask is None:
                mask = pygame.mask.from_surface(image)
                obj["mask"] = mask
            return bool(mask.get_at((local_x, local_y)))

        return obj["rect"].collidepoint(world_pos)

    def update_hover_state(self, mouse_pos=None):
        if mouse_pos is None:
            mouse_pos = pygame.mouse.get_pos()

        self.hovered_object = None
        self.hovered_group = ""
        self.hovered_hint = ""

        if self.note_open_id or self.camera_place_mode:
            return

        ordered_groups = [
            (self.notes, "note"),
            (self.plants, "plant"),
            (self.broken_objects, "broken"),
            (self.cleanup_objects, "cleanup"),
            (self.key_objects, "key"),
            (self.world_pickups, "pickup"),
            (self.generators, "generator"),
            (self.switches, "switch"),
            (self.interactives, "interactive"),
            (self.placed_cameras, "placed_camera"),
        ]

        for objects, kind in ordered_groups:
            obj = self.find_clicked_object(mouse_pos, objects)
            if obj is None or obj.get("removed"):
                continue
            if kind == "plant" and obj.get("watered", False):
                continue
            if kind == "broken" and obj.get("fixed", False):
                continue
            if kind == "cleanup" and obj.get("cleaned", False):
                continue
            self.hovered_object = obj
            self.hovered_group = obj.get("group", "") if kind == "interactive" else ""
            self.hovered_hint = HOVER_HINTS.get(kind, "")
            return

    def set_door_removed(self, door_id, removed):
        changed = False
        targets = self.resolve_target_family(door_id, allowed_types={"door", "laser_barrier"})
        if not targets:
            door = self.doors_by_id.get(door_id)
            targets = [door] if door else []
        for door in targets:
            if door and door["removed"] != removed:
                door["removed"] = removed
                changed = True
        if changed:
            self.door_state_version += 1
            self.invalidate_ray_cache()
        return changed

    def open_door(self, door_id):
        self.set_door_removed(door_id, True)

    def close_door(self, door_id):
        self.set_door_removed(door_id, False)

    def set_wall_group_active(self, wall_id, active):
        if not wall_id:
            return False

        changed = False
        targets = self.resolve_target_family(wall_id, allowed_types={"wall"})
        for wall in targets:
            if wall.get("active") == active and wall.get("removed") == (not active):
                continue
            wall["active"] = active
            wall["removed"] = not active
            changed = True
        if changed:
            self.door_state_version += 1
            self.invalidate_ray_cache()
        return changed

    def set_button_target_state(self, target_id, active):
        changed = False
        changed = self.set_door_removed(target_id, active) or changed
        changed = self.set_wall_group_active(target_id, not active) or changed
        return changed

    def set_button_targets_state(self, target_value, active):
        changed = False
        for target_id in self.parse_target_ids(target_value):
            changed = self.set_button_target_state(target_id, active) or changed
        return changed

    def restart_to_checkpoint(self):
        self.player.respawn(*self.current_checkpoint)
        for box, (x, y) in zip(self.boxes, self.boxes_initial):
            box["rect"].topleft = (x, y)
            box["x"] = x
            box["y"] = y
        self.note_open_id = None
        self.note_open_text = ""
        self.camera_place_mode = False
        self.camera_preview = None
        self.set_message(MESSAGES["checkpoint_return"])
        self.refresh_logic()
        self.update_camera_follow(force=True)

    def handle_event(self, event):
        if self.tutorial_index is not None:
            if event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                self.advance_tutorial()
            return

        if event.type == pygame.KEYDOWN:
            if pygame.K_1 <= event.key <= pygame.K_9:
                self.selected_slot = event.key - pygame.K_0
            elif event.key == pygame.K_r:
                self.restart_to_checkpoint()
            elif event.key == pygame.K_e:
                self.handle_e_action()
            elif event.key == pygame.K_n:
                self.toggle_god_mode()
            elif event.key == pygame.K_l:
                self.teleport_player_to_mouse()

        elif event.type == pygame.MOUSEMOTION:
            self.update_hover_state(event.pos)

        elif event.type == pygame.MOUSEBUTTONDOWN:
            if self.camera_place_mode:
                if event.button == 1:
                    self.confirm_camera_placement()
                elif event.button == 3:
                    self.cancel_camera_placement()
                return

            if self.note_open_id and event.button == 3:
                self.note_open_id = None
                self.note_open_text = ""
                return

            if event.button == 1:
                self.handle_left_click(event.pos)
            elif event.button == 3:
                self.handle_right_click(event.pos)

    def handle_e_action(self):
        if self.note_open_id:
            return
        if self.selected_slot == 1 and self.inventory["camera"] > 0:
            self.begin_camera_placement()
            return
        self.try_pickup_nearby_placed_camera()

    def toggle_god_mode(self):
        self.god_mode = not self.god_mode
        self.set_message(MESSAGES["god_mode_on"] if self.god_mode else MESSAGES["god_mode_off"])

    def advance_tutorial(self):
        if self.tutorial_index is None:
            return
        self.tutorial_index += 1
        if self.tutorial_index >= len(TUTORIAL_PAGES):
            self.tutorial_index = None

    def teleport_player_to_mouse(self):
        if not self.god_mode:
            return

        mouse_x, mouse_y = self.screen_to_world_view(pygame.mouse.get_pos())
        world_x = mouse_x + self.camera_x - self.player.rect.width // 2
        world_y = mouse_y + self.camera_y - self.player.rect.height // 2

        world_x = max(0, min(world_x, self.world_width - self.player.rect.width))
        world_y = max(0, min(world_y, self.world_height - self.player.rect.height))

        self.player.respawn(world_x, world_y)
        self.update_checkpoint_touch()
        self.refresh_logic()
        self.update_camera_follow(force=True)
        self.set_message(MESSAGES["god_teleport"])

    def handle_left_click(self, mouse_pos):
        clicked_note = self.find_clicked_object(mouse_pos, self.notes)
        if clicked_note:
            self.note_open_id = clicked_note["id"]
            self.note_open_text = clicked_note.get("note_text", "") or "..."
            clicked_note["interacted_once"] = True
            if clicked_note["id"] == "note_1":
                self.note_1_read = True
                if self.eaten:
                    self.set_message(MESSAGES["thank_wife"])
            return

        clicked_plant = self.find_clicked_object(mouse_pos, self.plants)
        if clicked_plant and self.is_close_enough(clicked_plant["rect"]):
            self.water_plant(clicked_plant)
            return

        clicked_broken = self.find_clicked_object(mouse_pos, self.broken_objects)
        if clicked_broken and self.is_close_enough(clicked_broken["rect"]):
            self.repair_broken_object(clicked_broken)
            return

        clicked_key = self.find_clicked_object(mouse_pos, self.key_objects)
        if clicked_key and self.is_close_enough(clicked_key["rect"]):
            self.use_key(clicked_key)
            return

        clicked_generator = self.find_clicked_object(mouse_pos, self.generators)
        if clicked_generator and self.is_close_enough(clicked_generator["rect"]):
            self.toggle_generator(clicked_generator)
            return

        clicked_interactive = self.find_clicked_object(mouse_pos, self.interactives)
        if clicked_interactive and self.is_close_enough(clicked_interactive["rect"]):
            self.interact_with_generic(clicked_interactive)
            return

        clicked_switch = self.find_clicked_object(mouse_pos, self.switches)
        if clicked_switch and self.is_close_enough(clicked_switch["rect"]):
            self.toggle_switch(clicked_switch)
            return

        clicked_pickup = self.find_clicked_object(mouse_pos, self.world_pickups)
        if clicked_pickup and self.is_close_enough(clicked_pickup["rect"]):
            self.pickup_world_item(clicked_pickup)

    def handle_right_click(self, mouse_pos):
        clicked_cleanup = self.find_clicked_cleanup_object(mouse_pos)
        if clicked_cleanup and self.is_close_enough(clicked_cleanup["rect"]):
            self.cleanup_object(clicked_cleanup)
            return
        nearby_cleanup = self.find_nearest_cleanup_object()
        if nearby_cleanup is not None:
            self.cleanup_object(nearby_cleanup)
            return

        clicked_key = self.find_clicked_object(mouse_pos, self.key_objects)
        if clicked_key and self.is_close_enough(clicked_key["rect"]):
            self.use_key(clicked_key)
            return

        clicked_pickup = self.find_clicked_object(mouse_pos, self.world_pickups)
        if clicked_pickup and self.is_close_enough(clicked_pickup["rect"]):
            self.pickup_world_item(clicked_pickup)
            return

        self.try_pickup_clicked_placed_camera(mouse_pos)

    def interact_with_generic(self, obj):
        obj["interacted_once"] = True
        group_id = obj.get("group", "")
        if group_id:
            for grouped_obj in self.interactives:
                if grouped_obj.get("removed"):
                    continue
                if grouped_obj.get("group", "") == group_id:
                    grouped_obj["interacted_once"] = True
        if obj["group"] == "bedroom":
            self.set_message(MESSAGES["already_slept"])
        elif obj["group"] == "kitchen":
            if self.eaten:
                self.set_message(MESSAGES["kitchen_done"])
            else:
                self.set_message(MESSAGES["kitchen_hungry"])
        elif obj["group"] == "food":
            self.eaten = True
            self.player.heal(1)
            if self.note_1_read:
                self.set_message(MESSAGES["food_after_note"])
            else:
                self.set_message(MESSAGES["food_default"])
        elif obj["id"] == "painting":
            self.set_message(MESSAGES["painting"])

    def use_key(self, key_obj):
        target_id = key_obj.get("target_id", "")
        if not target_id:
            return
        self.got_key = True
        key_obj["interacted_once"] = True
        self.open_door(target_id)
        key_obj["removed"] = True
        self.refresh_logic()
        self.update_hover_state()
        self.set_message(MESSAGES["key_used"])

    def pickup_world_item(self, obj):
        if obj.get("picked"):
            return

        kind = obj.get("pickup_kind", obj["id"])
        obj["interacted_once"] = True
        if kind == "camera":
            self.inventory["camera"] += 1
            self.set_message(MESSAGES["camera_picked"])
        elif kind == "watering_can":
            self.inventory["watering_can"] += 1
            self.set_message(MESSAGES["watering_can_picked"])
        elif kind in {"health", "extra_health"}:
            self.player.max_hp += 1
            self.player.heal(1)
            self.set_message(MESSAGES["health_picked"])
        else:
            self.inventory[kind] += 1
            self.set_message(MESSAGES["item_picked"].format(kind=kind))

        obj["picked"] = True
        obj["removed"] = True

    def water_plant(self, plant):
        if plant.get("watered", False):
            return
        if self.get_equipped_item_kind() != "watering_can":
            self.set_message(MESSAGES["plant_needs_watering_can"])
            return
        plant["watered"] = True
        plant["interacted_once"] = True
        self.set_message(MESSAGES["plant_watered"])
        self.update_hover_state()

    def repair_broken_object(self, obj):
        if obj.get("fixed", False):
            return
        obj["fixed"] = True
        obj["interacted_once"] = True
        self.set_message(MESSAGES["broken_fixed"])
        self.update_hover_state()

    def cleanup_object(self, obj):
        if obj.get("cleaned", False):
            return
        obj["cleaned"] = True
        obj["removed"] = True
        obj["interacted_once"] = True
        self.set_message(MESSAGES["cleanup_done"])
        self.update_hover_state()

    def set_bridge_group_active(self, bridge_id, active):
        if not bridge_id:
            return False

        changed = False
        targets = self.resolve_target_family(bridge_id, allowed_types={"bridge"})
        if not targets:
            targets = list(self.bridges_by_id.get(bridge_id, [])) + list(self.bridge_tiles_by_id.get(bridge_id, []))
        for bridge in targets:
            if bridge.get("active") == active and bridge.get("removed") == (not active):
                continue
            bridge["on"] = 1 if active else 0
            bridge["active"] = active
            bridge["removed"] = not active
            changed = True
        return changed

    def bridge_group_is_active(self, bridge_id):
        if not bridge_id:
            return False
        targets = self.resolve_target_family(bridge_id, allowed_types={"bridge"})
        if not targets:
            targets = list(self.bridges_by_id.get(bridge_id, [])) + list(self.bridge_tiles_by_id.get(bridge_id, []))
        return any(target.get("active", False) for target in targets)

    def toggle_switch(self, switch_obj):
        target_ids = self.parse_target_ids(switch_obj.get("target_id", ""))
        bridge_targets = [target_id for target_id in target_ids if self.resolve_target_family(target_id, allowed_types={"bridge"})]
        if not bridge_targets:
            self.set_message(MESSAGES["switch_missing_target"])
            return

        next_state = not switch_obj.get("active", False)
        switch_obj["active"] = next_state
        switch_obj["interacted_once"] = True
        for target_id in bridge_targets:
            self.set_bridge_group_active(target_id, not self.bridge_group_is_active(target_id))
        self.set_message(MESSAGES["switch_on"] if next_state else MESSAGES["switch_off"])
        self.update_hover_state()

    def toggle_generator(self, generator):
        # Generators are intentionally simple for now: one click toggles the
        # source, then the whole power network is recomputed from level data.
        next_state = not self.is_generator_on(generator)
        generator["on"] = 1 if next_state else 0
        generator["interacted_once"] = True
        self.refresh_logic()
        self.update_hover_state()
        self.set_message(MESSAGES["generator_on"] if next_state else MESSAGES["generator_off"])

    def try_pickup_nearby_placed_camera(self):
        player_center = self.get_player_center()
        nearest = None
        nearest_dist = math.inf

        for cam in self.placed_cameras:
            if cam["removed"]:
                continue
            dist = math.hypot(player_center[0] - cam["rect"].centerx, player_center[1] - cam["rect"].centery)
            if dist <= INTERACT_DISTANCE and dist < nearest_dist:
                nearest = cam
                nearest_dist = dist

        if nearest:
            nearest["interacted_once"] = True
            nearest["removed"] = True
            self.inventory["camera"] += 1
            self.set_message(MESSAGES["camera_returned"])
            self.refresh_logic()
            self.update_hover_state()

    def try_pickup_clicked_placed_camera(self, mouse_pos):
        clicked = self.find_clicked_object(mouse_pos, self.placed_cameras)
        if clicked and self.is_close_enough(clicked["rect"]):
            clicked["interacted_once"] = True
            clicked["removed"] = True
            self.inventory["camera"] += 1
            self.set_message(MESSAGES["camera_returned"])
            self.refresh_logic()
            self.update_hover_state()

    def begin_camera_placement(self):
        if self.inventory["camera"] <= 0:
            self.set_message(MESSAGES["camera_slot_empty"])
            return

        tile_x = (self.player.rect.x // self.tile_size) * self.tile_size
        tile_y = (self.player.rect.y // self.tile_size) * self.tile_size
        preview_rect = pygame.Rect(tile_x, tile_y, self.tile_size, self.tile_size)

        if not self.rect_in_walkable(preview_rect) or self.collides_with_solid(preview_rect):
            self.set_message(MESSAGES["camera_bad_spot"])
            return

        self.camera_place_mode = True
        self.camera_preview = {
            "x": preview_rect.x,
            "y": preview_rect.y,
            "rect": preview_rect,
            "angle": self.facing_to_angle(self.player.facing),
            "range_tiles": CAMERA_PLACE_RANGE_TILES,
            "fov": CAMERA_FOV,
            "preview": True,
        }
        self.set_message(MESSAGES["camera_confirm"], frames=PERSISTENT_MESSAGE_FRAMES)

    def confirm_camera_placement(self):
        if not self.camera_place_mode or not self.camera_preview:
            return

        if not self.rect_in_walkable(self.camera_preview["rect"]) or self.collides_with_solid(self.camera_preview["rect"]):
            self.set_message(MESSAGES["camera_blocked"])
            self.camera_place_mode = False
            self.camera_preview = None
            return

        self.inventory["camera"] -= 1
        fallback_image = load_image("assets/images/player/player.png")
        camera_image_path = "assets/images/_used/portable_camera.png"
        camera_image = load_image(camera_image_path) if os.path.exists(camera_image_path) else fallback_image

        self.placed_cameras.append({
            "id": "placed_camera",
            "uid": self.next_camera_uid,
            "image": camera_image,
            "rect": self.camera_preview["rect"].copy(),
            "angle": self.camera_preview["angle"],
            "range_tiles": self.camera_preview["range_tiles"],
            "fov": self.camera_preview["fov"],
            "removed": False,
        })
        self.next_camera_uid += 1
        self.camera_place_mode = False
        self.camera_preview = None
        self.set_message(MESSAGES["camera_placed"])
        self.refresh_logic()

    def cancel_camera_placement(self):
        self.camera_place_mode = False
        self.camera_preview = None
        self.set_message(MESSAGES["camera_cancelled"])

    def facing_to_angle(self, facing):
        return {
            "right": 0,
            "down": 90,
            "left": 180,
            "up": -90,
        }.get(facing, 0)

    def update_camera_preview(self):
        if not self.camera_place_mode or not self.camera_preview:
            return
        mouse_x, mouse_y = self.screen_to_world_view(pygame.mouse.get_pos())
        world_mouse = (mouse_x + self.camera_x, mouse_y + self.camera_y)
        self.camera_preview["angle"] = angle_to(self.camera_preview["rect"].center, world_mouse)

    def update(self, keys):
        self.quantum_flame_tick += 1
        if self.box_push_cooldown > 0:
            self.box_push_cooldown -= 1
        self.update_camera_preview()
        self.update_hover_state()

        if self.tutorial_index is not None:
            self.player.update_animation(0, 0)
            self.update_camera_follow()
            if self.message_timer > 0 and self.message_timer != PERSISTENT_MESSAGE_FRAMES:
                self.message_timer -= 1
            return

        if self.note_open_id or self.camera_place_mode:
            self.player.update_animation(0, 0)
            self.update_camera_follow()
            if self.message_timer > 0 and self.message_timer != PERSISTENT_MESSAGE_FRAMES:
                self.message_timer -= 1
            return

        dx, dy = self.player.get_movement(keys)
        if self.box_push_cooldown > 0:
            dx *= BOX_PUSH_MOVE_FACTOR
            dy *= BOX_PUSH_MOVE_FACTOR

        if dx != 0:
            self.move_player_axis(dx, 0)
        if dy != 0:
            self.move_player_axis(0, dy)

        self.player.update_animation(dx, dy)
        self.update_checkpoint_touch()
        self.update_death_zone_touch()
        self.refresh_logic()
        self.update_camera_follow()

        if self.message_timer > 0 and self.message_timer != PERSISTENT_MESSAGE_FRAMES:
            self.message_timer -= 1

    def move_player_axis(self, dx, dy):
        if dx == 0 and dy == 0:
            return

        old_position = self.player.position.copy()
        old_rect = self.player.rect.copy()
        self.player.move_axis(dx, dy)

        for box in self.boxes:
            if self.player.rect.colliderect(box["rect"]):
                if not self.try_push_box(box, dx, dy):
                    self.player.position = old_position
                    self.player.rect = old_rect
                    return

        if self.collides_with_solid(self.player.rect, include_closed_doors=True):
            self.player.position = old_position
            self.player.rect = old_rect
            return

        if not self.rect_in_walkable(self.player.rect):
            self.player.position = old_position
            self.player.rect = old_rect
            return

        if not self.get_world_bounds().contains(self.player.rect):
            self.player.position = old_position
            self.player.rect = old_rect
            return

    def update_death_zone_touch(self):
        zone_rects = []
        zone_rects.extend(self.void_tile_rects)
        zone_rects.extend(
            bridge["rect"]
            for bridge in self.bridge_tiles
            if not bridge.get("active", False)
        )
        player_area = max(1, self.player.rect.width * self.player.rect.height)
        total_overlap = 0
        for zone_rect in zone_rects:
            overlap = self.player.rect.clip(zone_rect)
            total_overlap += overlap.width * overlap.height
        if total_overlap >= player_area * 0.9:
            self.restart_to_checkpoint()

    def try_push_box(self, box, dx, dy):
        if self.box_push_cooldown > 0:
            return False

        step_x = 0
        step_y = 0

        if dx > 0:
            step_x = BOX_PUSH_DISTANCE
        elif dx < 0:
            step_x = -BOX_PUSH_DISTANCE
        elif dy > 0:
            step_y = BOX_PUSH_DISTANCE
        elif dy < 0:
            step_y = -BOX_PUSH_DISTANCE
        else:
            return False

        target_rect = box["rect"].move(step_x, step_y)

        if not self.get_world_bounds().contains(target_rect):
            return False
        if not self.rect_in_walkable(target_rect):
            return False
        if self.collides_with_solid(target_rect, ignore_box=box, include_closed_doors=True):
            return False

        box["rect"] = target_rect
        box["x"] = target_rect.x
        box["y"] = target_rect.y
        self.box_push_cooldown = BOX_PUSH_COOLDOWN_FRAMES
        self.player.velocity.update(0.0, 0.0)
        return True

    def update_checkpoint_touch(self):
        player_rect = self.player.rect
        for cp in self.checkpoint_rects:
            if player_rect.colliderect(cp):
                candidate = pygame.Rect(cp.x, cp.y, self.tile_size, self.tile_size)
                if self.rect_in_walkable(candidate):
                    self.current_checkpoint = self.apply_checkpoint_offset(candidate.topleft)
                else:
                    best = self.find_nearest_walkable_tile(candidate.center)
                    if best is not None:
                        self.current_checkpoint = self.apply_checkpoint_offset(best)

    def find_nearest_walkable_tile(self, point):
        best = None
        best_dist = 10**18
        for y, row in enumerate(self.walkable_map):
            for x, code in enumerate(row):
                if code != "1":
                    continue
                rect = pygame.Rect(x * self.tile_size, y * self.tile_size, self.tile_size, self.tile_size)
                if not self.rect_in_walkable(rect):
                    continue
                dist = (rect.centerx - point[0]) ** 2 + (rect.centery - point[1]) ** 2
                if dist < best_dist:
                    best_dist = dist
                    best = rect.topleft
        return best

    def refresh_logic(self):
        # This is the central "rebuild the simulation state" pass. It is cheap
        # enough for now to recompute buttons, bridges, and power every frame.
        self.refresh_quantum_walls()
        self.refresh_quantum_buttons()
        self.refresh_pressure_buttons()
        self.refresh_permanent_buttons()
        self.refresh_power_networks()

    def is_generator_on(self, generator):
        return str(generator.get("on", 0)).lower() not in {"0", "false", "off", "no", ""}
