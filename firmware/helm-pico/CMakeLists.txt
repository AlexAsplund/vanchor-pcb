cmake_minimum_required(VERSION 3.13)

# Standard pico-sdk bootstrap: set PICO_SDK_PATH (or let the import file
# fetch it) before configuring. Target board is the Pico 2 (RP2350).
set(PICO_BOARD pico2 CACHE STRING "Board type")
include(pico_sdk_import.cmake)

project(vanchor_helm_pico C CXX ASM)
set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

pico_sdk_init()

add_executable(vanchor_helm_pico src/main.cpp)

target_include_directories(vanchor_helm_pico PRIVATE include)

# Explicit \r\n line endings are part of the wire contract — don't let the
# stdio layer translate them a second time.
target_compile_definitions(vanchor_helm_pico PRIVATE
    PICO_STDIO_DEFAULT_CRLF=0
)

target_link_libraries(vanchor_helm_pico
    pico_stdlib
    pico_flash
    hardware_adc
    hardware_flash
    hardware_i2c
    hardware_pwm
    hardware_watchdog
)

# USB CDC is the (only) control port; keep the UART free.
pico_enable_stdio_usb(vanchor_helm_pico 1)
pico_enable_stdio_uart(vanchor_helm_pico 0)

pico_add_extra_outputs(vanchor_helm_pico)   # .uf2 for BOOTSEL flashing
