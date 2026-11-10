/*********************************************************************
 * WiFi 配置模块：自建 AP 热点 + 网页配网
 *
 * 工作方式：
 *   - 配置以 SSID + 密码形式保存在 NVS（Preferences）
 *   - 未配网 / 配网失败时，开启 AP 热点（ESP32C3-Switch-XXXX），
 *     手机连接热点后访问 http://192.168.4.1 填写 WiFi 信息完成配网
 *   - 已配网：读取配置直接连接，不再开启热点
 *********************************************************************/

#include "wifi_config.h"
#include "config.h"

#include <WiFi.h>
#include <WebServer.h>
#include <Preferences.h>

static const char* NVS_NAMESPACE = "wifi";
static const char* KEY_SSID      = "ssid";
static const char* KEY_PASS      = "pass";

static Preferences   prefs;
static WebServer*    server     = nullptr;
static String        savedSSID;
static String        savedPass;
static bool          configMode = false;   // 是否正处于 AP 配网模式
static bool          configSaved = false;  // /save 已写入新配置

// ---------------------------------------------------------------------
// NVS 读写
// ---------------------------------------------------------------------

static bool loadSavedWiFi()
{
    prefs.begin(NVS_NAMESPACE, true);
    savedSSID = prefs.getString(KEY_SSID, "");
    savedPass = prefs.getString(KEY_PASS, "");
    prefs.end();
    return savedSSID.length() > 0;
}

static void storeSavedWiFi(const String &ssid, const String &pass)
{
    prefs.begin(NVS_NAMESPACE, false);
    prefs.putString(KEY_SSID, ssid);
    prefs.putString(KEY_PASS, pass);
    prefs.end();
}

void clearSavedWiFiConfig()
{
    prefs.begin(NVS_NAMESPACE, false);
    prefs.remove(KEY_SSID);
    prefs.remove(KEY_PASS);
    prefs.end();
    savedSSID = "";
    savedPass = "";
}

// ---------------------------------------------------------------------
// 连接保存的 WiFi（带超时）
// ---------------------------------------------------------------------

static bool connectSavedWiFi(uint32_t timeoutMs)
{
    WiFi.mode(WIFI_STA);
    WiFi.begin(savedSSID.c_str(), savedPass.c_str());
    Serial.printf("[WiFi] connecting \"%s\"", savedSSID.c_str());

    unsigned long start = millis();
    while (millis() - start < timeoutMs) {
        if (WiFi.status() == WL_CONNECTED) {
            Serial.printf("\n[WiFi] connected, IP: ");
            Serial.println(WiFi.localIP());
            return true;
        }
        delay(500);
        Serial.print(".");
    }
    Serial.println("\n[WiFi] connect timeout");
    return false;
}

// ---------------------------------------------------------------------
// AP 配网网页（内嵌 HTML/CSS/JS）
// ---------------------------------------------------------------------

