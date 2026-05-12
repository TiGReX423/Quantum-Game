import math
from collections import defaultdict

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
    ALERT_GLOW_COLOR,
    ALERT_GLOW_WIDTH,
    NOTE_GLOW_COLOR,
    NOTE_GLOW_WIDTH,
    NOTE_AURA_ALPHA,
    NOTE_AURA_MAX_RADIUS_PAD,
    NOTE_AURA_MIN_RADIUS_PAD,
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
from game_runtime import LevelRuntimeMixin, PowerRuntimeMixin, QuantumRuntimeMixin, WorldRuntimeMixin
from game_text import HUD_LINES, NOTE_CLOSE_TEXT, TUTORIAL_PAGES
from game_utils import load_image, load_sprite_strip
from settings import *


class Game(LevelRuntimeMixin, WorldRuntimeMixin, PowerRuntimeMixin, QuantumRuntimeMixin):
    def __init__(self, level_path):
        # Fonts are cached on the Game instance because they are reused by both
        # world-space hints and full-screen UI panels every frame.
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
        self.next_camera_uid = 1

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
        self.bridge_tiles = []
        self.bridge_tiles_by_id = defaultdict(list)
        self.target_entities_by_id = defaultdict(list)
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
        self.inventory_watering_can_icon = load_image("assets/images/tileset/basic/watering_can.png", scale=0.9)
        self.quantum_flame_frames = [
            load_image(f"assets/images/ui/quantum_flame_{index:02}.png")
            for index in range(5)
        ]
        self.electric_particle_frames = load_sprite_strip(
            "assets/images/_used/electric_particles.png",
            32,
            32,
        )
        self.quantum_flame_tick = 0
        self.powered_cable_cells = {}
        self.tinted_flame_cache = {}
        self.door_power_status = {}
        self.quantum_target_ids = set()
        self.quantum_group_state = {}
        self.quantum_wall_tiles = []
        self.quantum_wall_groups = defaultdict(list)
        self.quantum_wall_cells = set()

        self.load_level(level_path)

    def get_progress_entries(self):
        entries = []
        definitions = (
            ("Read", self.notes, lambda obj: obj.get("interacted_once", False), (90, 255, 140)),
            ("Clean", self.cleanup_objects, lambda obj: obj.get("removed", False) or obj.get("cleaned", False), (255, 120, 90)),
            ("Repair", self.broken_objects, lambda obj: obj.get("fixed", False), (255, 215, 90)),
            ("Water", self.plants, lambda obj: obj.get("watered", False), (90, 180, 255)),
            ("Scan", self.quantum_buttons, lambda obj: obj.get("scanned", False), (190, 120, 255)),
        )
        for label, objects, done_fn, color in definitions:
            total = len([obj for obj in objects if not obj.get("removed", False) or label == "Clean"])
            if label != "Clean":
                total = len(objects)
            done = sum(1 for obj in objects if done_fn(obj))
            percent = 100 if total <= 0 else int(round((done / total) * 100))
            entries.append({
                "label": label,
                "done": done,
                "total": total,
                "percent": percent,
                "color": color,
            })
        return entries

    def draw_tile_layer(self, screen, rows, skip_codes=None, layer_name=""):
        # Tile layers are rendered by grid cell. The tile art remains the source
        # of truth for visuals, while tile_meta adds optional gameplay metadata.
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
                if layer_name and not self.target_wall_is_active(layer_name, x, y):
                    continue
                if layer_name == "ground" and not self.bridge_tile_is_active(layer_name, x, y):
                    image = self.void_tile_image
                else:
                    image = self.tile_images.get(code)
                if image:
                    screen.blit(image, (x * self.tile_size - self.camera_x, y * self.tile_size - self.camera_y))

    def draw_object(self, screen, obj, override_image=None):
        if obj.get("removed"):
            return

        image = override_image if override_image is not None else self.get_object_display_image(obj)
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

        image = self.get_object_display_image(obj)
        draw_x, draw_y = self.get_object_draw_position(obj, image)
        screen.blit(image, (draw_x, draw_y))

    def get_object_display_image(self, obj):
        if obj.get("type") == "plant" and not obj.get("watered", False):
            return obj.get("image_gray", obj["image"])
        return obj["image"]

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
                pass
            else:
                screen.blit(door["image"], (door["x"] - self.camera_x, door["y"] - self.camera_y))

            status = self.door_power_status.get(door.get("id", ""))
            if not status:
                continue
            label = f"{status['received']}/{status['required']}"
            color = GREEN if status["powered"] else ORANGE
            text_shadow = self.tiny_font.render(label, True, BLACK)
            text_img = self.tiny_font.render(label, True, color)
            text_rect = text_img.get_rect(
                midbottom=(
                    door["x"] - self.camera_x + self.tile_size // 2,
                    door["y"] - self.camera_y - 4,
                )
            )
            screen.blit(text_shadow, text_rect.move(1, 1))
            screen.blit(text_img, text_rect)

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

    def draw_quantum_wall_flames(self, screen):
        if not self.quantum_flame_frames:
            return
        flame_frame = self.quantum_flame_frames[(self.quantum_flame_tick // QUANTUM_FLAME_FRAME_TIME) % len(self.quantum_flame_frames)]

        for wall in self.quantum_wall_tiles:
            # The flame is a pure feedback layer: it turns off when a camera is
            # currently observing the wall, but the wall itself stays in place.
            if not wall.get("active", True) or wall.get("collapsed_out", False) or wall.get("observed", False):
                continue
            if wall.get("resolved_state") != "unresolved":
                continue

            rect = wall["rect"]
            draw_x = rect.x - self.camera_x
            draw_y = rect.y - self.camera_y
            flame_x = draw_x + rect.width // 2 - flame_frame.get_width() // 2 + QUANTUM_FLAME_OFFSET_X
            flame_y = draw_y + rect.height // 2 - flame_frame.get_height() // 2 - QUANTUM_FLAME_OFFSET_Y
            screen.blit(flame_frame, (flame_x, flame_y))

    def cable_color(self, channel):
        palette = {
            1: (255, 90, 90),
            2: (255, 215, 70),
            3: (90, 210, 120),
            4: (80, 170, 255),
            5: (210, 110, 255),
            6: (255, 150, 70),
            7: (110, 240, 235),
            8: (255, 120, 190),
            9: (210, 210, 230),
        }
        return palette.get(int(channel), ORANGE)

    def get_tinted_flame_frame(self, frame_index, channel):
        key = (frame_index, int(channel))
        cached = self.tinted_flame_cache.get(key)
        if cached is not None:
            return cached

        base = self.quantum_flame_frames[frame_index].copy()
        tint = pygame.Surface(base.get_size(), pygame.SRCALPHA)
        tint.fill((*self.cable_color(channel), 255))
        base.blit(tint, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        scaled_width = max(8, int(base.get_width() * 0.38))
        scaled_height = max(8, int(base.get_height() * 0.34))
        scaled = pygame.transform.smoothscale(base, (scaled_width, scaled_height))
        alpha = pygame.Surface(scaled.get_size(), pygame.SRCALPHA)
        alpha.fill((255, 255, 255, 150))
        scaled.blit(alpha, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        self.tinted_flame_cache[key] = scaled
        return scaled

    def draw_cable_layer(self, screen, surface_name):
        # Cables are rendered from the same tile graph the power solver uses, so
        # the player sees the actual connectivity rather than a second hand-made
        # visual layer.
        cable_rows = self.cable_map.get(surface_name, [])
        if not cable_rows:
            return

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
            for x in range(start_x, end_x):
                channels = sorted(cable_rows[y][x])
                if not channels:
                    continue

                center_x = x * self.tile_size - self.camera_x + self.tile_size // 2
                center_y = y * self.tile_size - self.camera_y + self.tile_size // 2
                count = len(channels)
                spacing = 6
                base_offset = -spacing * (count - 1) / 2

                for index, channel in enumerate(channels):
                    offset = int(round(base_offset + index * spacing))
                    color = self.cable_color(channel)
                    local_center = (center_x + offset, center_y + offset)
                    neighbors = {
                        "left": x > 0 and channel in cable_rows[y][x - 1],
                        "right": x + 1 < self.level_width_tiles and channel in cable_rows[y][x + 1],
                        "up": y > 0 and channel in cable_rows[y - 1][x],
                        "down": y + 1 < self.level_height_tiles and channel in cable_rows[y + 1][x],
                    }

                    line_width = 3 if surface_name == "floor" else 2
                    inner = max(4, self.tile_size // 5)
                    outer = self.tile_size // 2

                    if neighbors["left"]:
                        pygame.draw.line(screen, color, local_center, (center_x - outer, center_y + offset), line_width)
                    if neighbors["right"]:
                        pygame.draw.line(screen, color, local_center, (center_x + outer, center_y + offset), line_width)
                    if neighbors["up"]:
                        pygame.draw.line(screen, color, local_center, (center_x + offset, center_y - outer), line_width)
                    if neighbors["down"]:
                        pygame.draw.line(screen, color, local_center, (center_x + offset, center_y + outer), line_width)

                    pygame.draw.circle(screen, color, local_center, inner)

    def draw_powered_cable_effect(self, screen, surface_name):
        # Powered cable cells get a tinted flame overlay so the player can see
        # exactly how far the current reached through the network.
        cable_rows = self.cable_map.get(surface_name, [])
        if not cable_rows or not self.quantum_flame_frames:
            return

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

        frame_index = (self.quantum_flame_tick // QUANTUM_FLAME_FRAME_TIME) % len(self.quantum_flame_frames)
        for y in range(start_y, end_y):
            for x in range(start_x, end_x):
                channels = [channel for channel in sorted(cable_rows[y][x]) if self.powered_cable_cells.get((x, y, channel), 0) > 0]
                if not channels:
                    continue

                center_x = x * self.tile_size - self.camera_x + self.tile_size // 2
                center_y = y * self.tile_size - self.camera_y + self.tile_size // 2
                count = len(channels)
                spacing = 6
                base_offset = -spacing * (count - 1) / 2

                for index, channel in enumerate(channels):
                    offset = int(round(base_offset + index * spacing))
                    flame = self.get_tinted_flame_frame(frame_index, channel)
                    draw_x = center_x + offset - flame.get_width() // 2
                    draw_y = center_y + offset - flame.get_height() // 2 + 2
                    screen.blit(flame, (draw_x, draw_y))

    def draw_generator_overlay(self, screen, obj):
        # Generators reuse the existing sprite and get a tiny status lamp so the
        # on/off state is visible even without dedicated art variants.
        if obj.get("removed"):
            return
        image = obj["image"]
        draw_x, draw_y = self.get_object_draw_position(obj, image)
        lamp_color = (110, 255, 120) if self.is_generator_on(obj) else (120, 120, 120)
        lamp_center = (draw_x + image.get_width() - 8, draw_y + 8)
        pygame.draw.circle(screen, BLACK, lamp_center, 5)
        pygame.draw.circle(screen, lamp_color, lamp_center, 3)

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

    def draw_broken_particles(self, screen):
        if not self.electric_particle_frames:
            return
        frame = self.electric_particle_frames[self.quantum_flame_tick % len(self.electric_particle_frames)]
        for obj in self.broken_objects:
            if obj.get("removed") or obj.get("fixed", False):
                continue
            rect = obj["rect"]
            effect_size = max(self.tile_size, min(rect.width, rect.height))
            effect = frame
            if frame.get_width() != effect_size or frame.get_height() != effect_size:
                effect = pygame.transform.smoothscale(frame, (effect_size, effect_size))
            draw_x = rect.centerx - self.camera_x - effect.get_width() // 2
            draw_y = rect.centery - self.camera_y - effect.get_height() // 2
            screen.blit(effect, (draw_x, draw_y))

    def draw_note_aura(self, screen):
        if self.note_open_id or self.camera_place_mode:
            return
        pulse = (math.sin((pygame.time.get_ticks() / INTERACT_GLOW_PERIOD_MS) * math.tau) + 1) / 2
        overlay = pygame.Surface((self.viewport_width, self.viewport_height), pygame.SRCALPHA)
        for obj in self.notes:
            if obj.get("removed") or obj.get("interacted_once", False):
                continue
            image = self.get_object_display_image(obj)
            draw_x, draw_y = self.get_object_draw_position(obj, image)
            center = (draw_x + image.get_width() // 2, draw_y + image.get_height() // 2)
            base_radius = max(image.get_width(), image.get_height()) // 2
            radius = base_radius + int(round(NOTE_AURA_MIN_RADIUS_PAD + (NOTE_AURA_MAX_RADIUS_PAD - NOTE_AURA_MIN_RADIUS_PAD) * pulse))
            pygame.draw.circle(overlay, (*NOTE_GLOW_COLOR[:3], NOTE_AURA_ALPHA), center, radius)
        screen.blit(overlay, (0, 0))

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

    def draw_interaction_radius(self, screen):
        center_x = self.player.rect.centerx - self.camera_x
        center_y = self.player.rect.centery - self.camera_y
        overlay = pygame.Surface((self.viewport_width, self.viewport_height), pygame.SRCALPHA)
        pygame.draw.circle(overlay, (255, 255, 255, 18), (center_x, center_y), INTERACT_DISTANCE)
        pygame.draw.circle(overlay, (255, 255, 255, 70), (center_x, center_y), INTERACT_DISTANCE, 1)
        screen.blit(overlay, (0, 0))

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
            (self.plants, ALERT_GLOW_COLOR, ALERT_GLOW_WIDTH, True),
            (self.broken_objects, ALERT_GLOW_COLOR, ALERT_GLOW_WIDTH, True),
            (self.cleanup_objects, ALERT_GLOW_COLOR, ALERT_GLOW_WIDTH, True),
            (self.key_objects, INTERACT_GLOW_COLOR, INTERACT_GLOW_WIDTH, True),
            (self.world_pickups, INTERACT_GLOW_COLOR, INTERACT_GLOW_WIDTH, True),
            (self.generators, INTERACT_GLOW_COLOR, INTERACT_GLOW_WIDTH, True),
            (self.switches, INTERACT_GLOW_COLOR, INTERACT_GLOW_WIDTH, True),
            (self.interactives, INTERACT_GLOW_COLOR, INTERACT_GLOW_WIDTH, True),
            (self.placed_cameras, INTERACT_GLOW_COLOR, INTERACT_GLOW_WIDTH, False),
        )

        for objects, base_color, line_width, ignore_distance_before_first_interaction in collections:
            for obj in objects:
                if obj.get("removed"):
                    continue
                if obj.get("type") == "plant" and obj.get("watered", False):
                    continue
                if obj.get("type") == "broken" and obj.get("fixed", False):
                    continue
                if obj.get("type") in {"trash", "polluter"} and obj.get("cleaned", False):
                    continue
                if obj.get("interacted_once", False):
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

    def draw_progress_panel(self, screen):
        entries = self.get_progress_entries()
        panel_width = 320
        panel_height = 180
        panel_rect = pygame.Rect(WIDTH - panel_width - 16, 16, panel_width, panel_height)
        self.draw_ui_panel(screen, panel_rect)

        label_x = panel_rect.x + 16
        bar_x = panel_rect.x + 92
        bar_w = 190
        bar_h = 18
        y = panel_rect.y + 16

        for entry in entries:
            label_img = self.small_font.render(entry["label"], True, WHITE)
            screen.blit(label_img, (label_x, y - 2))

            outer_rect = pygame.Rect(bar_x, y, bar_w, bar_h)
            inner_rect = outer_rect.inflate(-4, -4)
            pygame.draw.rect(screen, WHITE, outer_rect, 2, border_radius=4)
            pygame.draw.rect(screen, (35, 35, 35), inner_rect, border_radius=3)

            if entry["total"] > 0 and entry["done"] > 0:
                fill_w = max(6, int(inner_rect.w * (entry["done"] / entry["total"])))
                fill_rect = pygame.Rect(inner_rect.x, inner_rect.y, min(fill_w, inner_rect.w), inner_rect.h)
                pygame.draw.rect(screen, entry["color"], fill_rect, border_radius=3)

            pct_img = self.tiny_font.render(f"{entry['percent']}%", True, WHITE)
            pct_rect = pct_img.get_rect(midleft=(outer_rect.right + 8, outer_rect.centery))
            screen.blit(pct_img, pct_rect)
            y += 30

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

            slot_payload = None
            if slot_id == 1 and self.inventory["camera"] > 0:
                slot_payload = ("camera", self.inventory_camera_icon, self.inventory["camera"])
            elif slot_id == 2 and self.inventory["watering_can"] > 0:
                slot_payload = ("watering_can", self.inventory_watering_can_icon, self.inventory["watering_can"])

            if slot_payload:
                _kind, icon, count = slot_payload
                icon_x = draw_x + (slot_width - icon.get_width()) // 2
                icon_y = draw_y + UI_CAMERA_ICON_OFFSET_Y - icon.get_height() // 2
                screen.blit(icon, (icon_x, icon_y))

                count_img = self.slot_count_font.render(str(count), True, WHITE)
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
        self.draw_progress_panel(screen)

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
        self.draw_cable_layer(world_surface, "floor")
        self.draw_powered_cable_effect(world_surface, "floor")

        for obj in self.draw_below:
            self.draw_object(world_surface, obj)
            if obj.get("type") == "generator":
                self.draw_generator_overlay(world_surface, obj)

        self.draw_bridges(world_surface)
        self.draw_world_pickups(world_surface)
        self.draw_switches(world_surface)
        self.draw_interactives(world_surface)
        self.draw_doors(world_surface)
        self.draw_buttons(world_surface)
        self.draw_boxes(world_surface)
        self.draw_placed_cameras(world_surface)

        self.draw_tile_layer(world_surface, self.overlay_rows, skip_codes=self.hidden_tile_codes, layer_name="overlay")
        self.draw_cable_layer(world_surface, "wall")
        self.draw_powered_cable_effect(world_surface, "wall")
        self.draw_quantum_wall_flames(world_surface)

        for obj in self.draw_above:
            self.draw_object(world_surface, obj)
            if obj.get("type") == "generator":
                self.draw_generator_overlay(world_surface, obj)

        self.draw_broken_particles(world_surface)
        self.draw_note_aura(world_surface)
        self.draw_notes(world_surface)
        self.draw_keys(world_surface)
        self.draw_interaction_radius(world_surface)
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
