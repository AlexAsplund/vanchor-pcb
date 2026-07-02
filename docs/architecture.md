# Vanchor system architecture

How the boards, sensors, networks and the tablet fit together.
(All diagrams are Mermaid — GitHub renders them inline.)

## System overview

```mermaid
graph TB
    subgraph BOAT["boat 12V system"]
        BATT[("12V battery")]
    end

    subgraph HELM["HELM BOARD (125x95)"]
        PWR["F1 10A + reverse-FET<br/>+ XL4015 buck 5V (U5)"]
        SBC["Orange Pi Zero 3 / RPi<br/>Linux: vanchor-ng + Signal K"]
        PICO["Pico 2 (RP2350)<br/>real-time motor ctrl, I2C 0x42"]
        SRVBR["servo H-bridge<br/>2x BTN8982TA"]
        XCVR["SN65HVD230<br/>CAN transceiver on J12"]
        PWR --> SBC
        PWR --> PICO
        SBC <-->|"I2C3 (ribbon)"| PICO
        PICO --> SRVBR
        PICO <-->|"GP18/19 can2040"| XCVR
    end

    subgraph THRUST["THRUST DRIVER (95x92)"]
        HBRIDGE["H-bridge 2-4x BTN8982TA<br/>base ~30A / high ~50A"]
    end

    TABLET["tablet / phone<br/>OpenCPN, Signal K web"]
    IMU["HWT901B AHRS<br/>(heading, roll, pitch)"]
    N2K[("NMEA2000 backbone<br/>MFD, GPS, wind, AIS")]
    N183["NMEA0183 device<br/>(GPS puck, AIS rx)"]
    SERVO["12V worm-gear servo<br/>+ AS5600 encoder"]
    MOTOR(("trolling motor"))

    BATT -->|"J16 (1.5mm2)"| PWR
    BATT ==>|"fat cable + ANL fuse"| HBRIDGE
    SBC -.->|"WiFi AP / LAN"| TABLET
    IMU -->|"J3 UART5 TTL"| SBC
    N183 -->|"J4 UART2 (TTL, see note)"| SBC
    XCVR <-->|"CAN H/L + J5 pwr/shield"| N2K
    PICO -->|"J13 -> J1 straight 8-wire"| HBRIDGE
    SRVBR -->|"J22"| SERVO
    SERVO -->|"J11 AS5600 I2C"| PICO
    HBRIDGE ==> MOTOR
```

Two supply domains, deliberately separate: the helm board takes a fused
1.5 mm² feed for logic + servo (≤10 A), while the motor current
(30–50 A) runs battery → thrust driver → motor on fat lugged cable and
never touches the helm board.

## Software / data flow to the tablet

```mermaid
graph LR
    subgraph SBC["SBC (Linux)"]
        SK["Signal K server"]
        VNG["vanchor-ng autopilot"]
        SK <--> VNG
    end
    subgraph PICO2["Pico 2"]
        FW["motor firmware<br/>watchdog 800ms"]
        GW["N2K gateway (core 1)<br/>can2040 + Actisense framing"]
    end

    HWT["HWT901B @ /dev/ttyAS5"] --> SK
    N183IN["NMEA0183 @ /dev/ttyAS2"] --> SK
    GW -->|"USB CDC or UART<br/>(Actisense NGT-1 emulation)"| SK
    VNG -->|"I2C 0x42: thrust/steer cmd"| FW
    FW -->|"status: angle, currents, vbat"| VNG
    SK -->|"WiFi: Signal K web, TCP 10110<br/>(NMEA0183 over IP)"| TAB["tablet: OpenCPN /<br/>Freeboard / WilhelmSK"]
```

The Zero 3's on-board WiFi runs as an access point (hostapd + dnsmasq) or
joins the boat's network; the tablet needs nothing but a browser or a
chartplotter app pointed at the Signal K/NMEA-over-TCP port.

## HWT901B attitude sensor (heading source)

The WitMotion HWT901B-TTL (9-axis AHRS + barometer, Kalman-filtered
roll/pitch/yaw) connects to **J3 (UART5)** with a 4-wire cable:

| J3 pin | Net | HWT901B pin |
|---|---|---|
| 1 | 3V3 (from SBC) | VCC (3.3–5 V) |
| 2 | UART5_TX (SBC out) | RXD |
| 3 | UART5_RX (SBC in) | TXD |
| 4 | GND | GND |

```mermaid
graph LR
    subgraph J3["helm J3 (UART5, XH-4)"]
        P1["1: 3V3"]
        P2["2: TX"]
        P3["3: RX"]
        P4["4: GND"]
    end
    subgraph HWT["HWT901B-TTL"]
        VCC["VCC"]
        RXD["RXD"]
        TXD["TXD"]
        GNDS["GND"]
    end
    P1 --- VCC
    P2 --- RXD
    P3 --- TXD
    P4 --- GNDS
```

