# ToothPacket 线上协议

本文是发射端与接收端之间的协议参考。定义源：

- `shared/toothpacket.proto`：包结构（权威来源）
- `shared/toothpacket.options`：变长字段的静态数组上限（权威来源，proto 内注释可能滞后）
- `firmware/components/ble/ble.h`：UUID、固件版本号、包长上限
- `firmware/components/SecureSession/`：加密参数

`tools/ble_probe.py` 按本协议实现了独立的发射端，整条链路经实测验证。

## GATT 布局

| 名称 | UUID | 用途 |
|---|---|---|
| 服务 | `19b10000-e8f2-537e-4f6c-d104768a1214` | 设备广播该服务，Web 端按此过滤扫描 |
| 数据写入 | `6856e119-2c7b-455a-bf42-cf7ddd2c5907` | 发射端 → 板子，write-without-response，载荷为 `DataPacket` |
| 响应通知 | `6856e119-2c7b-455a-bf42-cf7ddd2c5908` | 板子 → 发射端，notify，载荷为 `ResponsePacket` |
| MAC 读取 | `19b10002-e8f2-537e-4f6c-d104768a1214` | 返回真实 MAC。Web BLE 对 MAC 做混淆，本地存储键需要真实 MAC |

UUID 在固件 `ble.h` 与网页 `BLEContext.tsx` 各定义一份，必须同步。

## 密钥协商

曲线 P-256（secp256r1）。分两种流程。

### 配对（首次，公钥带外交换）

1. 用户长按 BOOT 键 10 秒，固件进入 PAIRING，生成新的 ECDH 密钥对。
2. 约 5 秒后，固件把本机公钥（压缩格式 33 字节，base64 后 44 字符）以打字方式经 USB 输出到所插主机。
3. 用户把这段公钥粘进网页端配对弹窗。
4. 网页端解压公钥，生成自己的密钥对，把**未压缩公钥（65 字节，0x04 开头）的 base64（88 字符）**作为 AUTH 包（`packetID = AUTH_PACKET`）的 `encryptedData` 发送，`dataLen` 必须等于该 base64 的长度。
5. 双方做 ECDH 得到共享密钥并各自保存。固件把对端公钥哈希登记进配对槽。

### 重连（已配对）

1. 网页端从本地存储读出 SelfPublicKey，原样作为 AUTH 包发送。
2. 固件按公钥哈希查配对登记，命中后生成新盐。
3. 固件经 CHALLENGE 通知下发 32 字节随机盐——**每次连接都重新生成**。
4. 双方各自派生会话密钥，之后正常收发。

### 连接验证（VERIFY/PONG，固件 ≥ 0.10.0）

派生出会话密钥不等于双方派生出**同一个**密钥。公钥粘错、NVS 损坏都会让两侧各算各的，之后所有加密包在板子上 GCM 认证失败。连接验证在握手时刻暴露这种不一致：

1. 发射端收到 CHALLENGE（或 PEER_KNOWN）后派生密钥，随即发一个加密 VERIFY 包，载荷为 16 字节随机 nonce（`VerifyPacket`，oneof 分支 8）。
2. 板子解密成功则回 PONG 通知，nonce 原样放在 `challengeData` 回传。回传不加密：板子能解开 VERIFY 已证明两侧密钥一致，明文回传不减少证明力。
3. 发射端 3 秒内收到 nonce 一致的 PONG 才把连接置为可用（ready）。超时或收到 DECRYPT_FAILED 都判定密钥不匹配，界面引导重新配对。
4. 固件版本低于 0.10.0 时发射端不发 VERIFY，收到 CHALLENGE 直接可用（旧行为）。

VERIFY 包很小：明文约 22 字节，加密后连 DataPacket 外层约 60 字节，远低于 253 字节上限。

### 密钥派生参数

| 参数 | 值 |
|---|---|
| 共享密钥 | ECDH 输出的 X 坐标，32 字节（PSA `psa_raw_key_agreement` 与 WebCrypto `deriveBits(256)` 结果一致） |
| 派生函数 | HKDF-SHA256 |
| salt | 固件本次连接生成的 32 字节随机盐 |
| info | ASCII 字符串 `aes-gcm-256` |
| 输出 | 32 字节 AES-256-GCM 密钥 |

会话密钥每次连接都变。发射端**必须**收到 CHALLENGE 通知才能派生出匹配密钥，收不到就派生不出。连接验证（见上节）把"两侧各算各的"这类静默失败提前到连接时暴露。会话中途仍可能出现解密失败（如密钥中途失效），由 DECRYPT_FAILED 通知兜底（见下文 ResponsePacket）。

