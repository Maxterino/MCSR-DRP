"""
MCSR Discord Rich Presence Tracker
====================================
Reads SpeedRunIGT's latest_world data to update Discord Rich Presence
with your current Minecraft speedrun progress.

Supported splits:
  - Started new run (Overworld)
  - Entered Nether
  - Entered Bastion / Fortress
  - Built First Portal
  - Found Stronghold
  - Entered End
  - Finished (Dragon killed)

Requirements:
  pip install pypresence watchdog requests

Usage:
  python main.py
"""

import os
import sys
import json
import time
import logging
import argparse
import threading
from pathlib import Path
from datetime import datetime

try:
    from pypresence import Presence, PyPresenceException
except ImportError:
    print("ERROR: pypresence not installed. Run: pip install pypresence")
    sys.exit(1)

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("ERROR: watchdog not installed. Run: pip install watchdog")
    sys.exit(1)

# ─────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────

# Your Discord Application Client ID (from discord.com/developers)
# The default below is for the public MCSR RPC app.
# Create your own at https://discord.com/developers/applications
DISCORD_CLIENT_ID = "1234567890123456789"  # <-- REPLACE WITH YOUR OWN CLIENT ID

# Where SpeedRunIGT writes live run data
# Adjust if you use a custom .minecraft directory
DEFAULT_MC_DIR = Path.home() / "AppData" / "Roaming" / ".minecraft"
SPEEDRUNIGT_FOLDER = "speedrunigt"
LATEST_WORLD_FILE = "latest_world"

# How often (seconds) to poll the file if watchdog misses a change
POLL_INTERVAL = 2

# ─────────────────────────────────────────────
#  SPLIT DEFINITIONS
#  Maps internal split names → (display label, image key, image text)
#  Image keys must be uploaded to your Discord application's Art Assets
# ─────────────────────────────────────────────

SPLIT_INFO = {
    "none": {
        "state": "Starting a new run",
        "details": "Grinding the overworld...",
        "large_image": "overworld",
        "large_text": "Overworld",
        "small_image": "grass_block",
        "small_text": "Just started",
    },
    "nether": {
        "state": "Entered the Nether",
        "details": "Trading piglins / looting bastion...",
        "large_image": "nether",
        "large_text": "The Nether",
        "small_image": "nether_portal",
        "small_text": "Nether entered",
    },
    "bastion": {
        "state": "In Bastion Remnant",
        "details": "Looting gold & ender pearls...",
        "large_image": "nether",
        "large_text": "The Nether",
        "small_image": "bastion",
        "small_text": "Bastion found",
    },
    "fortress": {
        "state": "In Nether Fortress",
        "details": "Collecting blaze rods...",
        "large_image": "nether",
        "large_text": "The Nether",
        "small_image": "fortress",
        "small_text": "Fortress found",
    },
    "first_portal": {
        "state": "Built First Portal",
        "details": "Returning to the overworld...",
        "large_image": "nether",
        "large_text": "The Nether",
        "small_image": "obsidian",
        "small_text": "Portal constructed",
    },
    "stronghold": {
        "state": "Locating Stronghold",
        "details": "Throwing eyes of ender...",
        "large_image": "stronghold",
        "large_text": "Searching for Stronghold",
        "small_image": "ender_eye",
        "small_text": "Stronghold phase",
    },
    "end": {
        "state": "Entered the End",
        "details": "Fighting the Ender Dragon!",
        "large_image": "end",
        "large_text": "The End",
        "small_image": "end_portal",
        "small_text": "End portal entered",
    },
    "finish": {
        "state": "Run Complete! 🎉",
        "details": "Dragon has been slain!",
        "large_image": "credits",
        "large_text": "Finished!",
        "small_image": "dragon_egg",
        "small_text": "Run finished",
    },
}

# Split priority order (later = further in run)
SPLIT_ORDER = ["none", "nether", "bastion", "fortress", "first_portal", "stronghold", "end", "finish"]


# ─────────────────────────────────────────────
#  LOGGING
# ─────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("mcsr_rpc.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("MCSR-RPC")


# ─────────────────────────────────────────────
#  HELPERS
# ─────────────────────────────────────────────

def ms_to_igt(ms: int) -> str:
    """Convert IGT milliseconds to mm:ss.xxx string."""
    if ms is None or ms <= 0:
        return "0:00.000"
    total_s = ms // 1000
    millis = ms % 1000
    minutes = total_s // 60
    seconds = total_s % 60
    return f"{minutes}:{seconds:02d}.{millis:03d}"


def get_current_split(data: dict) -> str:
    """
    Determine the furthest completed split from the record JSON.
    Returns a key from SPLIT_ORDER.
    """
    if not data:
        return "none"

    # Check from latest split backwards
    for split in reversed(SPLIT_ORDER[1:]):  # skip "none"
        if data.get(split) is not None:
            return split

    return "none"


