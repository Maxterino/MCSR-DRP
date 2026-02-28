"""
MCSR Discord Rich Presence Tracker
====================================
Real-time split detection by tailing logs/latest.log.

Confirmed log lines from actual gameplay (1.16.1 + SpeedRunIGT):

  NEW RUN  : "Loaded 0 advancements"             <- world switch/reset
  NETHER   : advancement [We Need to Go Deeper]
  BASTION  : advancement [Those Were the Days]
  FORTRESS : advancement [A Terrible Fortress]
  STRONGHOLD: advancement [Eye Spy]              <- throwing ender eye
  END      : advancement [The End?]
  CREDITS  : advancement [Free the End]          <- dragon killed

These all fire INSTANTLY in the log — no saving required.
"""

import re
import sys
import json
import time
import logging
import argparse
import threading
import configparser
from pathlib import Path

try:
    from pypresence import Presence, PyPresenceException
except ImportError:
    print("ERROR: pypresence not installed. Run:  pip install pypresence")
    sys.exit(1)


# ---------------------------------------------------------------------------
# SPLIT CONFIG
# ---------------------------------------------------------------------------

SPLIT_ORDER = [
    "none",
    "enter_nether",
    "enter_bastion",
    "enter_fortress",
    "looking_for_stronghold",   # back in overworld after fortress, scanning with Ninjabrain
    "enter_stronghold",
    "enter_end",
    "credits",
]

SPLIT_INFO = {
    "none": {
        "state":       "Starting a new run",
        "details":     "In the overworld",
        "large_image": "overworld",
        "large_text":  "The Overworld",
        "small_image": "grass_block",
        "small_text":  "New run",
    },
    "enter_nether": {
        "state":       "Entered the Nether",
        "details":     "In the Nether",
        "large_image": "nether",
        "large_text":  "The Nether",
        "small_image": "nether_portal",
        "small_text":  "Nether entered",
    },
    "enter_bastion": {
        "state":       "Routing the Bastion",
        "details":     "In the Nether",
        "large_image": "nether",
        "large_text":  "The Nether",
        "small_image": "bastion",
        "small_text":  "Bastion",
    },
    "enter_fortress": {
        "state":       "Entered Fortress",
        "details":     "In the Nether",
        "large_image": "nether",
        "large_text":  "The Nether",
        "small_image": "fortress",
        "small_text":  "Fortress",
    },
    "looking_for_stronghold": {
        "state":       "Looking for Stronghold",
        "details":     "Back in the overworld",
        "large_image": "overworld",
        "large_text":  "The Overworld",
        "small_image": "ender_eye",
        "small_text":  "Scanning with Ninjabrain",
    },
    "enter_stronghold": {
        "state":       "Entered Stronghold",
        "details":     "In the stronghold",
        "large_image": "stronghold",
        "large_text":  "Stronghold",
        "small_image": "ender_eye",
        "small_text":  "Stronghold",
    },
    "enter_end": {
        "state":       "Entered the End",
        "details":     "In the End",
        "large_image": "end",
        "large_text":  "The End",
        "small_image": "end_portal",
        "small_text":  "End",
    },
    "credits": {
        "state":       "Finished Speedrun!",
        "details":     "Dragon slain",
        "large_image": "credits",
        "large_text":  "Finished!",
        "small_image": "dragon_egg",
        "small_text":  "GG!",
    },
}

# SpeedRunIGT record.json aliases (used for IGT time lookup only)
TIMELINE_ALIASES = {
    "enter_nether":    "enter_nether",    "nether":                "enter_nether",
    "enter_bastion":   "enter_bastion",   "bastion":               "enter_bastion",
    "enter_fortress":  "enter_fortress",  "fortress":              "enter_fortress",
    "nether_fortress": "enter_fortress",
    # first_portal in record.json = player returned to overworld = looking for stronghold
    "first_portal":    "looking_for_stronghold", "blind": "looking_for_stronghold",
    "enter_stronghold":"enter_stronghold","stronghold":            "enter_stronghold",
    "eye_spy":         "enter_stronghold",
    "enter_end":       "enter_end",       "end":                   "enter_end",
    "credits":         "credits",         "finish":                "credits",
    "complete":        "credits",         "dragon_killed":         "credits",
}


