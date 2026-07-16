/*
 * i2c_tunnel.h — pico glue for the I2C line-protocol tunnel (slave 0x42 on
 * GP4/GP5, the SBC ribbon's I2C3). Logic lives in tunnel_core.h; spec in
 * docs/I2C-TUNNEL.md.
 */
#ifndef HELM_I2C_TUNNEL_H
#define HELM_I2C_TUNNEL_H

#include <stdint.h>

#define TUN_I2C_ADDR 0x42

void i2cTunnelInit();

// Main-loop side: pop one inbound command byte (-1 = none).
int i2cTunnelGetchar();

// Queue a feedback line (CRLF appended) IF the tunnel is active — i.e. a
// master transaction was seen within the last few seconds. Keeps the TX
// FIFO from filling with stale telemetry when nobody is on the bus.
void i2cTunnelSendLine(const char *line, uint32_t nowMs);

bool i2cTunnelActive(uint32_t nowMs);

#endif  // HELM_I2C_TUNNEL_H
