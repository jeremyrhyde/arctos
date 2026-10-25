"""Watch a driver's limit inputs during a move and report when a switch becomes triggered.

A switch that is already triggered when the guard starts is ignored until it releases,
so a move can drive off a limit it's parked on. Once released it is armed again.
"""

from .mks import MksDriver

SENSOR_MASK = 0b11  # 0x34 bits 0 and 1: IN_1/IN_2, or En/Dir after the 0x9E remap


class LimitGuard:
    def __init__(self, driver: MksDriver, triggered_level: int):
        self.d = driver
        self.level = triggered_level
        io = driver.read_io()
        self.start_io = io
        self.armed = ~self._triggered(io) & SENSOR_MASK

    def _triggered(self, io):
        """Bits (within SENSOR_MASK) that read the triggered level."""
        return (io if self.level else ~io) & SENSOR_MASK

    def already_triggered(self):
        return ~self.armed & SENSOR_MASK

    def check(self):
        """Read the inputs. Return the bits that just became triggered (0 if none)."""
        trig = self._triggered(self.d.read_io())
        hit = trig & self.armed
        self.armed |= ~trig & SENSOR_MASK  # re-arm anything that has released
        return hit

    def describe(self):
        bits = " ".join(f"bit{b}={self.start_io >> b & 1}" for b in range(2))
        text = f"sensor inputs at start: {bits} (triggered = {self.level})"
        parked = self.already_triggered()
        if parked:
            text += f"; {bit_names(parked)} already triggered, ignored until it releases"
        return text


def bit_names(bits):
    return "+".join(f"bit{b}" for b in range(2) if bits >> b & 1)
