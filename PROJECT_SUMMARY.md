# PROJECT_SUMMARY

> 本文件是 AI 与新成员了解项目的索引入口。只保留概览和链接，实现细节在对应文档里。

## 项目定位

ToothPaste 是一个硬件级 BLE 剪贴板，解决「在不装任何软件的设备上输入密码」的问题。用户在浏览器里打字或控制鼠标，输入经 BLE 传给一个 ESP32-S3 小设备，设备再以 USB 键盘 + 鼠标的身份把内容「敲」进目标主机。BIOS、物理隔离（air-gapped）系统、公用电脑等只有键盘可用的场景都能用。

数据全程用 AES-256-GCM 加密。密钥经 ECDH（P-256）与带外公钥交换协商，公钥不经 BLE 明文传输。V2.0 硬件把 ECDH 私钥放进 ATECC608B 安全芯片，私钥不落 ESP32 flash。

系统完全本地运行：无服务器、无账号、无云同步。风险边界见下文「安全模型」。

## 仓库组成

| 目录 | 内容 | 详细文档 |
|---|---|---|
| `web/` | 浏览器端 Web 应用（React + Vite，PWA） | [docs/WEBAPP.md](docs/WEBAPP.md) |
| `firmware/` | ESP32-S3 固件（ESP-IDF，组件见 `firmware/components/`） | [docs/FIRMWARE.md](docs/FIRMWARE.md) |
| `shared/` | 前后端共享的 Protobuf 协议定义（`toothpacket.proto` + `.options`） | [docs/PROTOCOL.md](docs/PROTOCOL.md) |
| `tools/` | `ble_probe.py`：独立于浏览器的板侧链路自检探针（Python） | [docs/PROTOCOL.md](docs/PROTOCOL.md) 末节 |
| `hardware/` | PCB 生产文件（Gerber、PDF、渲染图、3D 模型），无代码 | — |
| `docs/` | 项目文档 | 下文「文档索引」 |

## 核心数据链路

```
浏览器 Web 应用（发射端）
   │  AES-256-GCM 加密的 Protobuf 包，BLE write-without-response
   ▼
ESP32-S3 固件（接收端）：解密，按包类型分发
   │  USB HID（BOOT 键盘 + BOOT 鼠标 + 消费控制）
   ▼
目标主机（BIOS / PC / iPad / Linux……）
```

端到端流程与固件组件依赖见 [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)。GATT UUID、包格式、密钥协商见 [docs/PROTOCOL.md](docs/PROTOCOL.md)。

## 技术栈

- **固件**：ESP-IDF 5.5+，Arduino（arduino-esp32 组件）+ NimBLE + TinyUSB，C++
- **固件加密**：mbedTLS PSA（软件路径）或 ATECC608B + CryptoAuthLib（硬件路径），编译期切换
- **Web**：React 19、TypeScript、Vite、Tailwind CSS、vite-plugin-pwa
- **Web 加密**：WebCrypto（ECDH / HKDF / AES-GCM）、IndexedDB 本地存储（可选 Argon2id 加密）
- **协议**：Protobuf（proto3）。固件用 nanopb，Web 用 protoc-gen-es
- **工具链**：Python（bleak + cryptography）用于 BLE 探针

## 常用命令

### Web 应用（在 `web/` 目录）

| 命令 | 作用 |
|---|---|
| `npm run dev` | 启动开发服务器（0.0.0.0:3000）。前置脚本先从 GitHub Release 拉取固件二进制 |
| `npm run build` | 生产构建（同样先拉固件） |
| `npm run typecheck` | TypeScript 类型检查（两个 tsconfig 各跑一次） |
| `npm run deploy` | 构建产物推送到 `Brisk4t/ToothPasteWeb` 仓库（GitHub Pages，www.toothpasteapp.com） |

固件拉取失败时：本地已有 `public/firmware/manifest.json` 则保留并继续构建，否则失败。CI 中总是失败。机制见 [docs/WEBAPP.md](docs/WEBAPP.md)。

### 固件（在 `firmware/` 目录，先安装 ESP-IDF）