## 数据包格式

### DataPacket（外层，BLE 线上格式）

| 字段 | 类型 | 上限 | 说明 |
|---|---|---|---|
| packetID | enum | — | DATA_PACKET = 0（数据）/ AUTH_PACKET = 1（认证） |
| packetNumber | uint32 | — | 分包序号，当前实现固定为 1 |
| totalPackets | uint32 | — | 分包总数，当前实现固定为 1 |
| slowMode | bool | — | 为 true 时固件在按键间加延时（`SLOWMODE_DELAY_MS`，5 ms，见 `espHID.h`） |
| iv | bytes | 12 B | AES-GCM IV，AUTH 包为空（12 个 0） |
| dataLen | uint32 | — | 密文长度（AUTH 包为公钥 base64 长度） |
| encryptedData | bytes | 200 B | 密文，或 AUTH 包的 base64 公钥 |
| tag | bytes | 16 B | GCM tag，AUTH 包为空（16 个 0） |

proto 注释要求整个 DataPacket 在 BLE 上小于 253 字节。固件接收缓冲 `BLE_MAX_RAW_PACKET` 为 320 字节（`ble.h`）。

### EncryptedData（内层，解密后的明文）

字段 `packetType` 的枚举：KEYBOARD_STRING = 0、KEYBOARD_KEYCODE = 1、MOUSE = 2、RENAME = 3、CONSUMER_CONTROL = 4、COMPOSITE = 5。

实际分发按 oneof 分支识别（固件 `ble_taskexec.cpp` 的 `which_packetData`），分支与上限：

| oneof 分支（字段号） | 载荷 | 用途 |
|---|---|---|
| keyboardPacket (2) | `KeyboardPacket{message, length}`，message ≤ 190 B | 文本输入 |
| keycodePacket (3) | `KeycodePacket{code, length}`，code ≤ 190 B | 原始键码序列 |
| mousePacket (4) | `MousePacket{num_frames, frames[], l_click, r_click, wheel}`，frames 上限见 `.options` | 鼠标移动曲线 + 按键 + 滚轮 |
| renamePacket (5) | `RenamePacket{message, length}` | 改设备名 |
| consumerControlPacket (6) | `ConsumerControlPacket{code[], length}` | 消费控制（标准 HID Usage，如音量+ `0x00E9`、音量− `0x00EA`、电源 `0x0030`） |
| mouseJigglePacket (7) | `MouseJigglePacket{enable}` | 鼠标抖动开关 |
| verifyPacket (8) | `VerifyPacket{nonce}`，nonce 16 B | 连接验证，固件 ≥ 0.10.0，回 PONG |

注意：`MouseJigglePacket` 与 `VerifyPacket` 在 oneof 里，但 `packetType` 枚举没有对应值。发射端构造这两类包时 `packetType` 填 COMPOSITE（5），固件只按 oneof 分支分发。

### ResponsePacket（响应通知，另一条特征）

| responseType | 含义 |
|---|---|
| KEEPALIVE (0) | 保活 |
| PEER_UNKNOWN (1) | 认证被拒：公钥未登记，需重新配对 |
| PEER_KNOWN (2) | 认证成功 |
| CHALLENGE (3) | `challengeData` 携带 32 字节会话盐（上限 150 B） |
| DECRYPT_FAILED (4) | 收到数据包但 GCM 认证失败，密钥不匹配。每次连接只发第一条，断开后重新计数 |
| PONG (5) | VERIFY 包解密成功，`challengeData` 原样回传 nonce |

DECRYPT_FAILED 的节流按连接计。密钥不一致时按键连发会让失败成串出现，逐条通知会刷爆特征，所以每次连接只发第一条。

`firmwareVersion` 字段（上限 50 B）随通知下发，网页端据此做兼容性检查（见 [WEBAPP.md](WEBAPP.md)）。

## 加密算法参数

- AES-256-GCM，IV 12 字节（每包随机），tag 16 字节，无 AAD。
- WebCrypto 的 `encrypt()` 把 tag 拼在密文尾部，网页端按前 N−16 密文 / 后 16 tag 拆开放进 DataPacket。
- AUTH 包不加密（空 IV、空 tag、明文公钥），是唯一不上锁的包。

## 验证工具

`tools/ble_probe.py` 是独立于浏览器的发射端实现（Python，bleak + cryptography），用于验证板子整条链路：BLE 写入 → protobuf 解析 → 认证 → 密钥派生 → 解密 → USB HID 输出。首次使用需配对（`--pubkey-file` 配合长按 BOOT），之后一条命令自检，音量变化作为自动判据。
