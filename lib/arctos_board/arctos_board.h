// Board selection and bus IDs shared by every Arctos test.
// Per-node pins and limits come from config/config_<node>.yaml via the
// generated <node>_config.h headers. Wiring reference: docs/wiring.md.
#pragma once

#include <Arduino.h>

#if defined(ARDUINO_ARCH_AVR)
// Arduino Nano + MCP2515 (SPI)
#include <Servo.h>
#define ARCTOS_BOARD_NAME "Arduino Nano"
#define ARCTOS_HAS_MCP2515 1

#elif defined(ARDUINO_ARCH_ESP32)
// ESP32-WROOM-32U + SN65HVD230 (TWAI), planned
#include <ESP32Servo.h>
#define ARCTOS_BOARD_NAME "ESP32"
#define ARCTOS_HAS_TWAI 1

#else
#error "Unsupported board: add it to arctos_board.h and scripts/gen_config.py"
#endif

#include "gripper_config.h"

// ---- CAN bus: joint drivers (gripper ID is GRIPPER_CAN_ID) ----
constexpr uint8_t CAN_ID_JOINT_X = 0x01;  // base
constexpr uint8_t CAN_ID_JOINT_Y = 0x02;  // shoulder
constexpr uint8_t CAN_ID_JOINT_Z = 0x03;  // elbow
constexpr uint8_t CAN_ID_JOINT_A = 0x04;  // forearm roll
constexpr uint8_t CAN_ID_JOINT_B = 0x05;  // differential wrist
constexpr uint8_t CAN_ID_JOINT_C = 0x06;  // differential wrist
