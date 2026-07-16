/*
 * config.h — runtime-tunable configuration for the helm Pico.
 *
 * Every value that used to be a compile-time tuning constant lives in
 * HelmConfig; board.h now only supplies the DEFAULTS (and the pin map, which
 * is not runtime-tunable). The struct is plain floats so one generic key
 * table drives parsing, dumping, persistence and validation.
 *
 * Persistence model ("Values should only be saved if they diff"):
 *   - The serialized image is header + one float per key + CRC32.
 *   - configSerialize() builds the image; the flash layer compares it against
 *     the stored sector and skips the erase entirely when identical.
 *   - The on-flash layout is append-only: NEW keys go at the END of the
 *     table, so an image saved by an older firmware still loads (missing
 *     tail keeps defaults). Never reorder or remove keys — bump
 *     CONF_VERSION instead, which discards stored config wholesale.
 *
 * Everything here is hardware-free and exercised by tests/.
 */
#ifndef HELM_CONFIG_H
#define HELM_CONFIG_H

#include <stdint.h>
#include <string.h>

#include "board.h"

struct HelmConfig {
  // steering loop
  float steerKp = STEER_KP;
  float steerKi = STEER_KI;
  float steerKd = STEER_KD;
  float steerIlim = STEER_INTEGRAL_LIMIT;
  float steerDb = STEER_DEADBAND_DEG;
  float steerMinPwm = STEER_MIN_DRIVE_PWM;
  float steerMaxPwm = STEER_MAX_DRIVE_PWM;
  float steerRange = STEER_RANGE_DEG;
  float steerFull = STEER_FULL_SCALE_DEG;
  float stallErr = STEER_STALL_ERR_DEG;
  float stallMove = STEER_STALL_MOVE_DEG;
  float stallMs = STEER_STALL_TIME_MS;
  float stallA = STEER_STALL_CURRENT_A;
  float recenter = STEER_FAILSAFE_RECENTER;
  // encoder / hall geometry
  float encInvert = ENC_INVERT;
  float encGear = ENC_GEAR_RATIO;
  float hallDeg = HALL_ANGLE_DEG;
  // thrust
  float thrSlew = THR_SLEW_PER_S;
  float thrRevMs = THR_REVERSE_DEADTIME_MS;
  float thrHystA = THR_FREQ_HYST_A;
  // analog calibration
  float calThrVpa = THR_IS_V_PER_A;
  float calSrvVpa = SERVO_IS_V_PER_A;
  float calVbat = VBAT_SCALE;
};

struct ConfKey {
  const char *name;
  float HelmConfig::*field;
  float lo, hi;  // inclusive validation range; out-of-range is REJECTED
};

// Append-only! (see the persistence note above)
static const ConfKey CONF_KEYS[] = {
    {"steer.kp",         &HelmConfig::steerKp,    0.0f,   100.0f},
    {"steer.ki",         &HelmConfig::steerKi,    0.0f,   50.0f},
    {"steer.kd",         &HelmConfig::steerKd,    0.0f,   50.0f},
    {"steer.ilim",       &HelmConfig::steerIlim,  0.0f,   255.0f},
    {"steer.db",         &HelmConfig::steerDb,    0.1f,   45.0f},
    {"steer.minpwm",     &HelmConfig::steerMinPwm, 0.0f,  255.0f},
    {"steer.maxpwm",     &HelmConfig::steerMaxPwm, 1.0f,  255.0f},
    {"steer.range",      &HelmConfig::steerRange, 10.0f,  720.0f},
    {"steer.fullscale",  &HelmConfig::steerFull,  10.0f,  720.0f},
    {"steer.stall_err",  &HelmConfig::stallErr,   0.5f,   90.0f},
    {"steer.stall_move", &HelmConfig::stallMove,  0.1f,   45.0f},
    {"steer.stall_ms",   &HelmConfig::stallMs,    50.0f,  10000.0f},
    {"steer.stall_a",    &HelmConfig::stallA,     0.0f,   60.0f},
    {"steer.recenter",   &HelmConfig::recenter,   0.0f,   1.0f},
    {"enc.invert",       &HelmConfig::encInvert,  0.0f,   1.0f},
    {"enc.gear",         &HelmConfig::encGear,    0.01f,  100.0f},
    {"enc.hall_deg",     &HelmConfig::hallDeg,    -360.0f, 360.0f},
    {"thr.slew",         &HelmConfig::thrSlew,    0.05f,  10.0f},
    {"thr.rev_ms",       &HelmConfig::thrRevMs,   0.0f,   10000.0f},
    {"thr.hyst_a",       &HelmConfig::thrHystA,   0.5f,   20.0f},
    {"cal.thr_vpa",      &HelmConfig::calThrVpa,  0.001f, 1.0f},
    {"cal.srv_vpa",      &HelmConfig::calSrvVpa,  0.001f, 1.0f},
    {"cal.vbat",         &HelmConfig::calVbat,    1.0f,   30.0f},
};
static const int CONF_NKEYS = sizeof(CONF_KEYS) / sizeof(CONF_KEYS[0]);

