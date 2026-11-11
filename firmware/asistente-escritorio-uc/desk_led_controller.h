// =====================================================================
//  desk_led_controller.h
//  Controla tres LEDs del escritorio (rojo, verde y amarillo) con PWM
//  (periférico LEDC del ESP32-S3) y los expone al modelo de IA como
//  herramientas MCP. El modelo de lenguaje (por ejemplo, DeepSeek) solo
//  puede ejecutar estas cuatro herramientas: no puede ejecutar código
//  arbitrario en el dispositivo.
//
//  Herramientas registradas:
//    self.desk_leds.get_state  -> estado y brillo de cada LED (JSON)
//    self.desk_leds.turn_on    -> encender un LED o todos (brillo 1-100 %)
//    self.desk_leds.turn_off   -> apagar un LED o todos
//    self.desk_leds.blink      -> hacer parpadear un LED o todos (1-10 veces)
// =====================================================================
#ifndef DESK_LED_CONTROLLER_H
#define DESK_LED_CONTROLLER_H

#include "mcp_server.h"

#include <driver/gpio.h>
#include <driver/ledc.h>
#include <esp_log.h>
#include <freertos/FreeRTOS.h>
#include <freertos/task.h>

#include <atomic>
#include <cstdint>
#include <string>

class DeskLedController {
private:
    static constexpr const char* kTag = "DeskLed";

    // Estado de cada LED
    struct DeskLed {
        const char* name;        // nombre que usa la IA: "rojo", "verde", "amarillo"
        gpio_num_t gpio;         // pin de salida
        ledc_channel_t channel;  // canal PWM asignado
        bool on;                 // encendido / apagado
        int brightness;          // brillo en % (1-100)
    };

    static constexpr int kLedCount = 3;
    static constexpr ledc_mode_t kSpeedMode = LEDC_LOW_SPEED_MODE;
    static constexpr ledc_timer_t kTimer = LEDC_TIMER_1;          // el TIMER_0 queda libre
    static constexpr ledc_timer_bit_t kResolution = LEDC_TIMER_10_BIT;
    static constexpr uint32_t kMaxDuty = (1u << 10) - 1;          // 1023 = 100 %
    static constexpr uint32_t kPwmFrequencyHz = 5000;             // 5 kHz: sin parpadeo visible
    static constexpr int kBlinkHalfPeriodMs = 300;

    DeskLed leds_[kLedCount];
    std::atomic<bool> blinking_{false};
    int blink_mask_ = 0;
    int blink_times_ = 0;

    // Escribe en el PWM el ciclo de trabajo correspondiente a un LED.
    void WriteDuty(const DeskLed& led, bool lit) {
        uint32_t duty = lit ? kMaxDuty * static_cast<uint32_t>(led.brightness) / 100 : 0;
        ledc_set_duty(kSpeedMode, led.channel, duty);
        ledc_update_duty(kSpeedMode, led.channel);
    }

    // Aplica el estado guardado (on/off y brillo) a todos los LEDs.
    void ApplyAll() {
        for (const auto& led : leds_) {
            WriteDuty(led, led.on);
        }
    }

    // Convierte el nombre recibido de la IA en una máscara de bits:
    // bit 0 = rojo, bit 1 = verde, bit 2 = amarillo. Devuelve 0 si no es válido.
    int ParseLedName(const std::string& name) const {
        if (name == "todos" || name == "all") {
            return (1 << kLedCount) - 1;
        }
        for (int i = 0; i < kLedCount; ++i) {
            if (name == leds_[i].name) {
                return 1 << i;
            }
        }
        if (name == "red") return 1 << 0;
        if (name == "green") return 1 << 1;
        if (name == "yellow") return 1 << 2;
        return 0;
    }

    // Estado de los LEDs en JSON, por ejemplo:
    // {"rojo":{"on":true,"brightness":100},...,"blinking":false}
    std::string StateJson() const {
        std::string json = "{";
        for (int i = 0; i < kLedCount; ++i) {
            if (i > 0) {
                json += ",";
            }
            json += "\"" + std::string(leds_[i].name) + "\":{\"on\":" +
                    (leds_[i].on ? "true" : "false") +
                    ",\"brightness\":" + std::to_string(leds_[i].brightness) + "}";
        }
        json += std::string(",\"blinking\":") + (blinking_.load() ? "true" : "false") + "}";
        return json;
    }

    // Tarea temporal de FreeRTOS que hace parpadear los LEDs sin bloquear
    // al asistente (la conversación y el audio siguen funcionando).
    static void BlinkTask(void* arg) {
        auto* self = static_cast<DeskLedController*>(arg);
        for (int n = 0; n < self->blink_times_; ++n) {
            for (int i = 0; i < kLedCount; ++i) {
                if (self->blink_mask_ & (1 << i)) self->WriteDuty(self->leds_[i], true);
            }
            vTaskDelay(pdMS_TO_TICKS(kBlinkHalfPeriodMs));
            for (int i = 0; i < kLedCount; ++i) {
                if (self->blink_mask_ & (1 << i)) self->WriteDuty(self->leds_[i], false);
            }
            vTaskDelay(pdMS_TO_TICKS(kBlinkHalfPeriodMs));
        }
        self->ApplyAll();          // vuelve al estado que tenían antes de parpadear
        self->blinking_ = false;
        vTaskDelete(nullptr);
    }

