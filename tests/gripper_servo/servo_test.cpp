// Gripper servo bench test.
// Drives the gripper servo from serial commands so you can confirm it moves
// and find the jaw limits. The CAN module stays wired but idle.
// Procedure: tests/gripper_servo/README.md
//
// Serial 115200. Commands (send with Enter):
//   <angle>      move to angle, e.g. 95 (clamped to soft limits)
//   + / -        nudge 1 deg; +5 / -5 nudges 5
//   s            sweep between soft limits     x   stop
//   l <min> <max> set soft limits (0..180)     r   reset limits to jaw range
//   d            detach (servo goes limp)      a   attach again
//   p            print status                  h   help

#include <Arduino.h>
#include <arctos_board.h>

// Soft limits default to the measured jaw range (config/config_gripper.yaml);
// widen with `l` only to re-measure.
const int DEFAULT_MIN = min(GRIPPER_SERVO_ANGLE_CLOSED, GRIPPER_SERVO_ANGLE_OPEN);
const int DEFAULT_MAX = max(GRIPPER_SERVO_ANGLE_CLOSED, GRIPPER_SERVO_ANGLE_OPEN);
const int START_ANGLE = GRIPPER_SERVO_ANGLE_HOME;
const int HARD_MIN = 0;
const int HARD_MAX = 180;

static_assert(GRIPPER_SERVO_ANGLE_CLOSED >= HARD_MIN && GRIPPER_SERVO_ANGLE_CLOSED <= HARD_MAX &&
                  GRIPPER_SERVO_ANGLE_OPEN >= HARD_MIN && GRIPPER_SERVO_ANGLE_OPEN <= HARD_MAX,
              "jaw limits in config_gripper.yaml must be 0..180");
static_assert((GRIPPER_SERVO_ANGLE_HOME - GRIPPER_SERVO_ANGLE_CLOSED) *
                      (GRIPPER_SERVO_ANGLE_HOME - GRIPPER_SERVO_ANGLE_OPEN) <= 0,
              "angle_home in config_gripper.yaml must lie between angle_closed and angle_open");

const unsigned long STEP_INTERVAL_MS = 15;  // 1 deg per step, ~65 deg/s: slow enough to stop before a stall
const unsigned long SWEEP_DWELL_MS = 500;   // pause at each end of a sweep
const unsigned long LINE_TIMEOUT_MS = 50;   // lets "No line ending" serial monitors work too

Servo servo;
int limitMin = DEFAULT_MIN;
int limitMax = DEFAULT_MAX;
int current = START_ANGLE;  // last angle written to the servo
int target = START_ANGLE;
bool attached = false;
bool sweeping = false;
unsigned long lastStepMs = 0;
unsigned long dwellUntilMs = 0;

char line[24];
uint8_t lineLen = 0;
unsigned long lastCharMs = 0;

int clampToLimits(int angle) {
  if (angle < limitMin) return limitMin;
  if (angle > limitMax) return limitMax;
  return angle;
}

void printHelp() {
  Serial.println(F("Commands:"));
  Serial.println(F("  <angle>        move to angle (clamped to soft limits)"));
  Serial.println(F("  + / -          nudge 1 deg   (+5 / -5 nudges 5)"));
  Serial.println(F("  s / x          start / stop sweep between soft limits"));
  Serial.println(F("  l <min> <max>  set soft limits, 0..180"));
  Serial.println(F("  r              reset soft limits to defaults"));
  Serial.println(F("  d / a          detach (limp) / attach"));
  Serial.println(F("  p              status"));
  Serial.println(F("  h              this help"));
}

void printStatus() {
  Serial.print(F("angle "));
  Serial.print(current);
  if (target != current) {
    Serial.print(F(" -> "));
    Serial.print(target);
  }
  Serial.print(F("  limits "));
  Serial.print(limitMin);
  Serial.print(F(".."));
  Serial.print(limitMax);
  if (sweeping) Serial.print(F("  sweeping"));
  Serial.println(attached ? F("  attached") : F("  DETACHED"));
}

void attachServo() {
  servo.write(current);  // set the first pulse before attaching so the servo doesn't jump elsewhere first
  servo.attach(GRIPPER_PIN_SERVO, GRIPPER_SERVO_PULSE_MIN_US, GRIPPER_SERVO_PULSE_MAX_US);
  servo.write(current);
  attached = true;
}