def find_minecraft_dir() -> Path:
    """Attempt to auto-locate .minecraft across platforms."""
    home = Path.home()
    candidates = [
        # Windows
        home / "AppData" / "Roaming" / ".minecraft",
        # macOS
        home / "Library" / "Application Support" / "minecraft",
        # Linux
        home / ".minecraft",
        # MultiMC / Prism common locations
        home / "MultiMC" / "instances",
        home / ".local" / "share" / "PrismLauncher" / "instances",
    ]
    for path in candidates:
        if path.exists():
            return path
    return DEFAULT_MC_DIR


def find_speedrunigt_path(mc_dir: Path) -> Path | None:
    """
    Look for SpeedRunIGT's latest_world file.
    Supports both standard .minecraft and MultiMC-style instance directories.
    """
    # Standard path
    standard = mc_dir / SPEEDRUNIGT_FOLDER / LATEST_WORLD_FILE
    if standard.exists():
        return standard

    # MultiMC / Prism: scan instance directories
    for instance_dir in mc_dir.iterdir():
        if instance_dir.is_dir():
            candidate = instance_dir / ".minecraft" / SPEEDRUNIGT_FOLDER / LATEST_WORLD_FILE
            if candidate.exists():
                return candidate

    return None


# ─────────────────────────────────────────────
#  DISCORD RPC MANAGER
# ─────────────────────────────────────────────

class DiscordRPCManager:
    def __init__(self, client_id: str):
        self.client_id = client_id
        self.rpc: Presence | None = None
        self.connected = False
        self._lock = threading.Lock()
        self._last_presence = {}

    def connect(self) -> bool:
        """Try to connect to Discord. Returns True on success."""
        try:
            self.rpc = Presence(self.client_id)
            self.rpc.connect()
            self.connected = True
            log.info("✅ Connected to Discord RPC")
            return True
        except Exception as e:
            log.warning(f"⚠️  Discord not running or connection failed: {e}")
            self.connected = False
            return False

    def disconnect(self):
        if self.rpc and self.connected:
            try:
                self.rpc.close()
            except Exception:
                pass
        self.connected = False

    def update(self, split: str, run_data: dict):
        """Update Discord Rich Presence based on current split."""
        if not self.connected:
            if not self.connect():
                return  # Discord not open, skip silently

        info = SPLIT_INFO.get(split, SPLIT_INFO["none"])
        igt_ms = run_data.get(split) if split != "none" and split != "finish" else None
        elapsed_ms = run_data.get("finish") or run_data.get("end") or run_data.get("stronghold") or run_data.get("first_portal") or run_data.get("fortress") or run_data.get("bastion") or run_data.get("nether")

        # Build details line with IGT time if available
        details = info["details"]
        if split in run_data and run_data[split]:
            details = f"{info['details']} | IGT: {ms_to_igt(run_data[split])}"

        # Build state with split count context
        splits_done = sum(1 for s in SPLIT_ORDER[1:] if run_data.get(s) is not None)
        state = f"{info['state']} ({splits_done}/7 splits)"
        if split == "finish":
            state = f"🏁 FINISHED! IGT: {ms_to_igt(run_data.get('finish'))}"

        # Avoid spamming identical updates
        new_presence = {
            "state": state,
            "details": details,
            "large_image": info["large_image"],
            "small_image": info["small_image"],
        }
        with self._lock:
            if new_presence == self._last_presence:
                return
            self._last_presence = new_presence

        try:
            self.rpc.update(
                state=state,
                details=details,
                large_image=info["large_image"],
                large_text=info["large_text"],
                small_image=info["small_image"],
                small_text=info["small_text"],
                start=int(time.time()) if split == "none" else None,
            )
            log.info(f"🎮 RPC updated → {split.upper()}: {state}")
        except PyPresenceException as e:
            log.error(f"RPC update failed: {e}")
            self.connected = False
        except Exception as e:
            log.error(f"Unexpected RPC error: {e}")
            self.connected = False

    def clear(self):
        """Clear the RPC (called when Minecraft closes)."""
        if self.connected and self.rpc:
            try:
                self.rpc.clear()
                log.info("🔴 RPC cleared (Minecraft closed or run reset)")
            except Exception:
                pass
        self._last_presence = {}


# ─────────────────────────────────────────────
#  FILE WATCHER
# ─────────────────────────────────────────────

class SpeedRunIGTHandler(FileSystemEventHandler):
    """Watchdog handler that triggers on changes to latest_world."""

    def __init__(self, tracker: "MCRSTracker"):
        super().__init__()
        self.tracker = tracker

    def on_modified(self, event):
        if not event.is_directory:
            path = Path(event.src_path)
            if path.name == LATEST_WORLD_FILE:
                self.tracker.on_file_changed()

    def on_created(self, event):
        self.on_modified(event)


