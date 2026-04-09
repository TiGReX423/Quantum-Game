import os
import pygame
from settings import PLAYER_SPEED


class Player:
    def __init__(self, x, y):
        self.speed = PLAYER_SPEED
        self.scale = 3

        # Hitbox used for movement and collisions
        self.rect = pygame.Rect(x, y, 24 * self.scale, 12 * self.scale)

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

        # Idle sprite
        idle_img = pygame.image.load("assets/images/player/player.png").convert_alpha()
        crop_rect = idle_img.get_bounding_rect()
        if crop_rect.width > 0 and crop_rect.height > 0:
            idle_img = idle_img.subsurface(crop_rect).copy()

        self.idle_image = pygame.transform.scale(
            idle_img,
            (idle_img.get_width() * self.scale, idle_img.get_height() * self.scale)
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

            # Crop transparent empty space around the sprite
            crop_rect = image.get_bounding_rect()
            if crop_rect.width > 0 and crop_rect.height > 0:
                image = image.subsurface(crop_rect).copy()

            # Scale without smoothing to keep pixel art sharp
            image = pygame.transform.scale(
                image,
                (image.get_width() * self.scale, image.get_height() * self.scale)
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

        # Keep current facing if its key is still held
        if self.direction_key_held(keys, self.facing):
            return

        # Choose a new facing only if current facing key is no longer held
        if keys[pygame.K_w]:
            self.facing = "up"
        elif keys[pygame.K_s]:
            self.facing = "down"
        elif keys[pygame.K_a]:
            self.facing = "left"
        elif keys[pygame.K_d]:
            self.facing = "right"

    def get_movement(self, keys):
        dx = 0
        dy = 0

        if keys[pygame.K_w]:
            dy -= self.speed
        if keys[pygame.K_s]:
            dy += self.speed
        if keys[pygame.K_a]:
            dx -= self.speed
        if keys[pygame.K_d]:
            dx += self.speed

        self.choose_facing(keys, dx, dy)
        return dx, dy

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

    def draw(self, surface, camera_x, camera_y):
        # Draw sprite using bottom-center alignment to keep feet stable
        draw_x = self.rect.centerx - camera_x
        draw_y = self.rect.bottom - camera_y

        image_rect = self.image.get_rect(midbottom=(draw_x, draw_y))
        surface.blit(self.image, image_rect)

        # Debug hitbox
        # pygame.draw.rect(
        #     surface,
        #     (255, 0, 0),
        #     pygame.Rect(
        #         self.rect.x - camera_x,
        #         self.rect.y - camera_y,
        #         self.rect.width,
        #         self.rect.height
        #     ),
        #     1
        # )