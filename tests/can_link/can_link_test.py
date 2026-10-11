"""CAN link test: USB-CAN adapter <-> Nano + MCP2515, checked in both directions.

Procedure: tests/can_link/README.md. Needs the can_link_nano firmware on the Nano and
the Nano's USB cable plugged in (its serial output is how we see what it received).
Close any serial monitor on the Nano first.

    .venv/bin/python tests/can_link/can_link_test.py [--nano-port /dev/cu.usbserial-XXXX]
"""

import argparse
import glob
import pathlib
import queue
import sys
import threading
import time

import can
import serial

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "host"))

from arctos_host import config  # noqa: E402

GRIPPER_ID = config.load("gripper")["can"]["id"]
TEST_FRAMES = 5


def nano_reader(port, lines):
    """Push every line the Nano prints onto `lines`."""
    with serial.Serial(port, 115200, timeout=0.1) as s:  # opening resets the Nano
        while True:
            line = s.readline().decode(errors="replace").strip()
            if line:
                lines.put(line)


def wait_for_line(lines, predicate, timeout):
    deadline = time.monotonic() + timeout
    while (remaining := deadline - time.monotonic()) > 0:
        try:
            line = lines.get(timeout=remaining)
        except queue.Empty:
            break
        print(f"    nano: {line}")
        if predicate(line):
            return line
    return None


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--nano-port", help="Nano serial port (default: first /dev/cu.usbserial*)")
    parser.add_argument("--channel", help="adapter port (default: from config_can.yaml)")
    args = parser.parse_args()

    nano_port = args.nano_port or next(iter(sorted(glob.glob("/dev/cu.usbserial*"))), None)
    if not nano_port:
        raise SystemExit("Nano not found (/dev/cu.usbserial*). Is its USB cable plugged in?")

    # Open the adapter first so it's on the bus to ACK the Nano's crystal probe.
    bus = config.open_bus(args.channel)
    results = {}
    try:
        print(f"1. Starting the Nano ({nano_port}); it resets and probes the bus")
        lines = queue.Queue()
        threading.Thread(target=nano_reader, args=(nano_port, lines), daemon=True).start()
        link = wait_for_line(lines, lambda l: l.startswith("link up"), timeout=10)
        results["Nano MCP2515 link up"] = bool(link)
        if not link:
            raise SystemExit(report(results, "The Nano never got ACKs. Check CANH/CANL, J1, and that "
                                             "can_link_nano is the firmware on the Nano."))

        print(f"2. Nano -> PC: listening for heartbeats on 0x{GRIPPER_ID:02X}")
        heartbeats = 0
        deadline = time.monotonic() + 3.5
        while time.monotonic() < deadline:
            msg = bus.recv(timeout=0.2)
            if msg and msg.arbitration_id == GRIPPER_ID and bytes(msg.data[:2]) == b"HB":
                heartbeats += 1
                print(f"    pc:   heartbeat #{int.from_bytes(msg.data[2:4], 'big')}")
        results["Nano -> PC (heartbeats)"] = heartbeats >= 2

        print(f"3. PC -> Nano: sending {TEST_FRAMES} frames to 0x{GRIPPER_ID:02X}")
        received = 0
        for i in range(TEST_FRAMES):
            data = bytes([0xC0, 0xDE, i])
            bus.send(can.Message(arbitration_id=GRIPPER_ID, data=data, is_extended_id=False))
            want = f"data={data.hex(' ').upper()}"
            if wait_for_line(lines, lambda l: l.startswith("rx") and want in l, timeout=1.0):
                received += 1
        results[f"PC -> Nano ({received}/{TEST_FRAMES} frames)"] = received == TEST_FRAMES
    finally:
        bus.shutdown()

    print(report(results, "Crystal: see the 'link up' line above; record it in config_gripper.yaml."))


def report(results, note):
    rows = [f"  {'PASS' if ok else 'FAIL'}  {name}" for name, ok in results.items()]
    return "\nResults:\n" + "\n".join(rows) + f"\n  {note}"


if __name__ == "__main__":
    main()
