"""
test_splits.py — Confirmed Log Line Simulator
==============================================
Writes the EXACT log lines that Minecraft 1.16.1 produces during a
speedrun. Confirmed from real gameplay capture.

HOW TO USE:
  Terminal 1:  python main.py --mc-dir "C:/tmp/test_mc"
  Terminal 2:  python test_splits.py
"""

import time
import argparse
import tempfile
from pathlib import Path
from datetime import datetime

def ts():
    return datetime.now().strftime("[%H:%M:%S]")

def write_log(f, line):
    full = f"{ts()} [Server thread/INFO]: {line}\n"
    f.write(full)
    f.flush()
    print(f"  wrote: {line[:70]}")

# Exact log lines from confirmed Minecraft 1.16.1 + SpeedRunIGT output
SEQUENCE = [
    # New world join
    (3,  "Loading level 'Random Speedrun #99999'"),
    (0,  "Maxxter_MC[local:E:abc123] logged in with entity id 1 at (0.0, 64.0, 0.0)"),
    (0,  "Loaded 0 advancements"),              # <-- triggers NEW RUN

    # Get to nether (~1:30 in)
    (5,  "Maxxter_MC has made the advancement [We Need to Go Deeper]"),   # nether

    # Find bastion (~2:30)
    (4,  "Maxxter_MC has made the advancement [Those Were the Days]"),     # bastion

    # Find fortress (~3:30)
    (4,  "Maxxter_MC has made the advancement [A Terrible Fortress]"),     # fortress

    # Locate stronghold (~6:00) — Eye Spy is thrown ender eye
    (6,  "Maxxter_MC has made the advancement [Eye Spy]"),                 # stronghold

    # Enter end (~7:30)
    (4,  "Maxxter_MC has made the advancement [The End?]"),                # end

    # Kill dragon (~9:00)
    (5,  "Maxxter_MC has made the advancement [Free the End]"),            # credits

    # Reset / new run
    (4,  "Stopping singleplayer server as player logged out"),
    (1,  "StateOutput State: wall"),
    (2,  "Loaded 0 advancements"),              # <-- new run
]

def run(mc_dir: Path, speed: float):
    log_dir  = mc_dir / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "latest.log"

    print(f"\n  MCSR Simulator  (speed={speed}x)")
    print(f"  Log: {log_file}\n")

    with open(log_file, "a", encoding="utf-8") as f:
        for delay, line in SEQUENCE:
            time.sleep(delay / speed)
            write_log(f, line)

    print("\n  Done!\n")

def main():
    p = argparse.ArgumentParser()
    p.add_argument("--speed",  type=float, default=1.0)
    p.add_argument("--mc-dir", type=Path,  default=None)
    args = p.parse_args()

    mc_dir = args.mc_dir or (Path(tempfile.gettempdir()) / "mcsr_rpc_test_mc")

    print("\n" + "=" * 55)
    print("  Start the tracker in a separate terminal first:")
    print(f'  python main.py --mc-dir "{mc_dir}"')
    print("=" * 55)

    run(mc_dir, args.speed)

if __name__ == "__main__":
    main()
