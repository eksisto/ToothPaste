#!/usr/bin/env python3
"""
ToothPaste 板侧自检探针(独立于手机/网页,直接扮演 BLE 发射端)

用途:验证 板子固件整条链路 —— BLE 写入 → protobuf 解析 → ECDH 认证 →
HKDF 会话密钥派生 → AES-256-GCM 解密 → USB HID 键盘/消费控制输出。

依赖(Python 3.10+,仅 Linux 蓝牙经 bluez 测试过):
    python3 -m venv .venv && . .venv/bin/activate
    pip install -r tools/ble-probe-requirements.txt

用法:
    # 常规自检(身份已配对过,一条命令,约 20 秒)
    python3 tools/ble_probe.py

    # 首次对某块新板子使用(需要配对):
    #   1. 手机 ToothPaste 网页断开(板子单客户端)
    #   2. 新开终端运行(并保持该终端聚焦,别点其他窗口):
    #        rm -f /tmp/toothpaste_pubkey.txt && cat > /tmp/toothpaste_pubkey.txt
    #   3. 运行本脚本,长按板子 BOOT 键 10 秒进入配对模式;
    #      公钥会被板子打进上面的终端,脚本自动读取并完成握手。
    python3 tools/ble_probe.py --pubkey-file /tmp/toothpaste_pubkey.txt

    # 指定设备蓝牙地址(跳过扫描);或直接传入设备公钥
    python3 tools/ble_probe.py --address 10:20:BA:32:6E:52
    python3 tools/ble_probe.py --pubkey At1S00N/rYRYzQ1ExEElCt6GSd83x+uNTuv5wgg29IuB

成功判据(自动):
    - 有 pactl(PipeWire/PulseAudio)时自动对比发送前后系统音量,
      音量精确上涨一格 → 链路全通,打印 PASS,退出码 0;
    - 同时 --text(默认 TP-TEST-OK)会被打进当时聚焦的窗口,可人工确认。

状态与文件:
    身份私钥:~/.config/toothpaste-ble-probe/identity.pem   (首次运行自动生成,
                                                             对应板子里的一个配对槽)
    设备公钥:~/.config/toothpaste-ble-probe/device_pubkey.txt(配对成功后自动保存;
                                                             之后每次运行直接复用)
    板子重刷/清 NVS 后身份会失效:删除上面目录后重新走配对流程。

注意:
    - 写入已限速(每 5 秒最多 1 个 AUTH 包)。勿改回无节流重试——实测会把
      BLE 连接打断(write-without-response 轰炸)。
    - 运行中板子灯出现 黄→青→红闪 循环属脚本重连行为,非故障。
    - 解密失败时板子灯会闪蓝(DROP),本脚本的音量判据会报 FAIL。
"""

import argparse
import asyncio
import base64
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

from bleak import BleakClient, BleakScanner
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

SERVICE_UUID = "19b10000-e8f2-537e-4f6c-d104768a1214"
TX_CHAR      = "6856e119-2c7b-455a-bf42-cf7ddd2c5907"   # DataPacket 写入(WRITE_NR)
RESP_CHAR    = "6856e119-2c7b-455a-bf42-cf7ddd2c5908"   # ResponsePacket 通知

CONFIG_DIR       = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "toothpaste-ble-probe"
IDENTITY_FILE    = CONFIG_DIR / "identity.pem"
DEVICE_PUBKEY    = CONFIG_DIR / "device_pubkey.txt"

HKDF_INFO   = b"aes-gcm-256"   # 必须与固件 SecureSession.cpp / 网页 ECDHContext.tsx 一致
PUBKEY_RE   = re.compile(r"[A-Za-z0-9+/]{44}")  # 33B 压缩公钥的 base64,44 字符无填充


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


# ---------------- 极简 protobuf 编解码(proto3,按 toothpacket.proto 字段号) ----------------
def _varint(n: int) -> bytes:
    out = b""
    while True:
        b = n & 0x7F
        n >>= 7
        out += bytes([b | (0x80 if n else 0)])
        if not n:
            return out

