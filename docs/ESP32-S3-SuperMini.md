# ESP32-S3 Super Mini 开发资料

> 基于 ESP32-S3（ESP32S3FH4R2）的迷你开发板：双核 Xtensa LX7 @240MHz，4MB flash + 2MB PSRAM，Wi-Fi + 蓝牙 5，原生 USB，单面贴装、背面带铸锡焊盘，适合低功耗物联网与可穿戴项目。

## 规格速览

| 项目 | 规格 |
|:---|:---|
| 尺寸 / 重量 | 23.5 × 18 mm · 约 3 g |
| 芯片 | ESP32-S3FH4R2，双核 Xtensa LX7 @240MHz（带向量指令，适合边缘 AI）+ LP 低功耗核，revision v0.2 |
| 无线 | Wi-Fi 802.11b/g/n 2.4GHz（Station / SoftAP / 混合）· Bluetooth 5 (LE) · PCB 板载天线 |
| 存储 | 512KB SRAM · 384KB ROM · 4MB flash（XMC，quad）· 2MB QSPI PSRAM（固件默认不启用） |
| GPIO | 35 个全部引出：13 个在侧边排针、20 个为背面铸锡焊盘（GP14–18、GP21、GP33–42、GP45–48）、GP43/44 以 TX/RX 引出；片内 flash/PSRAM 用的 GP26–32 未引出，因此无"完全不可用"的引脚 |
| 模拟 / 外设 | ADC 18 通道（GP1–10 为 ADC1，GP11–18 为 ADC2；ADC2 在 WiFi 开启时不可用）· UART ×3 · I²C ×2 · SPI ×2 · PWM · I2S |
| 安全 | AES/哈希/RSA/HMAC 硬件加速 · 数字签名 · 安全启动 |
| 供电 / 电池 | 5V 输入 · 3V3(OUT) 输出供外设 · 锂电充电默认 100mA（短接 BOOST 焊桥后 300mA，仅限 >500mAh 电池）· 深睡约 43 µA |
| USB / 烧录 | USB Type-C 原生 USB（无转串口芯片）· esptool / OTA · QIO · sketch 最大 1.25MB，data 320KB |
| 板载 | WS2812 RGB + 红色 LED（共用 GP48）· 充电指示蓝灯（不受 GPIO 控制）· BOOT / RESET 按键 · 屏蔽罩 |

## 引脚布局

38 个引出脚，2.54mm 间距。BOOT 键接 GPIO0，RESET 键为 EN。括号内为板上 1–38 的物理引脚序号，**开发时一律以 GPIO 编号为准**。

```
顶边:               TX(UART0) · RX(UART0) · 5V · GND · 3V3(OUT)    [USB Type-C 同边]
左缘 自上而下:      GP1(6) · GP2(7) · GP3(8) · GP4(9) · GP5(10) · GP6(11) · GP7(12)    [BOOT 键]
右缘 自上而下:      GP13(18) · GP12(17) · GP11(16) · GP10(15) · GP9(14) · GP8(13)      [RESET 键]

背面顶边:           BATTERY+(B+) · BATTERY−(B−) · [BOOST 焊桥]
背面左缘 自上而下:  GP38(30) · GP37(29) · GP36(28) · GP35(27) · GP21(24) · GP18(23) · GP17(22) · GP16(21) · GP15(20) · GP14(19)
背面右缘 自上而下:  GP34(26) · GP33(25) · GP48(38) · GP47(37) · GP46(36) · GP45(34) · GP42(35) · GP41(33) · GP40(32) · GP39(31)
```

WS2812 RGB LED 的 DIN 接 GP48。

## 完整引脚表（38 脚）

类别：**安全** = 无启动/系统角色（18 个），优先选用；**注意** = 承担 UART/JTAG/FSPI/strapping 角色（17 个），占用前看说明。

