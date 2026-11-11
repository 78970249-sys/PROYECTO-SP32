#pragma once
typedef void (*TaskFunction_t)(void*);
BaseType_t xTaskCreate(TaskFunction_t, const char*, uint32_t, void*, unsigned, TaskHandle_t*);
void vTaskDelay(TickType_t); void vTaskDelete(TaskHandle_t);
