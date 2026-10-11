# Test: CAN link (adapter ↔ gripper node)

Proves the CAN bus works end to end before any motors are involved. The PC's USB-CAN adapter and the Nano's MCP2515 exchange frames in both directions. This test also finds the MCP2515's crystal frequency.

| | |
|---|---|
| **Nodes** | USB-CAN adapter (CANable 2.0, slcan) and the gripper node (Nano + MCP2515, CAN ID 0x07) |
| **Firmware** | [`can_link_test.cpp`](can_link_test.cpp), env `can_link_nano` |
| **Host script** | [`can_link_test.py`](can_link_test.py) |
| **Needs 24 V?** | No. The MCP2515 runs from the Nano's USB power. |
| **Unblocks** | Gripper CAN firmware, and the confidence that the bus works before debugging the MKS drivers |

## Wiring

- Adapter CANH to MCP2515 H, and adapter CANL to MCP2515 L.
- The MCP2515's **J1** jumper must be on.
- A ground wire isn't needed while both the Nano and the adapter are plugged into the same Mac.
- Both USB cables go into the Mac: the Nano's and the adapter's.

## Run

1. Close any serial monitor that's open on the Nano.
2. Flash and run:
   ```sh
   pio run -e can_link_nano -t upload
   .venv/bin/python tests/can_link/can_link_test.py
   ```

The script opens the adapter first, then the Nano's serial port, which resets the Nano. The Nano then:

1. finds the crystal (or uses `mcp2515_crystal_mhz` from `config_gripper.yaml`, if that isn't 0)
2. sends a heartbeat frame on 0x07 every second
3. prints every frame it receives

The script checks both directions and prints a PASS/FAIL table.

To put the servo test back on the Nano afterward: `pio run -e gripper_servo_nano -t upload`.

## Pass criteria

- [ ] `link up` appears on the Nano's output, along with the crystal frequency.
- [ ] Nano → PC: the PC receives heartbeats.
- [ ] PC → Nano: all 5 test frames are received.

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `no ACK from the bus` repeating | H and L are swapped or loose, J1 is off, or the adapter isn't open. The script opens it. |
| `Nano not found` | The Nano's USB cable isn't plugged in, or another program has the port open |
| Link up, but no heartbeats reach the PC | The adapter's bitrate doesn't match. Check `config_can.yaml`. |
| `tx errors: TEC=…` climbing after link up | The bus became disconnected mid-test, or termination is marginal |

## Results

| Date | Crystal | Nano → PC | PC → Nano | Notes |
|---|---|---|---|---|
| 2026-10-11 | 8 MHz | PASS | PASS (5/5) | Adapter ↔ MCP2515 only; J1 on, no adapter-end terminator, no ground wire |
