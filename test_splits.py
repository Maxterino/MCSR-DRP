"""
test_splits.py
==============
Simulates a full Minecraft speedrun by writing fake SpeedRunIGT data
to a temp directory. Run this alongside main.py to test your Discord
Rich Presence without having Minecraft open.

Usage:
  python test_splits.py
  python test_splits.py --speed 2   # 2x faster transitions
  python test_splits.py --dir path/to/.minecraft/speedrunigt
"""

import os
import json
import time
import argparse
import tempfile
import threading
from pathlib import Path

SPLITS_SEQUENCE = [
    # (split_name, delay_seconds, igt_ms)
    ("new_run",       3,   0),
    ("nether",        5,   145000),   # ~2:25
    ("bastion",       4,   195000),   # ~3:15
    ("fortress",      4,   240000),   # ~4:00
    ("first_portal",  5,   285000),   # ~4:45
    ("stronghold",    5,   350000),   # ~5:50
    ("end",           4,   420000),   # ~7:00
    ("finish",        5,   490000),   # ~8:10
]


def build_data(sequence_up_to: int, splits) -> dict:
    """Build a fake latest_world dict with splits filled up to a point."""
    data = {}
    split_keys = ["nether", "bastion", "fortress", "first_portal", "stronghold", "end", "finish"]

    for i, (name, _, igt_ms) in enumerate(splits):
        if name == "new_run":
            continue
        if i <= sequence_up_to:
            key = name
            data[key] = igt_ms
            data[f"{key}Rta"] = igt_ms + 5000  # fake RTA slightly higher

    return data


def run_simulation(output_dir: Path, speed: float = 1.0):
    output_file = output_dir / "latest_world"
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\n🎮 Starting MCSR run simulation")
    print(f"📂 Writing to: {output_file}")
    print(f"⚡ Speed multiplier: {speed}x")
    print("=" * 50)

    for i, (name, delay, igt_ms) in enumerate(SPLITS_SEQUENCE):
        actual_delay = delay / speed
        time.sleep(actual_delay)

        if name == "new_run":
            # Write empty/reset data for new run
            data = {}
            output_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            print(f"🌱 [{i+1}/{len(SPLITS_SEQUENCE)}] NEW RUN started")
        else:
            data = build_data(i, SPLITS_SEQUENCE)
            output_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
            mins = igt_ms // 60000
            secs = (igt_ms % 60000) / 1000
            print(f"✅ [{i+1}/{len(SPLITS_SEQUENCE)}] Split: {name.upper():15s} | IGT: {mins}:{secs:05.2f}")

    print("\n🏁 Simulation complete! Dragon slain.")
    print(f"📄 Final data written to: {output_file}\n")


def main():
    parser = argparse.ArgumentParser(description="Simulate a Minecraft speedrun for RPC testing")
    parser.add_argument(
        "--dir",
        type=Path,
        default=None,
        help="Directory to write fake latest_world file\n(defaults to temp dir printed on startup)",
    )
    parser.add_argument(
        "--speed",
        type=float,
        default=1.0,
        help="Speed multiplier for simulation (e.g. 2.0 = twice as fast)",
    )
    args = parser.parse_args()

    if args.dir:
        output_dir = args.dir
    else:
        output_dir = Path(tempfile.gettempdir()) / "mcsr_rpc_test" / "speedrunigt"

    print("\n" + "=" * 50)
    print("  MCSR Discord RPC — Split Simulator")
    print("=" * 50)
    print(f"\n📌 To test with main.py, run:")
    print(f'   python main.py --mc-dir "{output_dir.parent.parent}"')
    print(f"   (in a separate terminal)\n")

    run_simulation(output_dir, args.speed)


if __name__ == "__main__":
    main()
