// Prueba en PC de las herramientas MCP de desk_led_controller.h
// Usa stubs (simulaciones) del ESP-IDF y el mcp_server.h real de xiaozhi-esp32.
#include "desk_led_controller.h"
#include <map>
#include <cassert>
#include <iostream>
#include <stdexcept>
// ---- fake runtime -------------------------------------------------
[[noreturn]] void esp_system_abort(const char* m) { throw std::runtime_error(m); }
static std::map<int,uint32_t> g_duty;
esp_err_t ledc_timer_config(const ledc_timer_config_t* t){ assert(t->timer_num==LEDC_TIMER_1); return 0; }
esp_err_t ledc_channel_config(const ledc_channel_config_t* c){ g_duty[c->channel]=c->duty; return 0; }
esp_err_t ledc_set_duty(ledc_mode_t, ledc_channel_t ch, uint32_t d){ g_duty[ch]=d; return 0; }
esp_err_t ledc_update_duty(ledc_mode_t, ledc_channel_t){ return 0; }
static TaskFunction_t g_task; static void* g_arg;
BaseType_t xTaskCreate(TaskFunction_t f, const char*, uint32_t, void* a, unsigned, TaskHandle_t*){ g_task=f; g_arg=a; return pdPASS; }
static int g_delays=0; void vTaskDelay(TickType_t){ g_delays++; } void vTaskDelete(TaskHandle_t){}
static std::map<std::string, ToolCallback> g_tools;
McpServer::McpServer() {} McpServer::~McpServer() {}
void McpServer::AddTool(const std::string& n, const std::string&, const PropertyList&, ToolCallback cb){ g_tools[n]=cb; }
// ---- helpers ------------------------------------------------------
static std::string str(const ToolResult& r){
  if(!r) return "ERROR: " + r.error();
  if (auto s = std::get_if<std::string>(&*r)) return *s;
  if (auto b = std::get_if<bool>(&*r)) return *b ? "true" : "false";
  return "?";
}
int main(){
  static DeskLedController c(GPIO_NUM_17, GPIO_NUM_18, GPIO_NUM_8);
  assert(g_tools.size()==4);
  auto on = [](std::string led, int br){ PropertyList p({Property("led",kPropertyTypeString,led), Property("brightness",kPropertyTypeInteger,br,1,100)}); return g_tools["self.desk_leds.turn_on"](p); };
  auto off = [](std::string led){ PropertyList p({Property("led",kPropertyTypeString,led)}); return g_tools["self.desk_leds.turn_off"](p); };
  auto blink = [](std::string led, int t){ PropertyList p({Property("led",kPropertyTypeString,led), Property("times",kPropertyTypeInteger,t,1,10)}); return g_tools["self.desk_leds.blink"](p); };
  auto state = [](){ return g_tools["self.desk_leds.get_state"](PropertyList()); };

  std::cout << "estado inicial : " << str(state()) << "\n";
  std::cout << "rojo 100       : " << str(on("rojo",100)) << "\n";   assert(g_duty[LEDC_CHANNEL_1]==1023);
  std::cout << "verde 30       : " << str(on("verde",30)) << "\n";   assert(g_duty[LEDC_CHANNEL_2]==1023*30/100);
  std::cout << "apagar rojo    : " << str(off("rojo")) << "\n";      assert(g_duty[LEDC_CHANNEL_1]==0);
  std::cout << "led 'azul'     : " << str(on("azul",50)) << "\n";
  std::cout << "todos 50       : " << str(on("todos",50)) << "\n";   assert(g_duty[LEDC_CHANNEL_3]==1023*50/100);
  std::cout << "apagar todos   : " << str(off("all")) << "\n";       assert(g_duty[LEDC_CHANNEL_1]==0 && g_duty[LEDC_CHANNEL_2]==0 && g_duty[LEDC_CHANNEL_3]==0);
  on("amarillo", 80);
  std::cout << "parpadear x3   : " << str(blink("verde",3)) << "\n";
  std::cout << "otro parpadeo  : " << str(blink("rojo",2)) << "\n";
  g_task(g_arg);  // ejecutar la tarea de parpadeo
  assert(g_delays==6);
  assert(g_duty[LEDC_CHANNEL_2]==0 && g_duty[LEDC_CHANNEL_3]==1023*80/100);  // verde vuelve a apagado, amarillo sigue
  std::cout << "tras parpadeo  : " << str(state()) << "\n";
  std::cout << "parpadeo nuevo : " << str(blink("rojo",2)) << "\n";
  std::cout << "TODAS LAS PRUEBAS OK\n";
}
