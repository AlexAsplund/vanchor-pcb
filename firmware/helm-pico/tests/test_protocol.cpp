/*
 * Host test: the vendored contract + helm extensions + control logic.
 *
 *  1. Replays every golden vector from vendor/protocol_vectors.txt through
 *     vanchorAcceptLine (the exact accept/reject gate the firmware uses) and
 *     checks the verdicts, both with and without VANCHOR_REQUIRE_CRC.
 *  2. Parses the OK vectors with the real parsers (CMD / STEERD / THRUST)
 *     and checks the decoded fields.
 *  3. Round-trips outbound A/E lines through vanchorAppendCrc and re-verifies.
 *  4. Exercises ThrustGate (reverse dead-time, slew, failsafe states),
 *     SteeringLoop (PID direction, deadband hold, feedback-lost, stall) and
 *     EncoderUnwrap (multi-turn wrap in both directions).
 *
 * Build & run:  make        (any host g++, no SDK needed)
 */
#include <assert.h>
#include <math.h>
#include <stdio.h>
#include <string.h>

#include <fstream>
#include <string>
#include <vector>

#include "../src/protocol_ext.h"   // pulls in ../vendor/vanchor_protocol.h
#include "../src/config.h"
#include "../src/control_logic.h"

static const HelmConfig DEF;  // defaults

static int g_failures = 0;
#define CHECK(cond, ...)                                   \
  do {                                                     \
    if (!(cond)) {                                         \
      g_failures++;                                        \
      printf("FAIL %s:%d  ", __FILE__, __LINE__);          \
      printf(__VA_ARGS__);                                 \
      printf("\n");                                        \
    }                                                      \
  } while (0)

// ---------------------------------------------------------------- vectors --
static void testVectors() {
  std::ifstream f("../vendor/protocol_vectors.txt");
  CHECK(f.good(), "protocol_vectors.txt not found");
  std::string raw;
  int n = 0;
  while (std::getline(f, raw)) {
    if (raw.empty() || raw[0] == '#') continue;
    size_t sp = raw.find_first_of(" \t");
    std::string verdict = raw.substr(0, sp);
    size_t body = raw.find_first_not_of(" \t", sp);
    std::string line = raw.substr(body);
    n++;

    char buf[128];
    snprintf(buf, sizeof buf, "%s", line.c_str());
    bool accepted = vanchorAcceptLine(buf);
    if (verdict == "OK")
      CHECK(accepted, "OK vector rejected: %s", line.c_str());
    else if (verdict == "BAD")
      CHECK(!accepted, "BAD vector accepted: %s", line.c_str());
    else if (verdict == "NOCRC")
#if VANCHOR_REQUIRE_CRC
      CHECK(!accepted, "NOCRC vector accepted with REQUIRE_CRC: %s",
            line.c_str());
#else
      CHECK(accepted, "NOCRC vector rejected with REQUIRE_CRC=0: %s",
            line.c_str());
#endif
    else
      CHECK(false, "unknown verdict %s", verdict.c_str());
  }
  CHECK(n >= 10, "suspiciously few vectors (%d)", n);
  printf("vectors: %d replayed\n", n);
}

// ----------------------------------------------------------- field decode --
static void testParsers() {
  int pwm, steer, seq;
  char dir;
  float deg;

  char l1[] = "CMD 128 R -100 42*7D";
  CHECK(vanchorAcceptLine(l1), "l1 gate");
  CHECK(vanchorParseCmd(l1, &pwm, &dir, &steer, &seq), "l1 parse");
  CHECK(pwm == 128 && dir == 'R' && steer == -100 && seq == 42,
        "l1 fields: %d %c %d %d", pwm, dir, steer, seq);

  char l2[] = "STEERD -35.0 42*82";
  CHECK(vanchorAcceptLine(l2), "l2 gate");
  CHECK(vanchorParseSteerDeg(l2, &deg, &seq), "l2 parse");
  CHECK(fabsf(deg + 35.0f) < 1e-4f && seq == 42, "l2 fields: %f %d",
        (double)deg, seq);

  char l3[] = "THRUST 128 F*CD";
  CHECK(vanchorAcceptLine(l3), "l3 gate");
  CHECK(vanchorParseThrust(l3, &pwm, &dir, &seq), "l3 parse");
  CHECK(pwm == 128 && dir == 'F' && seq == -1, "l3 fields: %d %c %d", pwm, dir,
        seq);

  // no-seq CMD -> seq -1; malformed rejected wholesale
  char l4[] = "CMD 0 F 0*DC";
  CHECK(vanchorAcceptLine(l4) && vanchorParseCmd(l4, &pwm, &dir, &steer, &seq),
        "l4");
  CHECK(seq == -1, "l4 seq %d", seq);
  char l5[] = "CMD 0 X 0";
  CHECK(!vanchorParseCmd(l5, &pwm, &dir, &steer, &seq), "l5 must not parse");
  char l6[] = "THRUSTX 1 F";
  CHECK(!vanchorParseThrust(l6, &pwm, &dir, &seq), "l6 must not parse");
}

