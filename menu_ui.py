from button import Button


def make_vertical_buttons(
    labels,
    width,
    height,
    gap,
    screen_width,
    screen_height,
    center_x=None,
    top_y=None,
):
    if center_x is None:
        center_x = screen_width // 2

    total_h = len(labels) * height + max(0, len(labels) - 1) * gap
    if top_y is None:
        top_y = (screen_height - total_h) // 2

    x = center_x - width // 2
    return [
        Button(label, x, top_y + i * (height + gap), width, height)
        for i, label in enumerate(labels)
    ]


def make_horizontal_buttons(
    labels,
    width,
    height,
    gap,
    screen_width,
    screen_height,
    center_x=None,
    y=None,
):
    if center_x is None:
        center_x = screen_width // 2
    if y is None:
        y = screen_height // 2

    total_w = len(labels) * width + max(0, len(labels) - 1) * gap
    start_x = center_x - total_w // 2
    return [
        Button(label, start_x + i * (width + gap), y, width, height)
        for i, label in enumerate(labels)
    ]


def make_level_buttons(level_files, screen_width, screen_height, max_visible=7, width=440, height=46, gap=14):
    visible_files = level_files[:max_visible]
    labels = [path.split("\\")[-1].split("/")[-1] for path in visible_files]
    buttons = make_vertical_buttons(
        labels,
        width=width,
        height=height,
        gap=gap,
        screen_width=screen_width,
        screen_height=screen_height,
        center_x=screen_width // 2,
        top_y=(screen_height - (len(labels) * height + max(0, len(labels) - 1) * gap)) // 2,
    )
    return visible_files, buttons


def draw_centered_text(surface, font, text, y, color, screen_width):
    img = font.render(text, True, color)
    rect = img.get_rect(center=(screen_width // 2, y))
    surface.blit(img, rect)