| 引脚 | GPIO | 类别 | ADC | 说明 |
|:---:|:---|:---|:---|:---|
| 1 | 5V | 电源 | — | 5V 输入 |
| 2 | GND | 地 | — | |
| 3 | 3V3 | 电源 | — | 3.3V 输出，供外设 |
| 4 | TX (GP43) | 注意 | — | UART0 TX：默认串口日志/下载，占用后失去默认串口 |
| 5 | RX (GP44) | 注意 | — | UART0 RX：默认串口下载输入 |
| 6 | GP1 | 安全 | ADC1_CH0 | 优先选用 |
| 7 | GP2 | 安全 | ADC1_CH1 | |
| 8 | GP3 | 注意 | ADC1_CH2 | strapping：复位时选择 JTAG 信号源 |
| 9 | GP4 | 安全 | ADC1_CH3 | |
| 10 | GP5 | 安全 | ADC1_CH4 | |
| 11 | GP6 | 安全 | ADC1_CH5 | |
| 12 | GP7 | 安全 | ADC1_CH6 | |
| 13 | GP8 | 安全 | ADC1_CH7 | |
| 14 | GP9 | 注意 | ADC1_CH8 | 通用 SPI2（FSPI）IO_MUX：FSPIHD |
| 15 | GP10 | 注意 | ADC1_CH9 | FSPI：FSPICS0 |
| 16 | GP11 | 注意 | ADC2_CH0 | FSPI：FSPID（MOSI） |
| 17 | GP12 | 注意 | ADC2_CH1 | FSPI：FSPICLK |
| 18 | GP13 | 注意 | ADC2_CH2 | FSPI：FSPIQ（MISO） |
| 19 | GP14 | 注意 | ADC2_CH3 | FSPI：FSPIWP |
| 20 | GP15 | 安全 | ADC2_CH4 | |
| 21 | GP16 | 安全 | ADC2_CH5 | |
| 22 | GP17 | 安全 | ADC2_CH6 | |
| 23 | GP18 | 安全 | ADC2_CH7 | |
| 24 | GP21 | 安全 | — | |
| 25 | GP33 | 安全 | — | |
| 26 | GP34 | 安全 | — | |
| 27 | GP35 | 安全 | — | |
| 28 | GP36 | 安全 | — | |
| 29 | GP37 | 安全 | — | |
| 30 | GP38 | 安全 | — | |
| 31 | GP39 | 注意 | — | JTAG TCK（MTCK） |
| 32 | GP40 | 注意 | — | JTAG TDO（MTDO） |
| 33 | GP41 | 注意 | — | JTAG TDI（MTDI） |
| 34 | GP45 | 注意 | — | strapping：复位时选择 flash/PSRAM 电压（3.3V / 1.8V） |
| 35 | GP42 | 注意 | — | JTAG TMS（MTMS）；焊盘在背面，序号位于 GP45 与 GP46 之间 |
| 36 | GP46 | 注意 | — | strapping：与 GPIO0 共同决定启动模式；仅输入（无输出驱动），建议保留 |
| 37 | GP47 | 注意 | — | 普通 GPIO（仅 1.8V octal 存储型号才用作差分时钟） |
| 38 | GP48 | 注意 | — | 红色 LED 与 WS2812 DIN 共用此脚 |

### 选用要点

- **最安全 18 脚**：GP1、GP2、GP4、GP5、GP6、GP7、GP8、GP15、GP16、GP17、GP18、GP21、GP33、GP34、GP35、GP36、GP37、GP38 —— 按钮/传感器/LED 首选
- **JTAG 四脚** GP39/40/41/42：不用 JTAG 调试时可当普通 GPIO
- **FSPI 六脚** GP9–14：板上未接 SPI 外设时可自由使用（片内 flash 不走这几根线）
- **strapping 三脚** GP3 / GP45 / GP46：上电复位瞬间需保持有效电平，勿接会拉死电平的外设
- **模拟采集**优先用 ADC1（GP1–10）；ADC2（GP11–18）在 WiFi 开启时不可用

