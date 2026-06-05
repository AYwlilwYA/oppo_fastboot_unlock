#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""OPPO/OnePlus OCDT解锁补丁工具
将原厂OCDT修改为解锁状态,同时保留prjname保持触摸正常。

工作原理:
  1. 修改Device State Flags: 0x528B -> 0x594D (三处冗余)
  2. 清零RSA签名段: 0x1100-0x11FF -> 全零
  3. 保留其他所有数据(Header Hash / Token / Entry Data)

适用设备:
  - OPPO Find X6 Pro (PGEM10, Snapdragon 8 Gen 2, ColorOS 15/16)
  - 理论上适用于所有使用解锁ABL的OPPO/OnePlus骁龙设备

使用方法:
  python3 patch_ocdt.py <输入OCDT镜像> [输出路径]

示例:
  python3 patch_ocdt.py ocdt.img                            # 输出 ocdt_unlock.img
  python3 patch_ocdt.py ocdt.img my_unlock_ocdt.img          # 指定输出名
"""

import sys
import struct
import hashlib
import os
import shutil

# 设置UTF-8输出
if sys.platform == 'win32':
    try:
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    except Exception:
        pass


# OCDT结构常量
OFFSET_FLAG0 = 0x1060  # Flags[0], uint16
OFFSET_FLAG1 = 0x1064  # Flags[1], uint16 (冗余副本)
OFFSET_FLAG2 = 0x1068  # Flags[2], uint16 (冗余副本)
OFFSET_SIG   = 0x1100  # RSA-2048签名, 256字节
SIG_SIZE     = 256

# 解锁/锁定标志值
LOCK_FLAG   = 0x528B  # 锁定
UNLOCK_FLAG = 0x594D  # 解锁 (ASCII: "MY")

# OCDT magic
MAGIC_TDCO = b'\x54\x44\x43\x4f'  # "TDCO" (大端序 OCDT)


def read_ocdt(path: str) -> bytearray:
    """读取OCDT镜像文件"""
    with open(path, 'rb') as f:
        data = bytearray(f.read())

    if len(data) != 131072:
        print(f"[WARN] OCDT大小={len(data)}, 预期131072字节(128KB)")
        if len(data) < 131072:
            print("  文件太小, 可能不是有效的OCDT镜像")
            sys.exit(1)

    if data[0:4] != MAGIC_TDCO:
        print(f"[WARN] OCDT magic不匹配, "
              f"期望'TDCO', 实际'{data[0:4].decode('ascii', errors='replace')}'")
        print("  文件可能不是有效的OCDT镜像, 继续处理...")

    return data


def analyze_ocdt(data: bytearray) -> dict:
    """分析OCDT当前状态"""
    info = {}

    f0 = struct.unpack('<H', data[OFFSET_FLAG0:OFFSET_FLAG0+2])[0]
    f1 = struct.unpack('<H', data[OFFSET_FLAG1:OFFSET_FLAG1+2])[0]
    f2 = struct.unpack('<H', data[OFFSET_FLAG2:OFFSET_FLAG2+2])[0]
    info['flags'] = [f0, f1, f2]

    if f0 == UNLOCK_FLAG and f1 == UNLOCK_FLAG and f2 == UNLOCK_FLAG:
        info['state'] = '已解锁'
    elif f0 == LOCK_FLAG:
        info['state'] = '已锁定'
    elif f0 == 0 and f1 == 0 and f2 == 0:
        info['state'] = '出厂空白'
    else:
        info['state'] = f'未知(0x{f0:04X})'

    sig_data = bytes(data[OFFSET_SIG:OFFSET_SIG+SIG_SIZE])
    sig_nonzero = sum(1 for b in sig_data if b != 0)
    info['sig_nonzero'] = sig_nonzero
    info['sig_valid'] = sig_nonzero > 0

    info['hash'] = data[0x10:0x30].hex()
    token = data[0x1030:0x1040]
    info['token'] = token.hex()
    info['token_ascii'] = ''.join(chr(b) if 32 <= b < 127 else '.' for b in token)

    info['sha256'] = hashlib.sha256(data).hexdigest()

    return info


def patch_ocdt(data: bytearray) -> int:
    """修改OCDT: Flags->0x594D, 签名清零, 返回修改数"""
    changes = 0

    for off in [OFFSET_FLAG0, OFFSET_FLAG1, OFFSET_FLAG2]:
        old = struct.unpack('<H', data[off:off+2])[0]
        if old != UNLOCK_FLAG:
            data[off:off+2] = struct.pack('<H', UNLOCK_FLAG)
            changes += 1
            print(f"  Flags[{off:#06x}]: 0x{old:04X} -> 0x{UNLOCK_FLAG:04X}")

    sig_nonzero_before = sum(1 for b in data[OFFSET_SIG:OFFSET_SIG+SIG_SIZE] if b != 0)
    if sig_nonzero_before > 0:
        data[OFFSET_SIG:OFFSET_SIG+SIG_SIZE] = b'\x00' * SIG_SIZE
        changes += 1
        print(f"  签名段[{OFFSET_SIG:#06x}-{OFFSET_SIG+SIG_SIZE:#06x}]: "
              f"清零 ({sig_nonzero_before}非零字节)")

    return changes


def print_info(info: dict, label: str):
    """打印OCDT信息"""
    f = info['flags']
    print(f"\n--- {label} ---")
    print(f"  状态: {info['state']}")
    print(f"  Flags: 0x{f[0]:04X}  0x{f[1]:04X}  0x{f[2]:04X}")
    print(f"  Header Hash: {info['hash'][:32]}...")
    print(f"  Token: {info['token_ascii']}")
    print(f"  RSA签名: {'有效' if info['sig_valid'] else '已清零'}"
          f" ({info['sig_nonzero']}/256 非零字节)")
    print(f"  SHA256: {info['sha256'][:24]}...")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("错误: 请指定输入OCDT镜像文件")
        sys.exit(1)

    input_path = sys.argv[1]

    if len(sys.argv) >= 3:
        output_path = sys.argv[2]
    else:
        base, ext = os.path.splitext(input_path)
        output_path = f"{base}_unlock{ext or '.img'}"

    if not os.path.exists(input_path):
        print(f"错误: 文件不存在: {input_path}")
        sys.exit(1)

    # 备份原文件
    backup_path = input_path + '.bak'
    if not os.path.exists(backup_path):
        shutil.copy2(input_path, backup_path)
        print(f"已备份原文件: {backup_path}")
    else:
        print(f"备份已存在: {backup_path} (跳过)")

    # 读取
    print(f"\n读取OCDT: {input_path}")
    data = read_ocdt(input_path)

    # 分析
    info_before = analyze_ocdt(data)
    print_info(info_before, "修改前")

    if info_before['state'] == '已解锁' and not info_before['sig_valid']:
        print("\n[WARN] OCDT已经是解锁状态且签名已清零, 无需修改!")
        print("  如需重新生成, 请从原厂锁定OCDT开始")
        return

    # 修改
    print(f"\n修改中...")
    changes = patch_ocdt(data)

    if changes == 0:
        print("  无需修改, OCDT已处于目标状态")
    else:
        print(f"  共 {changes} 处修改")

    # 验证
    info_after = analyze_ocdt(data)
    print_info(info_after, "修改后")

    # 写入
    with open(output_path, 'wb') as f:
        f.write(data)
    print(f"\n[OK] 已保存: {output_path}")

    # 最终验证
    f = info_after['flags']
    sig_ok = info_after['sig_nonzero'] == 0
    flag_ok = all(x == UNLOCK_FLAG for x in f)

    print(f"\n--- 验证 ---")
    print(f"  Flags=0x594D: {'[OK] 通过' if flag_ok else '[FAIL] 失败'}")
    print(f"  签名清零:     {'[OK] 通过' if sig_ok else '[FAIL] 失败'}")

    if flag_ok and sig_ok:
        basename = os.path.basename(output_path)
        print(f"\n[DONE] OCDT补丁成功!")
        print(f"\n刷入方法:")
        print(f"  方法1 (已有root+写保护关闭):")
        print(f"    adb push {output_path} /data/local/tmp/")
        print(f"    adb shell su -c 'dd if=/data/local/tmp/{basename} "
              f"of=/dev/block/by-name/ocdt'")
        print(f"    adb reboot")
        print(f"\n  方法2 (fastboot解锁后):")
        print(f"    adb reboot bootloader")
        print(f"    fastboot flash ocdt {output_path}")
        print(f"    fastboot reboot")
    else:
        print(f"\n[FAIL] 补丁验证失败, 请检查输入文件")


if __name__ == '__main__':
    main()
