// GENERATED from config/config_gripper.yaml by scripts/gen_config.py. Do not edit;
// change the YAML and rebuild (or run the script).
#pragma once

#include <stdint.h>

constexpr uint32_t GRIPPER_CAN_ID = 0x07;
// GRIPPER_CAN_BITRATE: unset (null in config)
constexpr char GRIPPER_SERVO_MODEL[] = "DS3230MG";
constexpr float GRIPPER_SERVO_SUPPLY_VOLTS = 6.0f;
constexpr long GRIPPER_SERVO_ANGLE_CLOSED = 65;
constexpr long GRIPPER_SERVO_ANGLE_OPEN = 115;
constexpr long GRIPPER_SERVO_ANGLE_HOME = 90;
constexpr long GRIPPER_SERVO_PULSE_MIN_US = 544;
constexpr long GRIPPER_SERVO_PULSE_MAX_US = 2400;

#if defined(ARDUINO_ARCH_AVR)  // nano
constexpr uint8_t GRIPPER_PIN_SERVO = 9;
constexpr uint8_t GRIPPER_PIN_MCP2515_CS = 10;
constexpr uint8_t GRIPPER_PIN_MCP2515_INT = 2;
// GRIPPER_MCP2515_CRYSTAL_MHZ: unset (null in config)
#elif defined(ARDUINO_ARCH_ESP32)  // esp32
constexpr uint8_t GRIPPER_PIN_SERVO = 18;
constexpr uint8_t GRIPPER_PIN_TWAI_TX = 5;
constexpr uint8_t GRIPPER_PIN_TWAI_RX = 4;
#else
#error "No gripper config for this board: add it under boards: in config/config_gripper.yaml"
#endif
