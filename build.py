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
VERSION = "1.0.0"

# 图标文件路径 (确保 favicon.ico 在项目根目录下)
ICON_FILE = "favicon.ico"

# UPX 压缩工具路径 (下载地址: https://upx.github.io/，解压后填入路径，留空则不启用)
# UPX_DIR = r"C:\upx-5.1.1-win64"
UPX_DIR = r""

# 是否打包成单文件False / True
ONE_FILE = True
# ===============================================

def check_pyinstaller():
    try:
        import PyInstaller
        print(f"[✓] 检测到 PyInstaller 版本: {PyInstaller.__version__}")
    except ImportError:
        print("[✗] 未检测到 PyInstaller，正在尝试安装...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyinstaller"])

def build():
    print(f"\n🚀 开始打包 {APP_NAME} V{VERSION}...")
    
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", APP_NAME,
        "--noconfirm",
        "--clean",
        "--windowed",
    ]

    if ONE_FILE:
        cmd.append("--onefile")
    else:
        cmd.append("--onedir")

    # 加载图标 (同时设置为exe外壳图标 和 打包进内部作为运行时资源)
    if ICON_FILE and os.path.exists(ICON_FILE):
        cmd.extend(["--icon", ICON_FILE])
        # ★ 关键：将图标文件打包到程序内部，运行时需要用到
        cmd.extend(["--add-data", f"{ICON_FILE};."])
        print(f"[✓] 已设置程序图标并打包资源: {ICON_FILE}")

    # UPX 压缩配置
    if UPX_DIR and os.path.exists(UPX_DIR):
        cmd.extend(["--upx-dir", UPX_DIR])
        cmd.extend(["--upx-exclude", "PySide6"])
        print(f"[✓] 已启用 UPX 压缩: {UPX_DIR}")

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
    if ONE_FILE:
        print(f"📦 可执行文件位于: dist/{APP_NAME}.exe")
    else:
        print(f"📦 程序目录位于: dist/{APP_NAME}/")
    print("="*50)

if __name__ == "__main__":
    check_pyinstaller()
    build()
    input("按回车键退出...")
