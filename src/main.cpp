/*********************************************************************
 * ESP32-C3 ProMini 远程电源开关（点灯 Blinker + 自建 AP 热点配网）
 *
 * 功能：
 *   1. 通过「点灯」App 远程开/关一路 5V 电源输出（继电器 / MOSFET 通断），
 *      点「开」→ 设备通电，点「关」→ 设备断电
 *   2. 从未配过网时：自动开启 AP 热点（ESP32C3-Switch-XXXX），
 *      手机连热点访问 http://192.168.4.1 填写 WiFi 信息完成配网，
 *      配置自动保存到 NVS
 *   3. 已配过网：开机直接读取配置重连 WiFi，不再开启热点；
 *      连不上则自动重新开启 AP 热点，方便重新配网
 *   4. WiFi 掉线自动重连；长时间无法恢复自动重新开热点
 *   5. 开关状态存入 NVS，断电重启后自动恢复
 *   6. 长按板载 BOOT 键 5 秒：擦除 WiFi 配置并重启，重新进入配网模式
 *
 * 需要修改的配置（设备密钥 / 引脚 / 极性等）全部在 include/config.h
 *********************************************************************/

#define BLINKER_WIFI
#include <Blinker.h>
#include <Preferences.h>
#include <string.h>

#include "config.h"
#include "wifi_config.h"

// 点灯开关组件：key 需与 App 内「开关」组件的 key 一致（默认 sw-power）
char powerKey[] = "sw-power";
BlinkerButton PowerSwitch(powerKey);
Preferences powerPrefs;

bool powerOn = false;
bool bootPressed = false;
unsigned long bootPressStart = 0;

// 设置电源输出，并把状态存入 NVS（断电重启后恢复）
void setPower(bool on)
{
    powerOn = on;
    digitalWrite(POWER_PIN, on ? POWER_ON_LEVEL : POWER_OFF_LEVEL);
    powerPrefs.putBool("state", on);
    BLINKER_LOG("power -> %s", on ? "ON" : "OFF");
}

// 点灯 App 开关组件回调：收到 on / off 指令
void powerCallback(const String &state)
{
    if (state == BLINKER_CMD_ON) {
        setPower(true);
    } else if (state == BLINKER_CMD_OFF) {
        setPower(false);
    }
    PowerSwitch.print(powerOn ? BLINKER_CMD_ON : BLINKER_CMD_OFF);   // 同步状态到 App
    Blinker.vibrate();
}

// 心跳回调（设备在线时周期性触发）：把当前开关状态同步到 App，
// 解决设备重启/断线重连后 App 显示与真实状态不一致的问题
void heartbeat()
{
    PowerSwitch.print(powerOn ? BLINKER_CMD_ON : BLINKER_CMD_OFF);
}

void setup()
{
    Serial.begin(115200);
    delay(100);
    Serial.println("\n=== ESP32-C3 power switch boot ===");

    // 提醒：先填入点灯 App 设备密钥（检测到占位符即阻止继续运行）
    if (strstr(BLINKER_AUTH, "在此填入") != nullptr) {
        Serial.println("!! 请先在 include/config.h 的 BLINKER_AUTH 中填入点灯App设备密钥 !!");
        while (1) { delay(1000); }
    }

    pinMode(POWER_PIN, OUTPUT);
    pinMode(BOOT_PIN, INPUT_PULLUP);   // 板载 BOOT 键（GPIO9）

    // 恢复上次保存的开关状态（即使暂未联网，本地开关也保持）
    powerPrefs.begin("power", false);
    powerOn = powerPrefs.getBool("state", false);
    digitalWrite(POWER_PIN, powerOn ? POWER_ON_LEVEL : POWER_OFF_LEVEL);
    Serial.printf("[Power] restored: %s\n", powerOn ? "ON" : "OFF");

    // WiFi：有配置 → 读取重连；没配置/连不上 → 自建 AP 热点配网
    if (!setupWiFi()) {
        Serial.println("[WiFi] no config after AP timeout, rebooting...");
        delay(1000);
        ESP.restart();
    }

    // WiFi 已连接，初始化点灯（传入已保存的凭据，不再进入 Blinker 自带配网）
    Blinker.begin(BLINKER_AUTH, savedWiFiSSID(), savedWiFiPassword());
    PowerSwitch.attach(powerCallback);
    Blinker.attachHeartbeat(heartbeat);
    Serial.println("[Blinker] ready, remote power switch online");
}

void loop()
{
    Blinker.run();

    // WiFi 掉线自动重连 / 长时间掉线重新开热点配网
    maintainWiFi();

    // 长按 BOOT 键 RESET_HOLD_MS 毫秒：擦除 WiFi 配置，重启后重新配网
    bool pressed = (digitalRead(BOOT_PIN) == LOW);
    if (pressed) {
        if (!bootPressed) {
            bootPressed = true;
            bootPressStart = millis();
        } else if (millis() - bootPressStart >= RESET_HOLD_MS) {
            Serial.printf("[Reset] BOOT held %lu ms, erasing WiFi config...\n",
                          (unsigned long)RESET_HOLD_MS);
            // 先断开输出，避免复位期间负载通电
            setPower(false);
            delay(100);
            clearSavedWiFiConfig();
            Serial.println("[Reset] rebooting into AP config mode...");
            delay(200);
            ESP.restart();
        }
    } else {
        bootPressed = false;
    }
}