def _tag(field: int, wire: int) -> bytes:
    return _varint((field << 3) | wire)

def _ld(field: int, data: bytes) -> bytes:
    return _tag(field, 2) + _varint(len(data)) + data

def _vi(field: int, n: int) -> bytes:
    return _tag(field, 0) + _varint(n)

def build_auth_packet(pub_b64_ascii: bytes) -> bytes:
    """未加密 AUTH 包:encryptedData=自身公钥 base64 ASCII,dataLen 必须等于其长度。"""
    p  = _vi(1, 1)                    # packetID = AUTH_PACKET
    p += _vi(2, 1)                    # packetNumber
    p += _vi(4, 1)                    # slowMode = true
    p += _ld(5, b"\x00" * 12)         # iv 占位
    p += _vi(6, len(pub_b64_ascii))   # dataLen(固件配对路径依赖此值)
    p += _ld(7, pub_b64_ascii)        # encryptedData
    p += _ld(8, b"\x00" * 16)         # tag 占位
    return p

def build_encrypted_packet(iv: bytes, ct: bytes, tag: bytes) -> bytes:
    p  = _vi(1, 0) + _vi(2, 1) + _vi(3, 1) + _vi(4, 1)   # DATA_PACKET / 1/1 / slow
    p += _ld(5, iv) + _vi(6, len(ct)) + _ld(7, ct) + _ld(8, tag)
    return p

def keyboard_inner(message: str) -> bytes:
    kb = _ld(1, message.encode()) + _vi(2, len(message))
    return _vi(1, 0) + _ld(2, kb)     # packetType=KEYBOARD_STRING + oneof field 2

def consumer_inner(code: int) -> bytes:
    cc = _ld(1, _varint(code)) + _vi(2, 1)
    return _vi(1, 4) + _ld(6, cc)     # packetType=CONSUMER_CONTROL + oneof field 6

def parse_response(data: bytes) -> dict:
    fields, i = {}, 0
    while i < len(data):
        key, shift = 0, 0
        while True:
            b = data[i]; i += 1; key |= (b & 0x7F) << shift; shift += 7
            if not (b & 0x80):
                break
        f, w = key >> 3, key & 7
        if w == 0:
            v, shift = 0, 0
            while True:
                b = data[i]; i += 1; v |= (b & 0x7F) << shift; shift += 7
                if not (b & 0x80):
                    break
            fields.setdefault(f, []).append(v)
        elif w == 2:
            ln, shift = 0, 0
            while True:
                b = data[i]; i += 1; ln |= (b & 0x7F) << shift; shift += 7
                if not (b & 0x80):
                    break
            fields.setdefault(f, []).append(bytes(data[i:i + ln])); i += ln
        else:
            raise ValueError(f"unexpected wire type {w}")
    return fields

RESPONSE_TYPE = {0: "KEEPALIVE", 1: "PEER_UNKNOWN", 2: "PEER_KNOWN", 3: "CHALLENGE"}


# ---------------- 音量判据(仅 Linux,尽力而为) ----------------
def get_volume() -> int | None:
    if not shutil.which("pactl"):
        return None
    try:
        out = subprocess.run(["pactl", "get-sink-volume", "@DEFAULT_SINK@"],
                             capture_output=True, text=True, timeout=5).stdout
        m = re.search(r"front-left:\s*(\d+)", out)
        return int(m.group(1)) if m else None
    except Exception:
        return None


# ---------------- 设备发现 ----------------
async def find_device(address: str | None):
    if address:
        return await BleakScanner.find_device_by_address(address, timeout=15)
    devices = await BleakScanner.discover(timeout=10, return_adv=True)
    for d, adv in devices.values():
        name = d.name or ""
        if SERVICE_UUID.lower() in [u.lower() for u in adv.service_uuids] or "tooth" in name.lower():
            return d
    return None


