# 架构

## 系统组成

ToothPaste 由三部分组成：

- **发射端**：浏览器里的 Web 应用（`web/`）。用户在其中打字、控制鼠标，应用把输入加密后经 Web Bluetooth 发出。
- **接收端**：ESP32-S3 上的固件（`firmware/`）。设备对主机表现为 USB 键盘 + 鼠标，对发射端表现为 BLE 外设。
- **目标主机**：接收输入的设备。主机只看到一个普通 USB 键盘和鼠标，不需要装任何软件。

发射端和接收端通过 BLE GATT 通信。一次连接的流程：

1. 浏览器扫描广播 ToothPaste 服务的设备并连接。
2. 浏览器从本地存储读出自己的公钥，作为 AUTH 包发送以声明身份。
3. 固件识别身份后生成新的会话盐，经 CHALLENGE 通知下发。双方各自派生会话 AES 密钥。
4. 浏览器发加密 VERIFY 包，固件解密成功后回 PONG。浏览器收到 PONG 才把连接置为 ready。密钥不一致（如粘错公钥）会在这里或随后的 DECRYPT_FAILED 通知中暴露，界面提示重新配对。
5. 之后所有输入都装进加密包发送，固件解密后转成 USB HID 报文。

首次使用的配对流程（公钥带外交换）见 [PROTOCOL.md](PROTOCOL.md)。

## 端到端数据流

以「用户在实时控制页打字」为例：

```
键盘事件
  → services/inputHandlers/liveCaptureHooks（缓冲、diff、IME 过滤）
  → services/inputHandlers/keyboardHandler + services/packetService/packetFunctions（构造 KeyboardPacket）
  → context/ECDHContext（AES-256-GCM 加密，产出 DataPacket）
  → context/BLEContext.sendEncrypted（Protobuf 编码，BLE write-without-response）
  → 固件 ble 组件（收包、入队、解析）
  → SecureSession.decrypt（AES-256-GCM 解密）
  → ble_taskexec 按 oneof 分支分发
  → espHID（经 IDF_USB 的 HID 类）→ TinyUSB → USB HID 报文
  → 目标主机
```

固件解密平均耗时约 377 µs（带密钥缓存），数值来自 `ble/ble_taskexec.cpp` 的注释。

## 固件组件

固件组件在 `firmware/components/`。入口是 `main/main.cpp`：初始化 NVS、LED、状态机、HID、BLE 与安全会话，注册按键回调后进入 LED 主循环。

依赖方向（`A → B` 表示 A 依赖 B，来自各组件 `CMakeLists.txt` 的 `REQUIRES`）：

```
main          → espHID, ble, hwUI, rgbRMT, SecureSession, stateManager
ble           → espHID, SecureSession, stateManager, rgbRMT, toothPacket
SecureSession → toothPacket, stateManager, espHID, rgbRMT（软件模式不依赖 esp-cryptoauthlib）
espHID        → IDF_USB, toothPacket, esp_tinyusb
IDF_USB       → esp_tinyusb
toothPacket   → nanopb
stateManager  → rgbRMT
```

| 组件 | 职责 |
|---|---|
| `ble` | NimBLE 服务端：GATT 服务与特征、收包队列、认证与分发。`ble.h` 定义固件版本号、GATT UUID 与包长上限。`ble_auth.cpp` 处理配对与认证，`ble_taskexec.cpp` 解密并分发 |
| `SecureSession` | ECDH 密钥协商、HKDF 派生、AES-256-GCM 加解密、设备名存取。`SlotManager` 用 LRU 维护「对端身份 → 密钥槽」映射 |
| `stateManager` | 全局设备状态机（见下文），状态变化驱动 LED |
| `espHID` | TinyUSB HID 描述符（BOOT 键盘 + BOOT 鼠标 + 消费控制）、字符串/键码/鼠标输出、slowMode 延时 |
| `IDF_USB` | 改自 Espressif 官方代码的 USB HID 类库：键盘（含多种键盘布局）、鼠标、消费控制、系统控制、Gamepad、Vendor |
| `toothPacket` | nanopb 生成的 ToothPacket 序列化代码（`toothpacket.pb.c/h`），不要手改 |
| `hwUI` | BOOT 按键消抖与事件识别（单击、双击、长按），回调注册机制 |
| `rgbRMT` | WS2812 RGB LED 驱动（RMT 外设），引脚由 Kconfig 注入 |
| `esp-cryptoauthlib` | git 子模块（espressif/esp-cryptoauthlib），ATECC608B 的 CryptoAuthLib，仅硬件加密路径使用 |

`main/Kconfig.projbuild` 与构建变体见 [FIRMWARE.md](FIRMWARE.md)。`managed_components/` 与 `dependencies.lock` 由 IDF 组件管理器管理，不要手改。

