// GENERATED from config/config_joints.yaml by scripts/gen_config.py. Do not edit;
// change the YAML and rebuild (or run the script).
#pragma once

#include <stdint.h>

constexpr uint32_t JOINTS_X_CAN_ID = 0x01;
constexpr char JOINTS_X_NAME[] = "base";
constexpr uint32_t JOINTS_Y_CAN_ID = 0x02;
constexpr char JOINTS_Y_NAME[] = "shoulder";
constexpr uint32_t JOINTS_Z_CAN_ID = 0x03;
constexpr char JOINTS_Z_NAME[] = "elbow";
constexpr uint32_t JOINTS_A_CAN_ID = 0x04;
constexpr char JOINTS_A_NAME[] = "forearm roll";
constexpr uint32_t JOINTS_B_CAN_ID = 0x05;
constexpr char JOINTS_B_NAME[] = "wrist B (differential)";
constexpr char JOINTS_B_LOCATION[] = "left motor";
constexpr char JOINTS_B_DRIVER[] = "MKS SERVO42D";
constexpr float JOINTS_B_GEAR_RATIO = 67.82f;
constexpr char JOINTS_B_MENU_MODE[] = "SR_vFOC";
constexpr char JOINTS_B_MENU_CAN_RATE[] = "500K";
constexpr long JOINTS_B_MENU_CURRENT_MA = 1600;
constexpr long JOINTS_B_MENU_MICROSTEPS = 16;
constexpr char JOINTS_B_SENSORS_EN[] = "top hall (home)";
constexpr char JOINTS_B_SENSORS_DIR[] = "bottom hall (end limit)";
constexpr uint32_t JOINTS_C_CAN_ID = 0x06;
constexpr char JOINTS_C_NAME[] = "wrist C (differential)";
constexpr char JOINTS_C_LOCATION[] = "right motor";
constexpr char JOINTS_C_DRIVER[] = "MKS SERVO42D";
constexpr float JOINTS_C_GEAR_RATIO = 67.82f;
constexpr char JOINTS_C_MENU_MODE[] = "SR_vFOC";
constexpr char JOINTS_C_MENU_CAN_RATE[] = "500K";
constexpr long JOINTS_C_MENU_CURRENT_MA = 1600;
constexpr long JOINTS_C_MENU_MICROSTEPS = 16;
constexpr char JOINTS_C_SENSORS_EN[] = "north pole (home)";
constexpr char JOINTS_C_SENSORS_DIR[] = "south pole (end limit)";
