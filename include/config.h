#pragma once
#include <Arduino.h>

// =====================================================================
//  ESP32-C3 ProMini 远程电源开关 —— 用户配置区
//  本文件是唯一需要按自己设备/网络修改的文件，其余代码无需改动
// =====================================================================

// 1) 点灯 App 设备密钥（Device Secret Key）
//    点灯 App 内：「添加设备 → 独立设备 → WiFi 接入」，
//    把生成的设备密钥填到下面引号内
constexpr const char* BLINKER_AUTH = "在此填入点灯App的设备密钥";

// 2) 电源输出控制引脚（ProMini 引出脚为 GPIO0~10）
//    - 合宙 ProMini「继电器版」：板上继电器由 GPIO10 控制，保持默认即可
//    - 普通版 + 外接 MOSFET / 继电器模块：改成你实际接线的 GPIO
//    注意：GPIO2 / GPIO8 / GPIO9 是 strapping 脚，上电时序特殊，
//          不要用作开关输出；GPIO4~7 为 JTAG 复用脚，正常输出没问题
const uint8_t POWER_PIN = 10;

// 3) 输出电平极性（按你的硬件接法选择）
//    - ProMini 继电器版 / 低边 N-MOS（AO3400）：高电平通电 → 保持 HIGH
//    - 继电器模块（IN 低电平触发）：低电平通电 → 改成 LOW
const uint8_t POWER_ON_LEVEL  = HIGH;
const uint8_t POWER_OFF_LEVEL = LOW;

// 4) AP 配网热点
//    热点名 = AP_SSID_PREFIX + 芯片 MAC 后 4 位，例如 ESP32C3-Switch-A1B2
//    AP_PASSWORD 填 NULL 表示开放热点（配网最方便）；设置密码则必须 ≥ 8 位
constexpr const char* AP_SSID_PREFIX = "ESP32C3-Switch";
constexpr const char* AP_PASSWORD    = nullptr;

// 5) 用已保存配置连接 WiFi 的超时时间（毫秒），超时自动进入 AP 配网
const uint32_t WIFI_CONNECT_TIMEOUT_MS = 15000;

// 6) AP 配网模式的停留时长（毫秒），超时仍未配网则重启设备重新开热点
const uint32_t AP_CONFIG_TIMEOUT_MS = 300000;   // 5 分钟

// 7) 联网后 WiFi 掉线：持续掉线超过该时长，重新开启 AP 配网（毫秒）
const uint32_t WIFI_LOST_RECONFIG_MS = 120000;  // 2 分钟

// 8) 长按板载 BOOT 键擦除配网信息并重启的时长（毫秒）
const uint32_t RESET_HOLD_MS = 5000;

// 9) 板载 BOOT 按键引脚（ProMini：GPIO9，内部上拉，按下为低电平）
const uint8_t BOOT_PIN = 9;
