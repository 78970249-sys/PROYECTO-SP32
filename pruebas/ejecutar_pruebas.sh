#!/usr/bin/env bash
# Compila y ejecuta en la PC la prueba de las herramientas MCP de los LEDs.
# Requiere g++ 13 o superior (Linux, WSL o MSYS2) y una copia de xiaozhi-esp32.
# Uso: ./ejecutar_pruebas.sh RUTA_A_xiaozhi-esp32
set -e
XZ="${1:?Indica la ruta a xiaozhi-esp32}"
DIR="$(cd "$(dirname "$0")" && pwd)"
g++ -std=gnu++23 -Wall -Wno-unused-parameter \
    -I"$DIR/stubs" -I"$XZ/main" -I"$DIR/../firmware/asistente-escritorio-uc" \
    "$DIR/prueba_desk_leds.cc" -o "$DIR/prueba_desk_leds"
"$DIR/prueba_desk_leds"
