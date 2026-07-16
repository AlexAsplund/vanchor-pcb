# Vendored protocol contract

`vanchor_protocol.h` and `protocol_vectors.txt` are VERBATIM copies from the
vanchor-ng repo (`firmware/common/`, copied 2026-07-16). They define the wire
contract the Pi speaks (`src/vanchor/hardware/serial_devices.py` /
`serial_link.py`) and MUST NOT be edited here — re-copy from vanchor-ng when
the protocol version bumps, and re-run `make -C ../tests` afterwards.
