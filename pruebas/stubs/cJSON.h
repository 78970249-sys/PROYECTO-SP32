#pragma once
#include <cstddef>
typedef struct cJSON { int type; double valuedouble; char* valuestring; struct cJSON* next; struct cJSON* child; char* string; } cJSON;
#define cJSON_bool int
cJSON* cJSON_CreateObject(); cJSON* cJSON_CreateArray(); cJSON* cJSON_CreateString(const char*);
cJSON* cJSON_AddStringToObject(cJSON*, const char*, const char*);
cJSON* cJSON_AddBoolToObject(cJSON*, const char*, cJSON_bool);
cJSON* cJSON_AddNumberToObject(cJSON*, const char*, double);
cJSON_bool cJSON_AddItemToObject(cJSON*, const char*, cJSON*);
cJSON_bool cJSON_AddItemToArray(cJSON*, cJSON*);
cJSON* cJSON_Parse(const char*); char* cJSON_PrintUnformatted(const cJSON*);
void cJSON_Delete(cJSON*); void cJSON_free(void*);
cJSON* cJSON_GetObjectItem(const cJSON*, const char*);
cJSON_bool cJSON_IsString(const cJSON*); cJSON_bool cJSON_IsNumber(const cJSON*); cJSON_bool cJSON_IsBool(const cJSON*); cJSON_bool cJSON_IsTrue(const cJSON*); cJSON_bool cJSON_IsObject(const cJSON*); cJSON_bool cJSON_IsArray(const cJSON*);
cJSON* cJSON_CreateNumber(double); cJSON* cJSON_CreateBool(cJSON_bool); cJSON* cJSON_Duplicate(const cJSON*, cJSON_bool);
int cJSON_GetArraySize(const cJSON*); cJSON* cJSON_GetArrayItem(const cJSON*, int);
char* cJSON_Print(const cJSON*);