# ─────────────────────────────────────────────
#  MAIN TRACKER
# ─────────────────────────────────────────────

class MCRSTracker:
    def __init__(self, mc_dir: Path, client_id: str):
        self.mc_dir = mc_dir
        self.rpc = DiscordRPCManager(client_id)
        self.speedrunigt_path: Path | None = None
        self._last_data: dict = {}
        self._observer: Observer | None = None
        self._running = False

    def _read_latest_world(self) -> dict:
        """Read and parse the latest_world JSON file."""
        if not self.speedrunigt_path or not self.speedrunigt_path.exists():
            return {}
        try:
            text = self.speedrunigt_path.read_text(encoding="utf-8")
            if not text.strip():
                return {}
            return json.loads(text)
        except json.JSONDecodeError as e:
            log.debug(f"JSON parse error (file mid-write?): {e}")
            return {}
        except Exception as e:
            log.warning(f"Could not read latest_world: {e}")
            return {}

    def on_file_changed(self):
        """Called when the latest_world file changes."""
        data = self._read_latest_world()
        if data == self._last_data:
            return  # nothing actually changed
        self._last_data = data

        split = get_current_split(data)
        log.info(f"📂 File changed → detected split: {split}")
        self.rpc.update(split, data)

    def _setup_watcher(self):
        """Set up watchdog file watcher."""
        watch_dir = self.speedrunigt_path.parent
        event_handler = SpeedRunIGTHandler(self)
        self._observer = Observer()
        self._observer.schedule(event_handler, str(watch_dir), recursive=False)
        self._observer.start()
        log.info(f"👀 Watching: {watch_dir}")

    def _poll_loop(self):
        """Fallback polling loop in case watchdog misses events."""
        while self._running:
            # Also re-scan for the file in case it's created mid-session
            if self.speedrunigt_path is None or not self.speedrunigt_path.exists():
                found = find_speedrunigt_path(self.mc_dir)
                if found:
                    self.speedrunigt_path = found
                    log.info(f"✅ Found SpeedRunIGT file: {found}")
                    self._setup_watcher()

            self.on_file_changed()
            time.sleep(POLL_INTERVAL)

    def start(self):
        log.info("=" * 50)
        log.info("  MCSR Discord Rich Presence Tracker")
        log.info("=" * 50)
        log.info(f"📁 Minecraft directory: {self.mc_dir}")

        # Initial file search
        self.speedrunigt_path = find_speedrunigt_path(self.mc_dir)
        if self.speedrunigt_path:
            log.info(f"✅ Found SpeedRunIGT: {self.speedrunigt_path}")
        else:
            log.warning("⚠️  SpeedRunIGT latest_world not found yet.")
            log.warning("   Make sure SpeedRunIGT mod is installed and you start a world.")
            log.warning(f"   Expected path: {self.mc_dir / SPEEDRUNIGT_FOLDER / LATEST_WORLD_FILE}")

        # Connect to Discord
        self.rpc.connect()

        # Start poll loop (also handles watcher setup when file appears)
        self._running = True
        if self.speedrunigt_path:
            self._setup_watcher()

        log.info("🚀 Tracker running! Open Minecraft with SpeedRunIGT to begin.")
        log.info("   Press Ctrl+C to stop.\n")

        try:
            self._poll_loop()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        log.info("\n⏹️  Stopping tracker...")
        self._running = False
        if self._observer:
            self._observer.stop()
            self._observer.join()
        self.rpc.clear()
        self.rpc.disconnect()
        log.info("👋 Tracker stopped.")


# ─────────────────────────────────────────────
#  CLI ENTRY POINT
# ─────────────────────────────────────────────

def parse_args():
    parser = argparse.ArgumentParser(
        description="MCSR Discord Rich Presence Tracker",
        formatter_class=argparse.RawTextHelpFormatter,
    )
    parser.add_argument(
        "--mc-dir",
        type=Path,
        default=None,
        help="Path to your .minecraft directory\n(auto-detected if not specified)",
    )
    parser.add_argument(
        "--client-id",
        type=str,
        default=DISCORD_CLIENT_ID,
        help="Your Discord Application Client ID\n(see README for setup instructions)",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable verbose debug logging",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    mc_dir = args.mc_dir or find_minecraft_dir()
    client_id = args.client_id

    if client_id == "1234567890123456789":
        log.warning("⚠️  You're using the placeholder Client ID!")
        log.warning("   Create your own Discord app at https://discord.com/developers/applications")
        log.warning("   Then set --client-id YOUR_ID or edit DISCORD_CLIENT_ID in main.py\n")

    tracker = MCRSTracker(mc_dir, client_id)
    tracker.start()


if __name__ == "__main__":
    main()