Notes: default 9600 baud (raise to 115200 with WitMotion's config tool);
enable the `uart5` DT overlay → `/dev/ttyAS5`. **Mount the sensor ≥30 cm
from the servo/thrust cables and the motor**, level, bow-aligned, and run
a magnetometer calibration after installation — heading is the autopilot's
primary feedback. Signal K ingests it via the witmotion plugin (or
vanchor-ng reads it directly).

## NMEA0183 (v2 of NMEA — serial sentences)

J3/J4 are **3.3 V TTL** UARTs. Hobby-grade GPS pucks and AIS receivers
with TTL outputs connect directly (J4 shown; enable `uart2` overlay,
`/dev/ttyAS2`; if silent, swap TX/RX at the JST — documented hedge).
A *standards-compliant* NMEA0183 device talks RS-422 differential — put a
small RS422↔TTL (or MAX3232 for RS-232 talkers) converter in the cable:

```mermaid
graph LR
    DEV["NMEA0183 talker<br/>(RS-422 A/B pair)"] --> CONV["RS422-to-TTL<br/>converter"] --> J4["helm J4<br/>UART2 TTL"] --> SK2["Signal K"]
    SK2 -->|"TCP 10110 over WiFi"| APP["tablet apps"]
```

Outbound NMEA0183 (to a VHF with DSC, etc.) works the same way in
reverse; Signal K converts between 0183 sentences, N2K PGNs and its own
model, so the tablet sees one unified feed.

## NMEA2000 (v3 of NMEA — CAN bus)

CAN lives on the **Pico 2** (can2040 PIO CAN, 250 kbit/s, core 1), not on
the Linux SBC — the bus keeps its address claim and the motor watchdog
even if Linux reboots. Hardware on the helm board:

```mermaid
graph LR
    subgraph HELMN2K["helm board"]
        PICOC["Pico 2 core 1<br/>can2040 GP18/19 + NMEA2000 lib"]
        J12["J12 pins 1/8/6/7<br/>3V3 GND TX RX"]
        J5["J5: V+ / GND / SHIELD<br/>R41 0R DNP: feed bus from VIN<br/>R42 0R DNP: shield bond"]
        PICOC --- J12
    end
    MOD["SN65HVD230 module<br/>(CTX/CRX + screw terminal)"]
    J12 ---|"4 jumper wires"| MOD
    MOD ---|"CAN_H / CAN_L"| BB[("N2K backbone<br/>(terminated 2x 120R)")]
    J5 ---|"power + shield conductors"| BB
    BB --- MFD["MFD / chartplotter"]
    BB --- SRC["GPS / wind / depth / AIS"]
```

The Pico emulates an **Actisense NGT-1** over USB-CDC (or a UART jumper
J4↔J12 GP0/GP1), so Signal K/canboat/OpenCPN consume the bus with zero
custom drivers. Outbound, the autopilot broadcasts heading (127250),
rudder (127245) and the standard thruster PGNs (128006–128008); anything
vanchor-specific rides proprietary PGNs.

**Future smart nodes**: the thrust driver already carries DNP provision
(Pico 2 + regulator + the same transceiver hookup on J6, N2K power on J7)
to hang directly on the backbone and take commands as proprietary PGNs —
see `boards/thrust-driver/README.md`. A dedicated servo node would reuse
the same node core.

```mermaid
graph TB
    BB2[("NMEA2000 backbone")]
    HELM2["helm board<br/>(gateway + pilot)"] --- BB2
    TD2["thrust driver v1.1<br/>smart-node option (DNP)"] -.->|"populate U5/U6 + XCVR"| BB2
    SN2["future servo node<br/>(same node core)"] -.-> BB2
    HELM2 ---|"today: 8-wire J13 cable"| TD2
```

## Steering / thrust control loop

```mermaid
sequenceDiagram
    participant T as Tablet
    participant S as SBC (vanchor-ng)
    participant P as Pico 2
    participant D as Thrust driver
    participant V as Servo + AS5600

    T->>S: course / waypoint (WiFi)
    Note over S: PID: heading from HWT901B,<br/>position from N2K GPS
    S->>P: I2C 0x42 CMD {pwm, dir, steer}
    P->>D: RPWM/LPWM + EN (J13 cable)
    P->>V: BTN8982 bridge PWM
    V-->>P: AS5600 angle (I2C1)
    Note over P: closed-loop steer,<br/>800ms watchdog -> failsafe
    P-->>S: STATUS {angle, currents, vbat}
    S-->>T: telemetry / chart overlay
```

Failsafe chain: if the I²C command stream stops for 800 ms the Pico zeroes
thrust and holds steering (the worm gear self-locks); if the Pico resets,
100 k pulldowns on every EN pin keep both bridges disabled.
