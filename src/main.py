#!/usr/bin/env -S uv run
import subprocess
import time
from tuia import (
    TUIApp, Frame, Label, Button, TextInput, ProgressBar,
    pack, place, TOP, BOTTOM, LEFT, RIGHT, FILL_X, FILL_BOTH,
    BORDER_ROUNDED, BORDER_DOUBLE, BORDER_SINGLE, FocusManager
)


def main():
    # 1. Initialize core TUI engine
    app = TUIApp(fps_target=60)
    root = Frame(title=" Tuify Engine Showcase ", border_style=BORDER_ROUNDED)
    app.set_root(root)

    # Focus manager for Tab / Shift-Tab navigation
    focus_mgr = FocusManager(root)

    # 2. Dock Top Header Frame
    header_frame = Frame(parent=root, height=3, border_style=BORDER_SINGLE)
    pack(header_frame, side=TOP, fill=FILL_X, padx=1, pady=0)

    title_label = Label(
        parent=header_frame,
        text="TUIfy Engine: Docking, TrueColor, Z-Index & Handoff Demo",
        align="center"
    )
    pack(title_label, side=TOP, fill=FILL_X)

    # 3. Dock Main Sidebar Frame (Left)
    sidebar = Frame(parent=root, title=" Controls ",
                    width=30, border_style=BORDER_SINGLE)
    pack(sidebar, side=LEFT, fill=FILL_BOTH, padx=1, pady=0)

    # 4. Dock Content Area Frame (Right)
    content = Frame(
        parent=root, title=" Content & Dynamic Overlay ", border_style=BORDER_DOUBLE)
    pack(content, side=LEFT, fill=FILL_BOTH, expand=True, padx=0, pady=0)

    # --- Sidebar Controls ---
    lbl_instructions = Label(
        parent=sidebar, text="Press [Tab] to navigate", align="center")
    pack(lbl_instructions, side=TOP, fill=FILL_X, pady=1)

    # Progress bar demo state
    progress_bar = ProgressBar(parent=content, progress=0.25, width=40)
    place(progress_bar, x=2, y=2, relwidth=0.9)

    def inc_progress():
        progress_bar.progress = min(1.0, progress_bar.progress + 0.1)

    btn_progress = Button(
        parent=sidebar, text="Boost Progress", command=inc_progress, height=1)
    pack(btn_progress, side=TOP, fill=FILL_X, padx=2, pady=1)

    # Floating Overlay Frame (Demonstrating Z-Index + Hide/Show)
    overlay = Frame(parent=content, title=" Floating Modal ",
                    width=35, height=9, z_index=10, border_style=BORDER_ROUNDED)
    place(overlay, relx=0.2, rely=0.25)

    overlay_lbl = Label(
        parent=overlay, text="I'm a floating modal!", align="center")
    place(overlay_lbl, x=1, y=1, relwidth=0.9)

    def toggle_modal():
        if overlay.visible:
            overlay.hide()
        else:
            overlay.show()

    btn_modal = Button(parent=sidebar, text="Toggle Modal",
                       command=toggle_modal, height=1)
    pack(btn_modal, side=TOP, fill=FILL_X, padx=2, pady=1)

    # Screen Handoff Demo (Suspend curses -> Run shell command -> Resume curses)
    def trigger_handoff():
        with app.suspend_for_handoff():
            print("\n=======================================================")
            print(" [HANDOFF ACTIVE] TUI suspended. Running external command...")
            print("=======================================================\n")
            # Run an external app (e.g. system info command)
            subprocess.run(
                ["echo 'Hello from external shell process!'; sleep 2"], shell=True)
            print("\nReturning to TUI in 1 second...")
            time.sleep(1)

    btn_handoff = Button(parent=sidebar, text="Launch Ext. App",
                         command=trigger_handoff, height=1)
    pack(btn_handoff, side=TOP, fill=FILL_X, padx=2, pady=1)

    btn_quit = Button(parent=sidebar, text="Quit Application",
                      command=app.quit, height=1)
    pack(btn_quit, side=TOP, fill=FILL_X, padx=2, pady=1)

    # --- Content Area Widgets ---
    input_lbl = Label(parent=content, text="Interactive Input Field:")
    place(input_lbl, x=2, y=5)

    txt_input = TextInput(
        parent=content, placeholder="Type something here...", width=30)
    place(txt_input, x=2, y=7, relwidth=0.8)

    # Bind global input interceptor for Tab-based navigation
    original_handle = root.handle_event

    def custom_event_handler(key):
        # Initialize color engine insidecurses wrapper
        if focus_mgr.handle_tab_navigation(key):
            return True
        return original_handle(key)

    root.handle_event = custom_event_handler

    # Focus initial control
    focus_mgr.focus_next()

    # 5. Launch Application
    app.start()


if __name__ == "__main__":
    main()
