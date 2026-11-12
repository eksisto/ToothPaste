# Web 应用开发指南

代码在 `web/`。线上地址 www.toothpasteapp.com（GitHub Pages，CNAME 在 `web/public/CNAME`），构建产物推送到独立仓库 `Brisk4t/ToothPasteWeb`。

## 技术栈

- React 19 + TypeScript + Vite
- Tailwind CSS + @material-tailwind/react，基础组件在 `src/components/ui/`
- PWA：vite-plugin-pwa（autoUpdate，Workbox 运行时缓存）
- Lexical（富文本）、react-three/fiber + drei（关于页 3D 模型）、@heroicons/react
- 协议：@bufbuild/protobuf，生成文件在 `src/services/packetService/toothpacket/`
- Web 平台 API：Web Bluetooth（Web BLE）、Web Serial（固件更新）、WebCrypto、IndexedDB

## 命令

在 `web/` 目录执行：

| 命令 | 作用 |
|---|---|
| `npm run dev` | 开发服务器，监听 0.0.0.0:3000 |
| `npm run build` | 生产构建，产物在 `dist/` |
| `npm run typecheck` | 对 `tsconfig.json` 与 `tsconfig.node.json` 各跑一次 `tsc --noEmit` |
| `npm run deploy` | 把 `dist/` 推送到 `Brisk4t/ToothPasteWeb`（gh-pages） |

测试依赖（@testing-library）已声明，但仓库目前没有测试脚本。

浏览器只在 secure context（HTTPS 或 localhost）暴露 Web Bluetooth。Firefox 不支持。Brave 桌面版默认关闭 Web Bluetooth，需在设置中开启（`navigator.bluetooth` 为 undefined 时会报 `Cannot read properties of undefined`）。

## 构建期固件拉取

`predev` 和 `prebuild` 先执行 `npm run fetch-firmware`（`scripts/fetch-firmware.mjs`）：

1. 从 GitHub Release（`Brisk4t/ToothPaste`）下载 `ToothPasteFirmware_*.bin` 到 `public/firmware/<tag>/`，并生成 `manifest.json`。
2. UpdateOverlay 读 `manifest.json` 构建固件列表，用户经 Web Serial 选设备烧录。

之所以在构建期做：Release 下载域名没有 CORS 头，浏览器拿不到文件内容。tag 在文件路径里，保证 PWA 运行时缓存不会用旧版本二进制冒充新版本。

失败行为：`GITHUB_TOKEN` 可避免匿名限流（60 次/小时）。CI（设置了 `CI` 环境变量）中失败即构建失败。本地运行时若已有 `public/firmware/manifest.json` 则保留并警告，否则失败——离线开发要求至少成功拉取过一次。`public/firmware/` 已 gitignore。

## 目录结构

| 路径 | 职责 |
|---|---|
| `src/App.tsx` | 入口。state 切换视图（live / paste / about）与弹窗（pair / update / quickstart），无路由库 |
| `src/views/LiveCapture.tsx` | 实时键鼠控制页：键盘捕获、触控板、屏上键盘、预设按键、鼠标抖动 |
| `src/views/BulkSend.tsx` | 批量发送页：整段文本发送、Duckyscript 脚本选择与执行 |
| `src/views/about/` | 产品介绍页，演示区的输入是模拟的（`sections/demo/`） |
| `src/context/BLEContext.tsx` | Web BLE 连接、GATT 特征发现（带重试）、发包、通知处理、固件版本兼容检查 |
| `src/context/ECDHContext.tsx` | ECDH P-256 密钥对、公钥压缩/解压、HKDF 派生 AES 密钥、加解密、完整握手 |
| `src/context/DuckyscriptContext.tsx` | 脚本文件管理，数据来自 DuckyscriptService |
| `src/services/packetService/` | ToothPacket 构造（`packetFunctions.ts`）、生产者-消费者队列（`PacketQueue.ts`） |
| `src/services/inputHandlers/` | 键盘鼠标事件转 HID 包（`HIDMap`、`keyboardHandler`、`mouseHandler`）、实时输入 hooks（`liveCaptureHooks.ts`） |
| `src/services/localSecurity/` | `EncryptedStorage.ts`（IndexedDB 加密）、`AuthStateManager.ts`（认证状态机） |
| `src/services/duckyscript/` | Duckyscript 解析器与脚本存储 |
| `src/components/overlays/` | 配对（ECDHOverlay）、固件更新（UpdateOverlay）、引导（QuickStartOverlay）、认证（AuthenticationOverlay，由 Navbar 挂载） |

协议常量（服务 UUID、特征 UUID）在 `BLEContext.tsx` 与固件 `ble.h` 各定义了一份，改动协议时两处同步，详见 [PROTOCOL.md](PROTOCOL.md)。

## 输入流水线

实时输入的关键设计在 `services/inputHandlers/liveCaptureHooks.ts`：

- 输入先进缓冲区，20 ms debounce 后计算与上次发送的差量（diff），只发增量，减少包数量。
- IME 组合期间的事件被过滤（compositionStart / compositionEnd），避免自动纠错产生幽灵输入。
- 实时捕获输入框用 `type="password"`，移动端会弹系统安全键盘，属设计内行为。
- 发送统一走 `BLEContext.sendEncrypted`：生产者加密入队，消费者 BLE 写出（PacketQueue）。

## 本地加密存储

- 每台设备按真实 MAC 存三项：SelfPublicKey、PeerPublicKey、sharedSecret（`services/Storage.ts` 提供裸 IndexedDB 读写，`EncryptedStorage.ts` 在其上加解密）。
- EncryptedStorage 两种解锁模式：
  - 密码模式：Argon2id 派生 AES-GCM 会话密钥（参数 time=3、mem=64 MiB，见源码）。
  - 无密码模式：固定开发密钥，仅开发用，不安全。
- 上述三项都经会话密钥加密后写入（`encryptValue`）。未解锁时读写直接抛错（`loadBase64` 捕获后返回 null）。
- `AuthStateManager.ts` 是认证流程唯一状态源：未初始化 / 加载中 / 首次使用 / 待密码 / 待无密码验证 / 已解锁 / 存储损坏。

## Protobuf 生成

Web 侧生成物是 `src/services/packetService/toothpacket/toothpacket_pb.js`（protoc-gen-es 生成，不要手改），源文件是仓库根目录 `shared/toothpacket.proto`。

`package.json` 里的 `npm run protoc` 脚本按 `web/` 工作目录解析 `./shared` 路径，而 `web/shared` 不存在——脚本现状待确认，修复前不要依赖它（见 [PROJECT_SUMMARY.md](../PROJECT_SUMMARY.md) 待确认节）。

## 固件版本兼容

- 固件版本号定义在 `firmware/components/ble/ble.h`（`FIRMWARE_VERSION`），随响应通知下发。
- Web 端兼容列表在 `BLEContext.tsx`（`supportedFirmwareVersions`），`^` 后缀表示「不低于」，如 `0.9.0^`。不兼容时连接状态置为 unsupported。
