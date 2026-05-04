import json
import math
import os
from collections import Counter, defaultdict

import pygame

from game_constants import (
    CONE_CENTER_COLOR,
    CONE_CENTER_RADIUS,
    CONE_FILL_COLOR,
    CONE_LINE_COLOR,
    CONE_LINE_WIDTH,
    INTERACT_GLOW_COLOR,
    INTERACT_GLOW_MAX_ALPHA,
    INTERACT_GLOW_MIN_ALPHA,
    INTERACT_GLOW_PERIOD_MS,
    INTERACT_GLOW_WIDTH,
    NOTE_GLOW_COLOR,
    NOTE_GLOW_WIDTH,
    CURSOR_HAND_HOTSPOT_X,
    CURSOR_HAND_HOTSPOT_Y,
    CURSOR_HAND_SCALE,
    HOVER_HINT_OFFSET_X,
    HOVER_HINT_OFFSET_Y,
    HOVER_HINT_SCREEN_PADDING,
    HOVER_OUTLINE_WIDTH,
    HUD_LINE_HEIGHT,
    HUD_MARGIN_X,
    HUD_MARGIN_Y,
    MESSAGE_BOTTOM_MARGIN,
    NOTE_CLOSE_OFFSET_X,
    NOTE_CLOSE_OFFSET_Y,
    NOTE_OVERLAY_ALPHA,
    NOTE_PANEL_BORDER,
    NOTE_PANEL_MARGIN,
    NOTE_TEXT_LINE_HEIGHT,
    NOTE_TEXT_TOP,
    PAUSE_OVERLAY_ALPHA,
    PERSISTENT_MESSAGE_FRAMES,
    QUANTUM_FLAME_FRAME_TIME,
    QUANTUM_FLAME_OFFSET_X,
    QUANTUM_FLAME_OFFSET_Y,
    UI_CAMERA_ICON_OFFSET_Y,
    UI_PANEL_INFO_HEIGHT,
    UI_PANEL_INFO_WIDTH,
    UI_PANEL_PADDING_X,
    UI_PANEL_PADDING_Y,
    UI_PANEL_STATUS_HEIGHT,
    UI_PANEL_STATUS_WIDTH,
    UI_SELECTED_SLOT_NUDGE_X,
    UI_SELECTED_SLOT_NUDGE_Y,
    UI_SLOT_BOTTOM_MARGIN,
    UI_SLOT_COUNT,
    UI_SLOT_COUNT_OFFSET_X,
    UI_SLOT_COUNT_OFFSET_Y,
    UI_SLOT_COUNT_POP_OFFSET_Y,
    UI_SLOT_GAP,
    UI_SLOT_NUMBER_OFFSET_Y,
    UI_TOP_STATUS_Y,
)
from game_text import HOVER_HINTS, HUD_LINES, MESSAGES, NOTE_CLOSE_TEXT, TUTORIAL_PAGES
from game_utils import angle_diff, angle_to, load_image
from settings import *
from player import Player


