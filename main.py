import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import pygame
import sys

from game import Game
from settings import *
from button import Button


pygame.init()

screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption(TITLE)

clock = pygame.time.Clock()
font = pygame.font.SysFont(None, 40)

# Game state
state = "menu"  # menu / confirm_exit / game / pause
has_save = False

# Buttons
menu_buttons = [
    Button("New Game", 250, 150),
    Button("Load Game", 250, 220, enabled=has_save),
    Button("Settings", 250, 290),
    Button("Exit", 250, 360)
]

btn_yes = Button("Yes", 220, 300, 140, 50)
btn_no = Button("No", 440, 300, 140, 50)

pause_buttons = [
    Button("Save", 250, 150),
    Button("Main Menu", 250, 220),
    Button("Settings", 250, 290),
    Button("Resume", 250, 360)
]

# Player
game = Game()

running = True
while running:
    screen.fill(DARK)

    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False

        if event.type == pygame.KEYDOWN:
            if state == "game" and event.key == pygame.K_ESCAPE:
                state = "pause"
            elif state == "pause" and event.key == pygame.K_ESCAPE:
                state = "game"

        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()

            if state == "menu":
                if menu_buttons[0].is_clicked(mouse_pos):
                    state = "game"

                elif menu_buttons[1].is_clicked(mouse_pos):
                    print("Load game")

                elif menu_buttons[2].is_clicked(mouse_pos):
                    print("Settings")

                elif menu_buttons[3].is_clicked(mouse_pos):
                    state = "confirm_exit"

            elif state == "confirm_exit":
                if btn_yes.is_clicked(mouse_pos):
                    pygame.quit()
                    sys.exit()
                elif btn_no.is_clicked(mouse_pos):
                    state = "menu"

            elif state == "pause":
                if pause_buttons[0].is_clicked(mouse_pos):
                    print("Save game")

                elif pause_buttons[1].is_clicked(mouse_pos):
                    state = "menu"

                elif pause_buttons[2].is_clicked(mouse_pos):
                    print("Pause settings")

                elif pause_buttons[3].is_clicked(mouse_pos):
                    state = "game"

    keys = pygame.key.get_pressed()
    if state == "game":
        game.update(keys)

    # Draw
    if state == "menu":
        title = font.render("MAIN MENU", True, WHITE)
        screen.blit(title, (300, 80))

        for b in menu_buttons:
            b.draw(screen, font)

    elif state == "confirm_exit":
        text = font.render("Are you sure you want to exit?", True, WHITE)
        screen.blit(text, (180, 200))

        btn_yes.draw(screen, font)
        btn_no.draw(screen, font)

    elif state == "game":
        game.draw(screen)

    elif state == "pause":
        game.draw(screen)

        overlay = pygame.Surface((WIDTH, HEIGHT))
        overlay.set_alpha(160)
        overlay.fill(BLACK)
        screen.blit(overlay, (0, 0))

        title = font.render("PAUSE MENU", True, WHITE)
        screen.blit(title, (290, 80))

        for b in pause_buttons:
            b.draw(screen, font)

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()