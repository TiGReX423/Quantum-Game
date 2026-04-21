import os
import pygame
from settings import (
    PLAYER_SPEED,
    PLAYER_ACCELERATION,
    PLAYER_DECELERATION,
    PLAYER_MAX_HP,
    PLAYER_VISUAL_SCALE,
    PLAYER_HITBOX_WIDTH,
    PLAYER_HITBOX_HEIGHT,
    RED,
)


class Player:
    def __init__(self, x, y):
        self.speed = PLAYER_SPEED
        self.acceleration = PLAYER_ACCELERATION
        self.deceleration = PLAYER_DECELERATION
        self.scale = PLAYER_VISUAL_SCALE
        self.max_hp = PLAYER_MAX_HP
        self.hp = PLAYER_MAX_HP

        # Hitbox used for movement and collisions
        self.rect = pygame.Rect(x, y, PLAYER_HITBOX_WIDTH, PLAYER_HITBOX_HEIGHT)
        self.position = pygame.Vector2(float(x), float(y))
        self.velocity = pygame.Vector2()

        self.facing = "down"
        self.frame_index = 0
        self.animation_timer = 0.0
        self.animation_speed = 0.18

        self.animations = {
            "down": self.load_animation("assets/images/player/move/move_down"),
            "up": self.load_animation("assets/images/player/move/move_up"),
            "left": self.load_animation("assets/images/player/move/move_left"),
            "right": self.load_animation("assets/images/player/move/move_right"),
        }

        idle_img = pygame.image.load("assets/images/player/player.png").convert_alpha()
        crop_rect = idle_img.get_bounding_rect()
        if crop_rect.width > 0 and crop_rect.height > 0:
            idle_img = idle_img.subsurface(crop_rect).copy()

        self.idle_image = pygame.transform.scale(
            idle_img,
            (
                max(1, int(idle_img.get_width() * self.scale)),
                max(1, int(idle_img.get_height() * self.scale)),
            )
        )

        self.image = self.idle_image

    def load_animation(self, folder_path):
        frames = []

        file_names = sorted(
            [name for name in os.listdir(folder_path) if name.lower().endswith(".png")]
        )

        for file_name in file_names:
            full_path = os.path.join(folder_path, file_name)
            image = pygame.image.load(full_path).convert_alpha()

            crop_rect = image.get_bounding_rect()
            if crop_rect.width > 0 and crop_rect.height > 0:
                image = image.subsurface(crop_rect).copy()

            image = pygame.transform.scale(
                image,
                (
                    max(1, int(image.get_width() * self.scale)),
                    max(1, int(image.get_height() * self.scale)),
                )
            )

            frames.append(image)

        return frames

    def direction_key_held(self, keys, direction):
        if direction == "up":
            return keys[pygame.K_w]
        if direction == "down":
            return keys[pygame.K_s]
        if direction == "left":
            return keys[pygame.K_a]
        if direction == "right":
            return keys[pygame.K_d]
        return False

    def choose_facing(self, keys, dx, dy):
        if dx == 0 and dy == 0:
            return

        if self.direction_key_held(keys, self.facing):
            return

        if keys[pygame.K_w]:
            self.facing = "up"
        elif keys[pygame.K_s]:
            self.facing = "down"
        elif keys[pygame.K_a]:
            self.facing = "left"
        elif keys[pygame.K_d]:
            self.facing = "right"

    def get_movement(self, keys):
        input_x = 0
        input_y = 0

        if keys[pygame.K_w]:
            input_y -= 1
        if keys[pygame.K_s]:
            input_y += 1
        if keys[pygame.K_a]:
            input_x -= 1
        if keys[pygame.K_d]:
            input_x += 1

        input_vector = pygame.Vector2(input_x, input_y)
        if input_vector.length_squared() > 0:
            input_vector = input_vector.normalize() * self.speed
            self.velocity.x = self.move_towards(self.velocity.x, input_vector.x, self.acceleration)
            self.velocity.y = self.move_towards(self.velocity.y, input_vector.y, self.acceleration)
        else:
            self.velocity.x = self.move_towards(self.velocity.x, 0.0, self.deceleration)
            self.velocity.y = self.move_towards(self.velocity.y, 0.0, self.deceleration)

        self.choose_facing(keys, self.velocity.x, self.velocity.y)
        return self.velocity.x, self.velocity.y

    def move_towards(self, current, target, amount):
        if current < target:
            return min(current + amount, target)
        if current > target:
            return max(current - amount, target)
        return current

    def move_axis(self, dx, dy):
        self.position.x += dx
        self.position.y += dy
        self.sync_rect()

    def sync_rect(self):
        self.rect.x = int(round(self.position.x))
        self.rect.y = int(round(self.position.y))

    def update_animation(self, dx, dy):
        moving = dx != 0 or dy != 0

        if moving:
            self.animation_timer += self.animation_speed
            frame_count = len(self.animations[self.facing])

            if self.animation_timer >= frame_count:
                self.animation_timer = 0.0

            self.frame_index = int(self.animation_timer)
            self.image = self.animations[self.facing][self.frame_index]
        else:
            self.animation_timer = 0.0
            self.frame_index = 0
            self.image = self.idle_image

    def respawn(self, x, y):
        self.position.update(float(x), float(y))
        self.velocity.update(0.0, 0.0)
        self.sync_rect()

    def heal(self, amount=1):
        self.hp = min(self.max_hp, self.hp + amount)

    def draw(self, surface, camera_x, camera_y):
        draw_x = self.rect.centerx - camera_x
        draw_y = self.rect.bottom - camera_y

        image_rect = self.image.get_rect(midbottom=(draw_x, draw_y))
        surface.blit(self.image, image_rect)

    def draw_hitbox(self, surface, camera_x, camera_y):
        pygame.draw.rect(
            surface,
            RED,
            pygame.Rect(
                self.rect.x - camera_x,
                self.rect.y - camera_y,
                self.rect.width,
                self.rect.height,
            ),
            1,
        )
