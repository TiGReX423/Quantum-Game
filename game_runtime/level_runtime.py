
import json
import os
import random
from collections import Counter, defaultdict

import pygame

from game_utils import load_image, make_grayscale
from player import Player
from settings import *


class LevelRuntimeMixin:
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
        self.cable_map = self.sanitize_cable_map(self.level_data.get("cable_map", {}))
        self.cable_connections = self.level_data.get("cable_connections", [])
        self.switches = []
        self.bridges = []
        self.bridges_by_id = defaultdict(list)
        self.bridge_tiles = []
        self.bridge_tiles_by_id = defaultdict(list)
        self.target_entities_by_id = defaultdict(list)
        self.powered_cable_cells = {}
        self.tinted_flame_cache = {}
        self.door_power_status = {}
        self.quantum_wall_tiles = []
        self.quantum_wall_groups = defaultdict(list)
        self.quantum_wall_cells = set()
        self.quantum_wall_state = {}
        self.target_wall_tiles = []
        self.target_wall_groups = defaultdict(list)
        self.target_wall_cells = set()

        self.spawn_codes = {code for code, name in self.tile_defs.items() if "spawn_point" in name}
        self.checkpoint_codes = {code for code, name in self.tile_defs.items() if "check_point" in name}
        self.void_codes = {code for code, name in self.tile_defs.items() if name == "void"}
        self.hidden_tile_codes = set(self.spawn_codes) | set(self.checkpoint_codes)

        self.tile_images = {}
        for code, key_name in self.tile_defs.items():
            if not key_name:
                continue
            path = self.tile_paths.get(key_name)
            if path and code not in self.hidden_tile_codes:
                self.tile_images[code] = load_image(path)
        self.void_tile_image = next(
            (self.tile_images.get(code) for code, key_name in self.tile_defs.items() if key_name == "void"),
            None,
        )

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
        self.collect_bridge_tiles()
        self.collect_quantum_wall_tiles()
        self.collect_target_wall_tiles()
        self.void_tile_rects = self.build_void_tile_rects()

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
        self.plants = []
        self.broken_objects = []
        self.cleanup_objects = []

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
                "on": props.get("on", 0),
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
                self.register_target_entity(obj)

            elif obj_type == "laser_barrier":
                obj["rect"] = pygame.Rect(src["x"], src["y"], self.tile_size, self.tile_size)
                self.doors.append(obj)
                self.laser_barriers.append(obj)
                if obj_id:
                    self.doors_by_id[obj_id] = obj
                self.register_target_entity(obj)

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
                obj["scanned"] = False
                obj["occupied_now"] = False
                obj["pressed_once"] = False
                self.quantum_buttons.append(obj)
                self.quantum_groups[group or target_id].append(obj)
                for single_target_id in self.parse_target_ids(target_id):
                    self.quantum_target_ids.add(single_target_id)

            elif obj_type == "pushable_box":
                obj["rect"] = pygame.Rect(src["x"], src["y"], self.tile_size, self.tile_size)
                self.boxes.append(obj)
                self.boxes_initial.append((src["x"], src["y"]))

            elif obj_type == "pickup_item" or obj_id == "camera":
                pickup_kind = self.infer_pickup_kind(src["path"], obj_id)
                obj["pickup_kind"] = pickup_kind
                obj["rect"] = pygame.Rect(src["x"], src["y"], image.get_width(), image.get_height())
                self.world_pickups.append(obj)

            elif obj_type == "bridge":
                obj["rect"] = pygame.Rect(src["x"], src["y"], self.tile_size, self.tile_size)
                on_value = obj.get("on", props.get("on", ""))
                subtype_value = str(obj.get("subtype", "")).lower()
                obj["active"] = str(on_value).lower() in {"1", "true", "on", "yes", "enabled", "active"} or (
                    not str(on_value).strip() and subtype_value in {"on", "active", "enabled", "1", "true"}
                )
                obj["removed"] = not obj["active"]
                self.bridges.append(obj)
                if obj_id:
                    self.bridges_by_id[obj_id].append(obj)
                self.register_target_entity(obj)

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
                elif obj_type == "plant" or group in {"plant", "plants"}:
                    obj["watered"] = False
                    obj["image_gray"] = make_grayscale(image)
                    self.plants.append(obj)
                elif obj_type == "broken" or group in {"broken", "damaged"}:
                    obj["fixed"] = False
                    self.broken_objects.append(obj)
                elif obj_type in {"trash", "polluter", "pollution", "garbage", "litter"} or group in {"trash", "polluter", "pollution", "garbage", "litter"}:
                    obj["cleaned"] = False
                    self.cleanup_objects.append(obj)
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
                "button_states": {},
                "session_seed": None,
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

    def build_void_tile_rects(self):
        rects = []
        if not self.void_codes:
            return rects
        for y, row in enumerate(self.ground_rows):
            for x, code in enumerate(row):
                if code in self.void_codes:
                    rects.append(
                        pygame.Rect(
                            x * self.tile_size,
                            y * self.tile_size,
                            self.tile_size,
                            self.tile_size,
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
        # Tile metadata stores "special wall behavior" separately from the tile
        # art. Here we extract only the quantum-wall cells so gameplay and
        # rendering can query them without scanning the whole grid every frame.
        for layer_name, x, y, props in self.iter_tile_meta_cells() or []:
            tile_type = str(props.get("type", "")).lower()
            if tile_type != "quantum":
                continue
            rect = pygame.Rect(x * self.tile_size, y * self.tile_size, self.tile_size, self.tile_size)
            raw_group_id = props.get("group_id") or props.get("group") or props.get("id") or f"quantum_wall_{x}_{y}"
            group_id = str(raw_group_id).strip()
            tile = {
                "layer": layer_name,
                "x": x,
                "y": y,
                "rect": rect,
                "group_id": group_id,
                "subtype": props.get("subtype", "single_only") or "single_only",
                "active": True,
                "collapsed_out": False,
                "resolved_state": "unresolved",
            }
            self.quantum_wall_tiles.append(tile)
            self.quantum_wall_groups[group_id].append(tile)
            self.quantum_wall_cells.add((layer_name, x, y))

    def collect_target_wall_tiles(self):
        # Regular wall tiles can optionally behave like targetable obstacles.
        # If a wall tile has an id or group_id in tile_meta, buttons can toggle
        # it on/off similarly to doors, while group_id keeps family behavior.
        for layer_name, x, y, props in self.iter_tile_meta_cells() or []:
            tile_type = str(props.get("type", "")).lower()
            if tile_type != "wall":
                continue
            wall_id = str(props.get("id", "")).strip()
            group_id = str(props.get("group_id") or props.get("group") or "").strip()
            if not wall_id and not group_id:
                continue
            rect = pygame.Rect(x * self.tile_size, y * self.tile_size, self.tile_size, self.tile_size)
            tile = {
                "layer": layer_name,
                "x": x,
                "y": y,
                "rect": rect,
                "type": "wall",
                "id": wall_id,
                "group_id": group_id,
                "active": True,
                "removed": False,
            }
            self.target_wall_tiles.append(tile)
            if group_id:
                self.target_wall_groups[group_id].append(tile)
            self.target_wall_cells.add((layer_name, x, y))
            if wall_id:
                self.target_entities_by_id[wall_id].append(tile)

    def collect_bridge_tiles(self):
        # Bridge tiles reuse normal floor art, but tile_meta marks them as
        # switchable gameplay cells that can appear/disappear as walkable
        # support.
        for layer_name, x, y, props in self.iter_tile_meta_cells() or []:
            tile_type = str(props.get("type", "")).lower()
            if tile_type != "bridge":
                continue
            rect = pygame.Rect(x * self.tile_size, y * self.tile_size, self.tile_size, self.tile_size)
            bridge_id = str(props.get("id") or props.get("group_id") or props.get("group") or "").strip()
            subtype = str(props.get("subtype", "")).lower()
            on_value = props.get("on", "")
            active = str(on_value).lower() in {"1", "true", "on", "yes", "enabled", "active"} or (
                not str(on_value).strip() and subtype in {"on", "active", "enabled", "1", "true"}
            )
            tile = {
                "layer": layer_name,
                "x": x,
                "y": y,
                "rect": rect,
                "type": "bridge",
                "id": bridge_id,
                "group_id": str(props.get("group_id", "")).strip(),
                "on": 1 if active else 0,
                "active": active,
                "removed": not active,
            }
            self.bridge_tiles.append(tile)
            for key in {bridge_id, tile["group_id"]}:
                if key:
                    self.bridge_tiles_by_id[key].append(tile)
            if bridge_id:
                self.target_entities_by_id[bridge_id].append(tile)

    def register_target_entity(self, entity):
        entity_id = str(entity.get("id", "")).strip()
        if entity_id:
            self.target_entities_by_id[entity_id].append(entity)

    def parse_target_ids(self, raw_value):
        if isinstance(raw_value, list):
            chunks = raw_value
        else:
            chunks = str(raw_value or "").split(",")
        result = []
        seen = set()
        for chunk in chunks:
            target_id = str(chunk).strip()
            if not target_id or target_id in seen:
                continue
            seen.add(target_id)
            result.append(target_id)
        return result

    def resolve_target_family(self, target_id, allowed_types=None):
        # Resolve one explicit id first, then fan out across every entity that
        # shares the same type and group_id as that seed target.
        target_id = str(target_id or "").strip()
        if not target_id:
            return []

        seeds = list(self.target_entities_by_id.get(target_id, []))
        if allowed_types:
            allowed = {str(item).lower() for item in allowed_types}
            seeds = [seed for seed in seeds if str(seed.get("type", "")).lower() in allowed]
        if not seeds:
            return []

        seed = seeds[0]
        seed_type = str(seed.get("type", "")).lower()
        seed_group = str(seed.get("group_id", "") or seed.get("group", "")).strip()
        if not seed_group:
            return [seed]

        family = []
        for pool in (self.doors, self.bridges, self.bridge_tiles, self.target_wall_tiles):
            for entity in pool:
                if str(entity.get("type", "")).lower() != seed_type:
                    continue
                entity_group = str(entity.get("group_id", "") or entity.get("group", "")).strip()
                if entity_group == seed_group:
                    family.append(entity)
        return family or [seed]

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

    def target_wall_at(self, x, y):
        for tile in self.target_wall_tiles:
            if tile["x"] == x and tile["y"] == y:
                return tile
        return None

    def target_wall_is_active(self, layer_name, x, y):
        for tile in self.target_wall_tiles:
            if tile["layer"] == layer_name and tile["x"] == x and tile["y"] == y:
                return tile.get("active", True)
        return True

    def bridge_tile_is_active(self, layer_name, x, y):
        for tile in self.bridge_tiles:
            if tile["layer"] == layer_name and tile["x"] == x and tile["y"] == y:
                return tile.get("active", False)
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

    def infer_pickup_kind(self, path, obj_id):
        raw_id = str(obj_id or "").strip().lower()
        asset_name = os.path.splitext(os.path.basename(path or ""))[0].lower()
        if raw_id == "camera" or "camera" in asset_name:
            return "camera"
        if raw_id == "watering_can" or asset_name == "watering_can":
            return "watering_can"
        return raw_id or asset_name or "pickup"

    def build_static_blocking_rects(self):
        # A blocking rect is a world-space collision cell that should behave
        # like a solid wall for both movement and raycasts. Quantum walls are
        # handled dynamically elsewhere because they can collapse in/out.
        rects = []
        for y, row in enumerate(self.walkable_map):
            for x, code in enumerate(row):
                if code == "0":
                    if self.target_wall_at(x, y):
                        continue
                    rects.append(
                        pygame.Rect(x * self.tile_size, y * self.tile_size, self.tile_size, self.tile_size)
                    )
        return rects

    def invalidate_ray_cache(self):
        self.blocking_rects_cache_version = -1
        self.blocking_rects_cache = []
        self.camera_cone_cache.clear()