# ---------------------------------------------------------------------------
# LOG PATTERNS — confirmed from actual gameplay output above
#
# Format: (compiled_regex, split_name_or_None_for_reset)
# Matched against each new line in logs/latest.log
# ---------------------------------------------------------------------------

# These advancement names are the EXACT strings Minecraft 1.16.1 prints
ADVANCEMENT_SPLITS = [
    # Nether entry — "We Need to Go Deeper"
    (re.compile(r"has made the advancement \[We Need to Go Deeper\]"), "enter_nether"),
    # Bastion — "Those Were the Days"
    (re.compile(r"has made the advancement \[Those Were the Days\]"),   "enter_bastion"),
    # Fortress — "A Terrible Fortress"
    (re.compile(r"has made the advancement \[A Terrible Fortress\]"),   "enter_fortress"),
    # Eye Spy — thrown ender eye / stronghold found
    (re.compile(r"has made the advancement \[Eye Spy\]"),               "enter_stronghold"),
    # The End? — entered end portal
    (re.compile(r"has made the advancement \[The End\?\]"),             "enter_end"),
    # Free the End — dragon killed
    (re.compile(r"has made the advancement \[Free the End\]"),          "credits"),
]

# "Looking for stronghold" — player returned to overworld after nether.
# Triggered by StateOutput State: inworld when current split is fortress-level.
# This is a soft state change (doesn't advance split rank, just updates display).
OVERWORLD_RETURN_PATTERN = re.compile(r"StateOutput State: inworld,unpaused")

# New run / reset signals — confirmed from log output
# "Loaded 0 advancements" fires every time you join a fresh world
NEW_RUN_PATTERNS = [
    re.compile(r"Loaded 0 advancements"),
]

# World switch detection — fires when leaving a world
LEAVING_PATTERNS = [
    re.compile(r"Stopping singleplayer server"),
    re.compile(r"StateOutput State: wall"),
]


# ---------------------------------------------------------------------------
# LOGGING
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("mcsr_rpc.log", encoding="utf-8"),
    ],
)
log = logging.getLogger("MCSR-RPC")


# ---------------------------------------------------------------------------
# MULTIMC AUTO-DETECT
# ---------------------------------------------------------------------------

def find_multimc_instances() -> list:
    """Search common MultiMC / Prism install locations for .minecraft dirs."""
    home  = Path.home()
    roots = [
        home / "Desktop",
        home / "Desktop" / "MCSR",
        home / "Downloads",
        home / "AppData" / "Roaming" / "PrismLauncher" / "instances",
        home / "AppData" / "Local"   / "PrismLauncher" / "instances",
        home / "AppData" / "Roaming" / "MultiMC"       / "instances",
        home / "MultiMC" / "instances",
    ]
    for drive in ["C:", "D:", "E:"]:
        for sub in ["MultiMC", "MCSR", "Speedrun", "speedrun", "Prism"]:
            roots.append(Path(f"{drive}/{sub}"))

    found = []
    seen  = set()
    for root in roots:
        if not root.exists():
            continue
        try:
            for mc in root.rglob(".minecraft"):
                if mc.is_dir() and (mc / "logs").exists():
                    key = str(mc).lower()
                    if key not in seen:
                        seen.add(key)
                        found.append(mc)
        except PermissionError:
            pass
    return found


def auto_detect_mc_dir() -> Path | None:
    instances = find_multimc_instances()
    if instances:
        return max(instances, key=lambda p: p.stat().st_mtime)
    standard = Path.home() / "AppData" / "Roaming" / ".minecraft"
    return standard if standard.exists() else None


