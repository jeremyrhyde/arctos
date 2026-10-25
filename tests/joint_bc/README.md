# Test: wrist joints B and C (motors, then sensors)

This test brings up the two MKS SERVO42D drivers that run the differential wrist:

1. Confirm both drivers talk over CAN.
2. Confirm each motor moves the distance it's told to.
3. Check that the differential behaves as expected.
4. Check the hall sensors that home each joint.

| | |
|---|---|
| **Nodes** | B = CAN ID 0x05 (**left** motor), C = CAN ID 0x06 (**right** motor), both MKS SERVO42D on NEMA 17 |
| **Runs on** | Your Mac, through the USB-CAN adapter (CANable 2.0, slcan, 500 kbit/s) |
| **Tool** | [`bc_test.py`](bc_test.py), which uses [`host/arctos_host/mks.py`](../../host/arctos_host/mks.py) |
| **Config** | [`config/config_joints.yaml`](../../config/config_joints.yaml) for IDs, gear ratio, sensor names and test speeds and limits; [`config/config_can.yaml`](../../config/config_can.yaml) for the bitrate and adapter |
| **Sensors** | B: two KY-003 halls, "Top" on En (home) and "Bottom" on Dir. C: a WSH231 dual hall, north on En (home) and south on Dir. |
| **Unblocks** | Homing, wrist kinematics, the full CAN control software |

## Setup (one time)

```sh
python3 -m venv .venv
.venv/bin/pip install -r host/requirements.txt
.venv/bin/python tests/joint_bc/bc_test.py --help
```

All commands below are run from the repo root, and are written as `bc <command>` for short. That means `.venv/bin/python tests/joint_bc/bc_test.py <command>`.

## Safety

- The 24 V switch powers every joint. Before each power-on, put the arm in a stable resting pose.
- **Ctrl-C during any move sends an emergency stop to both motors.** `bc stop` does the same from a second terminal.
- Test moves are capped at `max_move_deg` (1800 motor degrees, which is about 27° at the joint by the 67.82 ratio). Seeks are capped at `max_seek_deg`. Both are set in `config_joints.yaml`.
- Stages 1–3 are meant to be run with the **belt off or loose**, so the motors spin freely and can't drive the wrist into anything.

## Stage 0: bus and driver setup (24 V off unless noted)

1. **Termination:** measure CANH to CANL at the adapter. It should read about **60 Ω**.
   - If it reads about 120 Ω, the adapter end is missing its terminator. Put a 120 Ω resistor across CANH and CANL in the adapter's screw terminal.
2. **Driver menus:** do this with 24 V on, using each driver's buttons and screen. All drivers ship as CAN ID 01, so this step is required.

   | Menu | B | C |
   |---|---|---|
   | `Mode` | `SR_vFOC` | `SR_vFOC` |
   | `CanRate` | `500K` | `500K` |
   | `CanID` | `05` | `06` |
   | `Ma` | 1600 (default) | 1600 (default) |
   | `MStep` | 16 (default) | 16 (default) |

3. Run **`Cal`** on each driver with its motor free (belt off). The motor spins during calibration.
4. Power-cycle the drivers.

## Stage 1: comms (read-only, nothing moves)

```sh
bc scan     # lists every ID 1..10 that answers
bc ping     # position, status and sensor bits for B and C
```

**Pass criteria:**
- [ ] `scan` shows 0x05 and 0x06.
- [ ] `ping` prints a position and the status `stopped` for both B and C.

If 0x01 also shows up, other drivers on the bus (X–A) are still at the factory ID. That's fine for this test, because we only talk to 0x05 and 0x06.

## Stage 2: single motor moves (belt off)

Mark each motor shaft with a piece of tape so you can see how far it turns.

```sh
bc move B 90      # quarter turn
bc move B -90     # and back
bc move B 360     # one full turn: the tape should return to the same spot
bc move C 90
bc move C -90
bc move C 360
```

Each move prints what it was asked to do, what the encoder says it actually did, and the error.

**Pass criteria:**
- [ ] Each move matches visually (a quarter turn, a full turn).
- [ ] The reported error is under about 1 motor degree.
- [ ] No `STALL` warnings.
- [ ] Motion is smooth and quiet, with no grinding or skipping.

Write down which direction `+` turns each shaft, as seen from the shaft end (CW or CCW).

## Stage 3: sensors (belt off)

1. **One-time remap.** The 42D has only one limit input, so Arctos wires the sensors to En and Dir instead. This tells the drivers to read them there:
   ```sh
   bc remap
   ```
