/*
 * tunnel_core.h — hardware-free core of the I2C line-protocol tunnel.
 *
 * The Pico is an I2C slave at 0x42 on the SBC ribbon (PI_SDA/PI_SCL ->
 * GP4/GP5). The tunnel carries the EXACT same ASCII line protocol as the
 * USB CDC port — CRC-8 framing end to end — through a tiny register map:
 * the master writes command bytes into a FIFO register and drains feedback
 * bytes from the same register. Full spec: docs/I2C-TUNNEL.md.
 *
 * This header contains the whole register state machine + both FIFOs with
 * no hardware dependencies; the ISR glue in i2c_tunnel.cpp is a thin shim,
 * so tests/ can simulate complete master transactions against the exact
 * shipped logic.
 *
 * Concurrency model (single producer / single consumer per ring):
 *   masterWrite/masterRead/stop  — ISR side (one byte per I2C event)
 *   getByte/queueLine            — main-loop side
 */
#ifndef HELM_TUNNEL_CORE_H
#define HELM_TUNNEL_CORE_H

#include <stdint.h>
#include <string.h>

// Same-core ISR/main-loop rings need COMPILER ordering only (no SMP here):
// without a fence the compiler may sink the buf[] store past the index store,
// letting the ISR pop a stale byte (or the converse on the consumer side).
// Hardware-free so the host tests can compile this header unchanged.
#ifndef TUN_COMPILER_BARRIER
#define TUN_COMPILER_BARRIER() __asm volatile("" ::: "memory")
#endif

// Set/clear of `flags` is a read-modify-write shared with the ISR; the main
// loop must run it with IRQs masked or the ISR's clear-on-read (or RX_OVF
// set) between the load and the store is lost. The firmware maps this to
// save_and_disable_interrupts()/restore_interrupts(); host tests are
// single-threaded and use the no-op default.
#ifndef TUN_IRQ_LOCK
#define TUN_IRQ_LOCK() 0
#define TUN_IRQ_UNLOCK(s) (void)(s)
#endif

// ------------------------------------------------------------ register map --
enum {
  TUN_REG_WHOAMI = 0x00,  // constant 0x56 ('V')
  TUN_REG_VERSION = 0x01, // tunnel layout version, constant 0x01
  TUN_REG_TXA_L = 0x02,   // feedback bytes waiting, low  (latches the count)
  TUN_REG_TXA_H = 0x03,   // feedback bytes waiting, high (latched value)
  TUN_REG_RXF_L = 0x04,   // command FIFO free space, low (latches)
  TUN_REG_RXF_H = 0x05,   // command FIFO free space, high (latched)
  TUN_REG_FLAGS = 0x06,   // bit0 RX overflow, bit1 TX overflow; clears on read
  TUN_REG_DATA = 0x10,    // the FIFO: write = command bytes, read = feedback
};
#define TUN_WHOAMI_VAL 0x56
#define TUN_VERSION_VAL 0x01
#define TUN_FLAG_RX_OVF 0x01
#define TUN_FLAG_TX_OVF 0x02
#define TUN_FILL_BYTE 0x00  // returned on DATA reads past the available count

// --------------------------------------------------------------- byte ring --
// Power-of-two SPSC ring. Indices only ever grow (mod 2^16 wrap is fine as
// long as N divides 65536).
template <int N>
struct ByteRing {
  static_assert((N & (N - 1)) == 0 && N <= 32768, "power of two");
  uint8_t buf[N];
  volatile uint16_t head = 0;  // producer writes buf[head % N]
  volatile uint16_t tail = 0;  // consumer reads buf[tail % N]

  uint16_t count() const { return (uint16_t)(head - tail); }
  uint16_t free() const { return (uint16_t)(N - count()); }
  bool push(uint8_t b) {
    if (count() >= N) return false;
    buf[head % N] = b;
    TUN_COMPILER_BARRIER();   // data visible before the index says so
    head = (uint16_t)(head + 1);
    return true;
  }
  int pop() {
    if (count() == 0) return -1;
    uint8_t b = buf[tail % N];
    TUN_COMPILER_BARRIER();   // read the byte before releasing the slot
    tail = (uint16_t)(tail + 1);
    return b;
  }
};

// ------------------------------------------------------------- tunnel core --
struct TunnelCore {
  ByteRing<256> rx;    // master -> pico (command lines)
  ByteRing<1024> tx;   // pico -> master (feedback lines)
  uint8_t reg = TUN_REG_WHOAMI;
  bool expectReg = true;      // next written byte selects the register
  uint8_t flags = 0;
  uint16_t latch = 0;         // multi-byte counter latched on the *_L read

  // ---- ISR side --------------------------------------------------------- //
  void masterWrite(uint8_t b) {
    if (expectReg) {
      reg = b;
      expectReg = false;
      return;
    }
    if (reg == TUN_REG_DATA) {
      if (!rx.push(b)) flags |= TUN_FLAG_RX_OVF;
    }
    // all other registers are read-only: extra written bytes are ignored
  }

  uint8_t masterRead() {
    expectReg = false;  // a pure read after STOP keeps the last register
    uint8_t out = 0;
    switch (reg) {
      case TUN_REG_WHOAMI:  out = TUN_WHOAMI_VAL; break;
      case TUN_REG_VERSION: out = TUN_VERSION_VAL; break;
      case TUN_REG_TXA_L:   latch = tx.count();  out = latch & 0xFF; break;
      case TUN_REG_TXA_H:   out = latch >> 8; break;
      case TUN_REG_RXF_L:   latch = rx.free();   out = latch & 0xFF; break;
      case TUN_REG_RXF_H:   out = latch >> 8; break;
      case TUN_REG_FLAGS:   out = flags; flags = 0; break;
      case TUN_REG_DATA: {
        int b = tx.pop();
        return (b < 0) ? TUN_FILL_BYTE : (uint8_t)b;  // DATA never increments
      }
      default: out = 0; break;
    }
    // Auto-increment through the status block ONLY (0x00..0x06, matching
    // I2C-TUNNEL.md). Walking further would reach DATA and silently pop
    // feedback bytes on any master that over-reads the status registers.
    if (reg < TUN_REG_FLAGS) reg++;
    return out;
  }

  void stop() { expectReg = true; }  // STOP/RESTART: next write selects reg

  // ---- main-loop side ---------------------------------------------------- //
  int getByte() { return rx.pop(); }

  // Queue one whole feedback line (+CRLF). All-or-nothing: a line that does
  // not fit is dropped and flagged, so the master never sees a truncated
  // line (and the CRC would reject one anyway).
  bool queueLine(const char *line) {
    uint16_t len = (uint16_t)strlen(line);
    if (tx.free() < len + 2) {
      unsigned long s = TUN_IRQ_LOCK();
      flags |= TUN_FLAG_TX_OVF;
      TUN_IRQ_UNLOCK(s);
      return false;
    }
    for (uint16_t i = 0; i < len; i++) tx.push((uint8_t)line[i]);
    tx.push('\r');
    tx.push('\n');
    return true;
  }
};

#endif  // HELM_TUNNEL_CORE_H
