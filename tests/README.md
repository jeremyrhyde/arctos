# Component tests

Bring up the arm one component at a time, starting with the simplest and leaving the most coupled for last. Each test gets its own folder with firmware, if it needs any, and a README that holds the procedure and results.

| # | Test | Folder | Board | Status |
|---|---|---|---|---|
| 1 | Gripper servo: sweep and jaw limits | [`gripper_servo/`](gripper_servo/) | Nano | Passed 2026-10-11 (working range 65–115°) |
| 2 | CAN link: adapter ↔ Nano/MCP2515 both ways, find crystal | [`can_link/`](can_link/) | Nano + host | Passed 2026-10-11 (8 MHz crystal) |
| 3 | Gripper CAN node: servo commanded over CAN ID 0x07 | — | Nano | Planned (needs #1 and #2) |
| 4 | Wrist B/C: driver comms, motor moves, hall sensors, differential | [`joint_bc/`](joint_bc/) | Host | Stages 1–2 passed 2026-10-11; remap done; Stage 3 (sensors) waiting on sensor wiring |
| 5 | MKS drivers X, Y, Z, A: config and moves, one joint at a time | — | Host | Planned |
| 6 | Gripper node on ESP32 (TWAI + SN65HVD230) | reuse #1 and #3 | ESP32 | Waiting on parts |

## Adding a test

1. Create `tests/<name>/`, containing:
   - a `README.md` that copies the layout of `gripper_servo/README.md` (purpose, wiring, safety, stages, pass criteria, results)
   - the firmware source, if any (`.cpp` that includes `<Arduino.h>` and `<arctos_board.h>`), **or**
   - a host script, for tests that talk to the drivers from the PC (see `joint_bc/bc_test.py`). It uses `host/arctos_host/` for the CAN bus and the MKS protocol.
2. Firmware tests only: add one PlatformIO env for each board it runs on:
   ```ini
   [env:<name>_nano]
   extends = nano
   build_src_filter = +<<name>/>
   lib_deps = ...
   ```
3. Take pins, IDs and limits from `config/config_*.yaml`, never from hard-coded numbers.
   - Firmware reads them through the generated headers included by `arctos_board.h`.
   - Host scripts read them through `arctos_host.config.load()`.
4. Add the test to the table above.
