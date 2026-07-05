# Analog chain simulations (ngspice)

Repeatable SPICE verification of the boards' critical analog paths.
Run: `docker run --rm -v $PWD/sim:/sim -w /sim debian:bookworm-slim sh -c "apt-get update -qq && apt-get install -y -qq ngspice gnuplot-nox && for f in *.cir; do ngspice -b $f; done && gnuplot plots.gp"`
(Digital parts — SBC, Pico, buck module, CAN — are not SPICE-able; this
suite covers every analog conditioning chain instead.)

## Results (2026-07-06, ngspice-39)

| Chain | Deck | Result | Verdict |
|---|---|---|---|
| Thrust IS telemetry (driver 1k loads → helm mix → ADC1) | `is_telemetry.cir` | 10 A → 0.21 V, 30 A → 0.63 V, 50 A → 1.05 V at the ADC (linear). **IS fault (4.4 mA): 2.10 V — inherently safe, clamp never conducts** (the mix/divider itself protects). | PASS |
| VBAT sense (47k/10k + BAT54S) | `vbat_sense.cir` | 12.6 V → 2.21 V. **40 V load-dump: ADC node clamps at 3.53 V pk** (< 3.6 V abs max), 0.42 mA into the 3V3 rail. | PASS |
| Reverse-polarity P-FET (IRF9540N + 12 V zener) | `reverse_fet.cir` | Forward 14.4 V @ 2.4 A: V(gs) −11.9 V (zener clamped), mV-class drop. **Reversed battery: load node 0 V** (fully blocked). | PASS |
| Hall zero input (10k pullup, 100n, 1k series) | `hall_input.cir` | Fall 3 µs (crisp edge for the zero index); **rise ≈ 1.3 ms** (10k·100n+cable). Fine for calibration-speed sweeps; fit C24 = 10 n if a fast index is ever needed. | PASS (note) |
| Servo IS telemetry (1k load, 10k+100n, clamp → ADC0) | `servo_is.cir` | 5 A → 0.22 V, 10 A stall → 0.44 V. Fault: 3.48 V clamped, 83 µA into 3V3. Bandwidth ≈ 160 Hz (see `servo_bw.svg`). | PASS |

Plots: `is_transfer.svg`, `vbat_dump.svg`, `hall_wave.svg`, `servo_bw.svg`.

## Firmware-relevant numbers

- ADC1 thrust scaling: **≈ 21 mV/A** at the pin (0.63 V @ 30 A) — use this,
  not a naive kILIS×1k calc (the helm mix divides by ~2.1).
- ADC0 servo scaling: **≈ 44 mV/A** (0.22 V @ 5 A).
- ADC2 battery: V(bat)·0.1754 (2.53 V @ 14.4 V).
- Hall GP0: falling edge is the index (3 µs); debounce ≥ 2 ms on release.

## Model caveats

Generic level-1 PMOS and simple diode models (BAT54/BZX85C12 parameters
approximated from datasheets). Good for topology/range verification, not
for mV-exact drops — the real IRF9540N forward drop is ~0.3 V at 2.4 A
(R_DS(on) 117 mΩ), which changes nothing qualitatively.
