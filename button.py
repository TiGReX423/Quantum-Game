import pygame
from settings import LIGHT, GRAY, DARK

class Button:
    def __init__(self, text, x, y, width=300, height=50, enabled=True):
        self.text = text
        self.enabled = enabled
        self.rect = pygame.Rect(x, y, width, height)

    def draw(self, surface, font):
        color = LIGHT if self.enabled else GRAY
        pygame.draw.rect(surface, color, self.rect)

        txt = font.render(self.text, True, DARK)
        text_rect = txt.get_rect(center=self.rect.center)
        surface.blit(txt, text_rect)

    def is_clicked(self, pos):
        return self.enabled and self.rect.collidepoint(pos)