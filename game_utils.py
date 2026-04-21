import os
import math

import pygame


def resolve_path(path):
    return os.path.normpath(path)


def crop_transparent(image):
    rect = image.get_bounding_rect()
    if rect.width > 0 and rect.height > 0:
        return image.subsurface(rect).copy()
    return image.copy()


def load_image(path, scale=1.0):
    full_path = resolve_path(path)
    image = crop_transparent(pygame.image.load(full_path).convert_alpha())
    if scale != 1.0:
        image = pygame.transform.scale(
            image,
            (
                max(1, int(round(image.get_width() * scale))),
                max(1, int(round(image.get_height() * scale))),
            ),
        )
    return image


def angle_to(from_pos, to_pos):
    dx = to_pos[0] - from_pos[0]
    dy = to_pos[1] - from_pos[1]
    return math.degrees(math.atan2(dy, dx))


def angle_diff(a, b):
    d = (a - b + 180) % 360 - 180
    return abs(d)
