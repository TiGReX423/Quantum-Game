import pygame
from settings import *
from player import Player

class Game:
    def __init__(self):
        scale = 2

        
        self.player = Player(400, 300)

        self.camera_x = 0
        self.camera_y = 0

        self.deadzone = pygame.Rect(
            DEADZONE_X,
            DEADZONE_Y,
            DEADZONE_WIDTH,
            DEADZONE_HEIGHT
        )

        # wall
        img_wall = pygame.image.load("assets/images/walls/wall.png").convert_alpha()

        self.wall_image = pygame.transform.scale(
            img_wall,
            (img_wall.get_width() * scale, img_wall.get_height() * scale)
        )

        self.wall_width = self.wall_image.get_width()
        self.wall_height = self.wall_image.get_height()

        # walls list (positions in world)
        self.walls = [
            pygame.Rect(300, 300, self.wall_width, self.wall_height),
            pygame.Rect(300, 350, self.wall_width, self.wall_height),
            pygame.Rect(300, 400, self.wall_width, self.wall_height),
        ]# wall
        scale = 2

        img_wall = pygame.image.load("assets/images/walls/wall.png").convert_alpha()

        self.wall_image = pygame.transform.scale(
            img_wall,
            (img_wall.get_width() * scale, img_wall.get_height() * scale)
        )

        self.wall_width = self.wall_image.get_width()
        self.wall_height = self.wall_image.get_height()

        # walls list (positions in world)
        self.walls = [
            pygame.Rect(300, 300, self.wall_width, self.wall_height),
            pygame.Rect(300, 350, self.wall_width, self.wall_height),
            pygame.Rect(300, 400, self.wall_width, self.wall_height),
        ]

        floor_img = pygame.image.load("assets/images/tiles/floor.png").convert_alpha()
        self.floor_tile = pygame.transform.scale(floor_img, (floor_img.get_width()*scale, floor_img.get_height()*scale))
        self.tile_width = self.floor_tile.get_width()
        self.tile_height = self.floor_tile.get_height()

    def update(self, keys):
        dx, dy = self.player.get_movement(keys)

        if keys[pygame.K_w]:
            dy -= self.player.speed
        if keys[pygame.K_s]:
            dy += self.player.speed
        if keys[pygame.K_a]:
            dx -= self.player.speed
            self.player.direction = "left"
        if keys[pygame.K_d]:
            dx += self.player.speed
            self.player.direction = "right"

        # move X
        self.player.rect.x += dx
        for wall in self.walls:
            if self.player.rect.colliderect(wall):
                if dx > 0:
                    self.player.rect.right = wall.left
                if dx < 0:
                    self.player.rect.left = wall.right

        # move Y
        self.player.rect.y += dy
        for wall in self.walls:
            if self.player.rect.colliderect(wall):
                if dy > 0:
                    self.player.rect.bottom = wall.top
                if dy < 0:
                    self.player.rect.top = wall.bottom

        self.player.update_animation(dx, dy)

        # Keep player inside world
        self.player.rect.x = max(0, min(self.player.rect.x, WORLD_WIDTH - self.player.rect.width))
        self.player.rect.y = max(0, min(self.player.rect.y, WORLD_HEIGHT - self.player.rect.height))

        # Player screen position
        px = self.player.rect.x - self.camera_x
        py = self.player.rect.y - self.camera_y

        # Camera movement using dead zone
        if px < self.deadzone.left:
            self.camera_x = self.player.rect.x - self.deadzone.left
        elif px + self.player.rect.width > self.deadzone.right:
            self.camera_x = self.player.rect.x + self.player.rect.width - self.deadzone.right

        if py < self.deadzone.top:
            self.camera_y = self.player.rect.y - self.deadzone.top
        elif py + self.player.rect.height > self.deadzone.bottom:
            self.camera_y = self.player.rect.y + self.player.rect.height - self.deadzone.bottom

        # Keep camera inside world bounds
        self.camera_x = max(0, min(self.camera_x, WORLD_WIDTH - WIDTH))
        self.camera_y = max(0, min(self.camera_y, WORLD_HEIGHT - HEIGHT))

    def draw_floor(self, screen):
        start_x = self.camera_x // self.tile_width
        end_x = (self.camera_x + WIDTH) // self.tile_width + 1

        start_y = self.camera_y // self.tile_height
        end_y = (self.camera_y + HEIGHT) // self.tile_height + 1

        for tile_x in range(start_x, end_x):
            for tile_y in range(start_y, end_y):
                world_x = tile_x * self.tile_width
                world_y = tile_y * self.tile_height

                screen_x = world_x - self.camera_x
                screen_y = world_y - self.camera_y

                screen.blit(self.floor_tile, (screen_x, screen_y))

    def draw(self, screen):
        self.draw_floor(screen)

        # draw walls
        for wall in self.walls:
            screen_x = wall.x - self.camera_x
            screen_y = wall.y - self.camera_y
            screen.blit(self.wall_image, (screen_x, screen_y))

        # World border
        world_rect = pygame.Rect(-self.camera_x, -self.camera_y, WORLD_WIDTH, WORLD_HEIGHT)
        pygame.draw.rect(screen, WHITE, world_rect, 4)

        # Dead zone debug
        pygame.draw.rect(screen, WHITE, self.deadzone, 3)

        # Player
        self.player.draw(screen, self.camera_x, self.camera_y)