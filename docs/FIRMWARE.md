# 固件开发指南

目标硬件是 ESP32-S3。代码在 `firmware/`，组件职责与依赖见 [ARCHITECTURE.md](ARCHITECTURE.md)，线上协议见 [PROTOCOL.md](PROTOCOL.md)。

## 环境要求

- [ESP-IDF](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/get-started/index.html) 5.5 及以上（`sdkconfig.defaults` 由 5.5.4 生成）。
- 修改 Protobuf 包时另需 protoc 与 nanopb，见下文「生成 ToothPacket 代码」。

## 构建变体

仓库用多个 `sdkconfig.defaults.*` 文件支持不同硬件。`sdkconfig.defaults` 是基线（NimBLE、PSRAM、ATECC I2C 引脚等），变体文件在其上叠加：

| 变体文件 | flash | 加密路径 | RGB LED 引脚 |
|---|---|---|---|
| `sdkconfig.defaults.8mb_mbedtls` | 8 MB | 软件（mbedTLS PSA） | Kconfig 默认值 |
| `sdkconfig.defaults.8mb_atecc` | 8 MB | 硬件（ATECC608B） | Kconfig 默认值 |
| `sdkconfig.defaults.4mb_mbedtls_led10` | 4 MB | 软件 | GPIO 10 |
| `sdkconfig.defaults.4mb_mbedtls_led48` | 4 MB | 软件 | GPIO 48 |

Release 产物（`ToothPasteFirmware_*.bin`，命名如 `4MB_MBEDTLS_LED48`）与变体文件的对应关系按命名推断，发布流水线不在本仓库（见 [PROJECT_SUMMARY.md](../PROJECT_SUMMARY.md) 待确认节）。

构建命令（以 4 MB LED48 变体为例）：

```bash
idf.py -B build_4mb -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.4mb_mbedtls_led48" build
idf.py -B build_4mb flash monitor
```

完整生成的 `sdkconfig` / `sdkconfig_4mb` 不入库（见根目录 `.gitignore`）。改配置请改 `sdkconfig.defaults.*`，不要提交生成的完整配置。

## Kconfig 自定义选项

定义在 `main/Kconfig.projbuild`：

| 选项 | 作用 |
|---|---|
| `TOOTHPASTE_SOFTWARE_CRYPTO` | y：ECDH 全部在软件（mbedTLS PSA）完成。n：私钥操作走 ATECC608B，需链接 esp-cryptoauthlib |
| `TOOTHPASTE_RGB_LED_PIN` | WS2812 数据线 GPIO，默认 12 |

选项启用时，构建系统给 `SecureSession` 组件定义 `USE_SOFTWARE_CRYPTO` 宏。`rgbRMT` 组件从选项读取引脚号。两条路径的代码差异见 [ARCHITECTURE.md](ARCHITECTURE.md)「双加密路径」。

## 日志级别

`main/log_config.cpp` 顶部三选一（取消注释一行）。改完只需重新编译该文件，不需要 full rebuild：

| 模式 | 行为 |
|---|---|
| `LOG_BUILD_DEBUG`（当前默认） | 全量 VERBOSE，包含 AES 密钥、共享密钥等敏感内容 |
| `LOG_BUILD_TESTING` | INFO。SESSION 与 BLE_AUTH 两个 tag 压到 ERROR（它们在 DEBUG 级别打印密钥） |
| `LOG_BUILD_PROD` | 只输出 ERROR |

`configure_log_levels()` 必须在 `initArduino()` 之后调用——Arduino 初始化会把日志级别重置（`main.cpp` 有注释说明）。发布固件前切到 `LOG_BUILD_PROD`。

## 按钮交互

BOOT 键（GPIO0）由 `hwUI` 组件轮询，回调在 `main.cpp` 注册：

| 操作 | 行为 |
|---|---|
| 单击 | 仅在 PAIRING 状态下有效：经 USB HID 重发一次本机公钥（公钥打字输出可能不完整，这是补发手段） |
| 长按 10 秒 | 进入配对模式。约 5 秒后，本机公钥（压缩格式 base64）被打进当前聚焦的文本框 |
| 双击 | `hwUI` 能识别该事件，当前无绑定 |

长按时长等常量在 `hwUI/hwUI.cpp` 顶部。

## LED 状态

LED 驱动是 `rgbRMT` 组件，状态由 `stateManager` 的回调着色，主循环调用 `led.blinkUpdate()` 刷新闪烁。

| 颜色 | 状态 | 含义 |
|---|---|---|
| 橙 | NOT_CONNECTED | 广播中，等待连接 |
| 黄（暗） | UNPAIRED | 已连接，对端未认证 |
| 紫闪 1 s → 常紫 | PAIRING | 配对模式：闪紫约 5 s 后公钥经 USB 打出，常紫 = 等待对端公钥 |
| 青（暗） | READY | 认证完成，可接收加密数据 |
| 红闪 0.5 s | DISCONNECTED | 对端断开（异常断开自动重新广播） |
| 蓝闪 0.5 s | DROP | 包被丢弃：长度不足 / 队列满 / 解密失败——排障时最有用的信号 |
| 红常亮约 3 s → 橙 | ERROR | 处理出错后自动复位状态 |

## 生成 ToothPacket 代码

固件侧 protobuf 代码在 `components/toothPacket/toothpacket.pb.c/h`，由 nanopb 从 `shared/toothpacket.proto` 生成，不要手改。

重新生成（在 `shared/` 目录执行）：

```bash
protoc -I. --nanopb_out=<仓库路径>/firmware/components/toothPacket toothpacket.proto
```

两个注意点：

- 同目录的 `toothpacket.options` 把变长字段编译成静态数组（字段上限的权威来源）。nanopb 生成命令必须在 `shared/` 目录内运行，它无法单独指定 `.options` 位置（`firmware/README.MD` 有说明）。
- Web 侧的生成命令与共享源文件见 [WEBAPP.md](WEBAPP.md)「Protobuf 生成」。