// ---------------------------------------------------------------- lookup --
static inline int confFind(const char *name) {
  for (int i = 0; i < CONF_NKEYS; i++)
    if (strcmp(CONF_KEYS[i].name, name) == 0) return i;
  return -1;
}

// Set key #i with validation. Returns false (and leaves the config
// untouched) when the value is outside the key's range or not finite.
static inline bool confSet(HelmConfig &c, int i, float v) {
  if (i < 0 || i >= CONF_NKEYS) return false;
  if (!(v >= CONF_KEYS[i].lo && v <= CONF_KEYS[i].hi)) return false;  // NaN too
  c.*(CONF_KEYS[i].field) = v;
  return true;
}

static inline float confGet(const HelmConfig &c, int i) {
  return c.*(CONF_KEYS[i].field);
}

// ------------------------------------------------------------ persistence --
// Image: [magic u32][version u16][count u16][float x count][crc32 u32]
#define CONF_MAGIC   0x56484331u  // "VHC1"
#define CONF_VERSION 1
#define CONF_IMAGE_MAX (4 + 2 + 2 + 4 * 64 + 4)

static inline uint32_t confCrc32(const uint8_t *p, size_t n) {
  uint32_t crc = 0xFFFFFFFFu;
  for (size_t i = 0; i < n; i++) {
    crc ^= p[i];
    for (int b = 0; b < 8; b++)
      crc = (crc >> 1) ^ (0xEDB88320u & (0u - (crc & 1u)));
  }
  return ~crc;
}

// Serialize the whole config. Returns the image length.
static inline size_t confSerialize(const HelmConfig &c, uint8_t *out) {
  uint8_t *p = out;
  uint32_t magic = CONF_MAGIC;
  uint16_t ver = CONF_VERSION, count = (uint16_t)CONF_NKEYS;
  memcpy(p, &magic, 4); p += 4;
  memcpy(p, &ver, 2); p += 2;
  memcpy(p, &count, 2); p += 2;
  for (int i = 0; i < CONF_NKEYS; i++) {
    float v = confGet(c, i);
    memcpy(p, &v, 4); p += 4;
  }
  uint32_t crc = confCrc32(out, (size_t)(p - out));
  memcpy(p, &crc, 4); p += 4;
  return (size_t)(p - out);
}

// Load an image into `c` (on top of defaults). Unknown tail keys in a NEWER
// image are ignored; a SHORTER (older-firmware) image leaves the missing
// keys at their defaults. Each stored value passes the same validation as a
// CONF command — an out-of-range survivor of a partial write can never load.
// Returns the number of keys applied, or -1 for no/invalid image.
static inline int confDeserialize(HelmConfig &c, const uint8_t *img,
                                  size_t cap) {
  if (cap < 12) return -1;
  uint32_t magic;
  uint16_t ver, count;
  memcpy(&magic, img, 4);
  memcpy(&ver, img + 4, 2);
  memcpy(&count, img + 6, 2);
  if (magic != CONF_MAGIC || ver != CONF_VERSION) return -1;
  size_t len = 8 + 4u * count;
  if (count > 64 || len + 4 > cap) return -1;
  uint32_t want, got = confCrc32(img, len);
  memcpy(&want, img + len, 4);
  if (want != got) return -1;
  int applied = 0;
  int n = (count < CONF_NKEYS) ? count : CONF_NKEYS;
  for (int i = 0; i < n; i++) {
    float v;
    memcpy(&v, img + 8 + 4 * i, 4);
    if (confSet(c, i, v)) applied++;
  }
  return applied;
}

#endif  // HELM_CONFIG_H