class Game:
    def __init__(self, level_path):
        self.level_path = level_path
        self.font = pygame.font.SysFont(None, 28)
        self.small_font = pygame.font.SysFont(None, 22)
        self.big_font = pygame.font.SysFont(None, 36)
        self.tiny_font = pygame.font.SysFont(None, 20)
        self.slot_count_font = pygame.font.SysFont(None, 30, bold=True)

        self.camera_x = 0
        self.camera_y = 0

        self.message = ""
        self.message_timer = 0
        self.note_open_id = None
        self.note_open_text = ""
        self.tutorial_index = 0
        self.camera_place_mode = False
        self.camera_preview = None
        self.god_mode = False
        self.box_push_cooldown = 0
        self.selected_slot = 1
        self.inventory = defaultdict(int)

        self.eaten = False
        self.got_key = False
        self.note_1_read = False
        self.current_checkpoint = None
        self.zoom = WORLD_ZOOM
        self.viewport_width = max(1, int(WIDTH / self.zoom))
        self.viewport_height = max(1, int(HEIGHT / self.zoom))
        self.screen_frame = pygame.Rect(
            CAMERA_FRAME_LEFT,
            CAMERA_FRAME_TOP,
            WIDTH - CAMERA_FRAME_LEFT - CAMERA_FRAME_RIGHT,
            HEIGHT - CAMERA_FRAME_TOP - CAMERA_FRAME_BOTTOM,
        )
        self.view_frame = pygame.Rect(
            int(self.screen_frame.x / self.zoom),
            int(self.screen_frame.y / self.zoom),
            max(1, int(self.screen_frame.width / self.zoom)),
            max(1, int(self.screen_frame.height / self.zoom)),
        )
        self.hovered_object = None
        self.hovered_group = ""
        self.hovered_hint = ""
        self.switches = []
        self.bridges = []
        self.bridges_by_id = defaultdict(list)
        self.static_blocking_rects = []
        self.blocking_rects_cache = []
        self.blocking_rects_cache_version = -1
        self.door_state_version = 0
        self.camera_cone_cache = {}
        self.ui_panel_cache = {}
        self.ui_panel_image = load_image("assets/images/ui/hud_panel.png")
        self.slot_idle_image = load_image("assets/images/ui/slot_idle.png", scale=2)
        self.slot_selected_image = load_image("assets/images/ui/slot_selected.png", scale=2)
        self.cursor_hand_image = load_image("assets/images/ui/cursor_hand.png", scale=CURSOR_HAND_SCALE)
        self.inventory_camera_icon = load_image("assets/images/_used/portable_camera.png", scale=0.9)
        self.quantum_flame_frames = [
            load_image(f"assets/images/ui/quantum_flame_{index:02}.png")
            for index in range(5)
        ]
        self.quantum_flame_tick = 0
        self.quantum_target_ids = set()
        self.quantum_group_state = {}
        self.quantum_wall_tiles = []
        self.quantum_wall_groups = defaultdict(list)
        self.quantum_wall_cells = set()

        self.load_level(level_path)

    # -------------------------------------------------------------------------
    # Level loading
    # -------------------------------------------------------------------------
    def load_level(self, level_path):
        with open(level_path, "r", encoding="utf-8") as f:
            self.level_data = json.load(f)

        meta = self.level_data["meta"]
        self.tile_size = meta["tile_size"]
        self.level_width_tiles = meta["width"]
        self.level_height_tiles = meta["height"]
        self.world_width = self.level_width_tiles * self.tile_size
        self.world_height = self.level_height_tiles * self.tile_size

        self.tile_defs = self.level_data["tile_defs"]
        self.tile_paths = self.level_data["tile_paths"]
        self.ground_rows = self.level_data["tile_layers"]["ground"]
        self.overlay_rows = self.level_data["tile_layers"]["overlay"]
        self.walkable_map = self.level_data["walkable_map"]
        self.zones = self.level_data.get("zones", [])
        self.death_zone_rects = self.build_zone_rects("death")
        self.cable_map = self.sanitize_cable_map(self.level_data.get("cable_map", {}))
        self.cable_connections = self.level_data.get("cable_connections", [])
        self.switches = []
        self.bridges = []
        self.bridges_by_id = defaultdict(list)
        self.quantum_wall_tiles = []
        self.quantum_wall_groups = defaultdict(list)
        self.quantum_wall_cells = set()

        self.spawn_codes = {code for code, name in self.tile_defs.items() if "spawn_point" in name}
        self.checkpoint_codes = {code for code, name in self.tile_defs.items() if "check_point" in name}
        self.hidden_tile_codes = set(self.spawn_codes) | set(self.checkpoint_codes)

        self.tile_images = {}
        for code, key_name in self.tile_defs.items():
            if not key_name:
                continue
            path = self.tile_paths.get(key_name)
            if path and code not in self.hidden_tile_codes:
                self.tile_images[code] = load_image(path)

        self.spawn_rects = []
        self.checkpoint_rects = []
        for rows in (self.ground_rows, self.overlay_rows):
            for y, row in enumerate(rows):
                for x, code in enumerate(row):
                    rect = pygame.Rect(x * self.tile_size, y * self.tile_size, self.tile_size, self.tile_size)
                    if code in self.spawn_codes and rect not in self.spawn_rects:
                        self.spawn_rects.append(rect)
                    if code in self.checkpoint_codes and rect not in self.checkpoint_rects:
                        self.checkpoint_rects.append(rect)
        self.collect_tile_meta_markers()
        self.collect_quantum_wall_tiles()

        spawn_point = self.resolve_spawn_position()
        self.player = Player(*spawn_point)
        self.current_checkpoint = spawn_point

        self.static_blocking_rects = self.build_static_blocking_rects()
        self.invalidate_ray_cache()

        self.draw_below = []
        self.draw_above = []
        self.doors = []
        self.doors_by_id = {}
        self.generators = []
        self.laser_barriers = []
        self.permanent_buttons = []
        self.pressure_buttons = []
        self.quantum_buttons = []
        self.quantum_groups = defaultdict(list)
        self.boxes = []
        self.boxes_initial = []
        self.notes = []
        self.note_by_id = {}
        self.placed_cameras = []
        self.world_pickups = []
        self.interactives = []
        self.key_objects = []

        raw_objects = self.expand_compact_objects(self.level_data)
        button_target_counts = Counter(
            obj["props"].get("target_id", "")
            for obj in raw_objects
            if obj["props"].get("type") == "button" and obj["props"].get("target_id")
        )

        for src in raw_objects:
            props = src.get("props", {})
            obj_type = props.get("type", "generic")
            obj_id = props.get("id", "")
            group_id = props.get("group_id", props.get("group", ""))
            group = group_id
            target_id = props.get("target_id", "")
            render_layer = src.get("render_layer", "above_overlay")
            scale = src.get("scale", 1.0)

            # Some level objects are clearly doors by id, even if the saved type is generic.
            # Normalize them here so gameplay logic still works without editing level data.
            if obj_id.startswith("door"):
                obj_type = "door"

            image = load_image(src["path"], scale)
            rect = pygame.Rect(src["x"], src["y"], max(self.tile_size, image.get_width()), max(self.tile_size, image.get_height()))

            obj = {
                "kind": src.get("kind", "static"),
                "path": src["path"],
                "image": image,
                "x": src["x"],
                "y": src["y"],
                "rect": rect,
                "id": obj_id,
                "type": obj_type,
                "group": group,
                "group_id": group_id,
                "target_id": target_id,
                "render_layer": render_layer,
                "z_order": src.get("z_order", 0),
                "direction": props.get("direction", "down"),
                "range": props.get("range", 4),
                "fov": props.get("fov", CAMERA_FOV),
                "pair_id": props.get("pair_id", ""),
                "subtype": props.get("subtype", ""),
                "cable_ids": props.get("cable_ids", ""),
                "power": props.get("power", 1),
                "on": props.get("on", 1),
                "generator_variant": props.get("generator_variant", "small"),
                "required_power": props.get("required_power", ""),
                "note_text": props.get("note_text", ""),
                "opens_when_powered": props.get("opens_when_powered", 1),
                "turns_off_when_powered": props.get("turns_off_when_powered", 1),
                "active": False,
                "removed": False,
                "picked": False,
                "interacted_once": False,
            }

            if obj_type == "door":
                obj["rect"] = pygame.Rect(src["x"], src["y"], self.tile_size, self.tile_size)
                self.doors.append(obj)
                self.doors_by_id[obj_id] = obj

            elif obj_type == "laser_barrier":
                obj["rect"] = pygame.Rect(src["x"], src["y"], self.tile_size, self.tile_size)
                self.doors.append(obj)
                self.laser_barriers.append(obj)
                if obj_id:
                    self.doors_by_id[obj_id] = obj

            elif obj_type == "generator":
                obj["rect"] = pygame.Rect(src["x"], src["y"], self.tile_size, self.tile_size)
                self.generators.append(obj)
                if render_layer == "below_overlay":
                    self.draw_below.append(obj)
                else:
                    self.draw_above.append(obj)

            elif obj_type == "button":
                obj["image_off"] = image
                obj["image_on"] = load_image(src["path"].replace("button_off", "button_on"), scale)
                obj["requires_hold"] = button_target_counts[target_id] > 1
                obj["pressed_once"] = False
                obj["occupied_now"] = False
                if obj["requires_hold"]:
                    self.pressure_buttons.append(obj)
                else:
                    self.permanent_buttons.append(obj)

            elif obj_type == "quantum":
                obj["image_off"] = image
                obj["image_on"] = load_image(src["path"].replace("button_off", "button_on"), scale)
                obj["collapsed_out"] = False
                obj["observable"] = False
                obj["occupied_now"] = False
                obj["pressed_once"] = False
                self.quantum_buttons.append(obj)
                self.quantum_groups[group or target_id].append(obj)
                if target_id:
                    self.quantum_target_ids.add(target_id)

            elif obj_type == "pushable_box":
                obj["rect"] = pygame.Rect(src["x"], src["y"], self.tile_size, self.tile_size)
                self.boxes.append(obj)
                self.boxes_initial.append((src["x"], src["y"]))

            elif obj_type == "pickup_item" or obj_id == "camera":
                pickup_kind = "camera" if obj_id == "camera" else obj_id
                obj["pickup_kind"] = pickup_kind
                obj["rect"] = pygame.Rect(src["x"], src["y"], self.tile_size, self.tile_size)
                self.world_pickups.append(obj)

            elif obj_type == "bridge":
                obj["rect"] = pygame.Rect(src["x"], src["y"], self.tile_size, self.tile_size)
                obj["active"] = str(obj.get("subtype", "")).lower() in {"on", "active", "enabled", "1", "true"}
                obj["removed"] = not obj["active"]
                self.bridges.append(obj)
                if obj_id:
                    self.bridges_by_id[obj_id].append(obj)

            elif obj_type == "switch":
                obj["rect"] = pygame.Rect(src["x"], src["y"], self.tile_size, self.tile_size)
                obj["active"] = False
                obj["image_off"] = image
                obj["image_on"] = self.load_optional_state_image(src["path"], scale, "_off", "_on", image)
                self.switches.append(obj)

            else:
                handled_by_special_draw = False
                if obj_type == "note" or obj_id.startswith("note_") or obj.get("note_text"):
                    self.notes.append(obj)
                    self.note_by_id[obj_id] = obj
                    handled_by_special_draw = True
                elif obj_id.startswith("key"):
                    self.key_objects.append(obj)
                    handled_by_special_draw = True
                elif group in {"bedroom", "kitchen", "food"} or obj_id in {"painting"}:
                    self.interactives.append(obj)

                if not handled_by_special_draw and render_layer == "below_overlay":
                    self.draw_below.append(obj)
                elif not handled_by_special_draw:
                    self.draw_above.append(obj)

        self.draw_below.sort(key=lambda o: o["z_order"])
        self.draw_above.sort(key=lambda o: o["z_order"])
        self.quantum_group_state = {
            group_id: {
                "was_observed": False,
                "mode": "classical",
                "observer_signature": 0,
                "collapsed_state": "",
                "collapse_mode": self.get_quantum_collapse_mode(buttons),
            }
            for group_id, buttons in self.quantum_groups.items()
        }

        self.update_camera_follow(force=True)
        self.refresh_logic()

    def expand_compact_objects(self, data):
        raw_objects = data.get("objects", [])
        object_defs = data.get("object_defs", {})
        if not isinstance(object_defs, dict):
            return raw_objects

        expanded = []
        for inst in raw_objects:
            if not isinstance(inst, dict) or "def" not in inst:
                expanded.append(inst)
                continue

            base = object_defs.get(inst.get("def"), {})
            obj = dict(base)
            obj["props"] = dict(base.get("props", {}))
            obj["props"].update(inst.get("props", {}))
            obj["x"] = inst.get("x", 0)
            obj["y"] = inst.get("y", 0)
            obj["z_order"] = inst.get("z_order", 0)
            obj["_coord_space"] = inst.get("_coord_space", "pixel32")
            expanded.append(obj)

        return expanded

    def sanitize_cable_map(self, raw):
        def empty_layer():
            return [[[] for _ in range(self.level_width_tiles)] for _ in range(self.level_height_tiles)]

        def clean_cell(value):
            if value is None or value == 0:
                return []
            if isinstance(value, int):
                return [value] if value > 0 else []
            if isinstance(value, str):
                items = value.replace(",", " ").split()
            elif isinstance(value, list):
                items = value
            else:
                return []
            channels = []
            for item in items:
                try:
                    channel = int(item)
                except (TypeError, ValueError):
                    continue
                if channel > 0 and channel not in channels:
                    channels.append(channel)
            return sorted(channels)

        def clean_grid(grid):
            out = []
            for y in range(self.level_height_tiles):
                src = grid[y] if isinstance(grid, list) and y < len(grid) and isinstance(grid[y], list) else []
                row = []
                for x in range(self.level_width_tiles):
                    row.append(clean_cell(src[x] if x < len(src) else []))
                out.append(row)
            return out

        if isinstance(raw, dict):
            return {
                "floor": clean_grid(raw.get("floor", [])),
                "wall": clean_grid(raw.get("wall", [])),
            }
        if isinstance(raw, list):
            return {"floor": clean_grid(raw), "wall": empty_layer()}
        return {"floor": empty_layer(), "wall": empty_layer()}

    def build_zone_rects(self, zone_type):
        rects = []
        for zone in self.level_data.get("zones", []):
            if zone.get("type") != zone_type:
                continue
            rects.append(
                pygame.Rect(
                    int(zone.get("x", 0)) * self.tile_size,
                    int(zone.get("y", 0)) * self.tile_size,
                    int(zone.get("w", 0)) * self.tile_size,
                    int(zone.get("h", 0)) * self.tile_size,
                )
            )
        return rects

    def collect_tile_meta_markers(self):
        tile_meta = self.level_data.get("tile_meta", {})
        if not isinstance(tile_meta, dict):
            return
        for _layer_name, grid in tile_meta.items():
            if not isinstance(grid, list):
                continue
            for y, row in enumerate(grid):
                if not isinstance(row, list):
                    continue
                for x, props in enumerate(row):
                    if not isinstance(props, dict):
                        continue
                    marker_type = str(props.get("type", "")).lower()
                    marker_asset = str(props.get("asset", "")).lower()
                    marker_id = str(props.get("id", "")).lower()
                    marker_text = " ".join((marker_type, marker_asset, marker_id))
                    rect = pygame.Rect(x * self.tile_size, y * self.tile_size, self.tile_size, self.tile_size)
                    if any(name in marker_text for name in ("player_spawn", "spawn_point")):
                        if rect not in self.spawn_rects:
                            self.spawn_rects.append(rect)
                    if any(name in marker_text for name in ("checkpoint", "check_point")):
                        if rect not in self.checkpoint_rects:
                            self.checkpoint_rects.append(rect)

    def iter_tile_meta_cells(self):
        tile_meta = self.level_data.get("tile_meta", {})
        if not isinstance(tile_meta, dict):
            return
        for layer_name, grid in tile_meta.items():
            if not isinstance(grid, list):
                continue
            for y, row in enumerate(grid):
                if not isinstance(row, list):
                    continue
                for x, props in enumerate(row):
                    if isinstance(props, dict):
                        yield layer_name, x, y, props

    def collect_quantum_wall_tiles(self):
        for layer_name, x, y, props in self.iter_tile_meta_cells() or []:
            tile_type = str(props.get("type", "")).lower()
            if tile_type != "quantum":
                continue
            rect = pygame.Rect(x * self.tile_size, y * self.tile_size, self.tile_size, self.tile_size)
            group_id = props.get("group_id") or props.get("group") or props.get("id") or f"quantum_wall_{x}_{y}"
            tile = {
                "layer": layer_name,
                "x": x,
                "y": y,
                "rect": rect,
                "group_id": group_id,
                "subtype": props.get("subtype", "single_only") or "single_only",
                "active": True,
                "collapsed_out": False,
            }
            self.quantum_wall_tiles.append(tile)
            self.quantum_wall_groups[group_id].append(tile)
            self.quantum_wall_cells.add((layer_name, x, y))

    def quantum_wall_at(self, x, y):
        for tile in self.quantum_wall_tiles:
            if tile["x"] == x and tile["y"] == y:
                return tile
        return None

    def quantum_wall_is_active(self, layer_name, x, y):
        for tile in self.quantum_wall_tiles:
            if tile["layer"] == layer_name and tile["x"] == x and tile["y"] == y:
                return tile.get("active", True)
        return True

    def resolve_spawn_position(self):
        if not self.spawn_rects and self.checkpoint_rects:
            self.spawn_rects.append(self.checkpoint_rects[0])

        if not self.spawn_rects:
            return self.find_first_walkable_position()

        marker = self.spawn_rects[0]
        candidate = pygame.Rect(marker.x, marker.y, self.tile_size, self.tile_size)
        if self.rect_in_walkable(candidate):
            return self.apply_checkpoint_offset(candidate.topleft)

        best = self.find_nearest_walkable_tile(marker.center)
        if best is not None:
            return self.apply_checkpoint_offset(best)

        return self.apply_checkpoint_offset(candidate.topleft)

    def find_first_walkable_position(self):
        for y, row in enumerate(self.walkable_map):
            for x, code in enumerate(row):
                if code == "1":
                    return self.apply_checkpoint_offset((x * self.tile_size, y * self.tile_size))
        return (0, 0)

    def apply_checkpoint_offset(self, pos):
        return (pos[0], pos[1] + CHECKPOINT_SPAWN_OFFSET_Y)

    def load_optional_state_image(self, path, scale, old_marker, new_marker, fallback):
        if old_marker not in path:
            return fallback
        alt_path = path.replace(old_marker, new_marker)
        if not os.path.exists(alt_path):
            return fallback
        return load_image(alt_path, scale)

    def build_static_blocking_rects(self):
        rects = []
        for y, row in enumerate(self.walkable_map):
            for x, code in enumerate(row):
                if code == "0":
                    if self.quantum_wall_at(x, y):
                        continue
                    rects.append(
                        pygame.Rect(x * self.tile_size, y * self.tile_size, self.tile_size, self.tile_size)
                    )
        return rects

    def invalidate_ray_cache(self):
        self.blocking_rects_cache_version = -1
        self.blocking_rects_cache = []
        self.camera_cone_cache.clear()

    # -------------------------------------------------------------------------
    # Utility
    # -------------------------------------------------------------------------
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
        return "Empty"

    def is_walkable_cell(self, tx, ty):
        if tx < 0 or ty < 0 or ty >= len(self.walkable_map) or tx >= len(self.walkable_map[ty]):
            return False
        return self.walkable_map[ty][tx] == "1"

    def rect_in_walkable(self, rect):
        feet_points = [
            (rect.left + 4, rect.bottom - 2),
            (rect.centerx, rect.bottom - 2),
            (rect.right - 4, rect.bottom - 2),
        ]
        for px, py in feet_points:
            tx = px // self.tile_size
            ty = py // self.tile_size
            if (
                not self.is_walkable_cell(tx, ty)
                and not self.point_on_active_bridge(px, py)
                and not self.point_on_inactive_quantum_wall(px, py)
            ):
                return False
        return True

    def point_on_inactive_quantum_wall(self, px, py):
        tx = int(px) // self.tile_size
        ty = int(py) // self.tile_size
        tile = self.quantum_wall_at(tx, ty)
        return bool(tile and not tile.get("active", True))

    def point_on_active_bridge(self, px, py):
        point = (int(px), int(py))
        for bridge in self.bridges:
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
            (self.key_objects, "key"),
            (self.world_pickups, "pickup"),
            (self.switches, "switch"),
            (self.interactives, "interactive"),
            (self.placed_cameras, "placed_camera"),
        ]

        for objects, kind in ordered_groups:
            obj = self.find_clicked_object(mouse_pos, objects)
            if obj is None or obj.get("removed"):
                continue
            self.hovered_object = obj
            self.hovered_group = obj.get("group", "") if kind == "interactive" else ""
            self.hovered_hint = HOVER_HINTS.get(kind, "")
            return

    def set_door_removed(self, door_id, removed):
        door = self.doors_by_id.get(door_id)
        if door and door["removed"] != removed:
            door["removed"] = removed
            self.door_state_version += 1
            self.invalidate_ray_cache()

    def open_door(self, door_id):
        self.set_door_removed(door_id, True)

    def close_door(self, door_id):
        self.set_door_removed(door_id, False)

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

    # -------------------------------------------------------------------------
    # Events / input
    # -------------------------------------------------------------------------
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

        clicked_key = self.find_clicked_object(mouse_pos, self.key_objects)
        if clicked_key and self.is_close_enough(clicked_key["rect"]):
            self.use_key(clicked_key)
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
        elif kind in {"health", "extra_health"}:
            self.player.max_hp += 1
            self.player.heal(1)
            self.set_message(MESSAGES["health_picked"])
        else:
            self.inventory[kind] += 1
            self.set_message(MESSAGES["item_picked"].format(kind=kind))

        obj["picked"] = True
        obj["removed"] = True

    def set_bridge_group_active(self, bridge_id, active):
        if not bridge_id:
            return False

        bridges = self.bridges_by_id.get(bridge_id, [])
        changed = False
        for bridge in bridges:
            if bridge.get("active") == active and bridge.get("removed") == (not active):
                continue
            bridge["active"] = active
            bridge["removed"] = not active
            changed = True
        return changed

    def toggle_switch(self, switch_obj):
        target_id = switch_obj.get("target_id", "")
        if not target_id or target_id not in self.bridges_by_id:
            self.set_message(MESSAGES["switch_missing_target"])
            return

        next_state = not switch_obj.get("active", False)
        switch_obj["active"] = next_state
        switch_obj["interacted_once"] = True
        self.set_bridge_group_active(target_id, next_state)
        self.set_message(MESSAGES["switch_on"] if next_state else MESSAGES["switch_off"])
        self.update_hover_state()

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

    def try_pickup_clicked_placed_camera(self, mouse_pos):
        clicked = self.find_clicked_object(mouse_pos, self.placed_cameras)
        if clicked and self.is_close_enough(clicked["rect"]):
            clicked["interacted_once"] = True
            clicked["removed"] = True
            self.inventory["camera"] += 1
            self.set_message(MESSAGES["camera_returned"])

    # -------------------------------------------------------------------------
    # Camera placement
    # -------------------------------------------------------------------------
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
            "image": camera_image,
            "rect": self.camera_preview["rect"].copy(),
            "angle": self.camera_preview["angle"],
            "range_tiles": self.camera_preview["range_tiles"],
            "fov": self.camera_preview["fov"],
            "removed": False,
        })
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

    # -------------------------------------------------------------------------
    # Game update
    # -------------------------------------------------------------------------
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
        if not self.death_zone_rects:
            return
        player_area = max(1, self.player.rect.width * self.player.rect.height)
        for zone_rect in self.death_zone_rects:
            overlap = self.player.rect.clip(zone_rect)
            if overlap.width * overlap.height >= player_area * 0.9:
                self.restart_to_checkpoint()
                return

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
        self.refresh_quantum_walls()
        self.refresh_quantum_buttons()
        self.refresh_pressure_buttons()
        self.refresh_permanent_buttons()
        self.refresh_power_networks()

    def parse_channel_list(self, value):
        if isinstance(value, list):
            items = value
        elif isinstance(value, int):
            items = [value]
        elif isinstance(value, str):
            items = value.replace(",", " ").split()
        else:
            items = []
        channels = []
        for item in items:
            try:
                channel = int(item)
            except (TypeError, ValueError):
                continue
            if channel > 0 and channel not in channels:
                channels.append(channel)
        return channels

    def parse_required_power(self, value):
        """
        Simple format: "3" means total incoming power from any cable in this cell.
        Advanced legacy format: "1:2, 2:1" means per-channel requirements.
        """
        if isinstance(value, dict):
            result = {}
            for key, amount in value.items():
                try:
                    result[int(key)] = int(amount)
                except (TypeError, ValueError):
                    continue
            return result

        if isinstance(value, int):
            return {"total": value} if value > 0 else {}

        result = {}
        if isinstance(value, list):
            for channel in self.parse_channel_list(value):
                result[channel] = 1
            return result

        if isinstance(value, str):
            stripped = value.strip()
            if stripped.isdigit():
                return {"total": int(stripped)}
            for chunk in value.replace(";", ",").split(","):
                chunk = chunk.strip()
                if not chunk:
                    continue
                if ":" in chunk:
                    channel_text, amount_text = chunk.split(":", 1)
                else:
                    channel_text, amount_text = chunk, "1"
                try:
                    channel = int(channel_text.strip())
                    amount = int(amount_text.strip())
                except ValueError:
                    continue
                if channel > 0 and amount > 0:
                    result[channel] = amount
        return result

    def powered_cell_total(self, powered, gx, gy):
        channels = sorted(set(self.cable_map.get("floor", [])[gy][gx] + self.cable_map.get("wall", [])[gy][gx]))
        return sum(powered.get((gx, gy, channel), 0) for channel in channels)

    def grid_pos_from_obj(self, obj):
        return int(obj.get("x", 0)) // self.tile_size, int(obj.get("y", 0)) // self.tile_size

    def has_active_cable(self, x, y, channel):
        if not (0 <= x < self.level_width_tiles and 0 <= y < self.level_height_tiles):
            return False
        if channel in self.cable_map.get("floor", [])[y][x]:
            return True
        if channel in self.cable_map.get("wall", [])[y][x]:
            wall = self.quantum_wall_at(x, y)
            if wall and not wall.get("active", True):
                return False
            return True
        return False

    def collect_power_for_generator(self, generator):
        if str(generator.get("on", 1)).lower() in {"0", "false", "off", "no"}:
            return {}
        gx, gy = self.grid_pos_from_obj(generator)
        channels = self.parse_channel_list(generator.get("cable_ids", ""))
        if not channels:
            single = generator.get("cable_id", "")
            channels = self.parse_channel_list(single)

        power = max(0, int(generator.get("power", 1)))
        powered = {}
        for channel in channels:
            if not self.has_active_cable(gx, gy, channel):
                continue
            visited = set()
            queue = [(gx, gy)]
            while queue:
                x, y = queue.pop(0)
                if (x, y) in visited or not self.has_active_cable(x, y, channel):
                    continue
                visited.add((x, y))
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if (nx, ny) not in visited and self.has_active_cable(nx, ny, channel):
                        queue.append((nx, ny))
            for cell in visited:
                powered[(cell[0], cell[1], channel)] = powered.get((cell[0], cell[1], channel), 0) + power
        return powered

    def refresh_power_networks(self):
        powered = {}
        for generator in self.generators:
            for key, amount in self.collect_power_for_generator(generator).items():
                powered[key] = powered.get(key, 0) + amount

        for obj in self.doors:
            requirements = self.parse_required_power(obj.get("required_power", ""))
            if not requirements:
                continue
            gx, gy = self.grid_pos_from_obj(obj)
            if "total" in requirements:
                is_powered = self.powered_cell_total(powered, gx, gy) >= requirements["total"]
            else:
                is_powered = all(powered.get((gx, gy, channel), 0) >= amount for channel, amount in requirements.items())
            obj_id = obj.get("id", "")
            if obj_id:
                self.set_door_removed(obj_id, is_powered)
            elif obj.get("removed") != is_powered:
                obj["removed"] = is_powered
                self.door_state_version += 1

    def refresh_permanent_buttons(self):
        actor_rects = [self.player.rect] + [box["rect"] for box in self.boxes]
        for button in self.permanent_buttons:
            if button["removed"]:
                continue
            if button["pressed_once"]:
                button["active"] = True
                continue
            occupied = any(button["rect"].colliderect(rect) for rect in actor_rects)
            if occupied:
                button["pressed_once"] = True
                button["active"] = True
                self.open_door(button["target_id"])

    def refresh_pressure_buttons(self):
        box_rects = [box["rect"] for box in self.boxes]
        groups = defaultdict(list)

        for button in self.pressure_buttons:
            button["occupied_now"] = any(button["rect"].colliderect(rect) for rect in box_rects)
            button["active"] = button["occupied_now"]
            groups[button["target_id"]].append(button)

        for target_id, buttons in groups.items():
            if buttons and all(button["active"] for button in buttons):
                self.open_door(target_id)

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

            target_ids = {button.get("target_id", "") for button in buttons if button.get("target_id", "")}
            if not observed_now:
                state["mode"] = "classical"
                state["collapsed_state"] = ""
                for button in buttons:
                    button["collapsed_out"] = False
                    button["pressed_once"] = False
                    button["active"] = False
                    button["observable"] = False
                for target_id in target_ids:
                    self.close_door(target_id)
                continue

            self.collapse_quantum_group(group_id, buttons, visible_pairs=visible_pairs)

            any_pressed = False
            for button in buttons:
                if button["removed"] or button.get("collapsed_out", False):
                    continue
                button["observable"] = True
                button["occupied_now"] = any(button["rect"].colliderect(rect) for rect in actor_rects)
                if button["occupied_now"]:
                    button["active"] = True
                    button["pressed_once"] = True
                    any_pressed = True

            for target_id in target_ids:
                if any_pressed:
                    self.open_door(target_id)
                else:
                    self.close_door(target_id)

    def refresh_quantum_walls(self):
        if not self.quantum_wall_groups:
            return

        cameras = [cam for cam in self.placed_cameras if not cam["removed"]]
        changed = False
        for group_id, walls in self.quantum_wall_groups.items():
            visible_pairs = []
            for wall in walls:
                for cam in cameras:
                    if self.camera_sees_rect(cam, wall["rect"], ignore_rect=wall["rect"]):
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
                    wall["active"] = True
                    wall["collapsed_out"] = False
                continue

            mode = next((wall.get("subtype", "") for wall in walls if wall.get("subtype")), "single_only")
            sorted_walls = sorted(walls, key=lambda wall: (wall["x"], wall["y"]))
            if mode == "single_only":
                survivor = min(visible_pairs, key=lambda item: item[0])[1]
                for wall in walls:
                    active = wall is survivor
                    if wall.get("active", True) != active:
                        changed = True
                    wall["active"] = active
                    wall["collapsed_out"] = not active
            else:
                cam = min(visible_pairs, key=lambda item: item[0])[2]
                signature = self.compute_observer_signature(group_id, cam, len(sorted_walls))
                collapsed_state = self.build_quantum_collapsed_state(mode, len(sorted_walls), signature)
                for wall, bit in zip(sorted_walls, collapsed_state):
                    active = bit == "1"
                    if wall.get("active", True) != active:
                        changed = True
                    wall["active"] = active
                    wall["collapsed_out"] = not active

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

    # -------------------------------------------------------------------------
    # Camera visibility / ray logic
    # -------------------------------------------------------------------------
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

    def raycast_to_wall(self, origin, angle_deg, max_distance):
        blockers = self.all_blocking_rects_for_rays()
        angle_rad = math.radians(angle_deg)
        dx = math.cos(angle_rad) * CAMERA_RAY_STEP
        dy = math.sin(angle_rad) * CAMERA_RAY_STEP

        x = origin[0]
        y = origin[1]
        travelled = 0

        while travelled < max_distance:
            x += dx
            y += dy
            travelled += CAMERA_RAY_STEP

            point = (int(x), int(y))
            if point[0] < 0 or point[1] < 0 or point[0] >= self.world_width or point[1] >= self.world_height:
                break

            if any(rect.collidepoint(point) for rect in blockers):
                x -= dx
                y -= dy
                break

        return (int(x), int(y))

    def get_camera_cone_points(self, cam):
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

        origin = cam["rect"].center
        max_distance = cam["range_tiles"] * self.tile_size
        half_fov = cam["fov"] / 2

        points = [origin]
        for i in range(CAMERA_RAY_COUNT + 1):
            angle = cam["angle"] - half_fov + (i / CAMERA_RAY_COUNT) * cam["fov"]
            points.append(self.raycast_to_wall(origin, angle, max_distance))

        if cam.get("id") == "placed_camera":
            self.camera_cone_cache[cache_key] = points
        return points

    # -------------------------------------------------------------------------
    # Camera follow
    # -------------------------------------------------------------------------
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

    # -------------------------------------------------------------------------
    # Drawing
    # -------------------------------------------------------------------------
    def draw_tile_layer(self, screen, rows, skip_codes=None, layer_name=""):
        if skip_codes is None:
            skip_codes = set()

        start_x = max(0, self.camera_x // self.tile_size - TILE_DRAW_MARGIN_TILES)
        end_x = min(
            self.level_width_tiles,
            (self.camera_x + self.viewport_width) // self.tile_size + TILE_DRAW_MARGIN_TILES + 2,
        )
        start_y = max(0, self.camera_y // self.tile_size - TILE_DRAW_MARGIN_TILES)
        end_y = min(
            self.level_height_tiles,
            (self.camera_y + self.viewport_height) // self.tile_size + TILE_DRAW_MARGIN_TILES + 2,
        )

        for y in range(start_y, end_y):
            row = rows[y]
            for x in range(start_x, end_x):
                code = row[x]
                if code in skip_codes:
                    continue
                if layer_name and not self.quantum_wall_is_active(layer_name, x, y):
                    continue
                image = self.tile_images.get(code)
                if image:
                    screen.blit(image, (x * self.tile_size - self.camera_x, y * self.tile_size - self.camera_y))

    def draw_object(self, screen, obj, override_image=None):
        if obj.get("removed"):
            return

        image = override_image if override_image is not None else obj["image"]
        draw_x, draw_y = self.get_object_draw_position(obj, image)

        screen.blit(image, (draw_x, draw_y))

    def get_object_draw_position(self, obj, image):
        world_x, world_y = self.get_object_draw_world_position(obj, image)
        draw_x = world_x - self.camera_x
        draw_y = world_y - self.camera_y
        return draw_x, draw_y

    def get_special_interaction_lift(self, obj):
        return 0

    def draw_special_object(self, screen, obj):
        if obj.get("removed"):
            return

        image = obj["image"]
        draw_x, draw_y = self.get_object_draw_position(obj, image)
        screen.blit(image, (draw_x, draw_y))

    def draw_boxes(self, screen):
        for box in self.boxes:
            if box["removed"]:
                continue
            screen.blit(box["image"], (box["rect"].x - self.camera_x, box["rect"].y - self.camera_y))
            pygame.draw.rect(
                screen,
                CYAN,
                pygame.Rect(
                    box["rect"].x - self.camera_x,
                    box["rect"].y - self.camera_y,
                    box["rect"].width,
                    box["rect"].height,
                ),
                1,
            )

    def draw_doors(self, screen):
        for door in self.doors:
            if door["removed"]:
                continue
            screen.blit(door["image"], (door["x"] - self.camera_x, door["y"] - self.camera_y))

    def draw_buttons(self, screen):
        for button in self.permanent_buttons + self.pressure_buttons:
            if button["removed"]:
                continue
            img = button["image_on"] if button["active"] else button["image_off"]
            screen.blit(img, (button["x"] - self.camera_x, button["y"] - self.camera_y))

        for button in self.quantum_buttons:
            if button["removed"] or button.get("collapsed_out", False):
                continue
            img = button["image_on"] if button["active"] else button["image_off"]
            draw_x = button["x"] - self.camera_x
            draw_y = button["y"] - self.camera_y
            screen.blit(img, (draw_x, draw_y))

            if not button.get("observable", False) and not button.get("pressed_once", False):
                flame_frame = self.quantum_flame_frames[(self.quantum_flame_tick // QUANTUM_FLAME_FRAME_TIME) % len(self.quantum_flame_frames)]
                flame_x = draw_x + button["rect"].width // 2 - flame_frame.get_width() // 2 + QUANTUM_FLAME_OFFSET_X
                flame_y = draw_y + button["rect"].height // 2 - flame_frame.get_height() // 2 - QUANTUM_FLAME_OFFSET_Y
                screen.blit(flame_frame, (flame_x, flame_y))

    def draw_world_pickups(self, screen):
        for obj in self.world_pickups:
            if obj.get("removed"):
                continue
            screen.blit(obj["image"], (obj["rect"].x - self.camera_x, obj["rect"].y - self.camera_y))

    def draw_bridges(self, screen):
        for obj in self.bridges:
            if obj.get("removed"):
                continue
            self.draw_special_object(screen, obj)

    def draw_switches(self, screen):
        for obj in self.switches:
            if obj.get("removed"):
                continue
            image = obj.get("image_on") if obj.get("active", False) else obj.get("image_off", obj["image"])
            self.draw_object(screen, obj, override_image=image)

    def draw_notes(self, screen):
        for obj in self.notes:
            if obj.get("removed"):
                continue
            self.draw_special_object(screen, obj)

    def draw_interactives(self, screen):
        for obj in self.interactives:
            if obj.get("removed"):
                continue
            if self.get_special_interaction_lift(obj) <= 0:
                continue
            self.draw_special_object(screen, obj)

    def draw_keys(self, screen):
        for obj in self.key_objects:
            if obj.get("removed"):
                continue
            self.draw_special_object(screen, obj)

    def draw_camera_cone(self, screen, cam):
        points = self.get_camera_cone_points(cam)
        screen_points = [(x - self.camera_x, y - self.camera_y) for x, y in points]

        cone_surface = pygame.Surface((self.viewport_width, self.viewport_height), pygame.SRCALPHA)
        if len(screen_points) >= 3:
            pygame.draw.polygon(cone_surface, CONE_FILL_COLOR, screen_points)
        pygame.draw.lines(cone_surface, CONE_LINE_COLOR, False, screen_points[1:], CONE_LINE_WIDTH)
        pygame.draw.circle(cone_surface, CONE_CENTER_COLOR, screen_points[0], CONE_CENTER_RADIUS)
        screen.blit(cone_surface, (0, 0))

    def draw_placed_cameras(self, screen):
        for cam in self.placed_cameras:
            if cam["removed"]:
                continue
            self.draw_camera_cone(screen, cam)
            screen.blit(cam["image"], (cam["rect"].x - self.camera_x, cam["rect"].y - self.camera_y))

        if self.camera_place_mode and self.camera_preview:
            self.draw_camera_cone(screen, self.camera_preview)
            pygame.draw.rect(
                screen,
                CYAN,
                pygame.Rect(
                    self.camera_preview["rect"].x - self.camera_x,
                    self.camera_preview["rect"].y - self.camera_y,
                    self.camera_preview["rect"].width,
                    self.camera_preview["rect"].height,
                ),
                2
            )

    def draw_camera_frame(self, screen):
        pygame.draw.rect(screen, WHITE, self.screen_frame, CAMERA_FRAME_LINE_WIDTH)

    def draw_hover_highlight(self, screen):
        if not self.hovered_object or self.hovered_object.get("removed"):
            return

        overlay = pygame.Surface((self.viewport_width, self.viewport_height), pygame.SRCALPHA)

        objects_to_highlight = [self.hovered_object]
        if self.hovered_group:
            grouped = [
                obj for obj in self.interactives
                if not obj.get("removed") and obj.get("group") == self.hovered_group
            ]
            if grouped:
                objects_to_highlight = grouped

        for obj in objects_to_highlight:
            image = obj["image"]
            mask = obj.get("mask")
            if mask is None:
                mask = pygame.mask.from_surface(image)
                obj["mask"] = mask

            outline = mask.outline()
            if not outline:
                continue

            draw_x, draw_y = self.get_object_draw_position(obj, image)
            points = [(draw_x + x, draw_y + y) for x, y in outline]

            if len(points) == 1:
                pygame.draw.circle(overlay, WHITE, points[0], HOVER_OUTLINE_WIDTH)
            else:
                pygame.draw.lines(overlay, WHITE, True, points, HOVER_OUTLINE_WIDTH)

        screen.blit(overlay, (0, 0))

    def get_outline_points(self, obj):
        image = obj["image"]
        mask = obj.get("mask")
        if mask is None:
            mask = pygame.mask.from_surface(image)
            obj["mask"] = mask

        outline = mask.outline()
        if not outline:
            return []

        draw_x, draw_y = self.get_object_draw_position(obj, image)
        return [(draw_x + x, draw_y + y) for x, y in outline]

    def draw_interaction_glow(self, screen):
        if self.note_open_id or self.camera_place_mode:
            return

        pulse = (math.sin((pygame.time.get_ticks() / INTERACT_GLOW_PERIOD_MS) * math.tau) + 1) / 2
        alpha = int(INTERACT_GLOW_MIN_ALPHA + (INTERACT_GLOW_MAX_ALPHA - INTERACT_GLOW_MIN_ALPHA) * pulse)
        overlay = pygame.Surface((self.viewport_width, self.viewport_height), pygame.SRCALPHA)

        collections = (
            (self.notes, NOTE_GLOW_COLOR, NOTE_GLOW_WIDTH, True),
            (self.key_objects, INTERACT_GLOW_COLOR, INTERACT_GLOW_WIDTH, True),
            (self.world_pickups, INTERACT_GLOW_COLOR, INTERACT_GLOW_WIDTH, True),
            (self.switches, INTERACT_GLOW_COLOR, INTERACT_GLOW_WIDTH, True),
            (self.interactives, INTERACT_GLOW_COLOR, INTERACT_GLOW_WIDTH, True),
            (self.placed_cameras, INTERACT_GLOW_COLOR, INTERACT_GLOW_WIDTH, False),
        )

        for objects, base_color, line_width, ignore_distance_before_first_interaction in collections:
            for obj in objects:
                if obj.get("removed"):
                    continue
                can_glow = self.can_interact_with(obj)
                if not can_glow and ignore_distance_before_first_interaction and not obj.get("interacted_once", False):
                    can_glow = True
                if not can_glow:
                    continue

                color = (*base_color[:3], alpha)

                points = self.get_outline_points(obj)
                if not points:
                    continue

                if len(points) == 1:
                    pygame.draw.circle(overlay, color, points[0], line_width)
                else:
                    pygame.draw.lines(overlay, color, True, points, line_width)

        screen.blit(overlay, (0, 0))

    def get_ui_panel(self, width, height):
        key = (width, height)
        panel = self.ui_panel_cache.get(key)
        if panel is None:
            panel = pygame.transform.scale(self.ui_panel_image, (width, height))
            self.ui_panel_cache[key] = panel
        return panel

    def draw_ui_panel(self, screen, rect):
        screen.blit(self.get_ui_panel(rect.width, rect.height), rect.topleft)

    def draw_inventory_bar(self, screen):
        slot_width = self.slot_idle_image.get_width()
        slot_height = self.slot_idle_image.get_height()
        total_width = UI_SLOT_COUNT * slot_width + (UI_SLOT_COUNT - 1) * UI_SLOT_GAP
        start_x = (WIDTH - total_width) // 2
        y = HEIGHT - slot_height - UI_SLOT_BOTTOM_MARGIN

        for index in range(UI_SLOT_COUNT):
            slot_id = index + 1
            slot_image = self.slot_selected_image if self.selected_slot == slot_id else self.slot_idle_image
            slot_x = start_x + index * (slot_width + UI_SLOT_GAP)
            draw_x = slot_x
            draw_y = y
            if self.selected_slot == slot_id:
                draw_x += UI_SELECTED_SLOT_NUDGE_X
                draw_y += UI_SELECTED_SLOT_NUDGE_Y
            screen.blit(slot_image, (draw_x, draw_y))

            number_img = self.tiny_font.render(str(slot_id), True, WHITE)
            number_rect = number_img.get_rect(center=(draw_x + slot_width // 2, draw_y + slot_height + UI_SLOT_NUMBER_OFFSET_Y))
            screen.blit(number_img, number_rect)

            if slot_id == 1 and self.inventory["camera"] > 0:
                cam_x = draw_x + (slot_width - self.inventory_camera_icon.get_width()) // 2
                cam_y = draw_y + UI_CAMERA_ICON_OFFSET_Y - self.inventory_camera_icon.get_height() // 2
                screen.blit(self.inventory_camera_icon, (cam_x, cam_y))

                count_img = self.slot_count_font.render(str(self.inventory["camera"]), True, WHITE)
                count_rect = count_img.get_rect(
                    midbottom=(
                        draw_x + slot_width // 2 + UI_SLOT_COUNT_OFFSET_X,
                        draw_y - UI_SLOT_COUNT_POP_OFFSET_Y,
                    )
                )
                screen.blit(count_img, count_rect)

    def draw_mouse_cursor(self, screen):
        if not self.should_draw_hand_cursor():
            return
        mouse_x, mouse_y = pygame.mouse.get_pos()
        screen.blit(
            self.cursor_hand_image,
            (mouse_x - CURSOR_HAND_HOTSPOT_X, mouse_y - CURSOR_HAND_HOTSPOT_Y),
        )

    def draw_ui(self, screen):
        info_rect = pygame.Rect(HUD_MARGIN_X, HUD_MARGIN_Y, UI_PANEL_INFO_WIDTH, UI_PANEL_INFO_HEIGHT)
        self.draw_ui_panel(screen, info_rect)

        lines = [f"HP {self.player.hp}/{self.player.max_hp}", *HUD_LINES]
        if self.current_checkpoint:
            lines.append(
                f"Checkpoint {self.current_checkpoint[0] // self.tile_size}, {self.current_checkpoint[1] // self.tile_size}"
            )

        y = info_rect.y + UI_PANEL_PADDING_Y
        for line in lines:
            text_img = self.small_font.render(line, True, WHITE)
            screen.blit(text_img, (info_rect.x + UI_PANEL_PADDING_X, y))
            y += HUD_LINE_HEIGHT

        status_rect = pygame.Rect(
            (WIDTH - UI_PANEL_STATUS_WIDTH) // 2,
            UI_TOP_STATUS_Y,
            UI_PANEL_STATUS_WIDTH,
            UI_PANEL_STATUS_HEIGHT,
        )
        self.draw_ui_panel(screen, status_rect)
        selected_name = self.get_slot_label(self.selected_slot)
        selected_text = self.font.render(selected_name, True, WHITE)
        selected_text_rect = selected_text.get_rect(center=status_rect.center)
        screen.blit(selected_text, selected_text_rect)

        self.draw_inventory_bar(screen)

        if self.hovered_hint and not self.note_open_id and self.can_interact_with(self.hovered_object):
            mouse_x, mouse_y = pygame.mouse.get_pos()
            hint_shadow = self.small_font.render(self.hovered_hint, True, BLACK)
            hint = self.small_font.render(self.hovered_hint, True, ORANGE)
            hint_rect = hint.get_rect(topleft=(mouse_x + HOVER_HINT_OFFSET_X, mouse_y + HOVER_HINT_OFFSET_Y))

            if hint_rect.right > WIDTH - HOVER_HINT_SCREEN_PADDING:
                hint_rect.right = WIDTH - HOVER_HINT_SCREEN_PADDING
            if hint_rect.bottom > HEIGHT - HOVER_HINT_SCREEN_PADDING:
                hint_rect.bottom = HEIGHT - HOVER_HINT_SCREEN_PADDING

            screen.blit(hint_shadow, hint_rect.move(2, 2))
            screen.blit(hint, hint_rect)

        if self.message and self.message_timer != 0:
            shadow = self.big_font.render(self.message, True, BLACK)
            text_img = self.big_font.render(self.message, True, WHITE)
            rect = text_img.get_rect(center=(WIDTH // 2, HEIGHT - MESSAGE_BOTTOM_MARGIN))
            screen.blit(shadow, rect.move(2, 2))
            screen.blit(text_img, rect)

    def draw_note_overlay(self, screen):
        if not self.note_open_id:
            return

        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, NOTE_OVERLAY_ALPHA))
        screen.blit(overlay, (0, 0))

        panel = pygame.Rect(
            NOTE_PANEL_MARGIN,
            NOTE_PANEL_MARGIN,
            WIDTH - NOTE_PANEL_MARGIN * 2,
            HEIGHT - NOTE_PANEL_MARGIN * 2,
        )
        panel_surface = pygame.Surface((panel.width, panel.height), pygame.SRCALPHA)
        panel_surface.fill((25, 25, 25, NOTE_BG_ALPHA))
        screen.blit(panel_surface, panel.topleft)
        pygame.draw.rect(screen, LIGHT, panel, NOTE_PANEL_BORDER)

        title = self.big_font.render(self.note_open_id.upper(), True, WHITE)
        screen.blit(title, (panel.x + 20, panel.y + 20))

        close_text = self.small_font.render(NOTE_CLOSE_TEXT, True, LIGHT)
        screen.blit(close_text, (panel.right - NOTE_CLOSE_OFFSET_X, panel.y + NOTE_CLOSE_OFFSET_Y))

        lines = []
        for raw_line in self.note_open_text.split("\n"):
            current = ""
            for word in raw_line.split():
                test = (current + " " + word).strip()
                if self.font.size(test)[0] <= panel.width - 40:
                    current = test
                else:
                    lines.append(current)
                    current = word
            lines.append(current)

        y = panel.y + NOTE_TEXT_TOP
        for line in lines:
            img = self.font.render(line, True, WHITE)
            screen.blit(img, (panel.x + 20, y))
            y += NOTE_TEXT_LINE_HEIGHT

    def draw_tutorial_overlay(self, screen):
        if self.tutorial_index is None:
            return

        page = TUTORIAL_PAGES[self.tutorial_index]
        overlay = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 220))
        screen.blit(overlay, (0, 0))

        title = self.big_font.render(page["title"], True, WHITE)
        title_rect = title.get_rect(center=(WIDTH // 2, HEIGHT // 2 - 120))
        screen.blit(title, title_rect)

        y = HEIGHT // 2 - 20
        for line in page["lines"]:
            img = self.font.render(line, True, WHITE)
            rect = img.get_rect(center=(WIDTH // 2, y))
            screen.blit(img, rect)
            y += 48

    def draw(self, screen, show_cursor=True):
        screen.fill(DARK)

        world_surface = pygame.Surface((self.viewport_width, self.viewport_height)).convert_alpha()
        world_surface.fill(DARK)

        self.draw_tile_layer(world_surface, self.ground_rows, skip_codes=self.hidden_tile_codes, layer_name="ground")

        for obj in self.draw_below:
            self.draw_object(world_surface, obj)

        self.draw_bridges(world_surface)
        self.draw_world_pickups(world_surface)
        self.draw_switches(world_surface)
        self.draw_interactives(world_surface)
        self.draw_doors(world_surface)
        self.draw_buttons(world_surface)
        self.draw_boxes(world_surface)
        self.draw_placed_cameras(world_surface)

        self.draw_tile_layer(world_surface, self.overlay_rows, skip_codes=self.hidden_tile_codes, layer_name="overlay")

        for obj in self.draw_above:
            self.draw_object(world_surface, obj)

        self.draw_notes(world_surface)
        self.draw_keys(world_surface)
        self.draw_interaction_glow(world_surface)
        self.draw_hover_highlight(world_surface)
        self.player.draw(world_surface, self.camera_x, self.camera_y)

        scaled_world = pygame.transform.scale(world_surface, (WIDTH, HEIGHT))
        screen.blit(scaled_world, (0, 0))

        self.draw_ui(screen)
        self.draw_note_overlay(screen)
        self.draw_tutorial_overlay(screen)
        if show_cursor:
            self.draw_mouse_cursor(screen)
