# Asistente Inteligente de Escritorio con ESP32-S3 N16R8

Asistente de voz en español basado en el firmware abierto **XiaoZhi AI** (xiaozhi-esp32).
El ESP32-S3 graba la voz con un micrófono I2S y la envía por Wi-Fi al servicio
**xiaozhi.me**, donde un modelo de lenguaje (**DeepSeek**) interpreta la orden y responde.
La respuesta se reproduce en un parlante propio.

Además del firmware oficial, este repositorio agrega una **placa personalizada** con
**tres LEDs controlados por voz** mediante **MCP** (Model Context Protocol). El modelo de IA solo
puede usar las herramientas que el firmware registra: no puede ejecutar otras acciones en el
dispositivo.

---

## 1. Materiales

| Componente | Cantidad | Uso |
|---|---|---|
| ESP32-S3-DevKitC-1 **N16R8** (16 MB Flash, 8 MB PSRAM) | 1 | Microcontrolador con Wi-Fi |
| Micrófono digital I2S **INMP441** | 1 | Entrada de voz |
| Amplificador I2S **MAX98357A** | 1 | Salida de audio |
| Parlante 4–8 Ω, 2–3 W | 1 | Voz del asistente |
| Pantalla OLED SSD1306 128×64 I2C (opcional) | 1 | Estados y texto |
| LEDs rojo, verde y amarillo | 3 | Dispositivos controlados por voz |
| Resistencias de 220–330 Ω | 3 | Limitar la corriente de los LEDs |
| Pulsador (opcional) | 1–3 | Hablar / volumen |
| Protoboard de 400 puntos | 2 | Montaje |
| Cables dupont y cable USB-C **de datos** | — | Conexiones y programación |

## 2. Conexiones

> Arma todo con la placa **desconectada** del USB. Todas las tierras (GND) van juntas.

| Módulo | Pin del módulo | Pin del ESP32-S3 |
|---|---|---|
| INMP441 | WS | GPIO 4 |
| INMP441 | SCK | GPIO 5 |
| INMP441 | SD | GPIO 6 |
| INMP441 | VDD / GND / L/R | 3V3 / GND / GND |
| MAX98357A | DIN | GPIO 7 |
| MAX98357A | BCLK | GPIO 15 |
| MAX98357A | LRC | GPIO 16 |
| MAX98357A | Vin / GND / SD | 3V3 / GND / unido a Vin |
| Parlante | + / − | Salida + / − del MAX98357A |
| OLED | SDA / SCL | GPIO 41 / GPIO 42 |
| OLED | VCC / GND | 3V3 / GND |
| LED rojo | ánodo (pata larga) con resistencia | GPIO 17 |
| LED verde | ánodo con resistencia | GPIO 18 |
| LED amarillo | ánodo con resistencia | GPIO 8 |
| LEDs | cátodo (pata corta) | GND |
| Pulsador "mantener para hablar" (opcional) | — | GPIO 47 ↔ GND |
| Pulsadores volumen + / − (opcionales) | — | GPIO 40 / GPIO 39 ↔ GND |

El botón **BOOT** de la placa (GPIO 0) inicia o termina la conversación.
El LED RGB de la placa (GPIO 48) muestra el estado del asistente.

---

## 3. Parte 1 — Instalar el firmware oficial (prueba rápida, sin compilar)

1. Entra a <https://github.com/78/xiaozhi-esp32/releases>, abre **Assets** y descarga
   `vX.Y.Z_bread-compact-wifi-128x64.zip` (o `vX.Y.Z_bread-compact-wifi.zip` si no tienes OLED
   de 128×64). No descargues "Source code". Descomprime: obtendrás `merged-binary.bin`.
2. Abre <https://espressif.github.io/esptool-js/> en **Chrome o Edge**, conecta la placa por el
   puerto USB-C marcado **COM/UART** y pulsa **Connect**.
3. (Recomendado) **Erase Flash**. Luego, en **Flash Address** escribe `0x0`, elige
   `merged-binary.bin` y pulsa **Program**. Al terminar, presiona **RST**.
   - Si no conecta: mantén **BOOT**, pulsa y suelta **RST**, suelta **BOOT** y reintenta.
4. Conéctate desde el celular a la red Wi-Fi **Xiaozhi-XXXX**; si no se abre la página,
   entra a `http://192.168.4.1`. Elige una red **2.4 GHz** y escribe la contraseña.
