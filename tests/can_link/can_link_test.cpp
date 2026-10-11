// CAN link test: Nano + MCP2515 <-> USB-CAN adapter.
// Finds the MCP2515 crystal (unless set in config_gripper.yaml), then prints every
// frame it receives and sends a heartbeat on GRIPPER_CAN_ID once a second.
// Procedure: tests/can_link/README.md
//
// Serial 115200 output:
//   link up: 500000 bps, 8 MHz crystal    MCP2515 talking and frames are being ACKed
//   rx id=0x007 dlc=3 data=C0 DE 01       a frame received from the bus
//   tx errors: TEC=128 flags=0x15         frames not ACKed (wiring, termination, adapter closed)

#include <Arduino.h>
#include <SPI.h>
#include <mcp2515.h>
#include <arctos_board.h>

#ifndef ARCTOS_HAS_MCP2515
#error "can_link test needs the MCP2515 gripper node (Nano)"
#endif

static_assert(CAN_BITRATE == 125000 || CAN_BITRATE == 250000 || CAN_BITRATE == 500000 ||
                  CAN_BITRATE == 1000000,
              "config_can.yaml bitrate must be 125000, 250000, 500000 or 1000000");
static_assert(GRIPPER_MCP2515_CRYSTAL_MHZ == 0 || GRIPPER_MCP2515_CRYSTAL_MHZ == 8 ||
                  GRIPPER_MCP2515_CRYSTAL_MHZ == 16,
              "config_gripper.yaml mcp2515_crystal_mhz must be 0 (auto), 8 or 16");

const unsigned long HEARTBEAT_MS = 1000;
const unsigned long RETRY_MS = 2000;

MCP2515 mcp(GRIPPER_PIN_MCP2515_CS);
bool linkUp = false;
uint16_t heartbeatCount = 0;
unsigned long lastHeartbeatMs = 0;
unsigned long lastRetryMs = 0;
uint8_t lastTec = 0;

CAN_SPEED bitrateSetting() {
  switch (CAN_BITRATE) {
    case 125000: return CAN_125KBPS;
    case 250000: return CAN_250KBPS;
    case 1000000: return CAN_1000KBPS;
    default: return CAN_500KBPS;
  }
}

void sendHeartbeat() {
  can_frame frame;
  frame.can_id = GRIPPER_CAN_ID;
  frame.can_dlc = 4;
  frame.data[0] = 'H';
  frame.data[1] = 'B';
  frame.data[2] = heartbeatCount >> 8;
  frame.data[3] = heartbeatCount & 0xFF;
  heartbeatCount++;
  mcp.sendMessage(&frame);
}

// Configure for one crystal and send a few frames. With the right crystal (and the
// adapter open on the bus) they are ACKed and the TX error counter stays at 0.
bool tryCrystal(int mhz) {
  mcp.reset();
  if (mcp.setBitrate(bitrateSetting(), mhz == 8 ? MCP_8MHZ : MCP_16MHZ) != MCP2515::ERROR_OK) return false;
  mcp.setNormalMode();
  for (int i = 0; i < 3; i++) {
    sendHeartbeat();
    delay(30);
  }
  return mcp.errorCountTX() == 0;
}

void bringUpLink() {
  const int candidates[] = {8, 16};
  for (int mhz : candidates) {
    if (GRIPPER_MCP2515_CRYSTAL_MHZ != 0 && mhz != GRIPPER_MCP2515_CRYSTAL_MHZ) continue;
    if (tryCrystal(mhz)) {
      linkUp = true;
      lastTec = 0;
      Serial.print(F("link up: "));
      Serial.print(CAN_BITRATE);
      Serial.print(F(" bps, "));
      Serial.print(mhz);
      Serial.println(F(" MHz crystal"));
      return;
    }
  }
  Serial.println(F("no ACK from the bus (is the adapter open? CANH/CANL? termination?); retrying"));
}

void printFrame(const can_frame &frame) {
  Serial.print(F("rx id=0x"));
  if (frame.can_id < 0x100) Serial.print('0');
  if (frame.can_id < 0x10) Serial.print('0');
  Serial.print(frame.can_id, HEX);
  Serial.print(F(" dlc="));
  Serial.print(frame.can_dlc);
  Serial.print(F(" data="));
  for (uint8_t i = 0; i < frame.can_dlc; i++) {
    if (frame.data[i] < 0x10) Serial.print('0');
    Serial.print(frame.data[i], HEX);
    if (i + 1 < frame.can_dlc) Serial.print(' ');
  }
  Serial.println();
}

void setup() {
  Serial.begin(115200);
  Serial.println();
  Serial.println(F("Arctos CAN link test (Nano + MCP2515)"));
  SPI.begin();
  bringUpLink();
  lastRetryMs = millis();
}

void loop() {
  unsigned long now = millis();

  if (!linkUp) {
    if (now - lastRetryMs >= RETRY_MS) {
      lastRetryMs = now;
      bringUpLink();
    }
    return;
  }

  can_frame frame;
  while (mcp.readMessage(&frame) == MCP2515::ERROR_OK) printFrame(frame);

  if (now - lastHeartbeatMs >= HEARTBEAT_MS) {
    lastHeartbeatMs = now;
    sendHeartbeat();
  }

  uint8_t tec = mcp.errorCountTX();
  if (tec != lastTec) {
    lastTec = tec;
    Serial.print(F("tx errors: TEC="));
    Serial.print(tec);
    Serial.print(F(" flags=0x"));
    Serial.println(mcp.getErrorFlags(), HEX);
  }
}