void moveTo(int angle) {
  sweeping = false;
  int clamped = clampToLimits(angle);
  if (clamped != angle) {
    Serial.print(F("clamped to "));
    Serial.print(clamped);
    Serial.println(F(" (outside soft limits; widen with l <min> <max>)"));
  }
  target = clamped;
  if (!attached) Serial.println(F("servo is detached; send a to attach"));
  printStatus();
}

void startSweep() {
  sweeping = true;
  dwellUntilMs = millis();
  target = (current < limitMax) ? limitMax : limitMin;
  printStatus();
}

void setLimits(int lo, int hi) {
  if (lo < HARD_MIN || hi > HARD_MAX || lo >= hi) {
    Serial.println(F("limits must satisfy 0 <= min < max <= 180"));
    return;
  }
  limitMin = lo;
  limitMax = hi;
  target = clampToLimits(target);
  printStatus();
}

void handleLine(char *cmd) {
  while (*cmd == ' ') cmd++;
  if (*cmd == '\0') return;
  char c = tolower(cmd[0]);

  if (isdigit(c)) {
    moveTo(atoi(cmd));
  } else if (c == '+' || c == '-') {
    int step = isdigit(cmd[1]) ? atoi(cmd + 1) : 1;
    int base = sweeping ? current : target;
    moveTo(base + (c == '+' ? step : -step));
  } else if (c == 's') {
    startSweep();
  } else if (c == 'x') {
    sweeping = false;
    target = current;
    printStatus();
  } else if (c == 'l') {
    int lo, hi;
    if (sscanf(cmd + 1, "%d %d", &lo, &hi) == 2) {
      setLimits(lo, hi);
    } else {
      Serial.println(F("usage: l <min> <max>"));
    }
  } else if (c == 'r') {
    setLimits(DEFAULT_MIN, DEFAULT_MAX);
  } else if (c == 'd') {
    sweeping = false;
    target = current;
    servo.detach();
    attached = false;
    printStatus();
  } else if (c == 'a') {
    if (!attached) attachServo();
    printStatus();
  } else if (c == 'p') {
    printStatus();
  } else if (c == 'h' || c == '?') {
    printHelp();
  } else {
    Serial.print(F("unknown command: "));
    Serial.println(cmd);
  }
}

void flushLine() {
  line[lineLen] = '\0';
  if (lineLen > 0) handleLine(line);
  lineLen = 0;
}

void readSerial() {
  while (Serial.available()) {
    char ch = Serial.read();
    lastCharMs = millis();
    if (ch == '\n' || ch == '\r') {
      flushLine();
    } else if (lineLen < sizeof(line) - 1) {
      line[lineLen++] = ch;
    }
  }
  if (lineLen > 0 && millis() - lastCharMs > LINE_TIMEOUT_MS) flushLine();
}

// Steps 1 deg at a time toward target so the jaws never slam into a stop.
void updateMotion() {
  if (!attached) return;
  unsigned long now = millis();
  if ((long)(now - dwellUntilMs) < 0) return;
  if (current == target) return;
  if (now - lastStepMs < STEP_INTERVAL_MS) return;
  lastStepMs = now;

  current += (target > current) ? 1 : -1;
  servo.write(current);

  if (current == target) {
    Serial.print(F("at "));
    Serial.println(current);
    if (sweeping) {
      dwellUntilMs = now + SWEEP_DWELL_MS;
      target = (target == limitMax) ? limitMin : limitMax;
    }
  }
}

void setup() {
#ifdef ARCTOS_HAS_MCP2515
  // Keep the CAN module deselected so it stays off the SPI bus.
  pinMode(GRIPPER_PIN_MCP2515_CS, OUTPUT);
  digitalWrite(GRIPPER_PIN_MCP2515_CS, HIGH);
#endif
  Serial.begin(115200);
  attachServo();

  Serial.println();
  Serial.print(F("Arctos gripper servo test ("));
  Serial.print(F(ARCTOS_BOARD_NAME));
  Serial.print(F(", servo pin "));
  Serial.print(GRIPPER_PIN_SERVO);
  Serial.println(F(")"));
  printHelp();
  printStatus();
}

void loop() {
  readSerial();
  updateMotion();
}