## 设备状态机

状态定义在 `stateManager/StateManager.h`，实例是全局变量 `stateManager`。颜色对应关系见 [FIRMWARE.md](FIRMWARE.md)。

| 状态 | 含义 |
|---|---|
| NOT_CONNECTED | 广播中，无客户端 |
| UNPAIRED | 已连接，对端未认证 |
| PAIRING | 配对模式，等待对端公钥 |
| READY | 认证完成，可接收数据 |
| DISCONNECTED | 对端断开，自动重新广播 |
| DROP | 包被丢弃（长度不足、队列满、解密失败）后的瞬时提示，随后回到正常状态 |
| ERROR | 处理出错，LED 常亮数秒后复位 |

## Web 连接状态

`BLEContext.tsx` 的 `ConnectionStatus` 驱动界面。绿框只在验证通过后出现：

| 状态 | 含义 | 界面表现 |
|---|---|---|
| disconnected (0) | 未连接 | 红框 |
| ready (1) | 已验证（固件 ≥ 0.10.0 时以 PONG 为准），可发送 | 绿框 |
| connected (2) | 已连接但未配对（PEER_UNKNOWN 或本地无密钥） | 橙框 + 配对横幅 |
| unsupported (3) | 固件版本不兼容 | 橙框 |
| verifying (4) | 密钥已派生，VERIFY 已发，等 PONG（3 秒超时） | 蓝框脉动 |
| mismatch (5) | DECRYPT_FAILED 或验证超时，密钥不匹配 | 红框 + 重新配对横幅 |

固件低于 0.10.0 时跳过验证：收到 CHALLENGE 直接 ready，避免老固件不回 PONG 被误判为 mismatch。

## 双加密路径

`CONFIG_TOOTHPASTE_SOFTWARE_CRYPTO` 决定 ECDH 私钥放在哪，`SecureSession.cpp` 用 `USE_SOFTWARE_CRYPTO` 宏区分：

- **软件路径**（选项为 y）：mbedTLS PSA 在 ESP32 上生成与保存私钥，私钥导出后按对端公钥哈希存入 NVS（命名空间 `swpkeys`）。开发板默认走这条路径。
- **硬件路径**（选项为 n，V2.0 PCB）：ATECC608B 在芯片内生成并保存私钥，ESP32 拿不到私钥本体。I2C 引脚等芯片配置在 `sdkconfig.defaults.*` 的 `CONFIG_ATCA_*` 项。

`SlotManager` 在两条路径下都工作：把对端公钥哈希映射到 ATECC key slot 或 NVS 条目，容量满时按 LRU 淘汰。容量与常量见 `SlotManager.h`。

改 `SecureSession` 时两条路径都要验证，没有硬件 ATECC 时至少要保证软件路径可编译可运行。

## Web 端分层

代码在 `web/src/`，分四层：

- **views/**：页面。`LiveCapture`（实时键鼠控制）、`BulkSend`（整段文本与 Duckyscript 批量发送）、`about/`（产品介绍页，演示区用模拟输入）。
- **components/**：UI 组件。`overlays/`（配对、固件更新、引导、认证弹窗）、`inputComponents/`（触控板、预设按键）、`Keyboard/`（屏上虚拟键盘）、`duckyscript/`（脚本编辑器）。
- **context/**：三个 React context 承载全局逻辑。`BLEContext`（连接、连接验证 VERIFY/PONG、发包队列、通知、固件版本兼容检查）、`ECDHContext`（密钥协商与加解密）、`DuckyscriptContext`（脚本管理）。
- **services/**：纯逻辑。`packetService/`（包构造、FIFO 队列）、`inputHandlers/`（键盘鼠标事件转包、实时输入 hooks）、`localSecurity/`（加密存储、认证状态机）、`duckyscript/`（解析与存储）。

没有路由库。`App.tsx` 用 state 在视图间切换（live / paste / about），弹窗同理（pair / update / quickstart）。

## 本地存储与信任边界

| 存储 | 内容 | 保护 |
|---|---|---|
| 浏览器 IndexedDB | 每设备的 SelfPublicKey、PeerPublicKey、sharedSecret，以及保存的宏与 Duckyscript | 可选：密码 + Argon2id 派生密钥加密（`localSecurity/EncryptedStorage.ts`） |
| 固件 NVS | 对端身份登记，软件路径下还有对端绑定的私钥 | 未加密，依赖物理安全 |
| ATECC608B（仅 V2.0） | ECDH 私钥 | 芯片内生成与保存，总线只出会话密钥 |

Web BLE 上报的 MAC 是混淆过的，固件提供 MAC 读取特征返回真实 MAC，存储键用真实 MAC（`BLEContext.tsx`）。
