# Test: gripper servo

Confirms that the gripper servo moves when driven from the gripper node, then finds the jaw's open and closed angles so later firmware can clamp to them.

The working limits are stored in [`config/config_gripper.yaml`](../../config/config_gripper.yaml) as `servo.angle_closed` and `servo.angle_open`, and this test uses them as its default soft limits. If you re-measure, update them there; the next build picks them up.

| | |
|---|---|
| **Node** | Gripper (CAN ID 0x07): Arduino Nano now, ESP32 later |
| **Firmware** | [`servo_test.cpp`](servo_test.cpp), envs `gripper_servo_nano` and `gripper_servo_esp32` |
| **Wiring** | [docs/wiring.md](../../docs/wiring.md), gripper node table |
| **CAN used?** | No. The MCP2515 stays wired, but the sketch holds its CS pin high so it's idle. |
| **Unblocks** | Gripper CAN firmware, which needs the jaw limits found here |

## What you need

- A USB cable for the Nano that carries data, not just charge
- A multimeter
- PlatformIO (see the [repo README](../../README.md#setup))
- The 24 V PSU, which feeds the buck that powers the servo

## Safety

- The 24 V switch also powers all six MKS drivers. Before you switch on, put the arm in a resting pose that is supported or stable.
- The first time it powers on, the servo jumps to **90°**. In Stage 2, keep your fingers out of the jaws.
- A servo that buzzes or hums without moving is **stalled**. It draws its maximum current and heats up fast. Back off right away with `-` or `+`, or send `d` to make it go limp.

## Stage 0: pre-flight (power off)

1. Check the wiring against the gripper node table in `docs/wiring.md`:
   - Servo signal goes to **D9**.
   - Servo V+ goes to buck OUT+, **not** to the Nano.
   - Nano VIN goes to buck OUT+.
2. Use continuity mode to check the common ground. Buck OUT−, Nano GND, servo GND and PSU − should all beep together.
3. Check the servo's voltage rating. 6 V is fine for SG90, MG90S, MG996R, DS3218 and most others. If the servo is rated 4.8 V only, stop here.
4. **If you can, take the horn off the servo or disconnect it from the gripper linkage** for Stage 1. A bad angle then can't jam the jaws.

## Stage 1: upload and bench sweep

1. **24 V off.** Connect the Nano to your Mac over USB only.
2. Upload and open the serial monitor:
   ```sh
   pio run -e gripper_servo_nano -t upload
   pio device monitor -e gripper_servo_nano
   ```
   - If the upload fails with `not in sync` or `programmer is not responding`, change `board = nanoatmega328` to `nanoatmega328new` in `platformio.ini` (the `[nano]` section), then retry.
   - If no port shows up, try another USB cable. Most clone Nanos use a CH340 chip, which recent macOS supports without a driver.
3. You should see the banner and help text:
   ```
   Arctos gripper servo test (Arduino Nano, servo pin 9)
   ...
   angle 90  limits 65..115  attached
   ```
   The servo **won't move yet**, because it's powered from the buck, not from USB. That's expected.
4. **Switch the 24 V on.** The servo should settle at 90°, maybe with a small twitch. Check the buck's display. It should read about 6.0 V.
5. Run these commands in the serial monitor and watch the servo:

   | Send | Expect |
   |---|---|
   | `p` | `angle 90  limits 65..115  attached` |
   | `80` | Moves smoothly and prints `at 80` |
   | `100` | Moves the other way and prints `at 100` |
   | `150` | Prints `clamped to 115` and moves to 115. The soft limits work. |
   | `90` | Returns to the center |
   | `s` | Sweeps 65 ↔ 115 (closed ↔ open) continuously with a short pause at each end. Let it run for about 1 minute. |
   | `x` | Stops where it is |
   | `d` | Servo goes limp, so you can turn the horn by hand. Some digital servos hold their position instead. |
   | `a` | Holds again |

**Pass criteria for Stage 1:**
- [ ] Every move is smooth, with no jitter while it holds still.
- [ ] The Nano doesn't reset during motion. A reset shows up as the banner reprinting.
- [ ] The buck stays at or above about 5.7 V while the servo moves.
- [ ] The servo is no more than slightly warm after the 1-minute sweep.

## Stage 2: find the jaw limits (servo mounted in the gripper)

1. Send `90` and wait for `at 90`. With the servo held at 90°, attach the horn or linkage so the jaws sit at about **half-open**. That gives you room to travel both ways.
2. Open the soft limits up: `l 0 180`. **From here on, nothing stops a stall except you.**
3. **Find the open limit.** Use `+5` (or `-5`) to step toward open. Within the first step or two you'll know which direction opens the jaws.
   - When the jaws are close to fully open, switch to single steps with `+` or `-`.
   - Stop at the first angle where the jaws stop moving or the servo starts to hum.
   - Back off **2–3°** until it's silent. Record that angle as **OPEN**.
4. **Find the closed limit** the same way in the other direction. Use the angle where the jaws just touch with no hum. That gives closed-on-nothing, not grip force. Record it as **CLOSED**.
5. Lock in the new range. `l` takes the smaller angle first: `l <smaller> <larger>`.
6. Send `s` and watch 3–5 full open/close cycles. There should be no humming at either end.
7. Record the results below, and tick the matching boxes in `docs/wiring.md` → Status.

**Pass criteria for Stage 2:**
- [ ] The jaws reach full open and full closed with no stall hum at either end.
- [ ] The sweep across the measured range runs cleanly.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| No serial output at all | Wrong port, or the baud rate isn't 115200. Press the Nano's reset button. |
| Serial works but the servo never moves | No 6 V at the servo connector (measure it), signal not on D9, or the grounds aren't shared |
| Servo jitters while holding | Loose ground, or the buck is sagging. Check that the signal ground goes back to the Nano. |
| Nano resets when the servo moves | Brownout. The servo draws more than the buck supplies. Check the buck's current rating against the servo's stall current. |
| Servo moves the wrong way | Nothing's wrong. Just record which way is "open". |
| Hums at a limit | Stall. Back off a few degrees and record the smaller angle. |

## Results

Copy a row for each run.

| Date | Board | Servo model | Stage 1 pass | OPEN ° | CLOSED ° | Notes |
|---|---|---|---|---|---|---|
| 2026-10-11 | Nano | DS3230MG | Yes | 120 | 60 | 6.0 V supply. Hard stops; working range set to 65–115 for margin. |