// 配网主页：WiFi 名称输入 + 扫描网络 + 密码 + 保存
static const char PAGE_CONFIG[] PROGMEM = R"html(
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>ESP32-C3 智能开关 · WiFi 配网</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body { font-family: "PingFang SC", "Microsoft YaHei", sans-serif; background: #f2f4f8; color: #222; padding: 24px 16px; }
  .card { max-width: 420px; margin: 0 auto; background: #fff; border-radius: 14px; padding: 28px 24px; box-shadow: 0 4px 20px rgba(0,0,0,.08); }
  h1 { font-size: 20px; margin-bottom: 6px; }
  .sub { font-size: 13px; color: #888; margin-bottom: 22px; }
  label { display: block; font-size: 13px; font-weight: 600; margin: 14px 0 6px; }
  input { width: 100%; padding: 12px; border: 1px solid #d9dde3; border-radius: 8px; font-size: 15px; outline: none; }
  input:focus { border-color: #2f7bff; }
  button { border: 0; border-radius: 8px; padding: 12px; font-size: 15px; cursor: pointer; }
  .ghost { width: 100%; background: #eef2f7; color: #444; margin-top: 6px; }
  .btn-save { width: 100%; background: #2f7bff; color: #fff; margin-top: 22px; font-weight: 600; }
  #scanList { margin-top: 10px; }
  #scanList div { padding: 10px 12px; border: 1px solid #e4e8ee; border-radius: 8px; margin-bottom: 6px; font-size: 14px; cursor: pointer; }
  #scanList div.cur { background: #eaf3ff; border-color: #2f7bff; }
  #status { margin-top: 14px; font-size: 13px; color: #2f7bff; display: none; }
</style>
</head>
<body>
<div class="card">
  <h1>ESP32-C3 智能开关</h1>
  <div class="sub">选择要连接的 WiFi 并保存，设备将自动连接</div>
  <form method="POST" action="/save" onsubmit="return submitSave(this)">
    <label for="ssid">WiFi 名称（SSID）</label>
    <input type="text" id="ssid" name="ssid" placeholder="点击下方网络，或手动输入" required>
    <button type="button" class="ghost" onclick="scanNetworks()">扫描可用网络</button>
    <div id="scanList"></div>
    <label for="pass">WiFi 密码</label>
    <input type="password" id="pass" name="pass" placeholder="无密码请留空">
    <button type="submit" class="btn-save">保存并连接</button>
    <div id="status"></div>
  </form>
</div>
<script>
async function scanNetworks() {
  var box = document.getElementById('scanList');
  box.innerHTML = '<div>正在扫描…</div>';
  try {
    var res = await fetch('/scan');
    var list = await res.json();
    if (!list.length) { box.innerHTML = '<div>未扫描到可用网络</div>'; return; }
    box.innerHTML = '';
    list.forEach(function(ssid) {
      var d = document.createElement('div');
      d.textContent = ssid;
      d.onclick = function() {
        document.getElementById('ssid').value = ssid;
        Array.prototype.forEach.call(box.children, function(x){ x.classList.remove('cur'); });
        d.classList.add('cur');
      };
      box.appendChild(d);
    });
  } catch (e) {
    box.innerHTML = '<div>扫描失败，请手动输入</div>';
  }
}
function submitSave(f) {
  var ssid = document.getElementById('ssid').value.trim();
  if (!ssid) { alert('请输入 WiFi 名称'); return false; }
  document.getElementById('status').style.display = 'block';
  document.getElementById('status').textContent = '配置已提交，设备正在连接 WiFi，手机可断开本热点…';
  return true;
}
</script>
</body>
</html>
)html";

// 保存成功页
static const char PAGE_DONE[] PROGMEM = R"html(
<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>配置已保存</title>
<style>
  body { font-family: "PingFang SC", "Microsoft YaHei", sans-serif; background: #f2f4f8; padding: 40px 16px; }
  .card { max-width: 420px; margin: 0 auto; background: #fff; border-radius: 14px; padding: 32px 24px; text-align: center; }
  h1 { font-size: 19px; margin-bottom: 10px; color: #1c8a4d; }
  p { font-size: 14px; color: #666; line-height: 1.7; }
</style>
</head>
<body>
<div class="card">
  <h1>✓ 配置已保存</h1>
  <p>设备正在连接 WiFi，请稍后在「点灯」App 中查看设备上线。<br>手机现在可以断开当前热点了。</p>
</div>
</body>
</html>
)html";

static String jsonEscape(const String &s)
{
    String out;
    for (size_t i = 0; i < s.length(); i++) {
        char c = s[i];
        if (c == '"' || c == '\\') out += '\\';
        out += c;
    }
    return out;
}

// ---------------------------------------------------------------------
// WebServer 路由
// ---------------------------------------------------------------------

static void handleRoot()
{
    server->send(200, "text/html; charset=utf-8", FPSTR(PAGE_CONFIG));
}

static void handleScan()
{
    int n = WiFi.scanNetworks();   // AP_STA 模式下可正常扫描
    String json = "[";
    for (int i = 0; i < n; i++) {
        if (i) json += ",";
        json += "\"" + jsonEscape(WiFi.SSID(i)) + "\"";
    }
    json += "]";
    WiFi.scanDelete();
    server->send(200, "application/json; charset=utf-8", json);
}

static void handleSave()
{
    String ssid = server->arg("ssid");
    String pass = server->arg("pass");
    ssid.trim();
    if (ssid.length() == 0) {
        server->send(400, "text/plain; charset=utf-8", "SSID 不能为空");
        return;
    }
    storeSavedWiFi(ssid, pass);
    savedSSID = ssid;
    savedPass = pass;
    Serial.printf("[AP] WiFi config saved: \"%s\"\n", ssid.c_str());
    server->send(200, "text/html; charset=utf-8", FPSTR(PAGE_DONE));
    configSaved = true;   // 让配网循环退出
}

// ---------------------------------------------------------------------
// 开启 AP 热点
// ---------------------------------------------------------------------

static void startAP()
{
    uint8_t mac[6];
    WiFi.macAddress(mac);
    char apName[32];
    snprintf(apName, sizeof(apName), "%s-%02X%02X",
             AP_SSID_PREFIX, mac[4], mac[5]);

    WiFi.mode(WIFI_AP_STA);   // AP + STA 双开，配网页才能扫描周围网络
    bool ok;
    if (AP_PASSWORD != nullptr && strlen(AP_PASSWORD) >= 8) {
        ok = WiFi.softAP(apName, AP_PASSWORD);
    } else {
        ok = WiFi.softAP(apName);   // 开放热点
    }
    if (!ok) {
        Serial.println("[AP] softAP start FAILED!");
        return;
    }
    Serial.printf("[AP] hotspot \"%s\" started, config page: http://192.168.4.1\n", apName);
    Serial.println("[AP] connect phone to this hotspot and open http://192.168.4.1 in browser");

    if (server == nullptr) {
        server = new WebServer(80);
        server->on("/", HTTP_GET, handleRoot);
        server->on("/scan", HTTP_GET, handleScan);
        server->on("/save", HTTP_POST, handleSave);
        server->begin();
    }
}

// ---------------------------------------------------------------------
// AP 配网主循环（阻塞，直到配网完成或超时）
// 返回 true = 已保存配置；false = 超时且无配置
// ---------------------------------------------------------------------

static bool runAPConfigLoop(uint32_t timeoutMs)
{
    configMode  = true;
    configSaved = false;

    WiFi.disconnect();   // 停止 STA 用旧配置反复重试
    startAP();

    unsigned long start = millis();
    while (configMode) {
        server->handleClient();
        if (configSaved) break;
        if (timeoutMs > 0 && (millis() - start) > timeoutMs) break;
        delay(5);
    }

    WiFi.softAPdisconnect(true);
    if (server != nullptr) server->close();
    WiFi.mode(WIFI_STA);
    configMode = false;

    if (configSaved) {
        Serial.println("[AP] config done");
        return true;
    }
    // 超时：若有旧配置（本次配网失败进来的），仍可回去再试一次
    return loadSavedWiFi();
}

// ---------------------------------------------------------------------
// 对外接口
// ---------------------------------------------------------------------

bool isConfigMode()
{
    return configMode;
}

const char* savedWiFiSSID()
{
    return savedSSID.c_str();
}

const char* savedWiFiPassword()
{
    return savedPass.c_str();
}

bool setupWiFi()
{
    // 情况一：从未配过网 → 直接开 AP 配网
    if (!loadSavedWiFi()) {
        Serial.println("[WiFi] no saved config, opening AP config mode...");
        if (!runAPConfigLoop(AP_CONFIG_TIMEOUT_MS)) {
            Serial.println("[WiFi] AP timed out without config");
            return false;
        }
        return connectSavedWiFi(WIFI_CONNECT_TIMEOUT_MS);
    }

    // 情况二：已配过网 → 读取配置重连
    Serial.printf("[WiFi] saved config found, reconnecting \"%s\"...\n",
                  savedSSID.c_str());
    if (connectSavedWiFi(WIFI_CONNECT_TIMEOUT_MS)) {
        return true;
    }

    // 连接失败（密码变了/网络没了）→ 开 AP 让用户重新配置
    Serial.println("[WiFi] saved config failed, opening AP for re-config...");
    if (runAPConfigLoop(AP_CONFIG_TIMEOUT_MS)) {
        return connectSavedWiFi(WIFI_CONNECT_TIMEOUT_MS);
    }
    return false;
}

void maintainWiFi()
{
    if (configMode) return;

    static unsigned long lastCheck = 0;
    static unsigned long lostAt    = 0;

    if (millis() - lastCheck < 3000) return;
    lastCheck = millis();

    if (WiFi.status() == WL_CONNECTED) {
        lostAt = 0;
        return;
    }

    // 掉线：先自动重连（使用保存的凭据）
    if (lostAt == 0) {
        lostAt = millis();
        Serial.println("[WiFi] connection lost, auto reconnecting...");
        WiFi.reconnect();
    }

    // 长时间无法恢复 → 重新开 AP 配网，配网完成后重启设备生效
    if (millis() - lostAt > WIFI_LOST_RECONFIG_MS) {
        Serial.println("[WiFi] cannot reconnect for a long time, opening AP config...");
        runAPConfigLoop(AP_CONFIG_TIMEOUT_MS);
        Serial.println("[WiFi] rebooting with new config...");
        delay(200);
        ESP.restart();
    }
}
