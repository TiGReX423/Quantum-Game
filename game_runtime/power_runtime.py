
import math
from collections import defaultdict


class PowerRuntimeMixin:
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

    def object_cable_contact_cells(self, obj):
        # Power sources and consumers can connect through the tile they occupy
        # or any orthogonally adjacent tile. This matches the editor workflow,
        # where cables are often drawn flush against a generator or door sprite.
        rect = obj.get("rect")
        if rect is None:
            gx, gy = self.grid_pos_from_obj(obj)
            return [(gx, gy)]

        left = max(0, rect.left // self.tile_size)
        right = min(self.level_width_tiles - 1, (rect.right - 1) // self.tile_size)
        top = max(0, rect.top // self.tile_size)
        bottom = min(self.level_height_tiles - 1, (rect.bottom - 1) // self.tile_size)

        cells = set()
        for gy in range(top, bottom + 1):
            for gx in range(left, right + 1):
                cells.add((gx, gy))
                if gx > 0:
                    cells.add((gx - 1, gy))
                if gx + 1 < self.level_width_tiles:
                    cells.add((gx + 1, gy))
                if gy > 0:
                    cells.add((gx, gy - 1))
                if gy + 1 < self.level_height_tiles:
                    cells.add((gx, gy + 1))
        return sorted(cells)

    def has_active_cable(self, x, y, channel):
        # Cables are tile-based graph nodes. A cable exists if the channel is
        # recorded in either floor or wall cable_map for that cell.
        if not (0 <= x < self.level_width_tiles and 0 <= y < self.level_height_tiles):
            return False
        if channel in self.cable_map.get("floor", [])[y][x]:
            return True
        if channel in self.cable_map.get("wall", [])[y][x]:
            wall = self.quantum_wall_at(x, y)
            # A wall cable on a quantum wall only conducts while that wall is
            # currently observed and resolved as present. If observation is
            # removed, the wall may still be drawn again as "uncertain", but
            # the cable cannot be trusted to exist through empty space.
            if wall:
                if not wall.get("active", True):
                    return False
                if wall.get("resolved_state") == "classical":
                    return True
                if not wall.get("observed", False):
                    return False
            return True
        return False

    def collect_power_for_generator(self, generator):
        # Power spreads by BFS over orthogonally adjacent cable cells. Equal
        # channel number means "same cable type", while physical adjacency
        # decides whether the cells are actually connected.
        if not self.is_generator_on(generator):
            return {}
        channels = self.parse_channel_list(generator.get("cable_ids", ""))
        if not channels:
            single = generator.get("cable_id", "")
            channels = self.parse_channel_list(single)

        contact_cells = self.object_cable_contact_cells(generator)
        reachable_by_channel = {}
        for channel in channels:
            starts = [(gx, gy) for gx, gy in contact_cells if self.has_active_cable(gx, gy, channel)]
            if not starts:
                continue
            visited = set()
            queue = list(starts)
            while queue:
                x, y = queue.pop(0)
                if (x, y) in visited or not self.has_active_cable(x, y, channel):
                    continue
                visited.add((x, y))
                for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                    if (nx, ny) not in visited and self.has_active_cable(nx, ny, channel):
                        queue.append((nx, ny))
            if visited:
                reachable_by_channel[channel] = visited

        if not reachable_by_channel:
            return {}

        power = max(0, int(generator.get("power", 1)))
        scored_channels = self.order_power_channels(generator, reachable_by_channel)
        consumer_channels = [channel for distance, channel in scored_channels if distance != math.inf]
        channel_order = consumer_channels or [channel for _, channel in scored_channels]
        base_share = power // len(channel_order)
        remainder = power % len(channel_order)

        powered = {}
        for index, channel in enumerate(channel_order):
            channel_power = base_share + (1 if index < remainder else 0)
            if channel_power <= 0:
                continue
            for cell in reachable_by_channel[channel]:
                powered[(cell[0], cell[1], channel)] = powered.get((cell[0], cell[1], channel), 0) + channel_power
        return powered

    def channel_priority_distance(self, generator, reachable_cells):
        generator_cells = self.object_cable_contact_cells(generator)
        best = math.inf
        for door in self.doors:
            requirements = self.parse_required_power(door.get("required_power", ""))
            if not requirements:
                continue
            for gx, gy in self.object_cable_contact_cells(door):
                if (gx, gy) not in reachable_cells:
                    continue
                for sgx, sgy in generator_cells:
                    best = min(best, abs(gx - sgx) + abs(gy - sgy))
        return best

    def order_power_channels(self, generator, reachable_by_channel):
        scored = []
        for channel, cells in reachable_by_channel.items():
            scored.append((self.channel_priority_distance(generator, cells), channel))
        scored.sort(key=lambda item: (item[0], item[1]))
        return scored

    def refresh_power_networks(self):
        # Powered cells accumulate contributions from all enabled generators.
        # Doors then query the total power that reached their own grid cell.
        powered = {}
        self.door_power_status = {}
        for generator in self.generators:
            for key, amount in self.collect_power_for_generator(generator).items():
                powered[key] = powered.get(key, 0) + amount
        self.powered_cable_cells = powered

        for obj in self.doors:
            requirements = self.parse_required_power(obj.get("required_power", ""))
            if not requirements:
                continue
            contact_cells = self.object_cable_contact_cells(obj)
            if "total" in requirements:
                received_total = max((self.powered_cell_total(powered, gx, gy) for gx, gy in contact_cells), default=0)
                required_total = requirements["total"]
                is_powered = received_total >= required_total
            else:
                required_total = sum(requirements.values())
                received_total = sum(
                    min(
                        max((powered.get((gx, gy, channel), 0) for gx, gy in contact_cells), default=0),
                        amount,
                    )
                    for channel, amount in requirements.items()
                )
                is_powered = all(
                    max((powered.get((gx, gy, channel), 0) for gx, gy in contact_cells), default=0) >= amount
                    for channel, amount in requirements.items()
                )
            self.door_power_status[obj.get("id", "")] = {
                "received": received_total,
                "required": required_total,
                "powered": is_powered,
            }
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
                self.set_button_targets_state(button["target_id"], True)

    def refresh_pressure_buttons(self):
        box_rects = [box["rect"] for box in self.boxes]
        groups = defaultdict(list)

        for button in self.pressure_buttons:
            button["occupied_now"] = any(button["rect"].colliderect(rect) for rect in box_rects)
            button["active"] = button["occupied_now"]
            groups[button["target_id"]].append(button)

        for target_id, buttons in groups.items():
            if buttons and all(button["active"] for button in buttons):
                self.set_button_targets_state(target_id, True)
            else:
                self.set_button_targets_state(target_id, False)
