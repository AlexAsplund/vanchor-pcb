#include "i2c_tunnel.h"

#include "hardware/gpio.h"
#include "hardware/i2c.h"
#include "pico/i2c_slave.h"
#include "pico/stdlib.h"

#include "board.h"
#include "tunnel_core.h"

#define TUN_ACTIVE_MS 3000

static TunnelCore g_tun;
static volatile uint32_t g_lastEventMs = 0;

static void slaveHandler(i2c_inst_t *i2c, i2c_slave_event_t event) {
  g_lastEventMs = to_ms_since_boot(get_absolute_time());
  switch (event) {
    case I2C_SLAVE_RECEIVE:
      g_tun.masterWrite(i2c_read_byte_raw(i2c));
      break;
    case I2C_SLAVE_REQUEST:
      i2c_write_byte_raw(i2c, g_tun.masterRead());
      break;
    case I2C_SLAVE_FINISH:
      g_tun.stop();
      break;
    default:
      break;
  }
}

void i2cTunnelInit() {
  gpio_set_function(PIN_PI_SDA, GPIO_FUNC_I2C);
  gpio_set_function(PIN_PI_SCL, GPIO_FUNC_I2C);
  // Weak internal pulls only as a belt-and-braces idle level; the real
  // pull-ups are the SBC's (or fit R5/R6 on the board — see the spec).
  gpio_pull_up(PIN_PI_SDA);
  gpio_pull_up(PIN_PI_SCL);
  i2c_init(i2c0, 400 * 1000);  // slave: the master's clock actually rules
  i2c_slave_init(i2c0, TUN_I2C_ADDR, &slaveHandler);
}

int i2cTunnelGetchar() { return g_tun.getByte(); }

bool i2cTunnelActive(uint32_t nowMs) {
  uint32_t last = g_lastEventMs;
  return last != 0 && (nowMs - last) < TUN_ACTIVE_MS;
}

void i2cTunnelSendLine(const char *line, uint32_t nowMs) {
  if (!i2cTunnelActive(nowMs)) return;
  g_tun.queueLine(line);
}