5. El asistente dirá un **código de 6 dígitos**. En <https://xiaozhi.me> crea una cuenta,
   abre la consola, crea un agente y agrega el dispositivo con ese código.
6. En la configuración del rol elige el modelo **DeepSeek** y en la descripción escribe
   *"Responde siempre en español"*. Guarda y reinicia la placa.
7. Pulsa **BOOT** y habla. Prueba de LED con el firmware oficial: un LED en **GPIO 18** se
   controla diciendo *"enciende la lámpara"* / *"apaga la lámpara"*.

---

## 4. Parte 2 — Firmware propio con 3 LEDs controlados por voz

### Requisitos
- **ESP-IDF v6.0.1 o superior** (Espressif recomienda la rama `release/v6.1`). ESP-IDF 5.x no
  sirve para la versión actual de xiaozhi-esp32.
- Git y Python (vienen con el instalador de ESP-IDF).

### Pasos (en la terminal de ESP-IDF)

```bash
# 1. Descargar el proyecto XiaoZhi y este repositorio
git clone https://github.com/78/xiaozhi-esp32.git
git clone https://github.com/78970249-sys/PROYECTO-SP32.git

# 2. Agregar la placa personalizada a XiaoZhi (copia la carpeta y registra la placa)
python PROYECTO-SP32/herramientas/instalar_placa.py xiaozhi-esp32

# 3. Compilar en español (la palabra de activación por defecto será "Hi ESP")
cd xiaozhi-esp32
python scripts/build.py asistente-escritorio-uc --language es-ES

# 4. Grabar en la placa (cambia COM5 por tu puerto)
idf.py -p COM5 flash monitor
```

También puedes grabar el archivo `xiaozhi-esp32/build/merged-binary.bin` con esptool-js en la
dirección `0x0`, igual que en la Parte 1. La configuración de Wi-Fi y la activación en
xiaozhi.me se hacen igual que en la Parte 1.

> La placa tiene su propio tipo (`asistente-escritorio-uc`), por eso las actualizaciones OTA del
> firmware oficial no reemplazan este firmware personalizado.

### Herramientas MCP que registra la placa

| Herramienta | Parámetros | Qué hace |
|---|---|---|
| `self.desk_leds.get_state` | — | Devuelve en JSON si cada LED está encendido y su brillo |
| `self.desk_leds.turn_on` | `led`: rojo, verde, amarillo o todos · `brightness`: 1–100 (100) | Enciende y ajusta el brillo (PWM) |
| `self.desk_leds.turn_off` | `led` | Apaga uno o todos |
| `self.desk_leds.blink` | `led` · `times`: 1–10 (3) | Parpadea y vuelve al estado anterior |

También quedan disponibles las herramientas comunes del firmware, como
`self.audio_speaker.set_volume` (volumen del parlante).

### Ejemplos de órdenes de voz
- "Enciende la luz roja."
- "Pon la luz verde al 30 por ciento."
- "Enciende todas las luces." / "Apaga todo."
- "Haz parpadear la luz amarilla cinco veces."
- "¿Qué luces están encendidas?"
- "Baja el volumen a 40."

---

## 5. Pruebas en PC (sin la placa)

`pruebas/` contiene una prueba que compila `desk_led_controller.h` junto con el
`mcp_server.h` real de xiaozhi-esp32 y simulaciones (stubs) del ESP-IDF. Verifica:
encendido, apagado, brillo, "todos", nombres inválidos, parpadeo y restauración del estado.

```bash
./pruebas/ejecutar_pruebas.sh RUTA_A/xiaozhi-esp32   # requiere g++ 13+ (Linux, WSL o MSYS2)
```

## 6. Estructura del repositorio

```
firmware/asistente-escritorio-uc/
    config.h                       Pines y parámetros de la placa
    config.json                    Tipo de placa para el script de compilación
    asistente_escritorio_board.cc  Inicialización: audio I2S, OLED, botones, LEDs
    desk_led_controller.h          LEDs con PWM (LEDC) + herramientas MCP
herramientas/instalar_placa.py     Registra la placa en una copia de xiaozhi-esp32
pruebas/                           Prueba en PC de las herramientas MCP
```

## 7. Créditos y licencia

- Firmware base: [xiaozhi-esp32](https://github.com/78/xiaozhi-esp32) (licencia MIT).
  `asistente_escritorio_board.cc` se deriva de la placa `bread-compact-wifi` de ese proyecto.
- Servicio de IA: xiaozhi.me con el modelo DeepSeek.
