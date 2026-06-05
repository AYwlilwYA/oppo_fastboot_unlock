# oppo_fastboot_unlock
用于修改原厂ocdt,永久解锁fb不掉触摸
# OPPO Fastboot 解锁补丁工具

## 概述

此工具用于修改OPPO设备的OCDT分区，实现**永久解锁Bootloader（fastboot可用）+ 保留触摸功能正常**。

### 适用设备
- OPPO Find X6 Pro (PGEM10, Snapdragon 8 Gen 2, ColorOS 15/16)
- 理论上适用于所有已刷入解锁ABL的OPPO/OnePlus骁龙设备

### 前置条件
1. ✅ 已刷入**解锁版ABL**（`unlock_abl.img`）到A/B双槽
2. ✅ 设备已**Root**（Magisk / APatch / KernelSU）
3. ⚠️ **必须使用原厂锁定OCDT作为输入**（不要用已修改过的）

---

## 使用方法

### 1. 准备原厂OCDT

从设备导出当前OCDT（设备需要已root）：

```bash
adb shell su -c 'dd if=/dev/block/by-name/ocdt of=/data/local/tmp/ocdt_original.img'
adb pull /data/local/tmp/ocdt_original.img .
```

### 2. 运行补丁脚本

```bash
# 基本用法（自动命名为 ocdt_original_unlock.img）
python3 patch_ocdt.py ocdt_original.img

# 指定输出文件名
python3 patch_ocdt.py ocdt_original.img ocdt_unlock.img
```

输出示例：
```
已备份原文件: ocdt_original.img.bak
读取OCDT: ocdt_original.img

--- 修改前 ---
  状态: 已锁定
  Flags: 0x528B  0x528B  0x528B
  ...

修改中...
  Flags[0x1060]: 0x528B -> 0x594D
  Flags[0x1064]: 0x528B -> 0x594D
  Flags[0x1068]: 0x528B -> 0x594D
  签名段[0x1100-0x1200]: 清零

✅ 已保存: ocdt_unlock.img
🎉 OCDT补丁成功!
```

### 3. 刷入设备

#### 方法A：Root直接刷入（推荐）
```bash
adb push ocdt_unlock.img /data/local/tmp/
adb shell su -c 'dd if=/data/local/tmp/ocdt_unlock.img of=/dev/block/by-name/ocdt'
adb reboot
```

#### 方法B：Fastboot刷入（需要先解锁）
```bash
adb reboot bootloader
fastboot flash ocdt ocdt_unlock.img
fastboot reboot
```

### 4. 验证结果

重启后检查：
```bash
adb shell getprop ro.boot.verifiedbootstate   # 应输出: orange
adb shell getprop ro.boot.flash.locked         # 应输出: 0
adb shell su -c 'cat /proc/touchpanel/tp_index' # 应输出: 0 (触摸正常)
```

---

## 回滚方法

如需恢复原厂锁定状态：
```bash
# 刷回备份的原厂OCDT
adb push ocdt_original.img /data/local/tmp/
adb shell su -c 'dd if=/data/local/tmp/ocdt_original.img of=/dev/block/by-name/ocdt'
adb reboot
```


## 注意事项

1. ⚠️ **必须使用原厂锁定OCDT**作为输入，不要用已修改过的
2. ⚠️ 脚本会自动备份原文件（`.bak`后缀），请妥善保管
3. ⚠️ 如果不刷入解锁ABL，只改OCDT会导致签名检查失败，设备无法开机

---

## 许可证

仅供安全研究和教育目的使用。使用者自行承担风险。
