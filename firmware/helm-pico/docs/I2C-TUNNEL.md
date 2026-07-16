# I²C line-protocol tunnel — wire spec + Pi implementation guide

**Audience**: whoever implements the master side in vanchor-ng. This
document is self-contained: everything the Pi needs to speak to the helm
Pico over I²C is specified here, byte by byte. The firmware side is
implemented in `src/tunnel_core.h` (register machine, host-tested in
`tests/`) and `src/i2c_tunnel.cpp` (ISR glue).

## 0. Concept

The tunnel does **not** define a new command set. It carries the exact
vanchor-ng ASCII line protocol — the same bytes that flow over the USB CDC
port, CRC-8 `*HH` framing included — through a tiny I²C register map with
two FIFOs:

```
Pi (master)                         Pico (slave 0x42)
  -- write reg 0x10 + bytes -->      RX FIFO (256 B)  --> line parser
  <-- read  reg 0x10           --    TX FIFO (1024 B) <-- A / E / C lines
```

Everything documented for the serial contract applies unchanged: `CMD`,
`STEERD`, `THRUST`, the `CONF*` family, the `A`/`E`/`C` replies, the 800 ms
watchdog, heartbeat seq semantics, CRC rules. If a line parses over USB it
parses over I²C. USB and I²C are live simultaneously; feedback is mirrored
to both, commands are accepted from both (do not drive from two places at
once — last writer wins).

## 1. Physical layer

| Item | Value |
|---|---|
| Bus | SBC ribbon I²C3: OPi Zero 3 pins 3 (SDA) / 5 (SCL) — nets `PI_SDA`/`PI_SCL` → Pico GP4/GP5 (I²C0 slave) |
| Address | **0x42** (7-bit) |
| Speed | 100 kHz or 400 kHz, master's choice (400 kHz recommended) |
| Levels | 3.3 V both ends, no level shifting |
| Pull-ups | The SBC side must provide them (the Zero 3 header does). If the bus floats, fit **R5/R6 (2.2 k, DNP)** on the helm board. The Pico enables its weak (~50 k) internal pulls only as an idle-level backstop. |
| SBC enable | `i2c3` DT overlay → `/dev/i2c-3` on the Zero 3 |
| Clock stretching | Not used by the slave in normal operation; tolerate it anyway (RP2350 hardware may stretch briefly inside a transaction). |

## 2. Register map

A write transaction's **first byte selects the register**; subsequent bytes
in the same transaction are data for that register. The register pointer
survives a STOP for the *following read* (standard write-pointer /
repeated-start-read convention). Registers `0x00–0x06` auto-increment as
they are read; `0x10` (DATA) does not.

| Reg | Name | R/W | Contents |
|---|---|---|---|
| 0x00 | `WHOAMI` | R | constant `0x56` (`'V'`) — probe/identity |
| 0x01 | `VERSION` | R | tunnel layout version, constant `0x01` |
| 0x02 | `TXA_L` | R | feedback bytes waiting, **low byte**. Reading it latches the full 16-bit count |
| 0x03 | `TXA_H` | R | high byte of the count **latched at the `TXA_L` read** |
| 0x04 | `RXF_L` | R | command-FIFO free space, low byte (latches, like TXA) |
| 0x05 | `RXF_H` | R | high byte of the latched free space |
| 0x06 | `FLAGS` | R | bit0 = RX overflow, bit1 = TX overflow. **Clears on read** |
| 0x10 | `DATA` | R/W | the FIFO. Write: command bytes in. Read: feedback bytes out; `0x00` filler when empty |
| other | — | — | read as `0x00`; writes ignored |

Rules that matter:

- **Always read `TXA_L` before `TXA_H`** (one 2-byte read starting at 0x02
  does this naturally via auto-increment). `TXA_H` alone returns whatever
  was last latched.
- Registers other than `DATA` are **read-only**; writing data bytes to
  them is silently ignored (verified by the firmware test suite).
- `DATA` reads never auto-increment — you can drain any number of bytes in
  one transaction starting at 0x10.
- Filler: reading `DATA` past the available count returns `0x00`. ASCII
  lines never contain `0x00`, so a master that over-reads can simply strip
  NULs. The clean pattern is: read the count, then read exactly that many.

## 3. Stream semantics

