import pygame
from settings import PLAYER_SPEED

class Player:
    def __init__(self, x, y):
        self.speed = PLAYER_SPEED
        self.direction = "right"

        scale = 3

        img_left = pygame.image.load("assets/images/player/player_left.png").convert_alpha()
        img_right = pygame.image.load("assets/images/player/player_right.png").convert_alpha()

        self.image_left = pygame.transform.scale(
            img_left,
            (img_left.get_width() * scale, img_left.get_height() * scale)
        )

        self.image_right = pygame.transform.scale(
            img_right,
            (img_right.get_width() * scale, img_right.get_height() * scale)
        )

        self.image = self.image_right

        # Rect matches the actual scaled sprite size
        self.rect = pygame.Rect(x, y, self.image.get_width(), self.image.get_height())

    def move(self, keys):
        if keys[pygame.K_w]:
            self.rect.y -= self.speed
        if keys[pygame.K_s]:
            self.rect.y += self.speed
        if keys[pygame.K_a]:
            self.rect.x -= self.speed
            self.direction = "left"
        if keys[pygame.K_d]:
            self.rect.x += self.speed
            self.direction = "right"

        if self.direction == "left":
            self.image = self.image_left
        else:
            self.image = self.image_right

    def draw(self, surface, camera_x, camera_y):
        screen_x = self.rect.x - camera_x
        screen_y = self.rect.y - camera_y
        surface.blit(self.image, (screen_x, screen_y))