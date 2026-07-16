/*
 * protocol_ext.h — helm-pico additions on top of the vendored contract.
 *
 * The vendored vanchor_protocol.h carries the CMD / STEERD parsers and the
 * CRC machinery. The split thrust channel token ("THRUST <pwm> <dir> [<seq>]",
 * firmware/README.md section 6.2 in vanchor-ng) has no reference parser in
 * that header, so it lives here — same style, same tolerance rules, and it is
 * exercised against the golden vectors by tests/test_protocol.cpp.
 */
#ifndef HELM_PROTOCOL_EXT_H
#define HELM_PROTOCOL_EXT_H

#include "../vendor/vanchor_protocol.h"

/*
 * Parse "THRUST <pwm> <dir> [<seq>]". Same contract shape as vanchorParseCmd:
 * outputs are written only when the whole line parses; seq is -1 when absent.
 */
inline bool vanchorParseThrust(const char *line, int *pwm, char *dir,
                               int *seq = 0) {
  while (*line == ' ') line++;
  const char hdr[] = "THRUST";
  for (int i = 0; hdr[i]; i++) {
    if (line[i] != hdr[i]) return false;
  }
  const char *p = line + 6;
  if (*p != ' ') return false;  // require a separator (not THRUSTX)

  while (*p == ' ') p++;
  if (*p < '0' || *p > '9') return false;
  long v = 0;
  while (*p >= '0' && *p <= '9') { v = v * 10 + (*p - '0'); p++; }
  if (v > 255) v = 255;

  while (*p == ' ') p++;
  char d = *p;
  if (d != 'F' && d != 'R') return false;
  p++;

  long q = -1;
  const char *pq = p;
  while (*pq == ' ') pq++;
  if (*pq >= '0' && *pq <= '9') {
    q = 0;
    while (*pq >= '0' && *pq <= '9') { q = q * 10 + (*pq - '0'); pq++; }
    if (q > VANCHOR_SEQ_MAX) q = VANCHOR_SEQ_MAX;
  }

  *pwm = (int)v;
  *dir = d;
  if (seq) *seq = (int)q;
  return true;
}

#endif  // HELM_PROTOCOL_EXT_H
