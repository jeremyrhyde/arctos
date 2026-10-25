"""Watch one driver's limit inputs and say whether a limit is hit. Read-only: nothing moves.

    .venv/bin/python tests/joint_move/limit_watch.py [joint]     # default y; or x..c, or a CAN ID like 0x02

The inputs are read once at start and taken as "no limit". Any change on bit 0 or 1
(IN_1/IN_2, or En/Dir after the 0x9E remap) prints LIMIT HIT; going back prints no limit.
Ctrl-C to quit.
"""

import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "host"))

from arctos_host import config  # noqa: E402
from arctos_host.mks import Inbox, MksDriver, MksError  # noqa: E402
from arctos_host.limits import SENSOR_MASK  # noqa: E402
from move_test import resolve_joint  # noqa: E402

name, can_id, _ = resolve_joint(sys.argv[1] if len(sys.argv) > 1 else "y")
bus = config.open_bus()
d = MksDriver(Inbox(bus), can_id, name)
try:
    idle = d.read_io() & SENSOR_MASK
    print(f"  {name}: watching bits 0-1 (idle = {idle:02b}). Ctrl-C to quit.")
    print("  no limit")
    last = idle
    while True:
        try:
            now = d.read_io() & SENSOR_MASK
        except MksError as e:
            print(f"  {e}")
            time.sleep(0.5)
            continue
        if now != last:
            changed = now ^ idle
            stamp = time.strftime("%H:%M:%S")
            if changed:
                bits = "+".join(f"bit{b}" for b in range(2) if changed >> b & 1)
                print(f"  {stamp}  LIMIT HIT ({bits}, inputs {now:02b})")
            else:
                print(f"  {stamp}  no limit")
            last = now
        time.sleep(0.02)
except KeyboardInterrupt:
    print()
finally:
    bus.shutdown()