    void RegisterTools() {
        auto& mcp_server = McpServer::GetInstance();

        // 1) Consultar el estado
        mcp_server.AddTool(
            "self.desk_leds.get_state",
            "Get the state of the three desk LEDs (rojo = red, verde = green, "
            "amarillo = yellow): whether each one is on and its brightness in percent.",
            PropertyList(),
            [this](const PropertyList& properties) -> ReturnValue {
                return StateJson();
            });

        // 2) Encender (con brillo opcional)
        mcp_server.AddTool(
            "self.desk_leds.turn_on",
            "Turn on a desk LED. `led` must be one of: \"rojo\" (red), \"verde\" (green), "
            "\"amarillo\" (yellow) or \"todos\" (all). `brightness` is a percentage from 1 to "
            "100 (default 100). Use it also to change the brightness of an LED.",
            PropertyList({
                Property("led", kPropertyTypeString),
                Property("brightness", kPropertyTypeInteger, 100, 1, 100),
            }),
            [this](const PropertyList& properties) -> ToolResult {
                int mask = ParseLedName(properties["led"].value<std::string>());
                if (mask == 0) {
                    return std::unexpected("Unknown LED. Use rojo, verde, amarillo or todos");
                }
                int brightness = properties["brightness"].value<int>();
                for (int i = 0; i < kLedCount; ++i) {
                    if (mask & (1 << i)) {
                        leds_[i].on = true;
                        leds_[i].brightness = brightness;
                        WriteDuty(leds_[i], true);
                    }
                }
                ESP_LOGI(kTag, "turn_on mask=%d brightness=%d", mask, brightness);
                return StateJson();
            });

        // 3) Apagar
        mcp_server.AddTool(
            "self.desk_leds.turn_off",
            "Turn off a desk LED. `led` must be one of: \"rojo\" (red), \"verde\" (green), "
            "\"amarillo\" (yellow) or \"todos\" (all).",
            PropertyList({
                Property("led", kPropertyTypeString),
            }),
            [this](const PropertyList& properties) -> ToolResult {
                int mask = ParseLedName(properties["led"].value<std::string>());
                if (mask == 0) {
                    return std::unexpected("Unknown LED. Use rojo, verde, amarillo or todos");
                }
                for (int i = 0; i < kLedCount; ++i) {
                    if (mask & (1 << i)) {
                        leds_[i].on = false;
                        WriteDuty(leds_[i], false);
                    }
                }
                ESP_LOGI(kTag, "turn_off mask=%d", mask);
                return StateJson();
            });

        // 4) Parpadear
        mcp_server.AddTool(
            "self.desk_leds.blink",
            "Blink a desk LED a number of times (1 to 10, default 3), then restore its previous "
            "state. `led` must be one of: \"rojo\", \"verde\", \"amarillo\" or \"todos\".",
            PropertyList({
                Property("led", kPropertyTypeString),
                Property("times", kPropertyTypeInteger, 3, 1, 10),
            }),
            [this](const PropertyList& properties) -> ToolResult {
                int mask = ParseLedName(properties["led"].value<std::string>());
                if (mask == 0) {
                    return std::unexpected("Unknown LED. Use rojo, verde, amarillo or todos");
                }
                if (blinking_.exchange(true)) {
                    return std::unexpected("A blink is already running, try again in a few seconds");
                }
                blink_mask_ = mask;
                blink_times_ = properties["times"].value<int>();
                if (xTaskCreate(BlinkTask, "desk_led_blink", 3072, this, 2, nullptr) != pdPASS) {
                    blinking_ = false;
                    return std::unexpected("Could not start the blink task");
                }
                ESP_LOGI(kTag, "blink mask=%d times=%d", mask, blink_times_);
                return true;
            });
    }

public:
    DeskLedController(gpio_num_t red_gpio, gpio_num_t green_gpio, gpio_num_t yellow_gpio)
        : leds_{{"rojo", red_gpio, LEDC_CHANNEL_1, false, 100},
                {"verde", green_gpio, LEDC_CHANNEL_2, false, 100},
                {"amarillo", yellow_gpio, LEDC_CHANNEL_3, false, 100}} {
        // Temporizador PWM compartido por los tres canales
        ledc_timer_config_t timer_config = {};
        timer_config.speed_mode = kSpeedMode;
        timer_config.duty_resolution = kResolution;
        timer_config.timer_num = kTimer;
        timer_config.freq_hz = kPwmFrequencyHz;
        timer_config.clk_cfg = LEDC_AUTO_CLK;
        ESP_ERROR_CHECK(ledc_timer_config(&timer_config));

        // Un canal PWM por LED; todos arrancan apagados (duty = 0)
        for (const auto& led : leds_) {
            ledc_channel_config_t channel_config = {};
            channel_config.gpio_num = led.gpio;
            channel_config.speed_mode = kSpeedMode;
            channel_config.channel = led.channel;
            channel_config.intr_type = LEDC_INTR_DISABLE;
            channel_config.timer_sel = kTimer;
            channel_config.duty = 0;
            channel_config.hpoint = 0;
            ESP_ERROR_CHECK(ledc_channel_config(&channel_config));
        }

        RegisterTools();
        ESP_LOGI(kTag, "Desk LEDs ready (rojo=%d, verde=%d, amarillo=%d)",
                 (int)red_gpio, (int)green_gpio, (int)yellow_gpio);
    }
};

#endif  // DESK_LED_CONTROLLER_H
