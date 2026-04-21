import os
os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"

import sys
import pygame

from button import Button
from game_constants import PAUSE_OVERLAY_ALPHA
from game_text import MENU_TEXT
from game import Game
from menu_ui import (
    draw_centered_text,
    make_horizontal_buttons,
    make_level_buttons,
    make_vertical_buttons,
)
from settings import *


def find_level_files():
    levels = []
    if os.path.isdir(LEVELS_DIR):
        for name in sorted(os.listdir(LEVELS_DIR)):
            if name.lower().endswith(".json"):
                levels.append(os.path.join(LEVELS_DIR, name))

    fallback = DEFAULT_LEVEL
    if not levels and os.path.isfile(fallback):
        levels.append(fallback)

    return levels

pygame.init()
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption(TITLE)
clock = pygame.time.Clock()

font = pygame.font.SysFont(None, 40)
small_font = pygame.font.SysFont(None, 26)

state = "menu"
game = None
selected_level = None

running = True
while running:
    screen.fill(DARK)
    events = pygame.event.get()

    level_files = find_level_files()

    menu_buttons = make_vertical_buttons(
        MENU_TEXT["main_buttons"],
        width=300,
        height=50,
        gap=20,
        screen_width=WIDTH,
        screen_height=HEIGHT,
        center_x=WIDTH // 2,
        top_y=HEIGHT // 2 - 40,
    )

    pause_buttons = make_vertical_buttons(
        MENU_TEXT["pause_buttons"],
        width=300,
        height=50,
        gap=20,
        screen_width=WIDTH,
        screen_height=HEIGHT,
        center_x=WIDTH // 2,
        top_y=HEIGHT // 2 - 110,
    )

    confirm_buttons = make_horizontal_buttons(
        MENU_TEXT["confirm_exit_buttons"],
        width=140,
        height=50,
        gap=10,
        screen_width=WIDTH,
        screen_height=HEIGHT,
        center_x=WIDTH // 2,
        y=HEIGHT // 2 + 40,
    )
    btn_yes, btn_no = confirm_buttons

    visible_level_files, level_buttons = make_level_buttons(
        level_files,
        screen_width=WIDTH,
        screen_height=HEIGHT,
        max_visible=7,
        width=440,
        height=46,
        gap=14,
    )

    back_button = Button(MENU_TEXT["back"], 20, HEIGHT - 60, 120, 40)

    for event in events:
        if event.type == pygame.QUIT:
            running = False

        if state == "game" and game is not None:
            game.handle_event(event)

        if event.type == pygame.KEYDOWN:
            if state == "game" and event.key == pygame.K_ESCAPE:
                state = "pause"
            elif state == "pause" and event.key == pygame.K_ESCAPE:
                state = "game"

        if event.type == pygame.MOUSEBUTTONDOWN:
            mouse_pos = pygame.mouse.get_pos()

            if state == "menu":
                if menu_buttons[0].is_clicked(mouse_pos):
                    state = "level_select"
                elif menu_buttons[1].is_clicked(mouse_pos):
                    state = "level_select"
                elif menu_buttons[2].is_clicked(mouse_pos):
                    state = "confirm_exit"

            elif state == "level_select":
                if back_button.is_clicked(mouse_pos):
                    state = "menu"
                else:
                    for path, button in zip(visible_level_files, level_buttons):
                        if button.is_clicked(mouse_pos):
                            selected_level = path
                            game = Game(path)
                            state = "game"
                            break

            elif state == "confirm_exit":
                if btn_yes.is_clicked(mouse_pos):
                    pygame.quit()
                    sys.exit()
                elif btn_no.is_clicked(mouse_pos):
                    state = "menu"

            elif state == "pause":
                if pause_buttons[0].is_clicked(mouse_pos):
                    state = "game"
                elif pause_buttons[1].is_clicked(mouse_pos):
                    if game is not None:
                        game.restart_to_checkpoint()
                    state = "game"
                elif pause_buttons[2].is_clicked(mouse_pos):
                    state = "level_select"
                elif pause_buttons[3].is_clicked(mouse_pos):
                    state = "menu"

    keys = pygame.key.get_pressed()
    if state == "game" and game is not None:
        game.update(keys)

    show_system_cursor = True
    if state == "game" and game is not None and game.should_draw_hand_cursor():
        show_system_cursor = False
    pygame.mouse.set_visible(show_system_cursor)

    if state == "menu":
        draw_centered_text(screen, font, MENU_TEXT["main_title"], 110, WHITE, WIDTH)
        for b in menu_buttons:
            b.draw(screen, font)

    elif state == "level_select":
        draw_centered_text(screen, font, MENU_TEXT["level_select_title"], 80, WHITE, WIDTH)

        if not level_files:
            draw_centered_text(screen, small_font, MENU_TEXT["level_select_empty"], HEIGHT // 2, WHITE, WIDTH)
        else:
            for b in level_buttons:
                b.draw(screen, small_font)

        back_button.draw(screen, small_font)

    elif state == "confirm_exit":
        draw_centered_text(screen, font, MENU_TEXT["confirm_exit_title"], HEIGHT // 2 - 30, WHITE, WIDTH)
        btn_yes.draw(screen, font)
        btn_no.draw(screen, font)

    elif state == "game":
        if game is not None:
            game.draw(screen, show_cursor=True)

    elif state == "pause":
        if game is not None:
            game.draw(screen, show_cursor=False)

        overlay = pygame.Surface((WIDTH, HEIGHT))
        overlay.set_alpha(PAUSE_OVERLAY_ALPHA)
        overlay.fill(BLACK)
        screen.blit(overlay, (0, 0))

        draw_centered_text(screen, font, MENU_TEXT["pause_title"], 100, WHITE, WIDTH)
        for b in pause_buttons:
            b.draw(screen, font)

    pygame.display.flip()
    clock.tick(FPS)

pygame.quit()
