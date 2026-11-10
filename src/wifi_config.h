#pragma once
#include <Arduino.h>

// 初始化 WiFi：
//   - 已有保存的配置 → 读取并重连，连不上则自动开启 AP 配网
//   - 没有配置 → 直接开启 AP 热点配网
// 返回 true = WiFi 已连接；false = AP 配网超时仍未配置（调用方应重启设备）
bool setupWiFi();

// 当前是否处于 AP 配网模式（main 循环里用于跳过 WiFi 掉线重连逻辑）
bool isConfigMode();

// 联网后循环调用：WiFi 掉线自动重连，
// 长时间无法恢复则重新开启 AP 配网，配网完成后重启设备生效
void maintainWiFi();

// 擦除已保存的 WiFi 配置（不影响开关状态记忆）
void clearSavedWiFiConfig();

// 当前使用的 WiFi 凭据（供 Blinker.begin 使用）
const char* savedWiFiSSID();
const char* savedWiFiPassword();
