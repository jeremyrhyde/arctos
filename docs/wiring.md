# Arctos robot arm: wiring and firmware context

Handoff notes for writing firmware. Hardware is wired per the official Arctos Cirkit Designer diagram, with the corrections noted below.

## System overview

- **Arm:** Arctos 6-axis, 3D-printed, CAN-bus closed-loop version.
- **Joint drivers:** MKS closed-loop stepper drivers on a shared CAN bus.
  - X (base), Y (shoulder), Z (elbow): CAN IDs 0x01, 0x02, 0x03
  - A (forearm roll): 0x04
  - B, C (differential wrist): 0x05, 0x06. These are MKS SERVO42D on NEMA 17.
- **Gripper:** its own CAN node, **ID 0x07**. An Arduino Nano with an MCP2515 module drives a hobby servo.
- **Host:** PC (macOS) connects to the bus through a USB-CAN adapter.

### Differential wrist (B and C)

B and C drive a bevel-gear differential, so they are coupled:

- pitch = (θB + θC) / 2
- roll = (θB − θC) / 2 × gear ratio
- Inverse: θB = pitch + roll, θC = pitch − roll

Motor direction (the MKS `Dir` setting) must be set so equal positive moves on B and C produce pure pitch. Not yet verified on hardware.

## Power

- **24 V PSU → rocker switch → 24 V bus.**
  - Daisy-chained to all six MKS drivers with the provided 18 AWG wire.
  - Split with lever connectors (WAGO 221 style).
- **Buck converter** (LM2596/XL4015-style module with display), fed from the switched 24 V.
  - Output set and verified at **6.02 V**, measured with a multimeter, no load.
  - **Diagram correction:** the official diagram does not show a ground into the buck's IN−. It is wired PSU − → buck IN−.
- **Common ground:** buck OUT− goes to the servo GND, Nano GND and MCP2515 GND. All grounds are shared with the PSU.
- **Fans (2):** planned, not yet wired. Voltage not yet confirmed.
  - If 24 V: in parallel on the 24 V bus, after the switch.
  - If 12 V: they need their own 12 V buck.

## Gripper node wiring (Nano + MCP2515 + servo)

| From | To | Notes |
|---|---|---|
| Buck OUT+ (6 V) | Nano **VIN** | Not the 5V pin |
| Buck OUT− | Nano GND | Common ground |
| Nano 5V | MCP2515 VCC | MCP powered from the Nano's regulator |
| Nano GND | MCP2515 GND | |
| Nano D10 | MCP2515 CS | |
| Nano D11 | MCP2515 SI (MOSI) | |
| Nano D12 | MCP2515 SO (MISO) | |
| Nano D13 | MCP2515 SCK | |
| Nano D2 | MCP2515 INT | |
| Buck OUT+ (6 V) | Servo red wire (V+) | Servo powered directly from the buck, not from the Nano |
| Buck OUT− | Servo brown/black wire (GND) | |
| Nano **D9** | Servo signal wire | Assumed pin; must match the firmware |
| MCP2515 CANH/CANL | CAN bus | |

## CAN bus

- Topology: a single daisy-chained bus.
  - USB-CAN adapter ↔ joint drivers X…C ↔ gripper MCP2515
- **Termination is at the two physical ends only:**
  - USB-CAN adapter: "120R" jumper on.
  - MCP2515: **J1 jumper on**.
  - **No termination on any MKS driver,** including joint C.
- Check: with power off, CANH–CANL should read about 60 Ω.

## Status

- [x] Buck set to 6 V and verified
- [x] Gripper node wired (Nano power, MCP2515 SPI, servo)
- [x] Servo-only test (`tests/gripper_servo/`) loaded and confirmed sweeping
  - Sweep between the jaw limits on D9
  - Serial at 115200 baud: send an angle, or `s` to sweep
- [x] Gripper jaw limits found (DS3230MG, 2026-10-11): hard stops at 60° closed and 120° open; **working range 65° closed to 115° open**. Stored in `config/config_gripper.yaml`.
- [ ] Gripper CAN firmware
- [ ] MKS drivers configured (mode `SR_vFOC`, CAN IDs, bitrate, current, direction) and tested over CAN
- [ ] B/C differential direction verified (equal moves give pure pitch)

## Firmware task: gripper CAN node (Nano + MCP2515)

Goal: the Nano listens on the CAN bus for frames addressed to **ID 0x07** and drives the servo to the commanded position.

Requirements:

- **Library:** use an MCP2515 Arduino library (for example `mcp_can` or `arduino-mcp2515`), with CS on D10 and INT on D2.
- **Bitrate:** must match the MKS drivers and the USB-CAN adapter. 500 kbps is the common default.
- **Crystal:** must match the MCP2515 module's crystal. Check whether it's marked 8 MHz or 16 MHz, because using the wrong setting breaks timing.
- **Servo:** use the `Servo` library on D9.
  - Clamp commands to the measured jaw limits so the servo never stalls against the jaws.
- **Message format:** match whatever the Arctos control software sends to the gripper. Check the official Arctos gripper sketch or GUI source first and keep compatibility with it.
- **Debugging:** optional serial output at 115200 baud showing received frames.

### Open questions to resolve before or while coding

1. Is the MCP2515 crystal 8 MHz or 16 MHz?
2. What is the CAN bitrate configured on the MKS drivers and the adapter?
3. What payload format does the Arctos software send to ID 0x07?
4. ~~What are the measured open and closed servo angles?~~ Hard stops at 60° closed and 120° open; working range 65–115°.
5. Is D9 the servo pin, or does the reference sketch use another?

## Planned later: swap the gripper node to an ESP32

- **Board:** ESP32-WROOM-32U dev board.
- **CAN:** use the ESP32's built-in CAN controller (TWAI) with an **SN65HVD230 3.3 V transceiver**, which needs to be ordered.
  - Don't connect the 5 V MCP2515 module to the ESP32. Its 5 V signals can damage the 3.3 V pins.
- **Termination:** the transceiver's onboard 120 Ω resistor replaces the J1 jumper.
- **Suggested pins:** TWAI TX on GPIO 5, TWAI RX on GPIO 4, servo on GPIO 18 using `ESP32Servo`.
  - Avoid GPIO 0, 2, 12 and 15 (they affect boot).
  - GPIO 34–39 are input-only.
- **Power:** 6 V from the buck into the board's 5V/VIN pin. Check the board's regulator first.
- **Firmware:** port the gripper sketch to the ESP32 TWAI driver, keeping the same message format and ID 0x07.
