# Host-side tests for the helm-pico firmware. No SDK required.
# The control logic + protocol code is hardware-free by construction; this
# compiles the exact headers the firmware ships.
CXX ?= g++
CXXFLAGS ?= -std=c++17 -Wall -Wextra -O1 -I../include

all: run

test_protocol: test_protocol.cpp ../src/protocol_ext.h ../src/control_logic.h \
               ../src/config.h ../vendor/vanchor_protocol.h ../include/board.h
	$(CXX) $(CXXFLAGS) -o $@ test_protocol.cpp

# Also prove the VANCHOR_REQUIRE_CRC=0 build accepts the NOCRC vectors.
test_protocol_nocrc: test_protocol.cpp ../src/protocol_ext.h \
                     ../src/control_logic.h ../vendor/vanchor_protocol.h
	$(CXX) $(CXXFLAGS) -DVANCHOR_REQUIRE_CRC=0 -o $@ test_protocol.cpp

run: test_protocol test_protocol_nocrc
	./test_protocol
	./test_protocol_nocrc

clean:
	rm -f test_protocol test_protocol_nocrc

.PHONY: all run clean
