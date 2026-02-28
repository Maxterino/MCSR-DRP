"""
diagnose.py — Live log viewer
==============================
Run this WHILE playing Minecraft. It prints every new line written to
latest.log in real time, so we can see exactly what gets logged when
you enter the nether, bastion, etc.

Usage:
  python diagnose.py

It will auto-find your MultiMC .minecraft. Leave it running, then:
  1. Start a new world
  2. Enter the nether
  3. Look at what lines printed here
  4. Tell the developer what you see

Press Ctrl+C to stop.
"""

import time
import sys
import glob
from pathlib import Path

# ---- find the log file ----

def find_log_files():
    home = Path.home()
    patterns = [
        # MultiMC / Prism on Desktop, common MCSR locations
        str(home / "Desktop" / "**" / ".minecraft" / "logs" / "latest.log"),
        str(home / "Desktop" / "MCSR" / "**" / ".minecraft" / "logs" / "latest.log"),
        str(home / "AppData" / "Roaming" / ".minecraft" / "logs" / "latest.log"),
        str(home / "AppData" / "Roaming" / "PrismLauncher" / "instances" / "**" / ".minecraft" / "logs" / "latest.log"),
        "C:/Users/*/Desktop/**/.minecraft/logs/latest.log",
        "C:/Users/*/Desktop/MCSR/**/.minecraft/logs/latest.log",
    ]
    found = []
    for pat in patterns:
        found.extend(glob.glob(pat, recursive=True))
    return list(set(found))

logs = find_log_files()

if not logs:
    print("ERROR: Could not find any latest.log file.")
    print("Please open Minecraft first, or pass the path manually:")
    print("  python diagnose.py C:/path/to/.minecraft/logs/latest.log")
    if len(sys.argv) > 1:
        logs = [sys.argv[1]]
    else:
        sys.exit(1)

if sys.argv[1:]:
    log_path = Path(sys.argv[1])
else:
    if len(logs) > 1:
        print("Found multiple log files:")
        for i, p in enumerate(logs):
            print(f"  [{i+1}] {p}")
        choice = int(input("Pick one: ")) - 1
        log_path = Path(logs[choice])
    else:
        log_path = Path(logs[0])

print(f"\nWatching: {log_path}")
print("=" * 60)
print("Start playing Minecraft. Every log line will appear here.")
print("Enter the nether and see what gets printed.")
print("Press Ctrl+C to stop.\n")

# ---- tail the file ----
pos = log_path.stat().st_size  # start from current end

try:
    while True:
        try:
            size = log_path.stat().st_size
            if size < pos:
                pos = 0  # file rotated
            if size > pos:
                with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                    f.seek(pos)
                    new = f.read()
                    pos = f.tell()
                for line in new.splitlines():
                    if line.strip():
                        print(line)
        except OSError:
            pass
        time.sleep(0.1)
except KeyboardInterrupt:
    print("\nStopped.")
