/*
 * control_logic.h — hardware-free control cores for the helm Pico.
 *
 * Everything in here is pure state-machine/math with injected time and an
 * injected HelmConfig, so the host test suite (tests/) exercises the exact
 * code that ships and the CONF machinery can retune it live:
 *
 *   ThrustGate   — engine.ino semantics: reverse dead-time interlock, slew
 *                  limit, watchdog failsafe, E-line state word.
 *   SteeringLoop — steering.ino semantics: PID + deadband + stiction floor +
 *                  stall detection + watchdog hold, on an encoder angle.
 *   EncoderUnwrap— AS5600 12-bit raw -> continuous multi-turn angle.
 *
 * The protocol constants (watchdog window etc.) come from the vendored
 * vanchor_protocol.h so firmware and contract cannot drift apart.
 */
#ifndef HELM_CONTROL_LOGIC_H
#define HELM_CONTROL_LOGIC_H

#include <math.h>
#include <stdint.h>

#include "board.h"
#include "config.h"

// ------------------------------------------------------------------------ //
// Thrust: reverse gate + slew (port of engine.ino, output-stage agnostic)
// ------------------------------------------------------------------------ //
struct ThrustGate {
  float applied = 0.0f;      // 0..1 magnitude currently at the bridge
  int8_t appliedDir = +1;    // +1 F, -1 R — direction the bridge is set to
  uint32_t zeroSinceMs = 0;  // when |applied| last fell to ~0 (0 = "not yet")

  const char *state = "RUN"; // E-line state word for the last update

  // One control tick. wantMag/wantDir are the *requested* throttle; failsafe
  // forces a slewed stop without flipping direction (engine.ino behaviour).
  // Returns the magnitude to output; appliedDir is the direction to output.
  float update(const HelmConfig &cfg, float wantMag, int8_t wantDir,
               bool failsafe, uint32_t nowMs, float dtS) {
    if (failsafe) {
      wantMag = 0.0f;
      wantDir = appliedDir;  // never flip while blind; just stop
    }
    if (wantMag < 0.0f) wantMag = 0.0f;
    if (wantMag > 1.0f) wantMag = 1.0f;

    // --- reverse dead-time interlock -------------------------------------
    bool nearZero = (applied <= THR_ZERO_EPS);
    if (nearZero) {
      if (zeroSinceMs == 0) zeroSinceMs = nowMs ? nowMs : 1;
    } else {
      zeroSinceMs = 0;
    }
    float allowed = wantMag;
    if (wantDir != appliedDir) {
      if (!nearZero) {
        allowed = 0.0f;                       // spin down first
      } else if (zeroSinceMs == 0 ||
                 (nowMs - zeroSinceMs) < (uint32_t)cfg.thrRevMs) {
        allowed = 0.0f;                       // rest at zero, keep waiting
      } else {
        appliedDir = wantDir;                 // safe to flip now
      }
    }

    // --- slew limit -------------------------------------------------------
    float maxStep = cfg.thrSlew * dtS;
    float delta = allowed - applied;
    if (delta > maxStep) delta = maxStep;
    if (delta < -maxStep) delta = -maxStep;
    applied += delta;
    if (applied < 0.0f) applied = 0.0f;
    if (applied > 1.0f) applied = 1.0f;

    state = failsafe                        ? "FAILSAFE"
            : (allowed < wantMag - 0.001f)  ? "REVDELAY"
            : (applied + 0.001f < allowed)  ? "SOFTSTART"
                                            : "RUN";
    return applied;
  }
};

// ------------------------------------------------------------------------ //
// Thrust PWM frequency schedule (boards/thrust-driver/README.md)
// ------------------------------------------------------------------------ //
// Piecewise-linear current -> frequency, with hysteresis applied by the
// caller (only retune when the ideal frequency moved by more than the band).
static inline float thrustFreqHzForAmps(float amps) {
  static const float A[] = {0, 5, 10, 15, 20, 25, 30, 40, 50};
  static const float K[] = {16, 16, 12, 8, 6, 5, 4, 3, 2};  // kHz
  const int n = sizeof(A) / sizeof(A[0]);
  if (amps <= A[0]) return K[0] * 1000.0f;
  for (int i = 1; i < n; i++) {
    if (amps <= A[i]) {
      float t = (amps - A[i - 1]) / (A[i] - A[i - 1]);
      return (K[i - 1] + t * (K[i] - K[i - 1])) * 1000.0f;
    }
  }
  return K[n - 1] * 1000.0f;
}

// ------------------------------------------------------------------------ //
// AS5600 raw counts -> continuous angle (multi-turn unwrap)
// ------------------------------------------------------------------------ //
struct EncoderUnwrap {
  int32_t accum = 0;       // continuous counts since boot
  uint16_t prevRaw = 0;
  bool primed = false;

