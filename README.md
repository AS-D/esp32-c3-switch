# ESP32-C3 ProMini 远程电源开关（点灯 Blinker + 自建 AP 热点配网）

通过「点灯」App 远程控制一路 **5V 电源输出** 的通断，用于给需要 5V 供电的设备（小风扇、灯带、传感器模块、继电器驱动的家电等）远程上电/断电。

## 功能特性

| 功能 | 说明 |
| --- | --- |
| 远程开关 | 点灯 App 内开关组件，点「开」→ 输出 5V 通电，点「关」→ 断电 |
| AP 热点配网 | **从未配过网**时自动开启热点 `ESP32C3-Switch-XXXX`，手机连热点后浏览器打开 `http://192.168.4.1` 填写 WiFi 信息完成配网，配置自动存入 flash |
| 自动重连 | **已配过网**：开机直接读取配置连 WiFi，**不再开启热点**；连不上会自动重新开热点，方便改网 |
| 掉线自愈 | 联网后 WiFi 掉线自动重连；持续掉线超 2 分钟重新开热点配网 |
| 状态记忆 | 开关状态存入 NVS，断电重启自动恢复上次状态 |
| 重新配网 | 长按板载 **BOOT 键 5 秒**：擦除 WiFi 配置并重启，重新进入配网模式 |

## 硬件接线（二选一）

> 共地原则：负载电源的 GND 必须与 ESP32 的 GND 相连。

### 方案 A：合宙 ProMini「继电器版」（最简单，零接线）

继电器版板载继电器由 **GPIO10** 控制，USB 5V 经继电器到板载输出端子：

```
USB 5V ── ProMini USB 口供电
需要 5V 的设备 ── 接到板载输出端子（5V+ / 5V-）
```

继电器高电平吸合，代码默认 `POWER_ON_LEVEL = HIGH`，无需改动。

### 方案 B：普通版 + 低边 N-MOS 开关（推荐，AO3400）

```
USB 5V ──┬── 负载 5V 引脚
         └── ESP32 5V 引脚（供电）
负载 GND ── AO3400 D(漏极)
AO3400 S(源极) ── ESP32 GND
AO3400 G(栅极) ── GPIO10（经 100Ω 限流电阻）
G-S 间并 100kΩ 下拉电阻（防上电误触发）
```

电平极性：高电平通电，代码默认 `POWER_ON_LEVEL = HIGH`。

### 方案 C：5V 继电器模块

```
继电器 VCC ── ESP32 5V    继电器 GND ── ESP32 GND
继电器 IN  ── GPIO10
负载电源正极 ── 继电器 COM    负载正极 ── 继电器 NO
```

继电器模块通常低电平触发，把 `include/config.h` 改为
`POWER_ON_LEVEL = LOW` / `POWER_OFF_LEVEL = HIGH`。

> **控制引脚**：默认 GPIO10。ProMini 引出脚 0~10 均可输出，但 **GPIO2/8/9 是 strapping 脚**（上电时序特殊），不要用作开关输出；GPIO4~7 为 JTAG 复用脚，正常输出没问题（仅硬件 JTAG 调试时冲突）。
>
> **供电注意**：5V 输出直通 USB 5V，负载电流不要超过 USB 供电能力（电脑 USB 口通常 500mA~1A，充电头通常 1~2A）。ESP32 的 3.3V 引脚只有几十 mA 能力，**不要从 3.3V 给负载供电**。

## 点灯 App 配置

1. 手机安装「点灯」App，注册登录。
2. App 内：**添加设备 → 选择 WiFi 接入的「独立设备」→ 复制生成的设备密钥**，填入 `include/config.h` 的 `BLINKER_AUTH`。
3. 编译烧录后，在设备控制面板 **添加「开关」组件**，把组件的 **key 设为 `sw-power`**（与代码一致），即可远程开/关。

## 首次配网流程（自建热点 + 网页）

1. 设备上电（未配过网），自动开启热点，热点名形如 **`ESP32C3-Switch-A1B2`**（MAC 后 4 位）。
2. 手机 WiFi 列表连接该热点（默认开放，无密码；如需密码见 `config.h` 的 `AP_PASSWORD`）。
3. 手机浏览器打开 **`http://192.168.4.1`**，出现配网页：
   - 点「扫描可用网络」可列出周围 WiFi，点选自动填入；或手动输入 WiFi 名称；
   - 输入 WiFi 密码（无密码留空）；
   - 点「保存并连接」。
4. 设备保存配置、自动连上家庭 WiFi，随后在点灯 App 上线。手机可断开热点。
5. 以后每次开机：设备**直接读取配置重连，不再开热点**。

## 编译与烧录

用 **VSCode 打开本目录**（安装 PlatformIO 插件）即可：

- 编译：底部工具栏 `✓`（或终端 `pio run`）
- 烧录：底部工具栏 `→`（或终端 `pio run -t upload`）

> ProMini 无自动复位电路：点击上传后**按住板载 BOOT 键再点一下 RST（或重新插拔）**，串口出现 `Connecting...` 时松开 BOOT。
> 若自动识别不到串口，在 `platformio.ini` 中取消注释 `upload_port` 改成实际串口号（如 `COM3`）。

## 重新配网 / 换 WiFi

- 方法一：**长按板载 BOOT 键 5 秒**，设备擦除 WiFi 配置并重启，重新进入热点配网。
- 方法二：`pio run -t erase` 擦除整片 flash 后重新上传。
- 已配网但连不上（如 WiFi 密码改了）：设备连接超时后会自动重新开热点，直接走上面的配网流程即可。

## 目录结构

```
esp32-c3-switch/
├── platformio.ini    # 工程配置（板型 / 串口 / 依赖库）
├── include/
│   └── config.h      # ★ 用户配置区：设备密钥 / 引脚 / 电平极性 / 热点名 / 超时
├── src/
│   ├── main.cpp      # 主程序：点灯远程开关 + 状态记忆 + BOOT 重置
│   ├── wifi_config.h
│   └── wifi_config.cpp  # WiFi 模块：NVS 存储 + AP 热点 + 192.168.4.1 配网页
└── README.md
```

## 日志说明

串口监视器波特率 `115200`，关键日志：

```
[WiFi] no saved config, opening AP config mode...
[AP] hotspot "ESP32C3-Switch-A1B2" started, config page: http://192.168.4.1
[WiFi] connecting "MyWiFi"......
[WiFi] connected, IP: 192.168.1.100
[Blinker] ready, remote power switch online
```

## 依赖

- PlatformIO 平台：`espressif32@6.12.0`（arduino-esp32 3.0.x，Blinker 兼容组合；新版 7.x 内核与 Blinker 存在 F() 宏兼容问题，故锁定此版本）
- 库：点灯 Blinker 官方 GitHub master 分支（0.3.12，`platformio.ini` 中以 zip 直连下载，已修复 ESP32 兼容问题；WiFi 由本工程自行管理，未使用 Blinker 自带配网）
- 其余（`WiFi` / `WebServer` / `Preferences`）均为 ESP32 Arduino 核心自带