// ------------------------------------------------------------- round trip --
static void testOutbound() {
  char fb[VANCHOR_LINE_MAX];
  snprintf(fb, sizeof fb, "A %.1f %d %d %d", -12.4, 1, -7, 42);
  vanchorAppendCrc(fb, sizeof fb);
  CHECK(strcmp(fb, "A -12.4 1 -7 42*C8") == 0, "A line CRC: %s", fb);

  snprintf(fb, sizeof fb, "E %d %c %s %d", 128, 'F', "RUN", 42);
  vanchorAppendCrc(fb, sizeof fb);
  CHECK(strcmp(fb, "E 128 F RUN 42*2E") == 0, "E line CRC: %s", fb);
}

// ------------------------------------------------------------ thrust gate --
static void testThrustGate() {
  ThrustGate g;
  uint32_t t = 1000;
  const float dt = 0.01f;

  // Ramp up under the slew limit: after 0.5 s at slew 1.0/s -> ~0.5.
  for (int i = 0; i < 50; i++) g.update(DEF, 1.0f, +1, false, t += 10, dt);
  CHECK(fabsf(g.applied - 0.5f) < 0.02f, "slew ramp: %f", (double)g.applied);
  CHECK(strcmp(g.state, "SOFTSTART") == 0, "state %s", g.state);

  // Request reverse at speed: must spin down first (REVDELAY), dir unchanged.
  for (int i = 0; i < 30; i++) g.update(DEF, 1.0f, -1, false, t += 10, dt);
  CHECK(g.appliedDir == +1, "dir flipped early");
  CHECK(strcmp(g.state, "REVDELAY") == 0, "state %s", g.state);

  // Keep asking: reaches zero, waits out the dead-time, then flips.
  for (int i = 0; i < 300; i++) g.update(DEF, 1.0f, -1, false, t += 10, dt);
  CHECK(g.appliedDir == -1, "dir did not flip after dead-time");
  CHECK(g.applied > 0.5f, "no thrust after flip: %f", (double)g.applied);

  // Failsafe: slews to zero, never flips, reports FAILSAFE.
  for (int i = 0; i < 200; i++) g.update(DEF, 1.0f, +1, true, t += 10, dt);
  CHECK(g.applied == 0.0f, "failsafe applied: %f", (double)g.applied);
  CHECK(g.appliedDir == -1, "failsafe flipped dir");
  CHECK(strcmp(g.state, "FAILSAFE") == 0, "state %s", g.state);
}

// ---------------------------------------------------------- steering loop --
static void testSteering() {
  SteeringLoop s;
  uint32_t t = 1000;

  // Error to starboard -> positive drive, at least the stiction floor.
  s.setTarget(DEF, 10.0f);
  int out = s.update(DEF, 0.0f, true, false, 0.0f, t += 2, 0.002f);
  CHECK(out >= (int)DEF.steerMinPwm, "drive toward +: %d", out);

  // Inside the deadband -> brake (0) and hold.
  s.setTarget(DEF, 0.0f);
  s.integral = 0;
  out = s.update(DEF, 0.5f, true, false, 0.0f, t += 2, 0.002f);
  CHECK(out == 0, "deadband hold: %d", out);

  // Feedback lost -> never drive.
  s.setTarget(DEF, 90.0f);
  out = s.update(DEF, 0.0f, false, false, 0.0f, t += 2, 0.002f);
  CHECK(out == 0, "drove blind: %d", out);

  // Stall: big error, no movement -> trips after STALL_TIME_MS, stops.
  SteeringLoop s2;
  s2.setTarget(DEF, 45.0f);
  uint32_t t2 = 5000;
  int last = 1;
  for (int i = 0; i < 500; i++)
    last = s2.update(DEF, 0.0f, true, false, 0.0f, t2 += 2, 0.002f);
  CHECK(s2.stalled, "stall never tripped");
  CHECK(last == 0, "still driving while stalled: %d", last);

  // Target clamped to the endstops.
  s.setTarget(DEF, 1000.0f);
  CHECK(s.targetDeg == DEF.steerRange, "endstop clamp: %f",
        (double)s.targetDeg);

  // Failsafe holds the measured angle (no drive once settled there).
  SteeringLoop s3;
  s3.setTarget(DEF, 90.0f);
  out = s3.update(DEF, 12.0f, true, true, 0.0f, 100, 0.002f);
  CHECK(out == 0, "failsafe should hold, drove %d", out);
}

