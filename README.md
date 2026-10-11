# Arctos test bench

Component bring-up tests for an Arctos 6-axis arm (CAN-bus closed-loop build):

- MKS closed-loop stepper drivers on joints X–C (CAN IDs 0x01–0x06)
- A servo gripper on its own CAN node (ID 0x07)
- That node is an Arduino Nano + MCP2515 today, and will move to an ESP32 + SN65HVD230 later.

## Layout

```
config/config_*.yaml           pins, CAN IDs, limits: the one place to change them
docs/wiring.md                 wiring, power, CAN termination, open questions, status
artifact/images/               official Arctos closed-loop wiring diagram
lib/arctos_board/              board selection + headers generated from config/ (firmware)
host/arctos_host/              Python CAN bus + MKS driver protocol (PC-side tests)
scripts/gen_config.py          YAML -> C++ header generator, runs before every build
tests/                         one folder per component test, see tests/README.md
platformio.ini                 one build env per firmware test per board
```

## Setup

Install PlatformIO, either the VS Code extension or the CLI:

```sh
brew install platformio      # or: pipx install platformio
```

For the PC-side tests that talk to the MKS drivers over the USB-CAN adapter, run this once:

```sh
python3 -m venv .venv && .venv/bin/pip install -r host/requirements.txt
```

## Running a test

Each test's README has the full procedure. The general pattern:

```sh
pio run -e gripper_servo_nano -t upload     # build + flash
pio device monitor -e gripper_servo_nano    # serial console (Ctrl-C to quit)
```

To target the ESP32 later, use the `_esp32` env of the same test. The pin map switches automatically in `lib/arctos_board/arctos_board.h`.

## Start here

1. [`tests/gripper_servo/`](tests/gripper_servo/README.md): the gripper servo sweep and jaw limits (passed)
2. [`tests/joint_bc/`](tests/joint_bc/README.md): wrist B/C drivers, motors, hall sensors and differential
