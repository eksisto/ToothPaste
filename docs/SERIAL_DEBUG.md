# 串口调试指南（USB 转串口 → UART0）

## 背景

固件把原生 USB 占用为 HID 键盘（Brisk4t ToothPaste Receiver），日志不走 USB，板子本身不产生串口。调试输出在 UART0：ESP32-S3 默认 GPIO43 = TX，GPIO44 = RX，115200 8N1。用 USB 转串口适配器查看。

SuperMini 这类不带转串口芯片的板卡必须外接适配器；DevKitC 这类自带 CP2102/CH340 的板卡直接用板上串口，烧录和看日志共用一个口。

## 接线

| ESP32-S3 板 | USB 转串口适配器 |
|---|---|
| UART0 TX (GPIO43) | RXD |
| UART0 RX (GPIO44) | TXD |
| GND | GND |

- 不接电源引脚。板子由自身 USB 供电，两路电源并联有风险。
- 适配器电平跳线拨到 3.3V。5V 档发出的信号进 GPIO44 会超过 ESP32-S3 上限。

## 验证步骤

前提：适配器和板子都能被系统识别，串口设备存在，当前用户在 `dialout` 组。系统已装 pyserial（3.5）。

### 第 1 步：确认设备

```bash
lsusb
ls /dev/ttyUSB* /dev/ttyACM* 2>/dev/null
groups | grep dialout
```

`lsusb` 编号怎么解读：

| 设备 | 编号 | 含义 |
|---|---|---|
| CH340 | `1a86:7523` | 芯片固化的身份，所有 CH340 相同 |
| CH341 | `1a86:5523` | 同厂另一颗芯片 |
| CH9102 | `1a86:7522` | CH340 的后继型号 |
| CP210x | `10c4:ea60` | Silicon Labs 转串口芯片 |
| FT232 | `0403:6001` | FTDI 转串口芯片 |
| 板子 | `cafe:0001` | 固件自定义的 VID:PID（定义在 `components/espHID/tudconfig.cpp`），含义是"在跑 ToothPaste 固件"，不是板子的硬件身份 |

适配器换了芯片型号，编号和驱动会变，后面的步骤不变。要区分具体哪块板，看 `lsusb -v` 的 iSerialNumber 或 BLE MAC。

### 第 2 步：抓包 30 秒

空闲时 UART 没有输出，这是正常的——ESP-IDF 只在事件时打日志。不要把静默当成链路不通。

```bash
python3 - <<'EOF'
import serial, time
ser = serial.Serial('/dev/ttyUSB0', 115200, timeout=0.2)
buf = bytearray()
end = time.time() + 30
while time.time() < end:
    try:
        data = ser.read(512)
        if data:
            buf.extend(data)
    except Exception as e:
        print(f"端口异常(设备可能被拔出): {e}")
        break
ser.close()
print(f"收到 {len(buf)} 字节")
print(buf.decode('utf-8', errors='replace')[:4000])
EOF
```

端口名按实际情况替换：外接适配器是 `/dev/ttyUSB0`，板载串口芯片通常是 `/dev/ttyACM0` 或 `/dev/ttyUSB0`。

### 第 3 步：触发日志（抓包运行期间执行，二选一）

方法 A（推荐，无副作用）：BLE 连接一次，固件会打出连接和状态日志。按固件广播的服务 UUID 找设备，与具体板子无关（UUID 定义在 `components/ble/ble.h`）。bleak 装在 venv 里：

```bash
python3 -m venv /tmp/bleprobe-venv \
  && /tmp/bleprobe-venv/bin/pip install -q -r tools/ble-probe-requirements.txt
/tmp/bleprobe-venv/bin/python - <<'EOF'
import asyncio
from bleak import BleakScanner, BleakClient

SERVICE_UUID = "19b10000-e8f2-537e-4f6c-d104768a1214"

async def main():
    dev = await BleakScanner.find_device_by_filter(
        lambda d, ad: SERVICE_UUID in ad.service_uuids, timeout=10)
    if not dev:
        print("未找到广播 ToothPaste 服务的设备（板子不在广播中？先拔插一次板子 USB）")
        return
    async with BleakClient(dev) as client:
        print(f"已连接 {dev.address}，挂 4 秒")
        await asyncio.sleep(4)
    print("已断开")

asyncio.run(main())
EOF
```

方法 B（终极判定）：抓包窗口内**只拔插板子的供电 USB**。板子断电重启后，ROM 横幅 `ESP-ROM:esp32s3-...` 必现。不要拔适配器的 USB，否则串口设备消失，抓包进程死掉。

### 第 4 步：判读

| 现象 | 结论 |
|---|---|
| 看到 BLE / STATE / NimBLE 等日志 | 链路通，可以调试 |
| 看到 ROM 横幅，之后无输出 | 链路通，应用日志要等事件 |
| 全程 0 字节 | 依次查：TX/RX 是否交叉、杜邦线接触、适配器丝印可能印反（对调两根信号线再试） |

## 日常监视

```bash
cd firmware && idf.py -p /dev/ttyUSB0 monitor   # Ctrl+] 退出
# 或者：
python3 -m serial.tools.miniterm /dev/ttyUSB0 115200
```

## 已知问题

- **日志泄露密钥**：`main/log_config.cpp` 当前为 `LOG_BUILD_DEBUG`，UART 输出包含会话密钥、包内容等材料。台架调试没问题，日常使用前切回 `LOG_BUILD_TESTING` 或 `LOG_BUILD_PROD` 并重编。
- **PSRAM 不可用**：当前构建开了 OPI 模式，SuperMini 的 QSPI PSRAM 初始化失败，固件无 PSRAM 运行（启动日志有 `octal_psram: PSRAM chip is not connected`）。换板卡时需核对 sdkconfig 的 PSRAM 模式与实际存储芯片匹配。
- **ble_probe.py 副作用**：全量自检会向当前聚焦窗口打入 "TP-TEST-OK"，音量 +1。只想触发串口日志时用上面方法 A。
