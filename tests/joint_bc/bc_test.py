"""Wrist B/C bench test: MKS SERVO42D drivers over CAN, then their hall sensors.

Procedure: tests/joint_bc/README.md. Run from the repo root with the venv:
    .venv/bin/python tests/joint_bc/bc_test.py <command> [args]

Commands:
    scan                    list every driver ID 1..10 that answers (read-only)
    ping                    read position, status and sensors on B and C (read-only)
    move B|C <deg>          relative move of one motor, in motor shaft degrees
    diff same|opposite <deg>  move B and C together (same = equal moves, opposite = B +deg, C -deg)
    io                      live sensor readout for B and C until Ctrl-C
    remap                   set B and C to read their sensors on En/Dir (one-time, 0x9E)
    seek B|C en|dir <deg>   move up to <deg> slowly; stop the moment that sensor changes
    stop                    emergency-stop both motors
    off                     disable both motors (shafts turn freely)

Ctrl-C during any move emergency-stops both motors. move and diff also e-stop both if a
limit switch becomes triggered. Options: --speed <rpm>, --no-cap (lift max_move_deg).
"""

import argparse
import pathlib
import sys
import time

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "host"))

from arctos_host import config  # noqa: E402
from arctos_host.limits import LimitGuard, bit_names  # noqa: E402
from arctos_host.mks import (  # noqa: E402
    MOTOR_STATUS, MOVE_LIMIT_STOP, Inbox, MksDriver, MksError,
    counts_to_deg, deg_to_counts, move_time_estimate,
)

JOINTS = config.load("joints")
TEST = JOINTS["host"]["test"]
IO_BITS = {"en": 0, "dir": 1}  # after the 0x9E remap


def joint_cfg(key):
    return JOINTS[key.lower()]


def make_driver(inbox, key):
    cfg = joint_cfg(key)
    return MksDriver(inbox, cfg["can_id"], key.upper())


def fmt_deg(key, motor_deg):
    joint_deg = motor_deg / joint_cfg(key)["gear_ratio"]
    return f"{motor_deg:+.1f} deg motor ({joint_deg:+.2f} deg joint)"


def sensor_text(key, io):
    sensors = joint_cfg(key)["sensors"]
    return "  ".join(f"{pin}={io >> bit & 1} [{sensors[pin]}]" for pin, bit in IO_BITS.items())


def check_move_size(deg, limit):
    if abs(deg) > limit:
        raise SystemExit(f"{deg} deg is over the {limit} deg limit (config_joints.yaml host.test)")


def estop_all(drivers):
    for d in drivers:
        try:
            d.estop()
        except MksError as e:
            print(f"  e-stop {d.name} failed: {e}")


# ---- commands ----

def cmd_scan(inbox, args):
    found = False
    for can_id in range(1, 11):
        d = MksDriver(inbox, can_id)
        try:
            pos = d.read_encoder()
        except MksError:
            continue
        found = True
        print(f"  ID 0x{can_id:02X} answers (encoder {pos})")
        if can_id == 1:
            print("    note: 0x01 is the factory default ID. Several unconfigured drivers can share it.")
    if not found:
        print("  no drivers answered. Check 24 V power, CanRate (500K), CANH/CANL wiring and termination.")


def cmd_ping(inbox, args):
    ok = True
    for key in "BC":
        d = make_driver(inbox, key)
        try:
            pos = d.read_encoder()
            status = d.read_status()
            stalled = d.is_stalled()
            io = d.read_io()
        except MksError as e:
            ok = False
            print(f"  {key}: {e}")
            continue
        print(f"  {key} (0x{d.can_id:02X}): position {fmt_deg(key, counts_to_deg(pos))}, "
              f"{MOTOR_STATUS.get(status, status)}{', STALLED' if stalled else ''}")
        print(f"      sensors: {sensor_text(key, io)}")
    if not ok:
        print("  Missing driver? Run `scan` to see which IDs answer.")


def run_moves(drivers, moves, speed):
    """Start every (driver, key, deg) move together, wait for all, then report.

    While waiting, polls each driver's limit inputs and e-stops everything if a switch
    becomes triggered (a switch already triggered at the start is ignored until it releases)."""
    guards = {d.name: LimitGuard(d, TEST["sensor_triggered_level"]) for d, _, _ in moves}
    for d, key, _ in moves:
        print(f"  {key}: {guards[d.name].describe()}")
    for d, _, _ in moves:
        d.enable()
    before = {d.name: d.read_encoder() for d, _, _ in moves}
    pending = {d.name for d, _, _ in moves}
    deadline = time.monotonic() + max(move_time_estimate(deg_to_counts(deg), speed) for _, _, deg in moves)
    try:
        for d, _, deg in moves:
            d.start_relative_move(deg_to_counts(deg), speed, TEST["acc"])
        while pending:
            if time.monotonic() > deadline:
                raise MksError(f"{', '.join(sorted(pending))}: move did not finish in time")
            for d, key, _ in moves:
                hit = guards[d.name].check()
                if hit:
                    estop_all(drivers)
                    print(f"  {key}: LIMIT {bit_names(hit)} triggered; emergency stop sent to all")
                    pending.clear()
                    break
                if d.name in pending:
                    reply = d.receive(0xF4, timeout=0)
                    if reply is not None:
                        pending.discard(d.name)
                        if reply[0] == MOVE_LIMIT_STOP:
                            print(f"  {key}: stopped early by an end-limit sensor")
            time.sleep(0.01)
    except KeyboardInterrupt:
        estop_all(drivers)
        raise SystemExit("\n  Ctrl-C: emergency stop sent")
    except MksError:
        estop_all(drivers)
        raise
    time.sleep(0.2)  # let the closed loop settle before reading back
    for d, key, deg in moves:
        actual = counts_to_deg(d.read_encoder() - before[d.name])
        print(f"  {key}: asked {fmt_deg(key, deg)}")
        print(f"     moved {fmt_deg(key, actual)}  (error {actual - deg:+.2f} deg motor)")
        if d.is_stalled():
            print(f"  {key}: STALL PROTECTION TRIPPED. Check for binding, then run with --release.")