## 板载 LED、USB 与电池

| LED | GPIO | 行为 |
|:---|:---|:---|
| 红色 LED | GPIO48 | `digitalWrite()` 控制 |
| WS2812 RGB | GPIO48（DIN） | FastLED / NeoPixel 控制 |
| 蓝色充电指示 | 不受 GPIO 控制 | 充电中常亮；接电池未充电时熄灭；无电池时闪烁 |

- **红色 LED 与 WS2812 共用 GP48**：数字电平信号与时序信号互相干扰，无法独立使用
- WS2812 示例（FastLED）：

```cpp
#include <FastLED.h>
#define DATA_PIN 48
CRGB leds[1];

void setup() { FastLED.addLeds<NEOPIXEL, DATA_PIN>(leds, 1); }
void loop() {
  leds[0] = CRGB::Red;   FastLED.show(); delay(1000);
  leds[0] = CRGB::Green; FastLED.show(); delay(1000);
  leds[0] = CRGB::Blue;  FastLED.show(); delay(1000);
}
```

- **USB**：USB-C 直连原生 USB（GP19/20，未引出），无需驱动。`Serial.print()` 需在 Arduino 中开启 `USB CDC On Boot: Enabled`，否则输出走到未焊接的 UART 引脚上
- **刷机救砖**：COM 口不出现或上传失败时，**按住 BOOT 插入 USB（或按住 BOOT 点 RESET）**强制进入 ROM bootloader，刷完按 RESET 运行；固件崩溃或深睡会连带 USB 端口消失，属正常现象
- **电池**：背面 B+ / B− 焊盘接锂电池；BOOST 焊桥默认断开（充电 100mA），短接后 300mA，**仅限容量 > 500 mAh 的电池**

## 开发环境速查

### Arduino IDE 2.x（Tools 设置，其余保持默认）

```
Board:            ESP32S3 Dev Module
USB CDC On Boot:  Enabled
Flash Size:       4MB (32Mb)
Flash Mode:       QIO
Partition Scheme: Default 4MB with spiffs (1.2MB APP/1.5MB SPIFFS)
Upload Speed:     921600
```

点灯自检（GPIO1 外接 LED；要亮板载灯改用 48）：

```cpp
void setup() { pinMode(1, OUTPUT); }
void loop() { digitalWrite(1, HIGH); delay(500); digitalWrite(1, LOW); delay(500); }
```

### PlatformIO

```ini
[env:esp32-s3-super-mini]
platform = espressif32
board = esp32-s3-devkitc-1
framework = arduino
monitor_speed = 115200
upload_speed = 921600
```

### ESPHome

```yaml
esp32:
  board: esp32-s3-devkitc-1
  variant: esp32s3
  framework:
    type: esp-idf
```

### esptool（烧录现成 .bin）

```bash
esptool --chip esp32s3 --port /dev/ttyACM0 --baud 921600 write_flash 0x0 firmware.bin
```

Windows 端口为 `COMx`。

### 启用 2MB PSRAM（默认关闭）

- **Arduino IDE**：`Tools → PSRAM → QSPI PSRAM`（**勿选 OPI**，那是 octal 芯片的选项，选了会崩溃）
- **PlatformIO**：`board_build.arduino.memory_type = qio_qspi`，并加 `-DBOARD_HAS_PSRAM`
- **ESPHome**：添加 `psram:` 且 `mode: quad`
- 验证：`ESP.getPsramSize()`（未启用返回 0）

## 注意事项

1. **部分批次陶瓷天线装反**：WiFi 距离异常差时先查天线方向——天线**白色条一侧是馈点**，可能被接到未连线的焊盘上；31mm 四分之一波长导线改装有效。
2. **PSRAM 默认关闭**：按上节方法启用；不同批次板子可能不同，用 `ESP.getPsramSize()` 实测确认。
3. **深睡约 43 µA**，适合电池供电项目。