- **Commands (Pi → Pico)** are raw line-protocol bytes: the full line
  including the `*HH` CRC and a terminating `\n` (`\r\n` also fine). A line
  MAY be split across multiple write transactions ("CMD 0 " then
  "F 0*DC\n") — bytes accumulate until the newline. Don't interleave two
  half-lines; there is one stream.
- **Feedback (Pico → Pi)** is whole `\r\n`-terminated lines: `A …` at
  ~10 Hz, `E …` at ~5 Hz, `C …` replies to `CONF*` commands. The firmware
  queues a line **all-or-nothing**: if the TX FIFO can't hold the entire
  line it is dropped and the TX-overflow flag is set — the master never
  sees a truncated line. (Even if it somehow did, the line CRC rejects it;
  keep verifying CRCs exactly like the serial driver does.)
- **Idle gating**: the Pico only queues feedback after it has seen a master
  transaction within the last **3 s**. First contact (any read, e.g. a
  WHOAMI probe) opens the tap; a master that stops polling for 3 s stops
  accumulating stale telemetry. Consequence: after (re)connecting, expect
  the first `A`/`E` lines to appear within ~100–200 ms of your first poll,
  not instantly.
- **Overflow behaviour**: RX full → excess command bytes are dropped and
  flagged; the mutilated line fails CRC/parse and the watchdog covers the
  gap (same degradation path as serial noise). TX full → whole feedback
  lines dropped, flagged. Poll `FLAGS` occasionally and log a warning when
  nonzero — in a healthy 10 Hz loop both flags stay 0 forever.
- **Sizing**: worst-case steady state is ~37 B per poll cycle at 10 Hz
  (one 25 B `A` line + half of a 22 B `E` line). A `CONFDUMP` burst is
  ~24 lines ≈ 750 B — under the 1024 B TX FIFO, but drain promptly (or
  dump while the motor loop is otherwise quiet).

## 4. Canonical master session (byte level)

Probe:
```
W 0x42: [0x00]            # set pointer to WHOAMI
R 0x42: [0x56, 0x01]      # WHOAMI, then VERSION via auto-increment
```

Send a command (one transaction):
```
W 0x42: [0x10, 'C','M','D',' ','0',' ','F',' ','0','*','D','C','\n']
```

Poll + drain feedback:
```
W 0x42: [0x02]            # pointer to TXA_L
R 0x42: [n_lo, n_hi]      # bytes available (latched pair)
if n > 0:
    W 0x42: [0x10]        # pointer to DATA
    R 0x42: n bytes       # exact drain; split into chunks if you like
```

Health check (optional, each few seconds):
```
W 0x42: [0x06]; R 0x42: [flags]   # nonzero -> log; flags auto-clear
```

`i2c-tools` bench equivalents (bus 3):
```sh
i2cdetect -y 3                               # shows 0x42
i2ctransfer -y 3 w1@0x42 0x00 r2             # 0x56 0x01
python3 - <<'EOF'                            # full round-trip
from smbus2 import SMBus, i2c_msg
import time
with SMBus(3) as bus:
    bus.i2c_rdwr(i2c_msg.write(0x42, b"\x10CMD 0 F 0*DC\n"))
    time.sleep(0.15)
    bus.i2c_rdwr(i2c_msg.write(0x42, b"\x02"))
    rd = i2c_msg.read(0x42, 2); bus.i2c_rdwr(rd)
    n = int.from_bytes(bytes(rd), "little")
    bus.i2c_rdwr(i2c_msg.write(0x42, b"\x10"))
    rd = i2c_msg.read(0x42, n); bus.i2c_rdwr(rd)
    print(bytes(rd).decode())                # A ...*HH \r\n E ...*HH
EOF
```
Use `i2c_msg`/`i2c_rdwr` (raw I²C), not the SMBus block calls — SMBus caps
transactions at 32 bytes and inserts a count byte the tunnel doesn't use.

## 5. Implementing the Pi side in vanchor-ng

The whole point: **do not touch `SerialMotorController` or the protocol
code.** Implement one new transport and let the existing stack run over it.

`src/vanchor/hardware/serial_link.py` defines the ABC every driver uses:

```python
class SerialTransport(abc.ABC):
    async def open(self) -> None
    async def close(self) -> None
    async def read_line(self) -> str      # one line, newline stripped
    async def write_line(self, line: str) -> None
    async def read(self, n: int = 4096) -> bytes
    async def write(self, data: bytes) -> None
```

