#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CloudTrace 自动打包脚本 
使用前请确保已安装: pip install pyinstaller
如果打包后运行错误可先执行： pip install "charset_normalizer==2.1.1"
"""

import os
import subprocess
import sys

# ===================== 配置区 =====================
APP_NAME = "CloudTrace"
MAIN_SCRIPT = "CloudTrace.py"
DEFAULT_VERSION = "1.0.0"  # 默认版本号，可运行时修改

# 图标文件路径 (确保 favicon.ico 在项目根目录下)
ICON_FILE = "favicon.ico"

# UPX 压缩工具路径 (下载地址: https://upx.github.io/，解压后填入路径，留空则不启用)
# 若在此处填写有效路径，打包时将直接使用，不再询问；若留空，打包时会提示输入。
UPX_DIR = r""
# ===============================================

def check_pyinstaller():
    try:
        import PyInstaller
        print(f"[✓] 检测到 PyInstaller 版本: {PyInstaller.__version__}")
    except ImportError:
        print("[✗] 未检测到 PyInstaller，正在尝试安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

def choose_pack_mode():
    """让用户选择打包模式：单文件或文件夹"""
    print("\n请选择打包模式：")
    print("  1. 单文件 (单个 .exe，启动稍慢)")
    print("  2. 文件夹 (多个文件，启动较快)")
    while True:
        choice = input("请输入数字 (1 或 2，默认 2): ").strip()
        if choice == "":
            choice = "2"
        if choice in ("1", "2"):
            break
        print("输入无效，请重新输入。")
    return choice == "1"

def get_version():
    """获取用户输入的版本号，回车使用默认值"""
    ver = input(f"\n请输入版本号 (默认 {DEFAULT_VERSION}): ").strip()
    if not ver:
        ver = DEFAULT_VERSION
    print(f"[+] 使用版本号: {ver}")
    return ver

def get_upx_dir():
    """询问 UPX 目录路径（可留空跳过）"""
    print("\nUPX 压缩工具 (可减小程序体积，下载地址: https://upx.github.io/)")
    upx = input("请输入 UPX 目录路径 (留空跳过): ").strip()
    if upx:
        if not os.path.exists(upx):
            print(f"[!] 路径不存在: {upx}，将不使用 UPX")
            return ""
        return upx
    return ""

def build():
    print(f"\n🚀 开始打包 {APP_NAME}...")
    
    # 运行时决定版本号
    version = get_version()
    # 运行时决定打包模式
    one_file = choose_pack_mode()
    mode_str = "单文件" if one_file else "文件夹"
    print(f"[+] 已选择打包模式: {mode_str}")

    # 生成版本号文件（供程序读取）
    with open("version.txt", "w", encoding="utf-8") as f:
        f.write(version)
    print(f"[✓] 已生成 version.txt，内容：{version}")

    # UPX 目录决策：若预设了有效路径则直接使用，否则交互输入
    if UPX_DIR and os.path.exists(UPX_DIR):
        upx_dir = UPX_DIR
        print(f"[✓] 使用预设 UPX 路径: {upx_dir}")
    else:
        if UPX_DIR:
            print(f"[!] 预设 UPX 路径不存在或无效: {UPX_DIR}")
        upx_dir = get_upx_dir()

    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", f"{APP_NAME}-{version}",
        "--noconfirm",
        "--clean",
        "--windowed",
    ]

    if one_file:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    # 加载图标
    if ICON_FILE and os.path.exists(ICON_FILE):
        cmd.extend(["--icon", ICON_FILE])
        cmd.extend(["--add-data", f"{ICON_FILE};."])
        print(f"[✓] 已设置程序图标并打包资源: {ICON_FILE}")

    # 将版本号文件也打包进去
    cmd.extend(["--add-data", f"version.txt{os.pathsep}."])
    print("[✓] 已将 version.txt 加入打包资源")

    # UPX 压缩配置
    if upx_dir:
        cmd.extend(["--upx-dir", upx_dir])
        cmd.extend(["--upx-exclude", "PySide6"])
        print(f"[✓] 已启用 UPX 压缩: {upx_dir}")
    else:
        print("[✓] 未启用 UPX 压缩")

    # ==================== 1. 剔除无用巨型模块 ====================
    excludes = [
        "tkinter", "matplotlib", "numpy", "PIL", "scipy", "pandas",
        "PySide6.QtNetwork", "PySide6.QtOpenGL", "PySide6.QtSvg", 
        "PySide6.QtXml", "PySide6.QtTest", "PySide6.QtSql", 
        "PySide6.QtMultimedia", "PySide6.QtWebEngine", 
        "PySide6.QtWebChannel", "PySide6.QtBluetooth",
        "aiohttp.worker",
    ]
    for excl in excludes:
        cmd.extend(["--exclude-module", excl])

    # ==================== 2. 强制收集核心隐式导入 ====================
    hidden_imports = [
        "PySide6.QtWidgets", "PySide6.QtCore", "PySide6.QtGui", 
        "asyncio", "ssl",
    ]
    for imp in hidden_imports:
        cmd.extend(["--hidden-import", imp])

    # ==================== 3. 全量收集网络依赖 ====================
    network_packages = ["aiohttp", "charset_normalizer", "multidict", "yarl", "idna", "attr", "aiosignal"]
    print(f"[+] 全量收集网络依赖库: {', '.join(network_packages)}")
    for pkg in network_packages:
        cmd.extend(["--collect-all", pkg])

    # 主脚本
    cmd.append(MAIN_SCRIPT)

    print(f"\n执行命令: \n{' '.join(cmd)}\n")
    subprocess.run(cmd, check=True)

    print("\n" + "="*50)
    print(f"✅ 打包完成！")
    if one_file:
        print(f"📦 可执行文件位于: dist/{APP_NAME}-{version}.exe")
    else:
        print(f"📦 程序目录位于: dist/{APP_NAME}-{version}/")
    print("="*50)

if __name__ == "__main__":
    check_pyinstaller()
    build()
    input("按回车键退出...")