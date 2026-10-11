# Component tests

Bring up the arm one component at a time, starting with the simplest and leaving the most coupled for last. Each test gets its own folder with firmware, if it needs any, and a README that holds the procedure and results.

| # | Test | Folder | Board | Status |
|---|---|---|---|---|
| 1 | Gripper servo: sweep and jaw limits | [`gripper_servo/`](gripper_servo/) | Nano | Passed 2026-10-11 (working range 65–115°) |
| 2 | CAN bus: termination (~60 Ω), USB-CAN adapter sees traffic | — | Host | Planned |
| 3 | Gripper CAN node: servo commanded over CAN ID 0x07 | — | Nano | Planned (needs #1 and #2) |
| 4 | MKS drivers: config (`SR_vFOC`, ID, bitrate, current, direction) and moves, one joint at a time | — | Host | Planned |
| 5 | B/C differential: equal moves give pure pitch | — | Host | Planned (needs #4) |
| 6 | Gripper node on ESP32 (TWAI + SN65HVD230) | reuse #1 and #3 | ESP32 | Waiting on parts |

## Adding a test

1. Create `tests/<name>/`, containing:
   - a `README.md` that copies the layout of `gripper_servo/README.md` (purpose, wiring, safety, stages, pass criteria, results)
   - the firmware source, if any (`.cpp` that includes `<Arduino.h>` and `<arctos_board.h>`)
2. Add one PlatformIO env for each board it runs on:
   ```ini
   [env:<name>_nano]
   extends = nano
   build_src_filter = +<<name>/>
   lib_deps = ...
   ```
3. Use only the pin and ID constants from `lib/arctos_board/arctos_board.h`, never hard-coded numbers. That way the ESP32 swap only touches the header.
4. Add the test to the table above.

Host-side tests, such as those that talk to the MKS drivers through the USB-CAN adapter, will go in a `host/` folder once we write the first one.