# ---------------------------------------------------------------------------
# SETUP WIZARD
# ---------------------------------------------------------------------------

def run_setup_wizard() -> dict:
    print("\n" + "=" * 60)
    print("  MCSR Discord RPC — First-Time Setup")
    print("=" * 60)
    print("\nScanning for MultiMC/Prism instances...\n")

    instances = find_multimc_instances()

    if instances:
        print(f"Found {len(instances)} Minecraft instance(s):\n")
        for i, p in enumerate(instances):
            print(f"  [{i+1}] {p}")
        print()
        if len(instances) == 1:
            choice  = 0
            print("Auto-selected the only instance found.")
        else:
            while True:
                try:
                    choice = int(input(f"Enter number [1-{len(instances)}]: ")) - 1
                    if 0 <= choice < len(instances):
                        break
                except ValueError:
                    pass
        mc_dir = instances[choice]
    else:
        print("No instances found automatically.")
        print("Paste the full path to your .minecraft folder:")
        mc_dir = Path(input("> ").strip().strip('"'))

    print(f"\nSelected: {mc_dir}")
    print()
    print("Enter your Discord Application Client ID.")
    print("Get one free at: https://discord.com/developers/applications")
    print("  -> New Application -> copy the number shown as Application ID")
    client_id = input("Client ID: ").strip()

    cfg = {
        "client_id":     client_id,
        "mc_dir":        mc_dir,
        "records_dir":   Path.home() / "speedrunigt" / "records",
        "poll_interval": 1.0,
        "debug":         False,
    }

    ini = Path(__file__).parent / "config.ini"
    ini.write_text(f"""# MCSR Discord Rich Presence — Configuration
[discord]
client_id = {client_id}

[minecraft]
mc_dir = {mc_dir}
records_dir = {cfg['records_dir']}

[tracker]
poll_interval = 1
debug = false
""", encoding="utf-8")
    print(f"\nSaved config to {ini}")
    print("Setup complete! Starting tracker...\n")
    return cfg


# ---------------------------------------------------------------------------
# CONFIG LOADER
# ---------------------------------------------------------------------------

def load_config() -> dict | None:
    ini = Path(__file__).parent / "config.ini"
    if not ini.exists():
        return None
    p = configparser.ConfigParser()
    p.read(ini, encoding="utf-8")
    client_id = p.get("discord", "client_id", fallback="").strip()
    mc_raw    = p.get("minecraft", "mc_dir",   fallback="").strip()
    rec_raw   = p.get("minecraft", "records_dir", fallback="").strip()
    if not client_id or not mc_raw or client_id == "1234567890123456789":
        return None
    return {
        "client_id":     client_id,
        "mc_dir":        Path(mc_raw),
        "records_dir":   Path(rec_raw) if rec_raw else Path.home() / "speedrunigt" / "records",
        "poll_interval": float(p.get("tracker", "poll_interval", fallback="1")),
        "debug":         p.getboolean("tracker", "debug", fallback=False),
    }


# ---------------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------------

def ms_to_igt(ms) -> str:
    """M:SS — no milliseconds."""
    if not ms or ms <= 0:
        return "0:00"
    s = int(ms) // 1000
    return f"{s // 60}:{s % 60:02d}"


def split_rank(name: str) -> int:
    try:
        return SPLIT_ORDER.index(name)
    except ValueError:
        return -1


def parse_record_json(path: Path) -> dict:
    """Read SpeedRunIGT record.json -> {split: igt_ms}"""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    result = {}
    for entry in data.get("timelines", []):
        raw   = str(entry.get("name", "")).lower().strip()
        igt   = int(entry.get("igt", 0) or 0)
        canon = TIMELINE_ALIASES.get(raw)
        if canon:
            result[canon] = igt
    return result