2. **Live readout:**
   ```sh
   bc io
   ```
   Wave a magnet past each sensor in turn. Every change prints a line.
   - **B Top:** `en` on B should flip. **B Bottom:** `dir` on B should flip.
   - **C, north pole:** `en` on C should flip. **C, south pole:** `dir` on C should flip.
   - For each sensor, record its **idle** and **triggered** values.
3. **Stop on trigger.** The motor turns slowly and must stop the instant the sensor changes. Hold the magnet away, start the command, then bring the magnet up to the sensor partway through:
   ```sh
   bc seek B en 720
   ```
   It should print `TRIGGERED after …` and stop immediately. Repeat for `B dir`, `C en` and `C dir`.

**Pass criteria:**
- [ ] All four sensors flip the expected bit, and only that bit.
- [ ] Each sensor returns to idle when the magnet is removed.
- [ ] `seek` stops on every sensor.

## Stage 4: differential, belt on (small moves)

Put the wrist in the middle of its range first, so it has room to move both ways.

```sh
bc diff same 90         # B +90, C +90
bc diff same -90
bc diff opposite 90     # B +90, C -90
bc diff opposite -90
```

At the joint, 90 motor degrees is only about 1.3°, so it's small but visible. Watch which motion each command produces.

**Pass criteria:**
- [ ] One mode gives **pure pitch** (the wrist nods) and the other gives **pure roll** (the wrist twists). Neither should produce a mix of the two.
- [ ] Record which is which. If `same` gives a mix, one motor's direction is reversed, and that gets fixed in software.

Then, with the belt on, run `seek` toward each real sensor. Use small numbers first and watch the wrist the whole time.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `No USB-CAN adapter found` | The adapter isn't plugged in. Check with `ls /dev/cu.usbmodem*`. |
| `no reply to 0x31` / `scan` finds nothing | 24 V is off, the CanRate isn't 500K, CANH and CANL are swapped, or termination is missing (measure for 60 Ω) |
| Only 0x01 answers | The drivers are still at the factory ID. Set `CanID` in the menu. |
| `move refused (status 0)` | The driver isn't in an `SR_` mode, or stall protection has tripped. Retry with `--release`. |
| Moves the wrong distance | Run `Cal` again with the motor free. Check that `MStep` is 16. |
| A sensor bit never changes | The remap hasn't been done, there's a wiring fault, or the wrong magnet pole is used (C's board is pole-specific) |

## Results

| Date | Stage | B | C | Notes |
|---|---|---|---|---|
| 2026-10-11 | 1 comms | PASS: 0x05 answers, stopped | PASS: 0x06 answers, stopped | Driver menus: SR_vFOC, 500K, MStep 16. Bus: adapter, B, C, MCP2515 (J1). |
| 2026-10-11 | 2 moves (`+` direction, error) | PASS: + = CW from shaft end; 90°: 0.9, 1.3; 180°: 0.3; 360°: 0.8° | PASS: + = CW; 90°: 1.1, 1.3; 360°: 0.4° | Encoder counts CCW positive, so the tool flips the sign. One C 360° move hit the 5 s timeout with no "complete" reply (C had moved ~364°); a repeat with logging was clean (complete at 2.06 s). |
| | 3 sensors (idle/triggered for en, dir) | | | |
| 2026-10-16 | 4 differential, both belts on (`diff same`) | +360 at 100 rpm: +0.53; +1000 no stops: +0.46 | +360: +0.37; +1000: +1.16 | Wrist moved cleanly (confirmed by the user). C started parked on its IN_1 switch at −2340 and `same +` drove it off. Still to record: whether `same` is pitch or roll. |
| 2026-10-16 | 4 differential, both belts on (`diff opposite`) | +1000 no stops, 100 rpm: +0.66 | −1000: −0.81 | Clean, with no limit hit. Still to record: which motion `opposite` gives. |
| 2026-10-16 | 4 repeat: `same` +1000, then `opposite` +1000 (100 rpm, no stops) | same: +0.20; opposite: −0.64 | same: +0.79; opposite: −0.68 | Both clean, with no limit hits. B is now +4360 and C −1980 at the motor. |
| 2026-10-16 | 4: `opposite` −2000 (100 rpm, no stops) | −1999.2 (+0.84) | +2002.1 (+2.08) | Reversed the opposite axis back to where it started. Clean, with no limit hits. C's 2.08 error is high. B now +2361, C +20 at the motor. |
| 2026-10-16 | 4: `same` −2000 (100 rpm, no stops) | −2000.9 (−0.94) | −2000.8 (−0.81) | Clean, with no limit hits. Wrist is back to just after the first `same +360`: B +360, C −1980 at the motor. |
| | 4 differential (same = ?, opposite = ?) | | | |