```bash
# 以 4 MB flash、软件加密、LED 在 GPIO48 的变体为例
idf.py -B build_4mb -D SDKCONFIG_DEFAULTS="sdkconfig.defaults;sdkconfig.defaults.4mb_mbedtls_led48" build
idf.py -B build_4mb flash monitor
```

构建变体与 `sdkconfig.defaults.*` 文件的对应关系见 [docs/FIRMWARE.md](docs/FIRMWARE.md)。

### BLE 探针

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -r tools/ble-probe-requirements.txt
python3 tools/ble_probe.py
```

首次使用需配对（长按板子 BOOT 键 10 秒），用法与判据见 `tools/ble_probe.py` 头部说明。

## 重要约定与限制

- **Web BLE 只有 Chromium 内核浏览器支持**。Firefox 不可用。Brave 桌面版默认不暴露 `navigator.bluetooth`。
- **发射端与接收端必须先配对**。公钥交换是带外的：板子把公钥以键盘打字的方式输出到所插主机，人工粘贴到网页端。长按 BOOT 键 10 秒进入配对模式。
- **板子是单客户端设备**。网页已连接时，BLE 探针等其它客户端无法同时连接。
- **协议对包大小有硬限制**，改 `shared/toothpacket.proto` 前先读 [docs/PROTOCOL.md](docs/PROTOCOL.md)。
- **固件有两条加密路径**：软件（mbedTLS PSA）与硬件（ATECC608B），由 `CONFIG_TOOTHPASTE_SOFTWARE_CRYPTO` 切换，`SecureSession.cpp` 用 `USE_SOFTWARE_CRYPTO` 宏区分。改加密相关代码时两条路径都要验证。
- **固件日志默认输出密钥材料**。`main/log_config.cpp` 当前为 `LOG_BUILD_DEBUG` 模式，发布前切到 `LOG_BUILD_PROD`。
- **Web 端 BLE 发送失败是静默的**（异常被 catch 后只写 console）。

## 安全模型

- 发射端与接收端配对后，输入数据以 AES-256-GCM 加密传输。会话密钥每次连接重新派生。
- V2.0 硬件：ECDH 私钥只在 ATECC608B 内生成与保存，I2C 总线上只出现会话级密钥。
- V1 / 开发板（软件路径）：私钥导出后存 NVS，物理攻击者可提取。
- Web 端把密钥材料存 IndexedDB，可用密码 + Argon2id 派生密钥加密（与带扩展的密码管理器同做法）。若浏览器数据被 dump，密钥即泄漏。README「More Security / 更多安全机制」一节有讨论。

## 文档索引

| 文档 | 主题 |
|---|---|
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | 系统架构、端到端数据流、固件组件依赖、状态机、Web 分层 |
| [docs/PROTOCOL.md](docs/PROTOCOL.md) | BLE GATT、ToothPacket 包格式、配对流程、密钥派生参数 |
| [docs/FIRMWARE.md](docs/FIRMWARE.md) | 固件构建变体、Kconfig、日志级别、按钮与 LED 状态、nanopb 生成 |
| [docs/WEBAPP.md](docs/WEBAPP.md) | Web 应用目录、命令、输入流水线、本地加密存储、PWA 与固件拉取 |
| [docs/ESP32-S3-SuperMini.md](docs/ESP32-S3-SuperMini.md) | 常用开发板（ESP32-S3 SuperMini）引脚与开发环境速查 |
| [README.md](README.md) / [README_zh.md](README_zh.md) | 项目背景、硬件故事、快速开始（用户视角） |
| [firmware/README.MD](firmware/README.MD) | 自制硬件 BOM、nanopb 包生成命令 |

## 待确认

- `web/package.json` 的 `protoc` 脚本以 `web/` 为工作目录解析 `./shared`，但 `web/shared` 不存在（协议文件在仓库根目录 `shared/`）。该脚本现状无法运行，生成命令待验证。
- Release 流水线：`web/scripts/fetch-firmware.mjs` 注释提到 release workflow 负责合并固件镜像，但本仓库 `.github/` 下没有 workflow 文件。工作流可能在其它分支或仓库。