Suggested `I2cTransport(SerialTransport)` (new file, e.g.
`src/vanchor/hardware/i2c_link.py`):

- **ctor** `(bus: int, addr: int = 0x42, poll_hz: float = 20.0)`.
- **open()**: open `/dev/i2c-<bus>` (smbus2 `SMBus`), probe WHOAMI==0x56
  and VERSION==0x01, raise on mismatch (that's what makes the supervisor's
  reconnect/backoff loop work unchanged). Start an internal poll task.
- **poll task** (the only I²C-specific logic): every `1/poll_hz`
  seconds — read `TXA` (2 bytes at 0x02), if nonzero read that many bytes
  at 0x10, append to a `bytearray`, split on `\n`, push complete lines
  (rstrip `\r`) into an `asyncio.Queue`. Every ~5 s read `FLAGS` (0x06)
  and log a rate-limited warning when nonzero.
- **read_line()**: `await queue.get()` — the read-supervisor and the
  CRC/parse layers above need nothing else. On a persistent bus error
  raise `EOFError` so `_SerialReadSupervisor` reconnects exactly as it
  does for a yanked USB cable.
- **write_line(line)**: one `i2c_rdwr` write of `b"\x10" + line.encode() +
  b"\r\n"`. Lines are ≤48 bytes, so a single transaction always suffices.
  Serialize writes with the poll task via an `asyncio.Lock` around bus
  access (SMBus handles are not concurrency-safe); run the *blocking*
  smbus2 calls in `asyncio.to_thread` / an executor, mirroring how
  `PySerialTransport` keeps the event loop clean.
- **read()/write()**: byte-level passthroughs of the same FIFOs (the ABC
  requires them; the motor driver doesn't use them).

Config plumbing suggestion (keeps today's semantics): accept an
`i2c:<bus>:<addr>` scheme in the existing `motor_port` field, e.g.
`motor_port: "i2c:3:0x42"`, and have the transport factory pick
`I2cTransport` for that scheme and `PySerialTransport` otherwise. Baud and
the serial framing knobs are simply ignored for I²C. Everything above the
transport — combined controller, heartbeat, health flags, telemetry — runs
byte-identically.

Timing sanity: at 400 kHz a 32-byte transaction is ~1 ms; the 20 Hz poll +
10 Hz command cadence uses well under 5 % of the bus. Don't poll faster
than ~50 Hz — it buys nothing and each transaction interrupts the Pico
briefly (the ISR is a few µs per byte; the control loop tolerates it, but
there's no reason to hammer it).

## 6. Failure modes & edge cases (read before coding)

| Situation | What happens | Master's job |
|---|---|---|
| Pico rebooting / SWD reflash | address NAKs | treat as transport error → supervisor backoff-reconnect (probe WHOAMI on reopen) |
| Master stops polling ≥3 s | tunnel goes idle, TX queueing stops (no stale backlog) | nothing; resume polling, fresh lines appear |
| TX FIFO overflow (master too slow) | whole lines dropped, bit1 of FLAGS | drain faster / log; never partial lines |
| RX FIFO overflow (writer runaway) | bytes dropped, bit0 of FLAGS; broken line fails CRC | back off; watchdog already covers the gap |
| Over-read of DATA | `0x00` filler | strip NULs or read exact counts |
| Noise/corruption on the bus | line CRC fails → line ignored (both directions) | identical to serial: reject, never guess |
| Both USB and I²C connected | both accept commands, both get feedback | don't drive from two controllers at once |
| Command watchdog | I²C commands feed the same 800 ms watchdog | keep the 10 Hz `CMD` cadence, same as serial |

## 7. Compliance checklist for the Pi implementation

- [ ] WHOAMI/VERSION probed on open; mismatch = failed open.
- [ ] `TXA_L` before `TXA_H` (single 2-byte read at 0x02).
- [ ] Raw-I²C transfers (`i2c_rdwr`), not 32-byte-capped SMBus block ops.
- [ ] CRC appended on every outbound line; CRC verified on every inbound
      line (reuse `append_crc` / `strip_verify_crc` — zero new code).
- [ ] `EOFError` on persistent bus failure so the existing supervisor
      reconnects.
- [ ] FLAGS polled occasionally; overflows logged, never fatal.
- [ ] Bench-verified against real firmware with the session in §4 before
      boat deployment (the same BENCH-VERIFY discipline as
      `serial_channels.py`).
