# Test: joint move accuracy (any MKS joint)

Drives one joint forward a set amount, then back the same amount, stopping every `sweep_step_deg` (360° by default) to read the encoder. It prints a table comparing where the motor was told to be with where it is.

| | |
|---|---|
| **Nodes** | Any MKS driver in [`config_joints.yaml`](../../config/config_joints.yaml) (X 0x01 … C 0x06), or a raw CAN ID |
| **Runs on** | Your Mac, through the USB-CAN adapter (CANable 2.0, slcan, 500 kbit/s) |
| **Tool** | [`move_test.py`](move_test.py), which uses [`host/arctos_host/mks.py`](../../host/arctos_host/mks.py) |
| **Config** | `host.test` in `config_joints.yaml`: `speed_rpm`, `acc`, `sweep_step_deg`, `max_sweep_deg` |

## Usage

From the repo root:

```sh
.venv/bin/python tests/joint_move/move_test.py y 720 --dry-run   # print the planned steps only
.venv/bin/python tests/joint_move/move_test.py y 720             # +360, +360, -360, -360
.venv/bin/python tests/joint_move/move_test.py 0x02 -100         # negative = go the other way first
```

| Option | Meaning |
|---|---|
| `--step <deg>` | Largest single move before stopping (default `sweep_step_deg`, capped at `max_move_deg`) |
| `--speed <rpm>`, `--acc <0..255>` | Override the config speed and ramp |
| `--release` | Clear stall protection first |
| `--one-way` | Go forward only; don't come back |
| `--off` | Disable the motor afterwards (shaft free). Leave this off for a gravity-loaded joint. |

To check a limit switch by hand (read-only, nothing moves), run `.venv/bin/python tests/joint_move/limit_watch.py y`. It prints `LIMIT HIT` when input bit 0 or 1 changes from its state at start, and `no limit` when it goes back.

All amounts are in **motor shaft** degrees. `+` is CW from the shaft end, as on B and C. If the joint has a `gear_ratio` in the config, the table adds a joint-degrees column.

## Safety

- Before a joint with the belt on moves, support the arm and make sure it has room for the full forward amount.
- **Ctrl-C emergency-stops the motor** and still prints the table so far. The test also stops on a stall, an end-limit reply, or any change on input bits 0–1 (polled every ~10 ms during each move).
- The driver must report `stopped` before the test starts.

## Pass criteria

- [ ] Every step error is under about 1 motor degree.
- [ ] The final position is within about 1° of the start.
- [ ] No `STALLED` or `END LIMIT` notes appear.
- [ ] Motion is smooth, with no skipping or grinding.

## Results

| Date | Joint | Amount | Max step err | Final pos | Notes |
|---|---|---|---|---|---|
| 2026-10-14 | Y (0x02) | 720° | 0.37° | −0.07° | PASS. Only 0x02 was on the bus. Started from +100° after a single +100° move (−0.09° error). |
| 2026-10-14 | Y (0x02) | 1000° | 0.06° | −0.02° | PASS. Inputs polled during every step: bit0 and bit1 stayed at 1 the whole way, so no sensor tripped. |
| 2026-10-15 | Y (0x02) | 720° | 0.33° | −0.13° | PASS. Sensor bits stayed at 1 (no limit). The first try failed with no reply to enable (0xF3) just after a driver power-cycle; the retry was clean. |
| 2026-10-15 | Y (0x02) | 1080°, no stops, 120 rpm | 0.33° | −0.13° | PASS. Belt off. Three turns each way in one move; sensor bits stayed at 1. |
| 2026-10-15 | Z (0x03) | 1000° | 0.92° | +0.02° | PASS (borderline on the 280° steps). Belt off. Overshot +0.90° at the +1000° turnaround, then cancelled out on the way back. Inputs idle bit0=1 bit1=0; no change. |
| 2026-10-15 | X (0x01) | 180° | 0.97° | −0.18° | PASS (borderline). First move on X. Overshot ~0.8–1.0° on both steps; the errors largely cancelled. |
| 2026-10-15 | Y (0x02) | 180° | 0.15° | −0.18° | PASS. |
| 2026-10-15 | Z (0x03) | 180° | 0.48° | −0.37° | PASS. |
| 2026-10-15 | A (0x04) | 260° | 0.71° | −0.42° | PASS. First move on A. Inputs idle bit0=1 bit1=0 (likely 42D); no change. |
| 2026-10-15 | A (0x04) | 1000° | 0.72° | −0.15° | PASS. |
| 2026-10-15 | A (0x04) | 1000° (repeat) | 1.27° | −0.59° | FAIL (marginal): step 4 was 1.27° over the ~1° limit. Position error stayed under 0.8° and did not build up. Same command passed (0.72°) one run earlier. |
| 2026-10-15 | Z (0x03) | 360° | 0.86° | −0.66° | PASS. |
| 2026-10-15 | Z (0x03) | +3600° one way, 120 rpm | 0.15° | +3600.18° | PASS. New `--one-way` option. Started from about +2520° (left there by an interrupted run), so Z finished at about +6120°. |
| 2026-10-16 | C (0x06) | 720°, no stops | 0.62° | −0.09° | PASS. All six drivers on the bus. About ±10.6° at the joint (gear ratio 67.82). |
| 2026-10-16 | B (0x05) | 720°, no stops | 0.48° | −0.29° | PASS. About ±10.6° at the joint. |
| 2026-10-16 | A (0x04) | 360° | 0.86° | −0.29° | PASS. |
| 2026-10-16 | A (0x04) | −1080° one way | 0.26° | −1080.33° | PASS. Left at about −1080° (3 turns CCW from the shaft end). |
| 2026-10-16 | A (0x04) | −1080° one way, no stops | 0.42° | −1080.42° | PASS. One continuous move (needed `--belt-off` to pass the 720° single-move cap). A now about −2160° from where the previous run started. |
| 2026-10-16 | C (0x06) | 720° | 1.91° | −0.24° | FAIL (marginal): the steps back were −1.91° and +1.60°. Every step finished, unlike the four C moves before it (timeouts, a +816° overshoot, a −309° short move reported as complete). Started from +613.8° with B at 0°. |
| 2026-10-16 | C (0x06) | 10000°, no stops | 0.33° | −0.26° | PASS. Belt off, after the user lubricated the wrist with vaseline. About 28 turns each way. Clean, so the earlier C faults point to load on the belt side, not the driver, motor or cable. |
| 2026-10-16 | C (0x06) | 1000°, C belt on (B belt off) | 2.00° | −0.53° | FAIL (accuracy): every step finished, but step errors were 1–2° against 0.06–0.33° with the belt off. Position error stayed within ±1.1° and did not build up. Lubricated with vaseline. |
| 2026-10-16 | C (0x06) | 5000°, no stops, C belt on | 1.24° | −0.66° | Completed cleanly; step error just over 1°. The user confirmed the travel is safe; the config ratio of 67.82 would make it about 74° at the joint, so that ratio is probably wrong. |
| 2026-10-16 | A (0x04) | 1000°, no stops | 0.27° | −0.53° | PASS. This followed a bind that confined A to about −100…+166° (fixed by hand while A was switched off). |
| 2026-10-17 | A (0x04) | 1000°, no stops (repeat) | 0.31° | −0.40° | PASS. |
| 2026-10-17 | A (0x04) | 2000°, no stops, 200 rpm | 0.32° | −0.44° | PASS. Fastest run so far. |
