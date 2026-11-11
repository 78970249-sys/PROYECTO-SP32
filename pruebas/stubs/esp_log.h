#pragma once
// Stub de esp_log.h para pruebas en PC: imprime los mensajes en consola
#include <cstdio>
#define ESP_LOGI(tag, fmt, ...) printf("  [log] " fmt "\n", ##__VA_ARGS__)
#define ESP_LOGE(tag, fmt, ...) printf("  [err] " fmt "\n", ##__VA_ARGS__)
#define ESP_LOGW(tag, fmt, ...) printf("  [warn] " fmt "\n", ##__VA_ARGS__)