def read_pubkey_sources(args) -> tuple[str | None, str]:
    """返回 (公钥, 来源说明)。优先级:--pubkey > 已存 device_pubkey.txt > --pubkey-file。"""
    if args.pubkey:
        return args.pubkey.strip(), "--pubkey 参数"
    if DEVICE_PUBKEY.exists():
        m = PUBKEY_RE.findall(DEVICE_PUBKEY.read_text(errors="replace"))
        if m:
            return m[-1], str(DEVICE_PUBKEY)
    return None, ("--pubkey-file(等待写入)" if args.pubkey_file else "无(需要 --pubkey-file / 已存公钥)")


def watch_pubkey_file(path: Path, timeout_s: int = 60) -> str | None:
    """轮询等待公钥出现在文件里(板子经 USB 把公钥打进聚焦的 `cat > 文件` 终端)。"""
    for _ in range(timeout_s):
        if path.exists():
            m = PUBKEY_RE.findall(path.read_text(errors="replace"))
            if m:
                return m[-1]
        time.sleep(1)
    return None


# ---------------- 主流程 ----------------
async def run(args) -> int:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # 本方身份(固定复用,对应板子里一个配对槽)
    if IDENTITY_FILE.exists():
        my_priv = serialization.load_pem_private_key(IDENTITY_FILE.read_bytes(), password=None)
        log(f"复用身份: {IDENTITY_FILE}")
    else:
        my_priv = ec.generate_private_key(ec.SECP256R1())
        IDENTITY_FILE.write_bytes(my_priv.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption()))
        IDENTITY_FILE.chmod(0o600)
        log(f"生成新身份: {IDENTITY_FILE}")
    my_pub65 = my_priv.public_key().public_bytes(
        serialization.Encoding.X962, serialization.PublicFormat.UncompressedPoint)
    auth_pkt = build_auth_packet(base64.b64encode(my_pub65))

    dev_pub_b64, src = read_pubkey_sources(args)
    if dev_pub_b64:
        log(f"设备公钥(来自 {src}): {dev_pub_b64}")
    elif args.pubkey_file:
        log(f"无已存公钥,将监听 {args.pubkey_file}(请保持 cat 终端聚焦并长按 BOOT 10 秒)")
    else:
        log("!! 没有任何公钥来源:首次使用请加 --pubkey-file 并按脚本头部说明配对")
        return 2

    vol_before = get_volume()
    if vol_before is not None:
        log(f"音量基线: {vol_before}")

    overall_deadline = time.time() + args.timeout
    attempt = 0
    while time.time() < overall_deadline:
        attempt += 1
        try:
            log(f"=== 第 {attempt} 次连接 ===")
            dev = await find_device(args.address)
            if not dev:
                log("未扫描到设备(手机网页若连着请先断开),5 秒后重试")
                await asyncio.sleep(5)
                continue
            log(f"连接 {dev.name} [{dev.address}]")

            notifications: asyncio.Queue = asyncio.Queue()

            def on_notify(_c, data: bytearray):
                try:
                    f = parse_response(bytes(data))
                    notifications.put_nowait((
                        RESPONSE_TYPE.get(f.get(1, [None])[0], "?"),
                        bytes(f.get(2, [b""])[0]),
                        f.get(3, [b""])[0].decode(errors="replace")))
                except Exception:
                    notifications.put_nowait(("PARSE_ERR", b"", ""))

            async with BleakClient(dev.address) as client:
                await client.start_notify(RESP_CHAR, on_notify)
                log("已连接并订阅通知")

                # 限速握手循环:每 5 秒最多写一个 AUTH(严禁提速,见脚本头部说明)
                salt = None
                peer_unknown = 0
                while time.time() < overall_deadline:
                    await client.write_gatt_char(TX_CHAR, auth_pkt, response=False)
                    cycle_end = time.time() + 5
                    while time.time() < cycle_end:
                        try:
                            name, cd, fw = await asyncio.wait_for(
                                notifications.get(), timeout=max(0.1, cycle_end - time.time()))
                        except asyncio.TimeoutError:
                            break
                        if name == "CHALLENGE" and len(cd) >= 32:
                            salt = cd[:32]
                            log(f"<== CHALLENGE! salt={salt.hex()} (fw={fw})")
                            break
                        if name == "PEER_UNKNOWN":
                            peer_unknown += 1
                            if peer_unknown % 10 == 1:
                                log(f"<== PEER_UNKNOWN × {peer_unknown}(等待配对模式:长按 BOOT 10 秒)")
                        else:
                            log(f"<== {name}")
                    if salt:
                        break
                if not salt:
                    log("!! 未等到 CHALLENGE(身份可能已失效——板子重刷过?删掉 "
                        f"{CONFIG_DIR} 后重新配对)")
                    return 4

                # 解析设备公钥(必要时等待文件出现)
                if not dev_pub_b64 and args.pubkey_file:
                    log(f"等待公钥写入 {args.pubkey_file} ...")
                    dev_pub_b64 = await asyncio.to_thread(
                        watch_pubkey_file, Path(args.pubkey_file))
                if not dev_pub_b64:
                    log("!! 未拿到设备公钥(终端焦点丢了?)")
                    return 5
                dev_pub_b64 = dev_pub_b64.strip()

                dev_pub = ec.EllipticCurvePublicKey.from_encoded_point(
                    ec.SECP256R1(), base64.b64decode(dev_pub_b64))
                shared = my_priv.exchange(ec.ECDH(), dev_pub)
                aes_key = HKDF(algorithm=hashes.SHA256(), length=32,
                               salt=salt, info=HKDF_INFO).derive(shared)
                log("会话密钥派生完成")

                async def send_inner(inner: bytes, desc: str):
                    iv = os.urandom(12)
                    ct_tag = AESGCM(aes_key).encrypt(iv, inner, None)
                    pkt = build_encrypted_packet(iv, ct_tag[:-16], ct_tag[-16:])
                    await client.write_gatt_char(TX_CHAR, pkt, response=False)
                    log(f"==> 已发送加密{desc} ({len(pkt)}B)")

                await send_inner(keyboard_inner(args.text + "\n"), f"打字包 '{args.text}'")
                await asyncio.sleep(1.5)
                if not args.no_volume:
                    try:
                        await send_inner(consumer_inner(0x00E9), "音量+ 包")
                    except Exception as e:
                        log(f"(音量包发送失败: {e})")
                await asyncio.sleep(2)

                # 保存公钥供下次直接使用
                DEVICE_PUBKEY.write_text(dev_pub_b64 + "\n")
                log(f"设备公钥已保存到 {DEVICE_PUBKEY}")

                vol_after = get_volume()
                if vol_before is not None and vol_after is not None:
                    if vol_after > vol_before:
                        log(f"=== PASS:音量 {vol_before} → {vol_after},"
                            "加密链路端到端验证通过 ===")
                        return 0
                    log(f"=== FAIL:音量未变化({vol_before} → {vol_after})——"
                        "板子可能闪了蓝灯(DROP),多为公钥不匹配,删除 "
                        f"{DEVICE_PUBKEY} 后重新配对 ===")
                    return 6
                log(f"=== 完成:{args.text} 应已打入聚焦窗口(无 pactl,音量判据不可用)===")
                return 0

        except Exception as e:
            log(f"连接异常: {type(e).__name__}: {e},3 秒后重试")
            await asyncio.sleep(3)

    log("!! 总超时,未完成")
    return 4


def main() -> int:
    ap = argparse.ArgumentParser(
        description="ToothPaste 板侧自检探针(详见脚本头部文档)",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    ap.add_argument("--address", default=None,
                    help="板子蓝牙地址(不给则按服务 UUID/名称扫描)")
    ap.add_argument("--pubkey", default=None,
                    help="直接指定设备公钥(44 字符 base64)")
    ap.add_argument("--pubkey-file", default=None,
                    help="首次配对时监听的公钥文件(配合 `cat > 文件` 使用)")
    ap.add_argument("--text", default="TP-TEST-OK", help="测试打入的字符串")
    ap.add_argument("--no-volume", action="store_true", help="不发音量+包")
    ap.add_argument("--timeout", type=int, default=300, help="总超时秒数")
    args = ap.parse_args()
    try:
        return asyncio.run(run(args))
    except KeyboardInterrupt:
        return 1


if __name__ == "__main__":
    sys.exit(main())