# ---------------------------------------------------------------------------
# DISCORD RPC
# ---------------------------------------------------------------------------

class DiscordRPCManager:
    def __init__(self, client_id: str):
        self.client_id  = client_id
        self.rpc        = None
        self.connected  = False
        self._lock      = threading.Lock()
        self._last_fp   = {}
        self._run_start = None

    def connect(self) -> bool:
        try:
            self.rpc = Presence(self.client_id)
            self.rpc.connect()
            self.connected = True
            log.info("Connected to Discord RPC.")
            return True
        except Exception as e:
            log.warning(f"Discord RPC connect failed: {e}")
            log.warning("  -> Make sure Discord desktop app is open.")
            self.connected = False
            return False

    def disconnect(self):
        if self.rpc and self.connected:
            try:
                self.rpc.close()
            except Exception:
                pass
        self.connected = False

    def update(self, split: str, igt_ms: int, new_run: bool):
        if not self.connected:
            if not self.connect():
                return

        if new_run or self._run_start is None:
            self._run_start = int(time.time())

        info = SPLIT_INFO.get(split, SPLIT_INFO["none"])

        # In Discord Rich Presence:
        #   details = TOP line    → IGT time  e.g. "2:25"
        #   state   = BOTTOM line → activity  e.g. "Routing the Bastion"
        activity = info["state"]
        if igt_ms and igt_ms > 0:
            igt_text = ms_to_igt(igt_ms)
        else:
            igt_text = info["details"]   # fallback text before IGT is known

        details = igt_text    # top
        state   = activity    # bottom

        fp = {"s": state, "d": details, "l": info["large_image"]}
        with self._lock:
            if fp == self._last_fp:
                return
            self._last_fp = fp

        try:
            self.rpc.update(
                details     = details,
                state       = state,
                large_image = info["large_image"],
                large_text  = info["large_text"],
                small_image = info["small_image"],
                small_text  = info["small_text"],
                start       = self._run_start,
            )
            log.info(f"Discord -> [{split.upper()}]  top='{details}'  bottom='{state}'")
        except PyPresenceException as e:
            log.error(f"RPC error: {e}")
            self.connected = False
        except Exception as e:
            log.error(f"RPC unexpected error: {e}")
            self.connected = False

    def clear(self):
        try:
            if self.connected and self.rpc:
                self.rpc.clear()
        except Exception:
            pass
        self._last_fp = {}


# ---------------------------------------------------------------------------
# LOG TAILER — tails latest.log in real time, 4x per second
# ---------------------------------------------------------------------------

class LogTailer:
    def __init__(self, log_path: Path, on_line):
        self.log_path = log_path
        self.on_line  = on_line
        self._pos     = 0
        self._running = False
        self._thread  = None

    def start(self):
        # Jump to the END of the current log — don't reprocess old lines
        self._pos = self.log_path.stat().st_size if self.log_path.exists() else 0
        self._running = True
        self._thread  = threading.Thread(target=self._loop, daemon=True, name="log-tailer")
        self._thread.start()
        log.info(f"Tailing: {self.log_path}")

    def stop(self):
        self._running = False

    def _loop(self):
        while self._running:
            self._read_new()
            time.sleep(0.1)   # 10 checks per second — very responsive

    def _read_new(self):
        if not self.log_path.exists():
            return
        try:
            size = self.log_path.stat().st_size
            if size < self._pos:          # file rotated (new game session)
                self._pos = 0
            if size == self._pos:
                return
            with open(self.log_path, "r", encoding="utf-8", errors="replace") as f:
                f.seek(self._pos)
                chunk = f.read()
                self._pos = f.tell()
            for line in chunk.splitlines():
                if line.strip():
                    self.on_line(line)
        except OSError:
            pass


# ---------------------------------------------------------------------------
# MAIN TRACKER
# ---------------------------------------------------------------------------

