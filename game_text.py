NOTE_TEXTS = {
    "note_1": "Darling, I left you some food on the table. Don't go to work hungry. Warm it up properly and make sure you eat. I love you.",
    "note_2": "The surveillance system is acting up again: the cameras in the lab are acting strangely near the experimental subjects. Check the image before your shift.",
    "note_3": "The key is hanging on the key holder near the exit. Take it if the door is still closed and simply use the mouse nearby.",
    "note_4": "There's a portable camera by the exit. Don't forget what it's for: sometimes only observation can change what's happening in the lab.",
    "note_5": "There's a labyrinth ahead. Take your time, look around, and don't get lost. Sometimes it's better to stop and think than to rush in.",
    "note_6": "The three quantum buttons are unstable. When the camera is looking at several at once, one of them disappears. If several are in view, the farthest one disappears.",
    "note_7": "This box is very heavy. You can only push it one square at a time and only forward. You can't push two boxes at once.",
    "note_8": "Some buttons require you to hold down. If you don't feel like standing there, try placing a box on them.",
    "note_9": "Good luck at work in the lab. And try not to blow anything up today.",
}

HOVER_HINTS = {
    "interactive": "LMB - interact",
    "switch": "LMB - toggle",
    "note": "LMB - read",
    "pickup": "LMB/RMB - pick up",
    "key": "LMB/RMB - use key",
    "placed_camera": "RMB - remove camera",
}

HUD_LINES = (
    "E - place/remove camera",
    "R - return to checkpoint",
)

NOTE_CLOSE_TEXT = "RMB - close"

TUTORIAL_PAGES = (
    {
        "title": "Movement",
        "lines": (
            "Use WASD to move.",
            "You can move diagonally.",
            "Press any key or click to continue.",
        ),
    },
    {
        "title": "Interaction",
        "lines": (
            "Use the mouse to interact with the world.",
            "LMB reads and interacts.",
            "RMB closes notes and can pick up or use some objects.",
            "Press any key or click to start.",
        ),
    },
)

MESSAGES = {
    "checkpoint_return": "Returned to checkpoint.",
    "thank_wife": "I should thank my wife.",
    "already_slept": "I've already slept enough.",
    "kitchen_done": "The kitchen feels cozy. I've already eaten.",
    "kitchen_hungry": "I should eat before heading to work.",
    "food_after_note": "My wife cooks so deliciously.",
    "food_default": "That was delicious.",
    "painting": "I love this painting.",
    "key_used": "Time to hit the road.",
    "camera_picked": "Picked up a camera.",
    "health_picked": "HP +1",
    "item_picked": "Picked up item: {kind}",
    "camera_returned": "Camera returned to inventory.",
    "camera_slot_empty": "There is no camera in the selected slot.",
    "camera_bad_spot": "You can't place a camera here.",
    "camera_confirm": "Place camera: LMB confirm, RMB cancel.",
    "camera_blocked": "You can't place the camera at this spot.",
    "camera_placed": "Camera placed.",
    "camera_cancelled": "Camera placement canceled.",
    "switch_on": "Bridge enabled.",
    "switch_off": "Bridge disabled.",
    "switch_missing_target": "This switch is not connected to a bridge.",
    "god_mode_on": "God mode enabled.",
    "god_mode_off": "God mode disabled.",
    "god_teleport": "Teleported.",
}

MENU_TEXT = {
    "main_title": "MAIN MENU",
    "main_buttons": ["New Game", "Level Select", "Exit"],
    "level_select_title": "SELECT LEVEL",
    "level_select_empty": "No .json levels found in /levels",
    "pause_title": "PAUSE MENU",
    "pause_buttons": ["Resume", "Restart CP", "Level Select", "Main Menu"],
    "confirm_exit_title": "Are you sure you want to exit?",
    "confirm_exit_buttons": ["Yes", "No"],
    "back": "Back",
}