  void feed(uint16_t raw12) {
    raw12 &= 0x0FFF;
    if (!primed) {
      prevRaw = raw12;
      primed = true;
      return;
    }
    int16_t d = (int16_t)(((raw12 - prevRaw + ENC_COUNTS_PER_REV / 2) &
                           (ENC_COUNTS_PER_REV - 1)) -
                          ENC_COUNTS_PER_REV / 2);
    accum += d;
    prevRaw = raw12;
  }

  // Continuous azimuth degrees relative to `zeroAccum` counts.
  float degrees(const HelmConfig &cfg, int32_t zeroAccum) const {
    float revs = (float)(accum - zeroAccum) / (float)ENC_COUNTS_PER_REV;
    float deg = revs * 360.0f / cfg.encGear;
    if (cfg.encInvert >= 0.5f) deg = -deg;
    return deg;
  }
};

// ------------------------------------------------------------------------ //
// Steering: PID + stall + failsafe hold (port of steering.ino updateControl)
// ------------------------------------------------------------------------ //
struct SteeringLoop {
  float targetDeg = 0.0f;
  float integral = 0.0f;
  float prevErr = 0.0f;

  float stallRefDeg = 0.0f;
  uint32_t stallSinceMs = 0;
  bool stalled = false;

  void setTarget(const HelmConfig &cfg, float deg) {
    if (deg > cfg.steerRange) deg = cfg.steerRange;
    if (deg < -cfg.steerRange) deg = -cfg.steerRange;
    targetDeg = deg;
  }

  // One tick. Returns the signed drive (-255..255 scale; 0 = brake/hold).
  // `servoAmps` feeds the optional current stall trip (cfg.stallA 0 = off).
  int update(const HelmConfig &cfg, float angleDeg, bool feedbackOk,
             bool failsafe, float servoAmps, uint32_t nowMs, float dtS) {
    float target = targetDeg;
    if (failsafe) {
      if (cfg.recenter >= 0.5f)
        target = 0.0f;
      else
        target = angleDeg;  // hold right here; the worm self-locks
    }
    if (target > cfg.steerRange) target = cfg.steerRange;
    if (target < -cfg.steerRange) target = -cfg.steerRange;

    float err = target - angleDeg;

    int out = 0;
    if (!feedbackOk) {
      integral = 0.0f;           // never drive blind
      stalled = false;
      stallSinceMs = 0;
    } else if (fabsf(err) <= cfg.steerDb) {
      integral *= 0.5f;          // bleed; worm holds
      stallSinceMs = 0;
      stalled = false;
      stallRefDeg = angleDeg;
    } else {
      integral += err * dtS;
      float iTerm = cfg.steerKi * integral;
      if (iTerm > cfg.steerIlim) {
        iTerm = cfg.steerIlim;
        if (cfg.steerKi > 0.0f) integral = iTerm / cfg.steerKi;
      }
      if (iTerm < -cfg.steerIlim) {
        iTerm = -cfg.steerIlim;
        if (cfg.steerKi > 0.0f) integral = iTerm / cfg.steerKi;
      }
      float dTerm = (dtS > 0.0f) ? cfg.steerKd * (err - prevErr) / dtS : 0.0f;
      float pid = cfg.steerKp * err + iTerm + dTerm;

      int minPwm = (int)cfg.steerMinPwm, maxPwm = (int)cfg.steerMaxPwm;
      int signedPwm = (int)pid;
      if (signedPwm > 0 && signedPwm < minPwm) signedPwm = minPwm;
      if (signedPwm < 0 && signedPwm > -minPwm) signedPwm = -minPwm;
      if (signedPwm > maxPwm) signedPwm = maxPwm;
      if (signedPwm < -maxPwm) signedPwm = -maxPwm;

      // --- stall detection ------------------------------------------------
      bool currentStall = (cfg.stallA > 0.0f) && (servoAmps > cfg.stallA);
      if (fabsf(err) > cfg.stallErr) {
        if (fabsf(angleDeg - stallRefDeg) > cfg.stallMove) {
          stallRefDeg = angleDeg;  // moving; reset the stall clock
          stallSinceMs = nowMs;
          stalled = false;
        } else {
          if (stallSinceMs == 0) stallSinceMs = nowMs ? nowMs : 1;
          if ((nowMs - stallSinceMs) > (uint32_t)cfg.stallMs || currentStall)
            stalled = true;
        }
      } else {
        stallSinceMs = 0;
        stalled = false;
        stallRefDeg = angleDeg;
      }

      if (stalled) {
        integral = 0.0f;  // anti-windup on a jam/endstop
      } else {
        out = signedPwm;
      }
    }
    prevErr = err;
    return out;
  }
};

#endif  // HELM_CONTROL_LOGIC_H
