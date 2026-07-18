# Lessons from ArduPilot and pypilot (firmware + electronics)

Researched 2026-07-19 against our helm-pico firmware and both boards.
pypilot is the closest cousin (Raspberry Pi autopilot + Arduino motor
controller over serial, marine, same problem shape as vanchor); ArduPilot
is the reliability benchmark. Below: what they do, what we already match,
and a prioritized punch list of what's worth stealing.

## 1. pypilot — firmware lessons

**Protocol & link.** Binary 4-byte frames with CRC-8 at 38400; the
firmware *waits for several consecutive valid frames before recognizing
commands at all* (noise can't twitch the motor at plug-in), and a **250 ms
serial timeout disengages** (vs our 800 ms contract watchdog). Our CRC
gate + enables-low-until-first-valid-command is the same idea; their
sync-window is stricter.

**Fault model — the biggest gap for us.** The controller continuously
reports FLAGS with a rich vocabulary:

- `OVERCURRENT_FAULT`, and **directional** `PORT/STARBOARD_OVERCURRENT` —
  a stall inhibits *further motion in that direction only*; the way back
  is always allowed. Our stall detection stops the whole servo drive.
- `DRIVER_TIMEOUT` — commanded, but **no current observed**: catches a
  broken motor wire / dead bridge, the failure our loop can't currently
  see (we'd just report a steering stall eventually).
- `SATURATED` — commanded faster than the drive can move ("a faster motor
  would improve steering"): performance telemetry, not a fault.
- Overvoltage, controller-overtemp, motor-overtemp (10 k NTC, 60–70 °C
  typical), fuse-corruption (`BAD_FUSES`) flags.

**Stall-vs-feedback philosophy.** Rudder feedback is *optional* and can
fail underway; current-based stall detection is the primary protection and
`max_current` is "the critical first tuning parameter" (4–7 A tiller,
15–20 A hydraulic). Validates our choice to keep `steer.stall_a` runtime-
tunable — but theirs defaults ON, ours defaults OFF.

**Motion shaping.** Separate slew rates (`servo.slew_speed` /
`servo.slew_slow`), a **minimum motor speed** ("short fast corrections"
beat inefficient slow crawling), a **minimum dwell between commands**
(`servo.period` ~0.3–0.4 s, anti-chatter), and a hard field lesson:
rudder speed is "one of the most important considerations" — ±30° in
6–8 s minimum, 15–20 °/s is good.

**Persistence.** EEPROM values are written in **three redundant banks**
and cross-checked on read — corruption loses nothing. They also insist on
enabling the **brown-out detector** because undervoltage during writes
corrupts AVR flash. Our single image + CRC32 falls back to *defaults* on
corruption: safe but lossy.

**Power stage.** Adaptive PWM — 62.5 Hz at full power, ~16 kHz partial —
same loss-vs-noise logic as our current-adaptive schedule (independent
validation). Bootstrap-refresh cycling at low duty. Clutch output with
full-power pull-in then PWM hold; `use_brake` (short the windings) is a
*tradeoff*, explicitly bad "if quick manual override is needed". Our worm
gear is always-brake with no clutch: no manual override by design —
that's an operational fact worth stating in the docs.

**ADC craft.** Heavy oversampling per channel, first 3 samples discarded
after mux switch, 32-bit accumulators; *ratiometric mode* makes the pot
feedback supply-independent (our AS5600 is digital — immune anyway).

## 2. ArduPilot — firmware lessons

**Watchdog culture.** Independent hardware watchdog + on-reset forensics:
a `WDG` log message, a `crash_dump.bin` of CPU state, and since 4.5.1 an
un-armable vehicle until the operator acknowledges the crash dump. The
lesson isn't the watchdog (we have one) — it's that **a watchdog reset is
a loud, sticky event**, never a silent reboot. RP2350 gives us
`watchdog_caused_reboot()` + scratch registers for free.

**Pre-arm check culture.** A comprehensive, categorized checklist gates
arming (sensor health, param storage readable, battery, calibration...),
with a bitmask escape hatch that exists but is discouraged — same
philosophy as our `VANCHOR_REQUIRE_CRC=0` bench switch. We have a minimal
version (enables low until first command; never drive blind on bad
feedback); we don't yet *verify* config storage or sensors as an explicit
gate with a reportable reason.

**Parameters.** AP_Param: save-only-if-changed (we match), backward-
compatible layout growth (we match with append-only), validation, and
flush-pending-saves-before-reboot. Their storage sits behind a layered
abstraction (HAL → StorageManager regions) — overkill at our scale, but
the *regions* idea (params / waypoints / signing keys separated) is why
they survived 15 years of format evolution.

**Failsafes are layered and graduated.** Two-stage battery failsafe
(warn → act), RC-loss vs GCS-loss vs EKF-loss handled distinctly, each
with an explicit configured action. Maps to us as: firmware reports
(VBAT, flags), the Pi decides policy — keep firmware policy-free.

**Observability.** Everything is logged (dataflash) and replayable; bugs
get found because the data exists. Our equivalent is free: the Pi should
log the raw `A`/`E`/`C`/`I` line streams (vanchor-ng side, one config
knob in their logging).

## 3. Electronics lessons (both projects)

| Practice | Them | Us today | Gap |
|---|---|---|---|
| Reverse polarity + fuse at entry | pypilot 10 A fuse + protection | F1 + P-FET ideal diode | none |
| Brown-out detection | AVR BOD fuse mandatory | RP2350 built-in BOR | none |
| V/I telemetry at the controller | both | VBAT + 2× IS ADCs | none |
| Power-stage temperature sensing | 10 k NTC, 60–70 °C limits | **none** (BTN8982's internal OT trip only — silent) | NTC pad on driver rev 2 / smart-node ADC |
| Endstop switch inputs | port/stbd pull-low fault pins | soft endstops only (`steer.range`) | GP2/GP3 on J12 could take switches |
| Logic/power isolation | optical isolation on serial | shared-ground ribbon/USB | acceptable (same enclosure); isolate only if CAN/0183 ground loops bite |
| EMI: motor wires vs sensors | twist pairs, ≥10 cm from IMU, compass ≥1 m from ferrous | HWT901B ≥30 cm note | add "twist J22/J13/battery pairs" to assembly docs |
| Feedback sensor wear | hall/AS5600 over pots | AS5600 | none — we're on their end state |

## 4. Recommendations (prioritized)

1. **A/B config sectors (power-loss-proof persistence)** — pypilot's
   triple-bank redundancy, adapted to NOR flash: alternate saves between
   TWO 4 kB sectors with a monotonic sequence number; boot loads the
   newest valid image. Never erases the only good copy (fixes our
   documented "power cut during erase → defaults" hole) and doubles wear
   life. Small change to `confPersist`/`confDeserialize`.
2. **Fault-flags telemetry + directional stall inhibit** — adopt the
   pypilot fault vocabulary: a flags word (stall-port, stall-stbd,
   overcurrent, driver-timeout = commanded-but-no-current, saturated,
   low-vbat, wdg-reboot) reported in `INFO` and a compact periodic `S
   <flags>*HH` line; make servo stall inhibit only the stalled direction.
   Firmware-only; the Pi can ignore it until it wants it.
3. **Watchdog forensics** — on boot read `watchdog_caused_reboot()`,
   count reboots in a watchdog scratch register, report cause + count in
   `INFO` (`I reset wdg n=2`), set the wdg flag bit until an operator
   `CONF`/command clears it. Loud, sticky, cheap.
4. **Motion-shaping config** — split `thr.slew` into up/down (fast to cut
   power, slow to apply — pypilot slew pair), add optional
   `steer.min_pwm_time`-style dwell (their `servo.period` anti-chatter)
   and consider defaulting `steer.stall_a` ON once calibrated (their
   "critical first parameter").
5. **Pi-side logging note** (vanchor-ng backlog): log raw protocol lines;
   it's the ArduPilot dataflash lesson at zero firmware cost.
6. **Board backlog (rev 2 / smart node)**: NTC footprint near the BTN8982
   pair on the driver (smart-node Pico has spare ADCs); label GP2/GP3 as
   optional endstop inputs; assembly-doc EMI notes (twisted pairs, route
   motor cables away from the HWT901B).

## Sources

- pypilot motor firmware: https://github.com/pypilot/pypilot/blob/master/arduino/motor/motor.ino
- pypilot motor README (BOD/fuses): https://github.com/pypilot/pypilot/blob/master/arduino/motor/README
- pypilot user manual (servo settings, flags, install/EMI): https://pypilot.org/doc/pypilot_user_manual/
- pypilot h-bridge controller: https://pypilot.org/schematics/hbridge_datasheet.htm
- ArduPilot independent watchdog + crash dump: https://ardupilot.org/copter/docs/common-watchdog.html
- ArduPilot pre-arm checks: https://ardupilot.org/copter/docs/common-prearm-safety-checks.html
- ArduPilot storage/EEPROM design: https://ardupilot.org/dev/docs/learning-ardupilot-storage-and-eeprom-management.html
- ArduPilot plane failsafe (layered battery): https://ardupilot.org/plane/docs/apms-failsafe-function.html
