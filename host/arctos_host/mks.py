"""MKS SERVO42D/57D CAN protocol client.

Source: MKS SERVO42&57D CAN User Manual V1.0.9
https://github.com/makerbase-motor/MKS-SERVO42D-57D (page numbers below refer to it).

Frame: standard ID = driver CAN ID; data = [cmd, payload..., crc], big-endian fields,
crc = (can_id + every data byte) & 0xFF. The driver replies with the same ID and cmd.
"""

import time

import can

COUNTS_PER_REV = 16384  # encoder counts per motor shaft revolution

# Sign convention: positive = the direction a positive move command turns the shaft,
# which is clockwise seen from the shaft end (measured on B and C, 2026-10-11).
# The driver's own encoder and speed readings count CCW as positive, so reads are negated.
_READ_SIGN = -1

# 0xF1 motor status codes (p.70)
MOTOR_STATUS = {0: "query failed", 1: "stopped", 2: "accelerating", 3: "decelerating",
                4: "full speed", 5: "homing", 6: "calibrating"}

# 0xF4/0xF5 position-move replies (p.86)
MOVE_FAILED, MOVE_STARTED, MOVE_COMPLETE, MOVE_LIMIT_STOP = 0, 1, 2, 3


class MksError(Exception):
    pass


def deg_to_counts(deg):
    return round(deg / 360 * COUNTS_PER_REV)


def counts_to_deg(counts):
    return counts * 360 / COUNTS_PER_REV


def _crc(can_id, data):
    return (can_id + sum(data)) & 0xFF


class Inbox:
    """Shared receive buffer, so waiting on one driver never discards another driver's replies."""

    MAX_PENDING = 256

    def __init__(self, bus: can.BusABC):
        self.bus = bus
        self.pending = []

    @staticmethod
    def _matches(msg, can_id, cmd):
        return (msg.arbitration_id == can_id and not msg.is_extended_id
                and len(msg.data) >= 2 and msg.data[0] == cmd)

    def _keep(self, msg):
        self.pending.append(msg)
        del self.pending[:-self.MAX_PENDING]

    def take(self, can_id, cmd, timeout):
        """Return the next frame from `can_id` replying to `cmd`, or None on timeout."""
        for i, msg in enumerate(self.pending):
            if self._matches(msg, can_id, cmd):
                return self.pending.pop(i)
        deadline = time.monotonic() + timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return None
            msg = self.bus.recv(timeout=remaining)
            if msg is None:
                return None
            if self._matches(msg, can_id, cmd):
                return msg
            self._keep(msg)

    def discard(self, can_id, cmd):
        """Drop stale replies from `can_id` to `cmd`."""
        while (msg := self.bus.recv(timeout=0)) is not None:
            self._keep(msg)
        self.pending = [m for m in self.pending if not self._matches(m, can_id, cmd)]


class MksDriver:
    def __init__(self, inbox: Inbox, can_id: int, name: str = ""):
        self.inbox = inbox
        self.can_id = can_id
        self.name = name or f"0x{can_id:02X}"

    # ---- framing ----

    def send(self, cmd, payload=b""):
        data = bytes([cmd]) + bytes(payload)
        data += bytes([_crc(self.can_id, data)])
        self.inbox.bus.send(can.Message(arbitration_id=self.can_id, data=data, is_extended_id=False))

    def receive(self, cmd, timeout):
        """Return the payload (without cmd and crc) of the next reply to `cmd`, or None on timeout."""
        msg = self.inbox.take(self.can_id, cmd, timeout)
        if msg is None:
            return None
        data = bytes(msg.data)
        if data[-1] != _crc(self.can_id, data[:-1]):
            raise MksError(f"{self.name}: bad checksum in reply {data.hex(' ')}")
        return data[1:-1]

    def request(self, cmd, payload=b"", timeout=0.3):
        self.inbox.discard(self.can_id, cmd)
        self.send(cmd, payload)
        reply = self.receive(cmd, timeout)
        if reply is None:
            raise MksError(f"{self.name}: no reply to 0x{cmd:02X} (check power, CanID, CanRate, wiring)")
        return reply

    def _ok(self, cmd, payload=b""):
        reply = self.request(cmd, payload)
        if not reply or reply[0] != 1:
            raise MksError(f"{self.name}: command 0x{cmd:02X} refused (reply {reply.hex(' ')})")

    # ---- reads ----

    def read_encoder(self):
        """Accumulated position in counts, same sign as move commands (0x31, int48, p.27)."""
        reply = self.request(0x31)
        return _READ_SIGN * int.from_bytes(reply[:6], "big", signed=True)

    def read_speed_rpm(self):
        """Shaft speed in rpm, same sign as move commands (0x32, p.27)."""
        return _READ_SIGN * int.from_bytes(self.request(0x32)[:2], "big", signed=True)

    def read_io(self):
        """Raw IO byte (0x34, p.52). bit0 IN_1 (or En after remap), bit1 IN_2 (or Dir after remap)."""
        return self.request(0x34)[0]

    def read_status(self):
        """Motor status code, see MOTOR_STATUS (0xF1, p.70)."""
        return self.request(0xF1)[0]

    def is_stalled(self):
        """True if locked-rotor protection has tripped (0x3E, p.50)."""
        return self.request(0x3E)[0] == 1

    # ---- control ----

    def enable(self, on=True):
        self._ok(0xF3, [1 if on else 0])

    def estop(self):
        self._ok(0xF7)

    def release_stall(self):
        self._ok(0x3D)

    def remap_limit_pins(self, on=True):
        """Use En/Dir as the home/end-limit inputs; needed on the 42D, which has only IN_1 (0x9E)."""
        self._ok(0x9E, [1 if on else 0])

    def start_relative_move(self, counts, speed_rpm, acc):
        """Start a relative move in encoder counts (0xF4, p.86). Returns once the driver accepts it."""
        if not -0x7FFFFF <= counts <= 0x7FFFFF:
            raise ValueError("move too large for one command")
        if not 0 <= speed_rpm <= 3000 or not 0 <= acc <= 255:
            raise ValueError("speed must be 0..3000 rpm and acc 0..255")
        payload = speed_rpm.to_bytes(2, "big") + bytes([acc]) + counts.to_bytes(3, "big", signed=True)
        status = self.request(0xF4, payload)[0]
        if status != MOVE_STARTED:
            raise MksError(f"{self.name}: move refused (status {status})")

    def wait_move_done(self, timeout):
        """Wait for the second 0xF4 reply. Returns MOVE_COMPLETE or MOVE_LIMIT_STOP."""
        reply = self.receive(0xF4, timeout)
        if reply is None:
            raise MksError(f"{self.name}: move did not finish within {timeout:.1f} s")
        return reply[0]


def move_time_estimate(counts, speed_rpm):
    """Seconds a move should take at cruise speed, plus margin for ramps."""
    revs = abs(counts) / COUNTS_PER_REV
    return revs / max(speed_rpm, 1) * 60 * 1.5 + 2.0
