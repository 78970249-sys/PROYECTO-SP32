#pragma once
#include <cstdint>
typedef void* TaskHandle_t; typedef long BaseType_t; typedef uint32_t TickType_t;
#define pdPASS 1
#define pdMS_TO_TICKS(x) ((TickType_t)(x))