def cmd_move(inbox, args):
    if not args.no_cap:
        check_move_size(args.deg, TEST["max_move_deg"])
    d = make_driver(inbox, args.joint)
    run_moves([d], [(d, args.joint.upper(), args.deg)], args.speed)


def cmd_diff(inbox, args):
    if not args.no_cap:
        check_move_size(args.deg, TEST["max_move_deg"])
    b, c = make_driver(inbox, "B"), make_driver(inbox, "C")
    c_deg = args.deg if args.mode == "same" else -args.deg
    print(f"  B {args.deg:+.1f}, C {c_deg:+.1f} deg motor at {args.speed} rpm")
    run_moves([b, c], [(b, "B", args.deg), (c, "C", c_deg)], args.speed)


def cmd_io(inbox, args):
    drivers = {key: make_driver(inbox, key) for key in "BC"}
    last = {}
    print("  watching sensors (Ctrl-C to quit). Changes are printed as they happen.")
    try:
        while True:
            for key, d in drivers.items():
                try:
                    io = d.read_io()
                except MksError as e:
                    io = str(e)
                if last.get(key) != io:
                    last[key] = io
                    stamp = time.strftime("%H:%M:%S")
                    text = sensor_text(key, io) if isinstance(io, int) else io
                    print(f"  {stamp}  {key}: {text}")
            time.sleep(0.05)
    except KeyboardInterrupt:
        print()


def cmd_remap(inbox, args):
    for key in "BC":
        d = make_driver(inbox, key)
        d.remap_limit_pins(True)
        print(f"  {key}: limit inputs remapped to En/Dir")


def cmd_seek(inbox, args):
    check_move_size(args.deg, TEST["max_seek_deg"])
    key = args.joint.upper()
    d = make_driver(inbox, key)
    bit = IO_BITS[args.sensor]
    start_level = d.read_io() >> bit & 1
    print(f"  {key} {args.sensor} reads {start_level} now; stopping when it changes")
    d.enable()
    before = d.read_encoder()
    counts = deg_to_counts(args.deg)
    d.start_relative_move(counts, TEST["seek_speed_rpm"], TEST["acc"])
    deadline = time.monotonic() + move_time_estimate(counts, TEST["seek_speed_rpm"])
    triggered = False
    try:
        while time.monotonic() < deadline:
            if (d.read_io() >> bit & 1) != start_level:
                d.estop()
                triggered = True
                break
            if d.receive(0xF4, timeout=0) is not None:  # move finished on its own
                break
            time.sleep(0.01)
        else:
            d.estop()
            print("  timed out; e-stop sent")
    except KeyboardInterrupt:
        d.estop()
        raise SystemExit("\n  Ctrl-C: emergency stop sent")
    time.sleep(0.2)
    travelled = counts_to_deg(d.read_encoder() - before)
    if triggered:
        print(f"  TRIGGERED after {fmt_deg(key, travelled)}")
    else:
        print(f"  sensor did NOT change over {fmt_deg(key, travelled)}")


def cmd_stop(inbox, args):
    drivers = [make_driver(inbox, key) for key in "BC"]
    estop_all(drivers)
    print("  e-stop sent to B and C")


def cmd_off(inbox, args):
    for key in "BC":
        make_driver(inbox, key).enable(False)
        print(f"  {key}: disabled (shaft free)")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--channel", help="adapter port (default: from config_can.yaml)")
    parser.add_argument("--release", action="store_true", help="clear stall protection on B and C first")
    parser.add_argument("--speed", type=int, default=TEST["speed_rpm"], help="move/diff speed in rpm (default: %(default)s)")
    parser.add_argument("--no-cap", action="store_true", help="move/diff: allow more than max_move_deg (you are watching the arm)")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("scan")
    sub.add_parser("ping")
    p = sub.add_parser("move")
    p.add_argument("joint", choices=["B", "C", "b", "c"])
    p.add_argument("deg", type=float)
    p = sub.add_parser("diff")
    p.add_argument("mode", choices=["same", "opposite"])
    p.add_argument("deg", type=float)
    sub.add_parser("io")
    sub.add_parser("remap")
    p = sub.add_parser("seek")
    p.add_argument("joint", choices=["B", "C", "b", "c"])
    p.add_argument("sensor", choices=["en", "dir"])
    p.add_argument("deg", type=float)
    sub.add_parser("stop")
    sub.add_parser("off")
    args = parser.parse_args()

    bus = config.open_bus(args.channel)
    inbox = Inbox(bus)
    try:
        if args.release:
            for key in "BC":
                make_driver(inbox, key).release_stall()
            print("  stall protection cleared on B and C")
        globals()[f"cmd_{args.command}"](inbox, args)
    except MksError as e:
        raise SystemExit(f"  error: {e}")
    finally:
        bus.shutdown()


if __name__ == "__main__":
    main()
