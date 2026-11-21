# Fake-Roblox-Ban-Prank
his script is a Windows prank / protocol-hijacking program built around a fake Roblox ban screen. When packaged into an executable and run, it copies itself into the Windows Startup folder, registers itself as the handler for roblox-player: links in HKCU, and renders a full-screen tkinter overlay showing a fake "Banned for 7 Days" / Hardware ID block message whenever a roblox-player: URI is triggered.

Because it modifies startup entries and protocol handlers, test it only on a personal or test machine where you want that behavior—and expect Windows Defender or third-party antivirus to flag or quarantine compiled .exe builds.

How It Works Under the Hood
Resource Path Resolution (resource_path): Uses getattr(sys, "_MEIPASS", None) to locate bundled assets (Screenshot 2026-04-14 183821.png and roblox.ico) inside a PyInstaller bundle, falling back to the current working directory when run as a normal .py script.

Backup & Persistence (backup_existing_protocol, install_and_hijack):

Only runs persistence steps when getattr(sys, "frozen", False) is true (meaning it is running as a compiled executable rather than a raw .py script).

Exports any existing HKCU\Software\Classes\roblox-player key to %TEMP%\roblox_player_protocol_backup.reg the first time it runs so it can be restored later.

Copies the running executable to %APPDATA%\Microsoft\Windows\Start Menu\Programs\Startup\RobloxPlayer.exe (unless already there or already running from that exact path).

Sets HKCU\Software\Classes\roblox-player\shell\open\command to launch RobloxPlayer.exe "%1".

Ban Overlay GUI (run_ban_gui):

Only launches when roblox-player: appears in sys.argv[1:] (for example, when a browser or Roblox launcher opens a roblox-player: link).

Opens a full-screen (zoomed), always-on-top (-topmost) tkinter window, crops/fits the background screenshot to screen resolution, darkens it by blending with a black image, draws a centered white dialog box with custom Segoe UI fonts, and adds a "Logout" label with hover states and click-to-close behavior.

Stores ImageTk.PhotoImage objects in _refs so Python's garbage collector does not drop images while the window is active.

Cleanup & Restoration (full_cleanup, restore_protocol_backup):

Sets cleanup_in_progress = True so persistence logic is skipped.

Recursively deletes HKCU\Software\Classes\roblox-player and imports %TEMP%\roblox_player_protocol_backup.reg via reg.exe import if a backup exists, then removes the .reg file.

Writes a temporary batch script (%TEMP%\cleanup_roblox_player.bat) that waits for the current process PID to exit, deletes RobloxPlayer.exe from the Startup folder, and deletes the batch file itself (%~f0).

How to Set Up & Use It
Prepare the files and dependencies:

Put your script (main.py), Screenshot 2026-04-14 183821.png, and roblox.ico in the same folder.

Install Pillow if you do not already have it:

Bash
pip install pillow
Test the GUI directly from source:

Because install_and_hijack() checks sys.frozen, running the .py file directly will not copy to Startup or hijack the registry. Pass a dummy roblox-player: argument to preview the window:

Bash
python main.py "roblox-player:1"
Build the executable (for full persistence/hijack behavior):

Package with PyInstaller, bundling the image and icon as data files:

Bash
pyinstaller --noconfirm --onefile --windowed --icon=roblox.ico --add-data "Screenshot 2026-04-14 183821.png;." --add-data "roblox.ico;." main.py
Run the resulting .exe from dist\main.exe to register persistence and protocol handling.

Use hotkeys and cleanup:

Ctrl + Alt + C: Opens the RobloxPlayer Debugger window displaying timestamped log entries.

Esc (or clicking Logout): Closes the current GUI window without removing persistence.

Ctrl + Alt +  (grave/tilde key while in the GUI): Triggersfull_cleanup(), restores the registry backup if present, schedules deletion of RobloxPlayer.exe` from Startup, opens the log console briefly, and exits.

--cleanup flag: Run RobloxPlayer.exe --cleanup from Command Prompt or PowerShell to trigger full_cleanup() directly without opening the ban screen first.

Limitations & Edge Cases to Keep in Mind
No real-time Ctrl + Alt hotkey hook when idle: root.bind(...) only listens while the tkinter GUI window has focus. When no GUI window is open, use the --cleanup command-line flag or manually remove the Startup file and registry key.

No official Roblox fallback: If there was no prior HKCU\Software\Classes\roblox-player key when the script first ran, restoring the backup will not recreate Roblox's protocol handler on its own—reinstalling or repairing Roblox restores normal roblox-player: launching.

Two-second sleep during cleanup: full_cleanup calls time.sleep(2) before destroying the window, which briefly pauses UI responsiveness right before exit.
