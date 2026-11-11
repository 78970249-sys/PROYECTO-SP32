// =====================================================================
//  Asistente Inteligente de Escritorio - ESP32-S3 N16R8 (XiaoZhi AI)
//  config.h : asignación de pines y parámetros de la placa
//
//  Basado en la placa "bread-compact-wifi" del proyecto xiaozhi-esp32,
//  con tres LEDs externos controlables por voz mediante MCP.
// =====================================================================
#ifndef _BOARD_CONFIG_H_
#define _BOARD_CONFIG_H_

#include <driver/gpio.h>

// ---------------------------------------------------------------------
// Audio
//  Entrada (micrófono INMP441): 16 kHz, mono, 16 bits efectivos.
//  Salida (amplificador MAX98357A): 24 kHz, mono.
//  Modo SIMPLEX: micrófono y amplificador usan buses I2S separados.
// ---------------------------------------------------------------------
#define AUDIO_INPUT_SAMPLE_RATE  16000
#define AUDIO_OUTPUT_SAMPLE_RATE 24000

#define AUDIO_I2S_MIC_GPIO_WS   GPIO_NUM_4   // INMP441 WS  (selección de palabra)
#define AUDIO_I2S_MIC_GPIO_SCK  GPIO_NUM_5   // INMP441 SCK (reloj de bit)
#define AUDIO_I2S_MIC_GPIO_DIN  GPIO_NUM_6   // INMP441 SD  (datos hacia el ESP32-S3)

#define AUDIO_I2S_SPK_GPIO_DOUT GPIO_NUM_7   // MAX98357A DIN  (datos hacia el amplificador)
#define AUDIO_I2S_SPK_GPIO_BCLK GPIO_NUM_15  // MAX98357A BCLK (reloj de bit)
#define AUDIO_I2S_SPK_GPIO_LRCK GPIO_NUM_16  // MAX98357A LRC  (reloj de canal)

// ---------------------------------------------------------------------
// Botones y LED de estado
// ---------------------------------------------------------------------
#define BUILTIN_LED_GPIO        GPIO_NUM_48  // LED RGB (WS2812) de la placa: estado del asistente
#define BOOT_BUTTON_GPIO        GPIO_NUM_0   // BOOT: iniciar/terminar conversación
#define TOUCH_BUTTON_GPIO       GPIO_NUM_47  // Pulsador externo: mantener presionado para hablar
#define VOLUME_UP_BUTTON_GPIO   GPIO_NUM_40  // Pulsador externo: subir volumen (opcional)
#define VOLUME_DOWN_BUTTON_GPIO GPIO_NUM_39  // Pulsador externo: bajar volumen (opcional)

// ---------------------------------------------------------------------
// Pantalla OLED SSD1306 128x64 (I2C, dirección 0x3C)
// Si la pantalla no responde, el firmware sigue funcionando sin ella.
// ---------------------------------------------------------------------
#define DISPLAY_SDA_PIN  GPIO_NUM_41
#define DISPLAY_SCL_PIN  GPIO_NUM_42
#define DISPLAY_WIDTH    128
#define DISPLAY_HEIGHT   64
#define DISPLAY_MIRROR_X true
#define DISPLAY_MIRROR_Y true

// ---------------------------------------------------------------------
// LEDs del escritorio controlados por voz (MCP)
// Cada LED se conecta: GPIO -> resistencia 220-330 ohm -> ánodo (+) del LED;
// cátodo (-) del LED -> GND.
// ---------------------------------------------------------------------
#define DESK_LED_RED_GPIO     GPIO_NUM_17
#define DESK_LED_GREEN_GPIO   GPIO_NUM_18
#define DESK_LED_YELLOW_GPIO  GPIO_NUM_8

#endif // _BOARD_CONFIG_H_