class MCSRTracker:
    def __init__(self, mc_dir: Path, records_dir: Path, client_id: str,
                 poll_interval: float = 1.0):
        self.mc_dir      = mc_dir
        self.records_dir = records_dir
        self.rpc         = DiscordRPCManager(client_id)
        self._poll_interval = poll_interval
        self._running    = False
        self._tailer: LogTailer | None = None

        # Run state
        self._lock       = threading.Lock()
        self._split      = "none"   # actual furthest split reached (rank)
        self._display_split = "none"  # what to show on Discord (may differ for overworld return)
        self._igt_ms     = 0
        self._is_new_run = True

        # Cooldown: ignore duplicate advancement lines within 2 seconds
        self._last_split_time: dict = {}

    # ---- log line processing -----------------------------------------------

    def _on_line(self, line: str):
        # Check new-run signals first
        for pat in NEW_RUN_PATTERNS:
            if pat.search(line):
                log.debug(f"New run signal: {line[:80]}")
                self._reset_run()
                return

        # Check split patterns
        for pat, split_name in ADVANCEMENT_SPLITS:
            if pat.search(line):
                # Cooldown: skip if we already fired this split in the last 2s
                now = time.time()
                last = self._last_split_time.get(split_name, 0)
                if now - last < 2.0:
                    log.debug(f"Skipping duplicate {split_name} (cooldown)")
                    return
                self._last_split_time[split_name] = now

                log.debug(f"Split from log: {split_name}  |  {line[:80]}")
                self._advance_split(split_name, 0)
                return

        # Check for overworld return — "Looking for stronghold" state
        # Only fires if the player has already done fortress (rank >= 3)
        # and hasn't yet found the stronghold
        if OVERWORLD_RETURN_PATTERN.search(line):
            with self._lock:
                current_rank = split_rank(self._split)
                fortress_rank = split_rank("enter_fortress")
                stronghold_rank = split_rank("enter_stronghold")
            if fortress_rank <= current_rank < stronghold_rank:
                log.debug("Overworld return detected — switching to looking_for_stronghold")
                self._set_display_state("looking_for_stronghold")

    def _reset_run(self):
        with self._lock:
            if self._split == "none" and self._is_new_run:
                return  # already reset
            log.info("NEW RUN detected")
            self._split      = "none"
            self._igt_ms     = 0
            self._is_new_run = True
            self._display_split = "none"
            self._last_split_time.clear()
        self._push()

    def _advance_split(self, split_name: str, igt_ms: int):
        with self._lock:
            if split_rank(split_name) <= split_rank(self._split):
                return  # never go backwards
            log.info(f"Split: {split_name.upper()}")
            self._split         = split_name
            self._display_split = split_name
            self._igt_ms        = igt_ms
            self._is_new_run    = False
        self._push()

    def _set_display_state(self, display_name: str):
        """Change what's shown on Discord without advancing the actual split rank."""
        with self._lock:
            if self._display_split == display_name:
                return
            log.info(f"Display state -> {display_name.upper()}")
            self._display_split = display_name
        self._push()

    # ---- IGT enrichment via record.json polling ----------------------------

    def _poll_record(self):
        """
        Called every 2 seconds. Enriches state with IGT times from record.json,
        and catches first_portal (= looking_for_stronghold) which has no log line.
        """
        saves = self.mc_dir / "saves"
        if not saves.is_dir():
            return

        records = list(saves.rglob("speedrunigt/record.json"))
        if not records:
            return
        newest = max(records, key=lambda p: p.stat().st_mtime if p.exists() else 0)
        if not newest.exists():
            return

        splits = parse_record_json(newest)
        if not splits:
            return

        updated = False
        with self._lock:
            current_rank = split_rank(self._split)

            for split_name, igt_ms in splits.items():
                rank = split_rank(split_name)

                if rank > current_rank:
                    log.info(f"Split from record.json: {split_name.upper()}  IGT={ms_to_igt(igt_ms)}")
                    self._split         = split_name
                    self._display_split = split_name
                    self._igt_ms        = igt_ms
                    self._is_new_run    = False
                    current_rank        = rank
                    updated             = True
                elif split_name == self._split and igt_ms > 0 and self._igt_ms == 0:
                    log.info(f"IGT filled in: {split_name.upper()} -> {ms_to_igt(igt_ms)}")
                    self._igt_ms = igt_ms
                    updated      = True

        if updated:
            self._push()

    # ---- Discord push ------------------------------------------------------

    def _push(self):
        with self._lock:
            split      = self._display_split
            igt_ms     = self._igt_ms
            is_new_run = self._is_new_run

        self.rpc.update(
            split    = split,
            igt_ms   = igt_ms,
            new_run  = is_new_run,
        )

    # ---- poll loop ---------------------------------------------------------

    def _poll_loop(self):
        counter = 0
        while self._running:
            time.sleep(self._poll_interval)
            counter += 1
            if counter % 2 == 0:
                self._poll_record()

    # ---- startup -----------------------------------------------------------

    def start(self):
        log.info("=" * 60)
        log.info("  MCSR Discord Rich Presence Tracker")
        log.info("  Real-time via log tailing")
        log.info("=" * 60)
        log.info(f".minecraft : {self.mc_dir}")

        if not self.mc_dir.exists():
            log.error(f"ERROR: .minecraft not found: {self.mc_dir}")
            sys.exit(1)

        log_path = self.mc_dir / "logs" / "latest.log"
        if not log_path.exists():
            log.warning(f"Log not found yet: {log_path}")
            log.warning("  -> Open Minecraft first, then restart the tracker.")
            # Wait for the file to appear
            log.info("Waiting for Minecraft to open...")
            while not log_path.exists():
                time.sleep(1)
            log.info("Log file found! Continuing...")

        self.rpc.connect()
        self._push()  # show "Starting a new run" immediately

        self._tailer  = LogTailer(log_path, self._on_line)
        self._tailer.start()

        log.info("\nTracker is running!")
        log.info("Splits will update INSTANTLY when advancements fire.")
        log.info("Press Ctrl+C to stop.\n")

        self._running = True
        try:
            self._poll_loop()
        except KeyboardInterrupt:
            self.stop()

    def stop(self):
        log.info("Stopping...")
        self._running = False
        if self._tailer:
            self._tailer.stop()
        self.rpc.clear()
        self.rpc.disconnect()
        log.info("Stopped. GG!")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description="MCSR Discord Rich Presence Tracker")
    p.add_argument("--setup",     action="store_true", help="Run setup wizard")
    p.add_argument("--mc-dir",    type=Path)
    p.add_argument("--client-id", type=str)
    p.add_argument("--debug",     action="store_true")
    p.add_argument("--scan",      action="store_true", help="Find instances and exit")
    return p.parse_args()


def main():
    args = parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if args.scan:
        print("\nScanning for MultiMC instances...\n")
        for i, p in enumerate(find_multimc_instances()):
            log_ok = "✓" if (p / "logs" / "latest.log").exists() else "✗ no log yet"
            print(f"  [{i+1}] {p}  [{log_ok}]")
        return

    cfg = load_config()
    if args.setup or cfg is None:
        cfg = run_setup_wizard()

    client_id = args.client_id or cfg["client_id"]
    mc_dir    = args.mc_dir    or cfg["mc_dir"]

    if args.debug:
        log.info("Debug mode ON")

    log.info(f"Discord Client ID : {client_id}")
    log.info(f".minecraft        : {mc_dir}")

    MCSRTracker(
        mc_dir        = mc_dir,
        records_dir   = cfg.get("records_dir", Path.home() / "speedrunigt" / "records"),
        client_id     = client_id,
        poll_interval = cfg.get("poll_interval", 1.0),
    ).start()


if __name__ == "__main__":
    main()
