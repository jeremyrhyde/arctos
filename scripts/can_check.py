"""One-shot CAN bus health check. Read-only: nothing moves.

    .venv/bin/python scripts/can_check.py

1. Is the USB-CAN adapter plugged in?
2. Does any traffic show up on the bus by itself?
3. Which MKS driver IDs (1..10) answer at the configured bitrate, with status and inputs?
4. If none answer, does anything answer at another bitrate?
Ends with a one-line verdict and what to check next.
"""

import glob
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "host"))

import can  # noqa: E402

from arctos_host import config  # noqa: E402
from arctos_host.mks import MOTOR_STATUS, Inbox, MksDriver, MksError, counts_to_deg  # noqa: E402

CAN_CFG = config.load("can")
JOINTS = config.load("joints")
NAMES = {cfg["can_id"]: f"{key.upper()} ({cfg.get('name', '')})"
         for key, cfg in JOINTS.items() if key != "host" and "can_id" in cfg}
IDS = range(1, 11)
OTHER_RATES = (125000, 250000, 1000000)


def find_adapter():
    channel = CAN_CFG.get("host", {}).get("channel", "auto")
    if channel != "auto":
        return channel if pathlib.Path(channel).exists() else None
    ports = sorted(glob.glob("/dev/cu.usbmodem*"))
    return ports[0] if ports else None


def open_bus(port, rate):
    return can.Bus(interface=CAN_CFG.get("host", {}).get("interface", "slcan"), channel=port, bitrate=rate)


def listen(bus, seconds):
    count, ids = 0, set()
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        msg = bus.recv(0.1)
        if msg is not None:
            count += 1
            ids.add(msg.arbitration_id)
    return count, ids


def scan(bus):
    inbox = Inbox(bus)
    found = []
    for can_id in IDS:
        d = MksDriver(inbox, can_id)
        try:
            pos = d.read_encoder()
        except MksError:
            continue
        try:
            status = MOTOR_STATUS.get(d.read_status(), "?")
            io = f"{d.read_io():04b}"
        except MksError:
            status, io = "?", "?"
        found.append((can_id, pos, status, io))
    return found


def main():
    rate = CAN_CFG["bitrate"]
    print("CAN bus check")

    port = find_adapter()
    if not port:
        print("  [FAIL] adapter: not found (/dev/cu.usbmodem*)")
        print("\nVerdict: plug in the USB-CAN adapter.")
        return 1
    print(f"  [ OK ] adapter: {port}")

    try:
        bus = open_bus(port, rate)
    except Exception as e:  # noqa: BLE001 - any open failure is the answer here
        print(f"  [FAIL] open at {rate // 1000}K: {e}")
        print("\nVerdict: the adapter won't open. Unplug it and plug it back in; close any other tool using it.")
        return 1

    try:
        count, ids = listen(bus, 1.0)
        heard = ", ".join(f"0x{i:03X}" for i in sorted(ids)) or "-"
        print(f"  [info] idle traffic in 1 s: {count} frames (IDs {heard})")

        found = scan(bus)
    finally:
        bus.shutdown()

    if found:
        print(f"  [ OK ] drivers answering at {rate // 1000}K:")
        for can_id, pos, status, io in found:
            name = NAMES.get(can_id, "not in config_joints.yaml")
            print(f"         0x{can_id:02X} {name}: {status}, encoder {counts_to_deg(pos):+.1f} deg, inputs {io}")
        missing = [f"0x{i:02X} {n}" for i, n in sorted(NAMES.items()) if i not in {f[0] for f in found}]
        if missing:
            print(f"  [info] in config but silent: {', '.join(missing)}")
        print("\nVerdict: bus OK.")
        return 0

    print(f"  [FAIL] no driver answered at {rate // 1000}K (IDs {IDS.start}..{IDS.stop - 1})")
    other = []
    for r in OTHER_RATES:
        try:
            bus = open_bus(port, r)
        except Exception:  # noqa: BLE001
            continue
        try:
            hits = scan(bus)
        finally:
            bus.shutdown()
        if hits:
            other.append((r, hits))
            print(f"  [info] at {r // 1000}K: " + ", ".join(f"0x{h[0]:02X}" for h in hits))
    if other:
        print(f"\nVerdict: drivers answer at the wrong bitrate. Set CanRate to {rate // 1000}K in their menus.")
    else:
        print("  [info] nothing at 125K, 250K or 1M either")
        print("\nVerdict: nothing on the bus answers. Check, in order:")
        print("  1. 24 V on and the driver screen lit (not in a menu)")
        print("  2. CANH/CANL seated at both the adapter and the driver, not swapped")
        print("  3. with 24 V off, CANH-CANL at the adapter reads ~60 ohm "
              "(120 = a terminator missing, 40 = one too many, open = broken wire)")
    return 1


if __name__ == "__main__":
    sys.exit(main())