// ------------------------------------------------------------- enc unwrap --
static void testUnwrap() {
  EncoderUnwrap e;
  e.feed(4090);          // prime
  e.feed(5);             // +11 across the wrap
  CHECK(e.accum == 11, "wrap fwd: %d", (int)e.accum);
  e.feed(4090);          // -11 back across
  CHECK(e.accum == 0, "wrap back: %d", (int)e.accum);
  // 0 counts offset -> 0 deg; a full electrical rev -> 360/gear.
  CHECK(fabsf(e.degrees(DEF, 0)) < 1e-3f, "zero deg");
  for (int i = 0; i < 8; i++) e.feed((uint16_t)((4090 + (i + 1) * 512) % 4096));
  CHECK(e.accum == 4096, "one rev accum: %d", (int)e.accum);
  CHECK(fabsf(e.degrees(DEF, 0) - 360.0f / DEF.encGear) < 1e-2f, "one rev deg");

  float f = thrustFreqHzForAmps(0.0f);
  CHECK(fabsf(f - 16000.0f) < 1.0f, "freq @0A: %f", (double)f);
  f = thrustFreqHzForAmps(12.5f);
  CHECK(f < 12000.0f && f > 8000.0f, "freq @12.5A: %f", (double)f);
  f = thrustFreqHzForAmps(99.0f);
  CHECK(fabsf(f - 2000.0f) < 1.0f, "freq @99A: %f", (double)f);
}

// ----------------------------------------------------------------- config --
static void testConfig() {
  HelmConfig c;

  // Every default is inside its own validation range.
  for (int i = 0; i < CONF_NKEYS; i++) {
    float v = confGet(c, i);
    CHECK(v >= CONF_KEYS[i].lo && v <= CONF_KEYS[i].hi,
          "default out of range: %s = %g", CONF_KEYS[i].name, (double)v);
  }

  // Lookup + set + clamp/reject.
  int i = confFind("steer.kp");
  CHECK(i >= 0, "steer.kp missing");
  CHECK(confSet(c, i, 8.5f) && confGet(c, i) == 8.5f, "set steer.kp");
  CHECK(!confSet(c, i, -1.0f), "negative kp accepted");
  CHECK(!confSet(c, i, 1e30f), "huge kp accepted");
  CHECK(!confSet(c, i, NAN), "NaN accepted");
  CHECK(confGet(c, i) == 8.5f, "rejected set clobbered the value");
  CHECK(confFind("bogus.key") == -1, "bogus key found");

  // Serialize round-trip: changed values survive, image is deterministic.
  confSet(c, confFind("thr.slew"), 0.5f);
  uint8_t img1[CONF_IMAGE_MAX], img2[CONF_IMAGE_MAX];
  size_t n1 = confSerialize(c, img1);
  size_t n2 = confSerialize(c, img2);
  CHECK(n1 == n2 && memcmp(img1, img2, n1) == 0, "serialize not deterministic");
  HelmConfig d;
  CHECK(confDeserialize(d, img1, n1) == CONF_NKEYS, "deserialize count");
  CHECK(d.steerKp == 8.5f && d.thrSlew == 0.5f, "round-trip values");

  // The diff guard's primitive: identical config -> identical image.
  HelmConfig e1 = d;
  uint8_t img3[CONF_IMAGE_MAX];
  confSerialize(e1, img3);
  CHECK(memcmp(img1, img3, n1) == 0, "equal cfg, different image");
  confSet(e1, confFind("steer.db"), 2.0f);
  confSerialize(e1, img3);
  CHECK(memcmp(img1, img3, n1) != 0, "changed cfg, same image");

  // Corruption and version safety.
  img1[10] ^= 0x40;
  HelmConfig f;
  CHECK(confDeserialize(f, img1, n1) == -1, "corrupt image accepted");
  CHECK(f.steerKp == STEER_KP, "corrupt image mutated config");
  img1[10] ^= 0x40;
  img1[4] ^= 0xFF;  // version
  CHECK(confDeserialize(f, img1, n1) == -1, "wrong version accepted");
  img1[4] ^= 0xFF;

  // Older (shorter) image: first two keys stored, the rest stay defaults.
  {
    uint8_t old_[CONF_IMAGE_MAX];
    uint32_t magic = CONF_MAGIC;
    uint16_t ver = CONF_VERSION, count = 2;
    memcpy(old_, &magic, 4);
    memcpy(old_ + 4, &ver, 2);
    memcpy(old_ + 6, &count, 2);
    float v0 = 9.0f, v1 = 2.5f;
    memcpy(old_ + 8, &v0, 4);
    memcpy(old_ + 12, &v1, 4);
    uint32_t crc = confCrc32(old_, 16);
    memcpy(old_ + 16, &crc, 4);
    HelmConfig g;
    CHECK(confDeserialize(g, old_, 20) == 2, "short image count");
    CHECK(g.steerKp == 9.0f && g.steerKi == 2.5f, "short image values");
    CHECK(g.steerKd == STEER_KD, "short image default tail");
  }
}

int main() {
  testVectors();
  testConfig();
  testParsers();
  testOutbound();
  testThrustGate();
  testSteering();
  testUnwrap();
  if (g_failures) {
    printf("%d FAILURE(S)\n", g_failures);
    return 1;
  }
  printf("all protocol + control-logic tests passed\n");
  return 0;
}
