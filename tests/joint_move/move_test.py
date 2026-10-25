"""Joint move accuracy test: go forward a set amount, come back the same amount, report the error.

Procedure: tests/joint_move/README.md. Run from the repo root with the venv:
    .venv/bin/python tests/joint_move/move_test.py <joint> <deg> [options]

<joint> is a key from config_joints.yaml (x, y, z, a, b, c) or a raw CAN ID (0x02).
<deg> is in motor shaft degrees; the sign picks which way "forward" is.

The move is split into steps of at most `sweep_step_deg` (config_joints.yaml host.test),
stopping after each. Every stop is read back from the encoder, and a table compares where
the motor was told to be with where it is.

Ctrl-C during any move emergency-stops the motor and prints the table so far.
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
SETTLE_S = 0.2  # let the closed loop settle before reading back


def resolve_joint(text):
    """Return (name, can_id, gear_ratio or None) for a joint key or a raw CAN ID."""
    key = text.lower()
    if key in JOINTS and key != "host":
        cfg = JOINTS[key]
        return f"{key.upper()} ({cfg.get('name', '')}, 0x{cfg['can_id']:02X})", cfg["can_id"], cfg.get("gear_ratio")
    can_id = int(text, 0)
    for key, cfg in JOINTS.items():
        if key != "host" and cfg.get("can_id") == can_id:
            return resolve_joint(key)
    return f"0x{can_id:02X}", can_id, None


def plan_steps(total, step, back=True):
    """Split `total` into steps of at most `step`, forward then (unless back=False) back."""
    out = []
    left = abs(total)
    sign = 1 if total >= 0 else -1
    while left > 1e-9:
        out.append(sign * min(step, left))
        left -= min(step, left)
    return out + [-s for s in reversed(out)] if back else out


def print_table(rows, gear_ratio):
    head = f"  {'#':>2}  {'dir':<4} {'asked':>8} {'moved':>8} {'step err':>9} {'target':>9} {'actual':>9} {'pos err':>8}"
    if gear_ratio:
        head += f" {'joint':>8}"
    print()
    print(head)
    print("  " + "-" * (len(head) - 2))
    for r in rows:
        line = (f"  {r['n']:>2}  {r['dir']:<4} {r['asked']:>+8.1f} {r['moved']:>+8.2f} {r['moved'] - r['asked']:>+9.2f} "
                f"{r['target']:>+9.1f} {r['actual']:>+9.2f} {r['actual'] - r['target']:>+8.2f}")
        if gear_ratio:
            line += f" {r['actual'] / gear_ratio:>+8.2f}"
        if r["note"]:
            line += f"  {r['note']}"
        print(line)
    print("  all values in motor shaft degrees, relative to the start position"
          + ("; joint = actual / gear ratio" if gear_ratio else ""))
    if rows:
        step_errs = [abs(r["moved"] - r["asked"]) for r in rows]
        print(f"\n  max step error   {max(step_errs):.2f} deg")
        print(f"  mean step error  {sum(step_errs) / len(step_errs):.2f} deg")
        print(f"  final position   {rows[-1]['actual']:+.2f} deg (target {rows[-1]['target']:+.1f})")


def wait_watching(d, counts, speed, guard):
    """Wait for a move to finish, polling the limit inputs. E-stop if a switch becomes triggered.

    Returns (driver result or None, newly triggered sensor bits)."""
    deadline = time.monotonic() + move_time_estimate(counts, speed)
    while time.monotonic() < deadline:
        hit = guard.check()
        if hit:
            d.estop()
            return None, hit
        reply = d.receive(0xF4, timeout=0)
        if reply is not None:
            return reply[0], 0
        time.sleep(0.01)
    raise MksError(f"{d.name}: move did not finish within {move_time_estimate(counts, speed):.1f} s")


def run(d, steps, speed, acc):
    rows = []
    start = d.read_encoder()
    last = start
    target = 0.0
    guard = LimitGuard(d, TEST["sensor_triggered_level"])
    print(f"  {guard.describe()}")
    d.enable()
    try:
        for n, asked in enumerate(steps, 1):
            target += asked
            counts = deg_to_counts(asked)
            d.start_relative_move(counts, speed, acc)
            result, changed = wait_watching(d, counts, speed, guard)
            time.sleep(SETTLE_S)
            now = d.read_encoder()
            note = ""
            if result == MOVE_LIMIT_STOP:
                note = "END LIMIT"
            if changed:
                note = "LIMIT " + bit_names(changed)
            stalled = d.is_stalled()
            if stalled:
                note = "STALLED"
            rows.append({"n": n, "dir": "fwd" if (asked > 0) == (steps[0] > 0) else "back", "asked": asked,
                         "moved": counts_to_deg(now - last), "target": target,
                         "actual": counts_to_deg(now - start), "note": note})
            print(f"  step {n}/{len(steps)}: asked {asked:+.1f}, moved {rows[-1]['moved']:+.2f} {note}")
            last = now
            if note:
                print("  stopping the test here.")
                break
    except KeyboardInterrupt:
        d.estop()
        print("\n  Ctrl-C: emergency stop sent")
    except MksError as e:
        d.estop()
        print(f"\n  error: {e}; emergency stop sent")
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("joint", help="x, y, z, a, b, c or a CAN ID such as 0x02")
    parser.add_argument("deg", type=float, help="forward amount in motor shaft degrees")
    parser.add_argument("--step", type=float, default=TEST["sweep_step_deg"],
                        help="largest single move before stopping (default: %(default)s)")
    parser.add_argument("--speed", type=int, default=TEST["speed_rpm"], help="rpm (default: %(default)s)")
    parser.add_argument("--acc", type=int, default=TEST["acc"], help="MKS ramp 0..255 (default: %(default)s)")
    parser.add_argument("--one-way", action="store_true", help="go forward only; don't come back")
    parser.add_argument("--no-stops", action="store_true", help="one continuous move each way (step = the whole amount)")
    parser.add_argument("--belt-off", action="store_true",
                        help="the motor is not driving the joint: lift the max_sweep_deg and max_move_deg caps")
    parser.add_argument("--dry-run", action="store_true", help="print the planned steps and exit")
    parser.add_argument("--release", action="store_true", help="clear stall protection first")
    parser.add_argument("--off", action="store_true", help="disable the motor at the end (shaft free)")
    parser.add_argument("--channel", help="adapter port (default: from config_can.yaml)")
    args = parser.parse_args()

    if args.no_stops:
        args.step = abs(args.deg)
    if not args.belt_off:
        if abs(args.deg) > TEST["max_sweep_deg"]:
            raise SystemExit(f"{args.deg} deg is over the {TEST['max_sweep_deg']} deg limit "
                             "(config_joints.yaml host.test; --belt-off lifts it)")
        if args.step > TEST["max_move_deg"]:
            raise SystemExit(f"a {args.step} deg step is over the {TEST['max_move_deg']} deg limit "
                             "(config_joints.yaml host.test; --belt-off lifts it)")
    if args.step <= 0:
        raise SystemExit("--step must be above 0")
    name, can_id, gear_ratio = resolve_joint(args.joint)
    steps = plan_steps(args.deg, args.step, back=not args.one_way)
    print(f"  {name}: {args.deg:+.1f} deg{"" if args.one_way else " and back"} in {len(steps)} steps at {args.speed} rpm, acc {args.acc}")
    print(f"  steps: {', '.join(f'{s:+.1f}' for s in steps)}")
    if args.dry_run:
        return

    bus = config.open_bus(args.channel)
    d = MksDriver(Inbox(bus), can_id, name)
    try:
        if args.release:
            d.release_stall()
        status = d.read_status()
        if status != 1:
            raise SystemExit(f"  {name} is {MOTOR_STATUS.get(status, status)}, not stopped")
        rows = run(d, steps, args.speed, args.acc)
        print_table(rows, gear_ratio)
        if args.off:
            d.enable(False)
            print(f"  {name}: disabled (shaft free)")
    except MksError as e:
        raise SystemExit(f"  error: {e}")
    finally:
        bus.shutdown()


if __name__ == "__main__":
    main()
