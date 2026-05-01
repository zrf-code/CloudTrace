#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CloudTrace 云迹 V1.0 (Win7兼容版)
"""

import sys
import random
import time
import ipaddress
import asyncio
import aiohttp
import socket
import ssl
from datetime import datetime
from typing import List, Optional, Dict
import csv  
import os
import platform
import json
import shutil
import requests




# ============ Windows 7 兼容性配置 ============
IS_WIN7 = (platform.system() == "Windows" and platform.release() == "7")

if IS_WIN7:  
    try:
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    except AttributeError:
        pass
    os.environ['QT_AUTO_SCREEN_SCALE_FACTOR'] = '0'
    os.environ['QT_SCALE_FACTOR'] = '1'
    os.environ['QT_FONT_DPI'] = '96'

if sys.version_info < (3, 6):
    print("错误: 此程序需要 Python 3.6 或更高版本")
    sys.exit(1)
# ===========================================

from PySide6.QtWidgets import (
    QApplication, QWidget, QLabel, QPushButton,
    QLineEdit, QProgressBar, QTableWidget, QTableWidgetItem,
    QVBoxLayout, QHBoxLayout, QHeaderView,
    QTextEdit, QComboBox, QFileDialog, QMessageBox,
    QSpinBox, QDialog, QFrame  
)
from PySide6.QtCore import Qt, QThread, Signal, QTimer
from PySide6.QtGui import QFont, QColor, QIcon  


def get_system_font():
    system = platform.system()
    if system == "Windows":
        return "Microsoft YaHei, SimHei, sans-serif"
    elif system == "Darwin":
        return "PingFang SC, Helvetica, sans-serif"
    else:
        return "DejaVu Sans, sans-serif"


SYSTEM_FONT = get_system_font()
FONT_FAMILY = SYSTEM_FONT.split(',')[0].strip()  

FONT_TITLE = QFont(FONT_FAMILY, 28)
FONT_TITLE.setBold(True)
FONT_BTN = QFont(FONT_FAMILY, 11)
FONT_SMALL = FONT_BTN  
FONT_STATUS = QFont(FONT_FAMILY, 10)
FONT_LABEL = QFont(FONT_FAMILY, 10)

BTN_W = 120
BTN_H = 32
SPACING = 8


# 保存路径 (兼容 PyInstaller 打包)
if getattr(sys, 'frozen', False):
    # 如果是打包后的 exe 环境，获取 exe 所在的目录
    APP_DIR = os.path.dirname(sys.executable)
	# PyInstaller 解压临时目录，用于寻找打包进来的资源文件
    _MEIPASS = sys._MEIPASS
else:
    # 如果是普通 Python 脚本环境，获取脚本所在的目录
    APP_DIR = os.path.dirname(os.path.abspath(__file__))
    _MEIPASS = APP_DIR
def resource_path(relative_path):
    """获取资源的绝对路径 (兼容开发环境与 PyInstaller 打包环境)"""
    try:
        # PyInstaller 创建临时文件夹，将路径存入 sys._MEIPASS
        return os.path.join(_MEIPASS, relative_path)
    except Exception:
        return os.path.join(APP_DIR, relative_path)


# ============ 新增：动态 IP 列表支持 ============


# Cloudflare 官方 IP 列表地址
CF_OFFICIAL_IPV4_URL = "https://www.cloudflare.com/ips-v4/"
CF_OFFICIAL_IPV6_URL = "https://www.cloudflare.com/ips-v6/"

# 缓存文件与更新间隔（30 天）
IP_CACHE_FILE = os.path.join(APP_DIR, "ip_cache.json")
IP_CACHE_UPDATE_INTERVAL = 30 * 24 * 3600

def fetch_official_cidrs(url: str):
    """从官方 URL 获取 CIDR 列表，失败返回 None"""
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        lines = resp.text.splitlines()
        return [line.strip() for line in lines if line.strip() and not line.startswith('#')]
    except Exception as e:
        print(f"[IP列表] 获取官方列表失败 ({url}): {e}")
        return None

def load_or_update_ip_cache(ip_version: int):
    """
    返回对应版本的 CIDR 列表（IPv4: 4, IPv6: 6）。
    优先使用本地缓存，过期则尝试从官方更新；失败时回退内置列表。
    """
    builtin = CF_IPV4_CIDRS if ip_version == 4 else CF_IPV6_CIDRS
    key = "ipv4" if ip_version == 4 else "ipv6"
    url = CF_OFFICIAL_IPV4_URL if ip_version == 4 else CF_OFFICIAL_IPV6_URL

    cache = {}
    # 读取本地缓存
    try:
        if os.path.exists(IP_CACHE_FILE):
            with open(IP_CACHE_FILE, 'r', encoding='utf-8') as f:
                cache = json.load(f)
    except Exception:
        pass

    current_time = time.time()
    # 如果缓存有效且未过期，直接返回
    if cache.get(key) and (current_time - cache.get('update_time', 0) < IP_CACHE_UPDATE_INTERVAL):
        return cache[key]

    # 尝试从官方更新
    official_list = fetch_official_cidrs(url)
    if official_list:
        cache[key] = official_list
        cache['update_time'] = current_time
        try:
            with open(IP_CACHE_FILE, 'w', encoding='utf-8') as f:
                json.dump(cache, f, ensure_ascii=False, indent=2)
            print(f"[IP列表] 已更新 {key} 列表（{len(official_list)} 个 CIDR）")
        except Exception:
            pass
        return official_list

    # 下载失败，使用缓存中已有的列表（即使过期）
    if cache.get(key):
        print(f"[IP列表] 无法更新，使用过期缓存（{len(cache[key])} 个 CIDR）")
        return cache[key]

    # 没有任何可用缓存，回退内置列表
    print(f"[IP列表] 无缓存，使用内置 {key} 列表")
    return builtin

SAVE_DIR = os.path.join(APP_DIR, "CloudTrace_history")

IPV4_SCAN_FILE = os.path.join(SAVE_DIR, "ipv4_scan_latest.json")
IPV6_SCAN_FILE = os.path.join(SAVE_DIR, "ipv6_scan_latest.json")
IPV4_SPEED_FILE = os.path.join(SAVE_DIR, "ipv4_speed_latest.json")
IPV6_SPEED_FILE = os.path.join(SAVE_DIR, "ipv6_speed_latest.json")
MAX_HISTORY = 5

CF_IPV4_CIDRS = [
    "173.245.48.0/20", "103.21.244.0/22", "103.22.200.0/22", "103.31.4.0/22",
    "141.101.64.0/18", "108.162.192.0/18", "190.93.240.0/20", "188.114.96.0/20",
    "197.234.240.0/22", "198.41.128.0/17", "162.158.0.0/15", "104.16.0.0/12",
    "172.64.0.0/17", "172.64.128.0/18", "172.64.192.0/19", "172.64.224.0/22",
    "172.64.229.0/24", "172.64.230.0/23", "172.64.232.0/21", "172.64.240.0/21",
    "172.64.248.0/21", "172.65.0.0/16", "172.66.0.0/16", "172.67.0.0/16",
    "131.0.72.0/22"
]

CF_IPV6_CIDRS = [
    "2400:cb00:2049::/48", "2400:cb00:f00e::/48", "2606:4700::/32",
    "2606:4700:10::/48", "2606:4700:130::/48", "2606:4700:3000::/48",
    "2606:4700:3001::/48", "2606:4700:3002::/48", "2606:4700:3003::/48",
    "2606:4700:3004::/48", "2606:4700:3005::/48", "2606:4700:3006::/48",
    "2606:4700:3007::/48", "2606:4700:3008::/48", "2606:4700:3009::/48",
    "2606:4700:3010::/48", "2606:4700:3011::/48", "2606:4700:3012::/48",
    "2606:4700:3013::/48", "2606:4700:3014::/48", "2606:4700:3015::/48",
    "2606:4700:3016::/48", "2606:4700:3017::/48", "2606:4700:3018::/48",
    "2606:4700:3019::/48", "2606:4700:3020::/48", "2606:4700:3021::/48",
    "2606:4700:3022::/48", "2606:4700:3023::/48", "2606:4700:3024::/48",
    "2606:4700:3025::/48", "2606:4700:3026::/48", "2606:4700:3027::/48",
    "2606:4700:3028::/48", "2606:4700:3029::/48", "2606:4700:3030::/48",
    "2606:4700:3031::/48", "2606:4700:3032::/48", "2606:4700:3033::/48",
    "2606:4700:3034::/48", "2606:4700:3035::/48", "2606:4700:3036::/48",
    "2606:4700:3037::/48", "2606:4700:3038::/48", "2606:4700:3039::/48",
    "2606:4700:a0::/48", "2606:4700:a1::/48", "2606:4700:a8::/48",
    "2606:4700:a9::/48", "2606:4700:a::/48", "2606:4700:b::/48",
    "2606:4700:c::/48", "2606:4700:d0::/48", "2606:4700:d1::/48",
    "2606:4700:d::/48", "2606:4700:e0::/48", "2606:4700:e1::/48",
    "2606:4700:e2::/48", "2606:4700:e3::/48", "2606:4700:e4::/48",
    "2606:4700:e5::/48", "2606:4700:e6::/48", "2606:4700:e7::/48",
    "2606:4700:e::/48", "2606:4700:f1::/48", "2606:4700:f2::/48",
    "2606:4700:f3::/48", "2606:4700:f4::/48", "2606:4700:f5::/48",
    "2606:4700:f::/48", "2803:f800:50::/48", "2803:f800:51::/48",
    "2a06:98c1:3100::/48", "2a06:98c1:3101::/48", "2a06:98c1:3102::/48",
    "2a06:98c1:3103::/48", "2a06:98c1:3104::/48", "2a06:98c1:3105::/48",
    "2a06:98c1:3106::/48", "2a06:98c1:3107::/48", "2a06:98c1:3108::/48",
    "2a06:98c1:3109::/48", "2a06:98c1:310a::/48", "2a06:98c1:310b::/48",
    "2a06:98c1:310c::/48", "2a06:98c1:310d::/48", "2a06:98c1:310e::/48",
    "2a06:98c1:310f::/48", "2a06:98c1:3120::/48", "2a06:98c1:3121::/48",
    "2a06:98c1:3122::/48", "2a06:98c1:3123::/48", "2a06:98c1:3200::/48",
    "2a06:98c1:50::/48", "2a06:98c1:51::/48", "2a06:98c1:54::/48",
    "2a06:98c1:58::/48"
]

AIRPORT_CODES = {
    "HKG": "香港", "TPE": "台北", "KHH": "高雄", "MFM": "澳门",
    "NRT": "东京", "HND": "东京", "KIX": "大阪", "NGO": "名古屋",
    "FUK": "福冈", "CTS": "札幌", "OKA": "冲绳",
    "ICN": "首尔", "GMP": "首尔", "PUS": "釜山",
    "SIN": "新加坡", "BKK": "曼谷", "DMK": "曼谷",
    "KUL": "吉隆坡", "HKT": "普吉岛",
    "MNL": "马尼拉", "CEB": "宿务",
    "HAN": "河内", "SGN": "胡志明市",
    "JKT": "雅加达", "DPS": "巴厘岛",
    "DEL": "德里", "BOM": "孟买", "MAA": "金奈",
    "DXB": "迪拜", "AUH": "阿布扎比",
    "SJC": "圣何塞", "LAX": "洛杉矶", "SFO": "旧金山",
    "SEA": "西雅图", "PDX": "波特兰",
    "LAS": "拉斯维加斯", "PHX": "菲尼克斯",
    "DEN": "丹佛", "DFW": "达拉斯", "IAH": "休斯顿",
    "ORD": "芝加哥", "MSP": "明尼阿波利斯",
    "ATL": "亚特兰大", "MIA": "迈阿密", "MCO": "奥兰多",
    "JFK": "纽约", "EWR": "纽约", "LGA": "纽约",
    "BOS": "波士顿", "PHL": "费城", "IAD": "华盛顿",
    "YYZ": "多伦多", "YVR": "温哥华", "YUL": "蒙特利尔",
    "LHR": "伦敦", "LGW": "伦敦", "STN": "伦敦",
    "CDG": "巴黎", "ORY": "巴黎",
    "FRA": "法兰克福", "MUC": "慕尼黑", "TXL": "柏林",
    "AMS": "阿姆斯特丹", "EIN": "埃因霍温",
    "MAD": "马德里", "BCN": "巴塞罗那",
    "FCO": "罗马", "MXP": "米兰", "LIN": "米兰",
    "ZRH": "苏黎世", "GVA": "日内瓦",
    "VIE": "维也纳", "PRG": "布拉格",
    "WAW": "华沙", "KRK": "克拉科夫",
    "HEL": "赫尔辛基", "OSL": "奥斯陆", "ARN": "斯德哥尔摩",
    "CPH": "哥本哈根",
    "SYD": "悉尼", "MEL": "墨尔本", "BNE": "布里斯班",
    "PER": "珀斯", "ADL": "阿德莱德",
    "AKL": "奥克兰", "WLG": "惠灵顿",
    "GRU": "圣保罗", "GIG": "里约热内卢", "EZE": "布宜诺斯艾利斯",
    "SCL": "圣地亚哥", "LIM": "利马", "BOG": "波哥大",
    "JNB": "约翰内斯堡", "CPT": "开普敦", "CAI": "开罗",
}

PORT_OPTIONS = ["443", "2053", "2083", "2087", "2096", "8443"]


# ===================== ★ 彻底重写：历史结果管理 =====================

def ensure_save_dir():
    os.makedirs(SAVE_DIR, exist_ok=True)
    _cleanup_legacy_files()
    _cleanup_all_types()


def save_results_to_file(results: List[Dict], ip_version: int, result_type: str) -> bool:
    ensure_save_dir()
    now = datetime.now()  # 修复：只调用一次datetime.now()，防止跨秒导致文件名与内容时间戳不一致
    timestamp = now.strftime("%Y%m%d_%H%M%S")
    ip_label = "ipv4" if ip_version == 4 else "ipv6"
    type_label = result_type  # 优化：移除冗余的三元表达式

    history_file = os.path.join(SAVE_DIR, f"{ip_label}_{type_label}_{timestamp}.json")

    save_data = {
        'save_time': now.strftime("%Y-%m-%d %H:%M:%S"),
        'ip_version': ip_version,
        'result_type': result_type,
        'count': len(results),
        'results': results
    }

    try:
        with open(history_file, 'w', encoding='utf-8') as f:
            json.dump(save_data, f, ensure_ascii=False, indent=2)

        if result_type == "scan":
            latest_file = IPV4_SCAN_FILE if ip_version == 4 else IPV6_SCAN_FILE
        else:
            latest_file = IPV4_SPEED_FILE if ip_version == 4 else IPV6_SPEED_FILE
        shutil.copy2(history_file, latest_file)

        _cleanup_by_prefix(ip_label, type_label)
        return True
    except Exception as e:
        print(f"[保存] 保存失败: {e}")
        return False


def _cleanup_by_prefix(ip_label: str, type_label: str):
    prefix = f"{ip_label}_{type_label}_"
    timestamped_files = []

    try:
        all_files = os.listdir(SAVE_DIR)
    except Exception as e:
        print(f"[清理] 无法列出目录 {SAVE_DIR}: {e}")
        return

    for f in all_files:
        if f.startswith(prefix) and f.endswith(".json") and "latest" not in f:
            full_path = os.path.join(SAVE_DIR, f)
            if os.path.isfile(full_path):
                timestamped_files.append(full_path)

    total = len(timestamped_files)
    if total <= MAX_HISTORY:
        return

    timestamped_files.sort(key=lambda x: os.path.basename(x), reverse=True)
    to_delete = timestamped_files[MAX_HISTORY:]
    
    deleted = 0
    for old_file in to_delete:
        try:
            os.remove(old_file)
            deleted += 1
            print(f"[清理] 已删除: {os.path.basename(old_file)}")
        except Exception as e:
            print(f"[清理] 删除失败 {os.path.basename(old_file)}: {e}")

    print(f"[清理] {ip_label}_{type_label}: 共{total}份, 保留{MAX_HISTORY}份, 删除{deleted}份")


def _cleanup_all_types():
    for ip_label in ("ipv4", "ipv6"):
        for type_label in ("scan", "speed"):
            _cleanup_by_prefix(ip_label, type_label)


def _cleanup_legacy_files():
    try:
        all_files = os.listdir(SAVE_DIR)
    except Exception as e:
        print(f"[清理旧格式] 无法列出目录: {e}")
        return

    for f in all_files:
        is_legacy = False
        for ip in ("ipv4", "ipv6"):
            if f.startswith(f"{ip}_") and "scan" not in f and "speed" not in f:
                is_legacy = True
                break

        if is_legacy and f.endswith(".json"):
            full_path = os.path.join(SAVE_DIR, f)
            try:
                if os.path.isfile(full_path):
                    os.remove(full_path)
                    print(f"[清理旧格式] 已删除: {f}")
            except Exception as e:
                print(f"[清理旧格式] 删除失败 {f}: {e}")


def load_results_from_file(filepath: str) -> Optional[Dict]:
    try:
        if not os.path.exists(filepath):
            return None
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if 'results' in data and isinstance(data['results'], list):
            return data
        return None
    except Exception as e:
        print(f"[加载] 加载失败: {e}")
        return None


def get_history_list(ip_version: int, result_type: str) -> List[Dict]:
    ensure_save_dir()
    ip_label = "ipv4" if ip_version == 4 else "ipv6"
    type_label = result_type
    prefix = f"{ip_label}_{type_label}_"
    history = []

    try:
        all_files = os.listdir(SAVE_DIR)
    except Exception:  # 修复：禁止使用裸except吞掉键盘中断
        return history

    for f in sorted(all_files, reverse=True):
        if f.startswith(prefix) and f.endswith(".json") and "latest" not in f:
            filepath = os.path.join(SAVE_DIR, f)
            try:
                with open(filepath, 'r', encoding='utf-8') as fp:
                    data = json.load(fp)
                history.append({
                    'filename': f,
                    'filepath': filepath,
                    'save_time': data.get('save_time', '未知'),
                    'count': data.get('count', 0),
                })
            except Exception:  # 修复：禁止使用裸except
                continue

    return history


# ===================== ★ 通用美化消息框 =====================
class CustomMessageBox(QDialog):
    TYPE_INFO = "info"
    TYPE_WARNING = "warning"
    TYPE_ERROR = "error"
    TYPE_QUESTION = "question"
    
    ICONS = {
        TYPE_INFO: "ℹ️",
        TYPE_WARNING: "⚠️",
        TYPE_ERROR: "❌",
        TYPE_QUESTION: "❓",
    }
    
    @classmethod
    def show(cls, parent, title: str, text: str, msg_type: str = TYPE_INFO, 
             buttons: List[str] = None, default_button: str = None) -> Optional[str]:
        dlg = cls(parent, title, text, msg_type, buttons, default_button)
        if dlg.exec() == QDialog.Accepted:
            return dlg.clicked_button
        return None
    
    @classmethod
    def information(cls, parent, title: str, text: str):
        dlg = cls(parent, title, text, cls.TYPE_INFO, ["确定"])
        dlg.exec()
        
    @classmethod
    def warning(cls, parent, title: str, text: str):
        dlg = cls(parent, title, text, cls.TYPE_WARNING, ["确定"])
        dlg.exec()
        
    @classmethod
    def critical(cls, parent, title: str, text: str):
        dlg = cls(parent, title, text, cls.TYPE_ERROR, ["确定"])
        dlg.exec()
        
    @classmethod
    def question(cls, parent, title: str, text: str, 
                 buttons: List[str] = None, default_button: str = None) -> Optional[str]:
        if buttons is None:
            buttons = ["是", "否"]
        dlg = cls(parent, title, text, cls.TYPE_QUESTION, buttons, default_button)
        if dlg.exec() == QDialog.Accepted:
            return dlg.clicked_button
        return None
    
    def __init__(self, parent, title: str, text: str, msg_type: str = TYPE_INFO,
                 buttons: List[str] = None, default_button: str = None):
        super().__init__(parent)
        self.clicked_button = None
        self.setWindowTitle(title)
        self.setModal(True)
        self.setFixedSize(380, 180)
        
        if buttons is None:
            buttons = ["确定"]
            
        bg_color = "#F9FAFB"
        border_color = "#E5E7EB"
        
        if msg_type == self.TYPE_WARNING:
            border_color = "#F59E0B"
        elif msg_type == self.TYPE_ERROR:
            border_color = "#EF4444"
        elif msg_type == self.TYPE_INFO:
            border_color = "#3B82F6"
            
        self.setStyleSheet(f"""
            QDialog {{
                background: {bg_color};
                border-radius: 12px;
                font-family: "{FONT_FAMILY}";
            }}
        """)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        header = QFrame()
        header.setFixedHeight(4)
        header.setStyleSheet(f"background: {border_color}; border-top-left-radius: 12px; border-top-right-radius: 12px;")
        layout.addWidget(header)
        
        content = QFrame()
        content.setStyleSheet("QFrame { background: transparent; border: none; }")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(24, 16, 24, 16)
        content_layout.setSpacing(12)
        
        header_row = QHBoxLayout()
        header_row.setSpacing(12)
        
        icon_label = QLabel(self.ICONS.get(msg_type, "ℹ️"))
        icon_label.setFont(QFont(FONT_FAMILY, 28))
        icon_label.setStyleSheet("background: transparent; border: none;")
        icon_label.setAlignment(Qt.AlignTop)
        header_row.addWidget(icon_label)
        
        text_label = QLabel(text)
        text_label.setFont(QFont(FONT_FAMILY, 10))
        text_label.setStyleSheet("color: #374151; background: transparent; border: none;")
        text_label.setWordWrap(True)
        text_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        header_row.addWidget(text_label, 1)
        
        content_layout.addLayout(header_row)
        
        btn_row = QHBoxLayout()
        btn_row.setSpacing(10)
        btn_row.addStretch()
        
        for btn_text in reversed(buttons):
            btn = QPushButton(btn_text)
            btn.setFixedSize(80, 32)
            btn.setFont(FONT_BTN)
            btn.setCursor(Qt.PointingHandCursor)
            
            is_primary = (btn_text == default_button) or (btn_text == "确定" and len(buttons) == 1)
            is_danger = (btn_text in ["是", "停止", "删除"])
            
            if is_danger:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: #EF4444; color: white; border-radius: 6px;
                        font-family: "{FONT_FAMILY}"; border: none;
                    }}
                    QPushButton:hover {{ background: #DC2626; }}
                    QPushButton:pressed {{ background: #B91C1C; }}
                """)
            elif is_primary:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: #3B82F6; color: white; border-radius: 6px;
                        font-family: "{FONT_FAMILY}"; border: none;
                    }}
                    QPushButton:hover {{ background: #2563EB; }}
                    QPushButton:pressed {{ background: #1D4ED8; }}
                """)
            else:
                btn.setStyleSheet(f"""
                    QPushButton {{
                        background: #E5E7EB; color: #374151; border-radius: 6px;
                        font-family: "{FONT_FAMILY}"; border: none;
                    }}
                    QPushButton:hover {{ background: #D1D5DB; }}
                    QPushButton:pressed {{ background: #9CA3AF; }}
                """)
            
            def make_handler(btn_text=btn_text):
                def handler():
                    self.clicked_button = btn_text
                    self.accept()
                return handler
            
            btn.clicked.connect(make_handler(btn_text))
            btn_row.addWidget(btn)
            
            if btn_text == default_button:
                btn.setDefault(True)
                btn.setFocus()
        
        content_layout.addLayout(btn_row)
        layout.addWidget(content)

# ===================== 自定义对话框 =====================

class HistorySelectDialog(QDialog):
    def __init__(self, ip_label: str, type_label: str, history: List[Dict], parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"选择{ip_label}{type_label}历史记录")
        self.setMinimumWidth(460)
        self.setMinimumHeight(320)
        self.selected_filepath = None
        self.history = history

        self.setStyleSheet(f"""
        QDialog {{ background: #F9FAFB; font-family: "{FONT_FAMILY}", sans-serif; }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        title_frame = QFrame()
        title_frame.setObjectName("dialogTitleFrame")
        title_frame.setStyleSheet("""
            #dialogTitleFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #1E3A5F, stop:1 #2563EB);
                border-radius: 8px;
            }
        """)
        
        title_layout = QVBoxLayout(title_frame)
        title_layout.setContentsMargins(14, 10, 14, 10)
        title_layout.setSpacing(2)
        
        title_text = QLabel(f"📋 {ip_label}{type_label}历史记录")
        title_text.setFont(QFont(FONT_FAMILY, 13))
        title_text.setStyleSheet("color: white; font-weight: bold; border: none; background: transparent;")
        title_layout.addWidget(title_text)
        
        subtitle = QLabel(f"共 {len(history)} 份记录，请选择要加载的版本")
        subtitle.setFont(FONT_SMALL)  # 优化：使用别名
        subtitle.setStyleSheet("color: rgba(255,255,255,180); border: none; background: transparent;")
        title_layout.addWidget(subtitle)
        
        layout.addWidget(title_frame)

        self.table = QTableWidget()
        self.table.setColumnCount(3)
        self.table.setHorizontalHeaderLabels(["保存时间", "IP数量", "文件"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.verticalHeader().setVisible(False)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setAlternatingRowColors(True)
        self.table.setRowCount(len(history))

        self.table.setStyleSheet(f"""
        QTableWidget {{
            background: white; border: 1px solid #E5E7EB; border-radius: 6px;
            gridline-color: #F3F4F6; font-family: "{FONT_FAMILY}", sans-serif;
            selection-background-color: #3B82F6; selection-color: white;
            alternate-background-color: #F9FAFB;
        }}
        QHeaderView::section {{
            background: #F3F4F6; color: #374151; border: none; height: 30px;
            padding-left: 10px; font-family: "{FONT_FAMILY}"; font-weight: bold;
            border-bottom: 2px solid #E5E7EB;
        }}
        QTableWidget::item {{ padding: 6px; border-bottom: 1px solid #F3F4F6; }}
        QTableWidget::item:selected {{ background: #3B82F6; color: white; }}
        """)

        for i, h in enumerate(history):
            time_item = QTableWidgetItem(h['save_time'])
            time_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 0, time_item)
            count_item = QTableWidgetItem(f"{h['count']} 个")
            count_item.setTextAlignment(Qt.AlignCenter)
            self.table.setItem(i, 1, count_item)
            self.table.setItem(i, 2, QTableWidgetItem(h['filename']))

        if history:
            self.table.selectRow(0)
        self.table.cellDoubleClicked.connect(self._on_accept)

        layout.addWidget(self.table, 1)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(90, 34)
        cancel_btn.setFont(FONT_BTN)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
        QPushButton {{
            background: #F3F4F6; color: #374151; border-radius: 6px;
            font-family: "{FONT_FAMILY}"; border: 1px solid #D1D5DB;
        }}
        QPushButton:hover {{ background: #E5E7EB; }}
        """)
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addWidget(cancel_btn)

        btn_layout.addSpacing(12)

        select_btn = QPushButton("加载")
        select_btn.setFixedSize(90, 34)
        select_btn.setFont(FONT_BTN)
        select_btn.setCursor(Qt.PointingHandCursor)
        select_btn.setStyleSheet(f"""
        QPushButton {{
            background: #3B82F6; color: white; border-radius: 6px;
            font-family: "{FONT_FAMILY}"; border: none;
        }}
        QPushButton:hover {{ background: #2563EB; }}
        """)
        select_btn.clicked.connect(self._on_accept)
        btn_layout.addWidget(select_btn)

        layout.addLayout(btn_layout)

    def _on_accept(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.history):
            self.selected_filepath = self.history[row]['filepath']
            self.accept()


class ExportSelectDialog(QDialog):
    def __init__(self, has_scan: bool, has_speed: bool, parent=None):
        super().__init__(parent)
        self.setWindowTitle("选择导出内容")
        self.setFixedSize(340, 220)
        self.choice = None

        self.setStyleSheet(f"""
        QDialog {{ background: #F9FAFB; font-family: "{FONT_FAMILY}", sans-serif; }}
        """)

        layout = QVBoxLayout(self)
        layout.setSpacing(14)
        layout.setContentsMargins(24, 20, 24, 20)

        title = QLabel("请选择要导出的内容")
        title.setFont(QFont(FONT_FAMILY, 12))
        title.setStyleSheet("color: #111827; font-weight: bold;")
        layout.addWidget(title)

        btn_style_base = """
        QPushButton {
            border-radius: 6px; font-family: "%s"; border: none;
            padding: 8px; text-align: center;
        }
        QPushButton:hover { opacity: 0.9; }
        """ % FONT_FAMILY

        if has_scan and has_speed:
            btn_both = QPushButton("📊 扫描结果 + 测速结果（分别保存）")
            btn_both.setFixedHeight(36)
            btn_both.setFont(FONT_BTN)
            btn_both.setCursor(Qt.PointingHandCursor)
            btn_both.setStyleSheet(btn_style_base + "QPushButton { background: #3B82F6; color: white; }")
            btn_both.clicked.connect(lambda: self._choose("both"))
            layout.addWidget(btn_both)

        if has_scan:
            btn_scan = QPushButton("🔍 仅扫描结果")
            btn_scan.setFixedHeight(36)
            btn_scan.setFont(FONT_BTN)
            btn_scan.setCursor(Qt.PointingHandCursor)
            btn_scan.setStyleSheet(btn_style_base + "QPushButton { background: #22C55E; color: white; }")
            btn_scan.clicked.connect(lambda: self._choose("scan"))
            layout.addWidget(btn_scan)

        if has_speed:
            btn_speed = QPushButton("⚡ 仅测速结果")
            btn_speed.setFixedHeight(36)
            btn_speed.setFont(FONT_BTN)
            btn_speed.setCursor(Qt.PointingHandCursor)
            btn_speed.setStyleSheet(btn_style_base + "QPushButton { background: #F97316; color: white; }")
            btn_speed.clicked.connect(lambda: self._choose("speed"))
            layout.addWidget(btn_speed)

        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedHeight(32)
        cancel_btn.setFont(FONT_BTN)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(btn_style_base + "QPushButton { background: #F3F4F6; color: #6B7280; border: 1px solid #D1D5DB; }")
        cancel_btn.clicked.connect(self.reject)
        layout.addWidget(cancel_btn)

    def _choose(self, choice: str):
        self.choice = choice
        self.accept()


# ===================== SSL / 网络工具 =====================

def create_compat_ssl_context():
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    if IS_WIN7:
        if hasattr(ssl, 'TLSVersion'):
            try:
                ctx.minimum_version = ssl.TLSVersion.TLSv1_2
                ctx.maximum_version = ssl.TLSVersion.TLSv1_2
            except AttributeError:
                pass
        else:
            ctx.options |= ssl.OP_NO_TLSv1_3
            ctx.options |= ssl.OP_NO_TLSv1_1
            ctx.options |= ssl.OP_NO_TLSv1
            ctx.options |= ssl.OP_NO_SSLv2
            ctx.options |= ssl.OP_NO_SSLv3
    return ctx


def get_iata_code_from_ip(ip: str, timeout: int = 3) -> Optional[str]:
    test_host = "speed.cloudflare.com"
    if ':' in ip:
        urls = [f"https://[{ip}]/cdn-cgi/trace", f"http://[{ip}]/cdn-cgi/trace"]
    else:
        urls = [f"https://{ip}/cdn-cgi/trace", f"http://{ip}/cdn-cgi/trace"]

    for url in urls:
        try:
            ctx = create_compat_ssl_context()
            if url.startswith('https://'):
                use_ssl = True
                host = url[8:].split('/')[0].strip('[]') if '[' in url else url[8:].split('/')[0]
            else:
                use_ssl = False
                host = url[7:].split('/')[0].strip('[]') if '[' in url else url[7:].split('/')[0]
            port = 443 if use_ssl else 80

            if ':' in host:
                addrinfo = socket.getaddrinfo(host, port, socket.AF_INET6, socket.SOCK_STREAM)
                family, socktype, proto, canonname, sockaddr = addrinfo[0]
                s = socket.socket(family, socktype, proto)
                s.settimeout(timeout)
                s.connect(sockaddr)
            else:
                s = socket.create_connection((host, port), timeout=timeout)

            if use_ssl:
                s = ctx.wrap_socket(s, server_hostname=test_host)

            request = f"GET /cdn-cgi/trace HTTP/1.1\r\nHost: {test_host}\r\nUser-Agent: Mozilla/5.0\r\nConnection: close\r\n\r\n".encode()
            s.sendall(request)

            data = b""
            body = b""
            while True:
                try:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    data += chunk
                    if b"\r\n\r\n" in data:
                        header_end = data.find(b"\r\n\r\n")
                        body = data[header_end + 4:]
                        break
                except socket.timeout:
                    break
            s.close()

            response_text = body.decode('utf-8', errors='ignore')
            for line in response_text.splitlines():
                if line.startswith('colo='):
                    colo_value = line.split('=', 1)[1].strip()
                    if colo_value and colo_value.upper() != 'UNKNOWN':
                        return colo_value.upper()

            if b'CF-RAY' in data:
                for line in data.decode('utf-8', errors='ignore').split('\r\n'):
                    if line.startswith('CF-RAY:'):
                        cf_ray = line.split(':', 1)[1].strip()
                        if '-' in cf_ray:
                            parts = cf_ray.split('-')
                            for part in parts[-2:]:
                                if len(part) == 3 and part.isalpha():
                                    return part.upper()
        except Exception:
            continue
    return None


async def get_iata_code_async(session: aiohttp.ClientSession, ip: str, timeout: int = 3) -> Optional[str]:
    test_host = "speed.cloudflare.com"
    if ':' in ip:
        urls = [f"https://[{ip}]/cdn-cgi/trace", f"http://[{ip}]/cdn-cgi/trace"]
    else:
        urls = [f"https://{ip}/cdn-cgi/trace", f"http://{ip}/cdn-cgi/trace"]

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Host": test_host
    }
    ssl_ctx = create_compat_ssl_context()

    for url in urls:
        try:
            use_ssl = url.startswith('https://')
            ssl_context = ssl_ctx if use_ssl else None
            async with session.get(
                url, headers=headers, ssl=ssl_context,
                timeout=aiohttp.ClientTimeout(total=timeout),
                allow_redirects=False
            ) as response:
                if response.status == 200:
                    text = await response.text()
                    for line in text.strip().split('\n'):
                        if line.startswith('colo='):
                            colo_value = line.split('=', 1)[1].strip()
                            if colo_value and colo_value.upper() != 'UNKNOWN':
                                return colo_value.upper()
                    if 'CF-RAY' in response.headers:
                        cf_ray = response.headers['CF-RAY']
                        if '-' in cf_ray:
                            parts = cf_ray.split('-')
                            for part in parts[-2:]:
                                if len(part) == 3 and part.isalpha():
                                    return part.upper()
        except Exception:
            continue
    return None


def get_iata_translation(iata_code: str) -> str:
    return AIRPORT_CODES.get(iata_code, iata_code)


async def async_tcp_ping(ip: str, port: int, timeout: float = 1.0) -> Optional[float]:
    start_time = time.monotonic()
    try:
        reader, writer = await asyncio.wait_for(asyncio.open_connection(ip, port), timeout=timeout)
        latency = (time.monotonic() - start_time) * 1000
        writer.close()
        await writer.wait_closed()
        return round(latency, 2)
    except Exception:  # 优化：合并冗余的异常捕获
        return None


async def measure_tcp_latency(ip: str, port: int, ping_times: int = 4, timeout: float = 1.0) -> Optional[float]:
    latencies = []
    for i in range(ping_times):
        latency = await async_tcp_ping(ip, port, timeout)
        if latency is not None:
            latencies.append(latency)
        if i < ping_times - 1:
            await asyncio.sleep(0.05)
    if latencies:
        return min(latencies)
    return None


# ===================== 扫描器 =====================

class BaseScanner:
    def __init__(self, log_callback=None, progress_callback=None, port=443,
                 max_workers=200, timeout=1.0, ping_times=3, latency_threshold=230):
        self.max_workers = max_workers
        self.timeout = timeout
        self.ping_times = ping_times
        self.latency_threshold = latency_threshold
        self.running = True
        self.log_callback = log_callback
        self.progress_callback = progress_callback
        self.port = port

    @property
    def ip_version(self) -> int:
        raise NotImplementedError

    @property
    def ip_label(self) -> str:
        return "IPv4" if self.ip_version == 4 else "IPv6"

    def generate_ips_from_cidrs(self) -> List[str]:
        raise NotImplementedError

    async def test_ip_latency(self, session, ip):
        if not self.running:
            return None
        return await measure_tcp_latency(ip, self.port, self.ping_times, self.timeout)

    async def test_single_ip(self, session, ip):
        if not self.running:
            return None
        latency = await self.test_ip_latency(session, ip)
        if latency is not None and latency < self.latency_threshold:
            iata_code = None
            if self.running:
                try:
                    iata_code = await get_iata_code_async(session, ip, self.timeout)
                except Exception as e:
                    if self.log_callback:
                        self.log_callback(f"获取地区码失败 {ip}: {str(e)}")
            return {
                'ip': ip, 'latency': latency, 'iata_code': iata_code,
                'chinese_name': get_iata_translation(iata_code) if iata_code else "未知地区",
                'success': True, 'ip_version': self.ip_version,
                'scan_time': datetime.now().strftime("%H:%M:%S"),
                'port': self.port, 'ping_times': self.ping_times
            }
        return None

    async def batch_test_ips(self, ip_list: List[str]):
        semaphore = asyncio.Semaphore(self.max_workers)

        async def test_with_semaphore(session, ip):
            async with semaphore:
                return await self.test_single_ip(session, ip)

        connector_kwargs = {
            'limit': self.max_workers, 'force_close': True,
            'enable_cleanup_closed': True, 'limit_per_host': 0
        }
        if self.ip_version == 6:
            connector_kwargs['family'] = socket.AF_INET6

        connector = aiohttp.TCPConnector(**connector_kwargs)
        successful_results = []
        start_time = time.time()

        async with aiohttp.ClientSession(connector=connector) as session:
            tasks = []
            for ip in ip_list:
                if not self.running:
                    break
                tasks.append(asyncio.create_task(test_with_semaphore(session, ip)))

            completed = 0
            total = len(tasks)
            last_update_time = time.time()

            pending = set(tasks)
            while pending:
                if not self.running:
                    # 取消所有未完成任务
                    for task in pending:
                        task.cancel()
                        await asyncio.gather(*pending, return_exceptions=True)
                        break
                done, pending = await asyncio.wait(pending, timeout=0.5, return_when=asyncio.FIRST_COMPLETED)

                for future in done:
                    completed += 1
                    try:
                        result = future.result()
                        if result:
                            successful_results.append(result)
                    except Exception:
                        pass
            


                current_time = time.time()
                if current_time - last_update_time >= 0.5 or completed == total:
                    elapsed = current_time - start_time
                    ips_per_second = completed / elapsed if elapsed > 0 else 0
                    if self.progress_callback:
                        self.progress_callback(completed, total, len(successful_results), ips_per_second)
                    last_update_time = current_time

        return successful_results

    async def run_scan_async(self):
        try:
            if self.log_callback:
                self.log_callback(f"正在从Cloudflare {self.ip_label} IP段生成随机IP... (端口: {self.port})")
                self.log_callback(f"并发数: {self.max_workers} | 延迟阈值: {self.latency_threshold}ms")
            ip_list = self.generate_ips_from_cidrs()
            if not ip_list:
                if self.log_callback:
                    self.log_callback(f"错误: 未能生成{self.ip_label} IP列表")
                return None
            if self.log_callback:
                self.log_callback(f"已生成 {len(ip_list)} 个随机{self.ip_label} IP")
                self.log_callback(f"开始延迟测试...")
            results = await self.batch_test_ips(ip_list)
            if not self.running:
                if self.log_callback:
                    self.log_callback(f"{self.ip_label}扫描被用户中止")
                return None
            if results:
                with_iata = sum(1 for r in results if r.get('iata_code'))
                if self.log_callback:
                    self.log_callback(f"{self.ip_label}扫描完成: 共{len(results)}个IP可用，{with_iata}个获取地区码")
            return results
        except Exception as e:
            if self.log_callback:
                self.log_callback(f"{self.ip_label}扫描过程中出现错误: {str(e)}")
            return None

    def stop(self):
        self.running = False


class IPv4Scanner(BaseScanner):
    @property
    def ip_version(self):
        return 4

    def generate_ips_from_cidrs(self) -> List[str]:
        ip_list = []
        # 改为从动态列表获取 CIDR
        cidrs = load_or_update_ip_cache(4)  # 4 代表 IPv4
        for cidr in cidrs:
            try:
                network = ipaddress.ip_network(cidr, strict=False)
                for subnet in network.subnets(new_prefix=24):
                    hosts = list(subnet.hosts())
                    for ip in random.sample(hosts, min(2, len(hosts))):
                        ip_list.append(str(ip))
            except ValueError as e:
                if self.log_callback:
                    self.log_callback(f"处理CIDR {cidr} 时出错: {e}")
        return ip_list


class IPv6Scanner(BaseScanner):
    @property
    def ip_version(self):
        return 6

    def __init__(self, **kwargs):
        kwargs.setdefault('latency_threshold', 320)
        kwargs.setdefault('ping_times', 2)
        super().__init__(**kwargs)

    def generate_ips_from_cidrs(self) -> List[str]:
        ip_list = []
        # 改为从动态列表获取 CIDR
        cidrs = load_or_update_ip_cache(6)  # 6 代表 IPv6
        for cidr in cidrs:
            try:
                network = ipaddress.ip_network(cidr, strict=False)
                if network.num_addresses > 2:
                    # 根据前缀长度动态决定采样数
                    prefixlen = network.prefixlen
                    if prefixlen <= 32:
                        sample_size = 2800   # 大段多抽
                    elif prefixlen <= 40:
                        sample_size = 500
                    else:
                        sample_size = 200   # /48 等小段保持原样

                    max_hosts = min(sample_size, network.num_addresses - 2)
                    for _ in range(max_hosts):
                        random_ip_int = random.randint(
                            int(network.network_address) + 1,
                            int(network.broadcast_address) - 1
                            )
                        ip_list.append(str(ipaddress.IPv6Address(random_ip_int)))
            except ValueError as e:
                if self.log_callback:
                    self.log_callback(f"处理CIDR {cidr} 时出错: {e}")
        return ip_list
                    


# ===================== 工作线程 =====================

def get_event_loop_policy():
    """提取公共的事件循环策略获取逻辑"""
    if sys.platform == 'win32':
        if IS_WIN7:
            return asyncio.WindowsSelectorEventLoopPolicy()
        else:
            return asyncio.WindowsProactorEventLoopPolicy()
    return asyncio.DefaultEventLoopPolicy()


class ScanWorker(QThread):
    progress_update = Signal(int, int, int, float)
    status_message = Signal(str)
    scan_completed = Signal(list)

    def __init__(self, scanner: BaseScanner):
        super().__init__()
        self.scanner = scanner

    def run(self):
        self.scanner.log_callback = lambda msg: self.status_message.emit(msg)
        self.scanner.progress_callback = lambda c, t, s, sp: self.progress_update.emit(c, t, s, sp)

        asyncio.set_event_loop_policy(get_event_loop_policy())
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            results = loop.run_until_complete(self.scanner.run_scan_async())
            if results is not None:
                self.scan_completed.emit(results)
        finally:
            loop.close()

    def stop(self):
        if self.scanner:
            self.scanner.stop()


class SpeedTestWorker(QThread):
    progress_update = Signal(int, int, float)
    status_message = Signal(str)
    speed_test_completed = Signal(list)

    def __init__(self, results, region_code=None, max_test_count=10, current_port=443):
        super().__init__()
        self.results = results
        self.region_code = region_code.upper() if region_code else None
        self.max_test_count = max_test_count
        self.download_interval = 3
        self.download_time_limit = 3
        self.test_host = "speed.cloudflare.com"
        self.running = True
        self.current_port = current_port

    def download_speed(self, ip, port):
        ctx = create_compat_ssl_context()
        req = (
            "GET /__down?bytes=50000000 HTTP/1.1\r\n"
            f"Host: {self.test_host}\r\n"
            "User-Agent: Mozilla/5.0\r\n"
            "Accept: */*\r\n"
            "Connection: close\r\n\r\n"
        ).encode()
        try:
            if ':' in ip:
                addrinfo = socket.getaddrinfo(ip, port, socket.AF_INET6, socket.SOCK_STREAM)
                family, socktype, proto, canonname, sockaddr = addrinfo[0]
                sock = socket.socket(family, socktype, proto)
                sock.settimeout(3)
                sock.connect(sockaddr)
            else:
                sock = socket.create_connection((ip, port), timeout=3)
            ss = ctx.wrap_socket(sock, server_hostname=self.test_host)
            ss.sendall(req)
            start = time.time()
            
            header_buf = b""  # 优化：分离 header_buf，头部解析完成后不再做无效拼接
            body = 0
            header_done = False
            
            while time.time() - start < self.download_time_limit:
                buf = ss.recv(8192)
                if not buf:
                    break
                if not header_done:
                    header_buf += buf
                    if b"\r\n\r\n" in header_buf:
                        header_done = True
                        body += len(header_buf.split(b"\r\n\r\n", 1)[1])
                else:
                    body += len(buf)
            ss.close()
            dur = time.time() - start
            return round((body / 1024 / 1024) / max(dur, 0.1), 2)
        except Exception as e:
            self.status_message.emit(f"测速失败 {ip}: {str(e)}")
            return 0.0

    def run(self):
        # 优化：移除同步线程中无意义的 asyncio.set_event_loop_policy 设置
        try:
            if not self.results:
                self.status_message.emit("错误：没有可用的IP进行测速")
                self.speed_test_completed.emit([])
                return

            if self.region_code:
                filtered_results = [r for r in self.results if r.get('iata_code') and r['iata_code'].upper() == self.region_code]
                region_name = AIRPORT_CODES.get(self.region_code, '未知地区')
                self.status_message.emit(f"开始地区测速：{self.region_code} ({region_name}) (端口: {self.current_port})")
                self.status_message.emit(f"找到 {len(filtered_results)} 个 {self.region_code} 地区的IP")
            else:
                filtered_results = self.results
                self.status_message.emit(f"开始完全测速 (端口: {self.current_port})")

            if not filtered_results:
                self.status_message.emit("没有找到可用的IP进行测速")
                self.speed_test_completed.emit([])
                return

            filtered_results.sort(key=lambda x: x.get('latency', float('inf')))
            target_ips = filtered_results[:min(self.max_test_count, len(filtered_results))]

            test_type = "地区测速" if self.region_code else "完全测速"
            self.status_message.emit(f"{test_type}：将对 {len(target_ips)} 个IP进行测速")

            speed_results = []
            for i, ip_info in enumerate(target_ips):
                if not self.running:
                    break
                ip = ip_info['ip']
                latency = ip_info.get('latency', 0)
                self.status_message.emit(f"[{i+1}/{len(target_ips)}] 正在测速 {ip}(端口: {self.current_port})")
                self.progress_update.emit(i+1, len(target_ips), 0)
                download_speed = self.download_speed(ip, self.current_port)
                colo = get_iata_code_from_ip(ip, timeout=3)
                if not colo or colo == "Unknown":
                    colo = ip_info.get('iata_code', 'UNKNOWN')
                speed_result = {
                    'ip': ip, 'latency': latency, 'download_speed': download_speed,
                    'iata_code': colo.upper() if colo else 'UNKNOWN',
                    'chinese_name': AIRPORT_CODES.get(colo.upper(), '未知地区') if colo else '未知地区',
                    'test_type': test_type, 'port': self.current_port
                }
                speed_results.append(speed_result)
                self.status_message.emit(f"  测速结果: {download_speed} MB/s, 地区: {speed_result['chinese_name']}")
                if i < len(target_ips) - 1:
                    for _ in range(self.download_interval * 10):
                        if not self.running:
                            break
                        time.sleep(0.1)

            speed_results.sort(key=lambda x: x['download_speed'], reverse=True)
            if speed_results:
                self.status_message.emit(f"测速完成！成功 {len(speed_results)}/{len(target_ips)} 个IP")
            else:
                self.status_message.emit("所有IP测速失败")
            self.speed_test_completed.emit(speed_results)
        except Exception as e:
            self.status_message.emit(f"测速过程中出现错误: {str(e)}")
            self.speed_test_completed.emit([])

    def stop(self):
        self.running = False


# ===================== 主界面 =====================

SCROLLBAR_CSS = f"""
QScrollBar:vertical {{ background: #0F4C75; width: 8px; border-radius: 3px; }}
QScrollBar::handle:vertical {{ background: #1E90FF; min-height: 20px; border-radius: 3px; }}
QScrollBar::handle:vertical:hover {{ background: #00BFFF; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0px; }}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{ background: none; }}
"""

TABLE_STYLE = f"""
QTableWidget {{
    background: #0B3C5D; border-radius: 8px; color: white;
    gridline-color: #1E4D6B;
}}
QHeaderView::section {{
    background: #0F4C75; color: white; border: none; height: 32px;
    padding-left: 10px; font-family: "{FONT_FAMILY}";
}}
QTableWidget::item {{
    padding: 5px; border-bottom: 1px solid #1E4D6B;
    font-family: "{FONT_FAMILY}", sans-serif;
}}
{SCROLLBAR_CSS}
"""

LOG_STYLE = f"""
QTextEdit {{
    background: #0B3C5D; border: 1px solid #0F4C75; border-radius: 6px;
    padding: 10px; color: #ECF0F1; font-family: "{FONT_FAMILY}", sans-serif;
}}
{SCROLLBAR_CSS}
"""


class CloudflareScanUI(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("CloudTrace 云迹 V1.0")
        self.resize(480, 850)
        self.setMinimumSize(460, 650)
		
		# ★ 设置窗口图标
        icon_path = resource_path("favicon.ico")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))

        self.setStyleSheet(f"""
        QWidget {{ font-family: "{FONT_FAMILY}", sans-serif; background: #F9FAFB; }}
        """)

        self.scan_worker = None
        self.speed_test_worker = None
        self.scanning = False
        self.speed_testing = False
        self.scan_results = []
        self.speed_results = []
        self.current_scan_port = 443
        self.current_ip_version = 4

        ensure_save_dir()
        self.init_ui()

    def make_btn(self, text, color, text_color="white", enabled=True, width=BTN_W):
        btn = QPushButton(text)
        btn.setFixedSize(width, BTN_H)
        btn.setFont(FONT_BTN)
        btn.setEnabled(enabled)
        btn.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)
        btn.setStyleSheet(f"""
        QPushButton {{
            background: {color}; color: {text_color}; border-radius: 6px;
            font-family: "{FONT_FAMILY}"; border: none;
        }}
        QPushButton:disabled {{ background: #E5E7EB; color: #9CA3AF; }}
        QPushButton:hover:!disabled {{ background: {color}; border: 1px solid rgba(255,255,255,0.3); }}
        """)
        return btn

    def make_stop_btn(self, text, enabled=True):
        btn = QPushButton(text)
        btn.setFixedSize(BTN_W, BTN_H)
        btn.setFont(FONT_BTN)
        btn.setEnabled(enabled)
        btn.setCursor(Qt.PointingHandCursor if enabled else Qt.ArrowCursor)
        btn.setStyleSheet(f"""
        QPushButton {{
            background: #EF4444; color: white; border-radius: 6px;
            font-family: "{FONT_FAMILY}"; border: none;
        }}
        QPushButton:disabled {{ background: #E5E7EB; color: #9CA3AF; }}
        QPushButton:hover:!disabled {{ background: #DC2626; }}
        """)
        return btn

    def _make_label(self, text):
        label = QLabel(text)
        label.setFont(FONT_SMALL)
        label.setStyleSheet(f'color: #E2E8F0; font-family: "{FONT_FAMILY}";')
        return label

    def init_ui(self):
        main = QVBoxLayout(self)
        main.setContentsMargins(14, 14, 14, 14)
        main.setSpacing(10)
        
        title_frame = QFrame()
        title_frame.setObjectName("titleFrame")
        title_frame.setStyleSheet("""
            #titleFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #1E3A5F, stop:0.5 #1E4976, stop:1 #2563EB);
                border-radius: 12px;
            }
        """)
        
        title_layout = QVBoxLayout(title_frame)
        title_layout.setContentsMargins(20, 14, 20, 14)
        title_layout.setSpacing(2)
        
        title = QLabel('☁ CloudTrace 云迹')
        title.setFont(FONT_TITLE) 
        title.setAlignment(Qt.AlignCenter)
        title.setStyleSheet("color: white; background: transparent; border: none;")
        title_layout.addWidget(title)
        
        subtitle = QLabel('V1.0  ·  Cloudflare IP 优选扫描工具')
        subtitle.setFont(QFont(FONT_FAMILY, 10))  # 优化：提取字体计算
        subtitle.setAlignment(Qt.AlignCenter)
        subtitle.setStyleSheet("color: rgba(255,255,255,180); background: transparent; border: none;")
        title_layout.addWidget(subtitle)
        
        main.addWidget(title_frame)

        control = QVBoxLayout()
        control.setSpacing(SPACING)
        control.setAlignment(Qt.AlignCenter)

        row1 = QHBoxLayout()
        row1.setSpacing(SPACING)
        row1.addStretch()
        
        self.btn_ipv4 = self.make_btn("IPv4 扫描", "#3B82F6")
        self.btn_ipv4.clicked.connect(self.start_ipv4_scan)
        row1.addWidget(self.btn_ipv4)
        
        row1.addSpacing(SPACING)
        
        self.btn_ipv6 = self.make_btn("IPv6 扫描", "#22C55E")
        self.btn_ipv6.clicked.connect(self.start_ipv6_scan)
        row1.addWidget(self.btn_ipv6)
        
        row1.addSpacing(SPACING)
        
        self.btn_stop = self.make_stop_btn("停止任务", enabled=False)
        self.btn_stop.clicked.connect(self.confirm_stop_all_tasks)
        row1.addWidget(self.btn_stop)
        row1.addStretch()
        
        control.addLayout(row1)

        row2 = QHBoxLayout()
        row2.setSpacing(SPACING)
        row2.addStretch()
        
        self.btn_load_ipv4_scan = self.make_btn("加载IPv4扫描结果", "#0EA5E9", width=160)
        self.btn_load_ipv4_scan.clicked.connect(self.load_ipv4_scan_results)
        row2.addWidget(self.btn_load_ipv4_scan)
        
        row2.addSpacing(SPACING)
        
        self.btn_load_ipv6_scan = self.make_btn("加载IPv6扫描结果", "#10B981", width=160)
        self.btn_load_ipv6_scan.clicked.connect(self.load_ipv6_scan_results)
        row2.addWidget(self.btn_load_ipv6_scan)
        row2.addStretch()
        
        control.addLayout(row2)

        row3 = QHBoxLayout()
        row3.setSpacing(SPACING)
        row3.addStretch()
        
        self.btn_area = self.make_btn("地区测速", "#EC4899", enabled=False)
        self.btn_area.clicked.connect(self.start_region_speed_test)
        row3.addWidget(self.btn_area)
        
        row3.addSpacing(SPACING)
        
        self.btn_full = self.make_btn("完全测速", "#F97316", enabled=False)
        self.btn_full.clicked.connect(self.start_full_speed_test)
        row3.addWidget(self.btn_full)
        
        row3.addSpacing(SPACING)
        
        self.btn_export = self.make_btn("导出结果", "#8B5CF6", enabled=False)
        self.btn_export.clicked.connect(self.export_results)
        row3.addWidget(self.btn_export)
        row3.addStretch()
        
        control.addLayout(row3)

        PARAM_BG = "#2153a5"
        PARAM_BORDER = "#1E4D6B"
        INPUT_BG = "#0F2B44"
        INPUT_BORDER = "#1A3D5C"
        TEXT_COLOR = "#F1F5F9"
        LABEL_COLOR = "#FFFFFF"
        FOCUS_COLOR = "#3B82F6"

        param_style = f"""
            QFrame#paramRow {{
                background: {PARAM_BG};
                border: 1px solid {PARAM_BORDER};
                border-radius: 8px;
                padding: 8px 14px;
            }}
            QLabel {{
                color: {LABEL_COLOR};
                font-size: 11px;
                font-family: "{FONT_FAMILY}";
                background: transparent;
                border: none;
                font-weight: 500;
            }}
            QLineEdit, QSpinBox, QComboBox {{
                background: {INPUT_BG};
                color: {TEXT_COLOR};
                border: 1px solid {INPUT_BORDER};
                border-radius: 4px;
                padding: 2px 6px;
                font-family: "{FONT_FAMILY}";
            }}
            QLineEdit:focus, QSpinBox:focus, QComboBox:focus {{
                border: 1px solid {FOCUS_COLOR};
            }}
        """

        param_frame = QFrame()
        param_frame.setObjectName("paramRow")
        param_frame.setStyleSheet(param_style)

        row4_layout = QVBoxLayout(param_frame)
        row4_layout.setContentsMargins(0, 4, 0, 4)
        row4_layout.setSpacing(6)

        row4 = QHBoxLayout()
        row4.setSpacing(20)
        row4.addStretch()

        def _make_group(label_text, widget):
            group_layout = QVBoxLayout()
            group_layout.setSpacing(2)
            group_layout.setContentsMargins(0, 0, 0, 0)
            lbl = QLabel(label_text)
            lbl.setObjectName("paramLabel")
            lbl.setAlignment(Qt.AlignCenter)
            lbl.setFont(FONT_SMALL)
            group_layout.addWidget(lbl)
            group_layout.addWidget(widget)
            return group_layout

        self.input_region = QLineEdit()
        self.input_region.setFixedSize(75, 28)
        self.input_region.setFont(FONT_BTN)
        self.input_region.setPlaceholderText("")
        self.input_region.setAlignment(Qt.AlignCenter)
        self.input_region.textChanged.connect(self.auto_uppercase)
        row4.addLayout(_make_group("地区码", self.input_region))

        self.input_speed_count = QSpinBox()
        self.input_speed_count.setFixedSize(60, 28)
        self.input_speed_count.setFont(FONT_SMALL)
        self.input_speed_count.setRange(1, 50)
        self.input_speed_count.setValue(10)
        self.input_speed_count.setAlignment(Qt.AlignCenter)
        row4.addLayout(_make_group("数量", self.input_speed_count))

        self.combo_port = QComboBox()
        self.combo_port.setFixedSize(75, 28)
        self.combo_port.setFont(FONT_SMALL)
        for port in PORT_OPTIONS:
            self.combo_port.addItem(port)
        self.combo_port.setCurrentText("443")
        row4.addLayout(_make_group("端口", self.combo_port))

        self.input_workers = QSpinBox()
        self.input_workers.setFixedSize(65, 28)
        self.input_workers.setFont(FONT_SMALL)
        self.input_workers.setRange(10, 500)
        self.input_workers.setValue(200)
        self.input_workers.setSingleStep(50)
        self.input_workers.setAlignment(Qt.AlignCenter)
        row4.addLayout(_make_group("并发", self.input_workers))

        self.input_threshold = QSpinBox()
        self.input_threshold.setFixedSize(65, 28)
        self.input_threshold.setFont(FONT_SMALL)
        self.input_threshold.setRange(50, 999)
        self.input_threshold.setValue(230)
        self.input_threshold.setSingleStep(10)
        self.input_threshold.setAlignment(Qt.AlignCenter)
        row4.addLayout(_make_group("阈值ms", self.input_threshold))

        row4.addStretch()
        row4_layout.addLayout(row4)

        control.addWidget(param_frame)
        
        main.addLayout(control)

        self.progress_bar = QProgressBar()
        self.progress_bar.setFixedHeight(8)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
        QProgressBar { background: #E5E7EB; border-radius: 4px; }
        QProgressBar::chunk { background: #22C55E; border-radius: 4px; }
        """)
        main.addWidget(self.progress_bar)

        status_frame = QHBoxLayout()
        self.status_label = QLabel("就绪")
        self.status_label.setStyleSheet(f'color: #6B7280; font-size: 12px; padding: 4px; font-family: "{FONT_FAMILY}";')
        self.speed_label = QLabel("速度: 0 IP/秒")
        self.speed_label.setStyleSheet(f'color: #6B7280; font-size: 12px; padding: 4px; font-family: "{FONT_FAMILY}";')
        status_frame.addWidget(self.status_label)
        status_frame.addStretch()
        status_frame.addWidget(self.speed_label)
        main.addLayout(status_frame)

        log_label = QLabel("扫描状态和统计信息")
        log_label.setFont(FONT_LABEL)
        log_label.setStyleSheet(f'color: #111827; font-size: 14px; font-family: "{FONT_FAMILY}";')
        main.addWidget(log_label)
        self.status_display = QTextEdit()
        self.status_display.setFont(FONT_STATUS)
        self.status_display.setMaximumHeight(180)
        self.status_display.setReadOnly(True)
        self.status_display.setStyleSheet(LOG_STYLE)
        main.addWidget(self.status_display)

        speed_label = QLabel("测速结果")
        speed_label.setFont(FONT_LABEL)
        speed_label.setStyleSheet(f'color: #111827; font-size: 14px; font-family: "{FONT_FAMILY}";')
        main.addWidget(speed_label)
        self.speed_table = QTableWidget()
        self.speed_table.setColumnCount(7)
        self.speed_table.setHorizontalHeaderLabels(["排名", "IP地址", "地区", "延迟", "下载速度", "端口", "测速类型"])
        for i in range(self.speed_table.columnCount() - 1):
            self.speed_table.horizontalHeader().setSectionResizeMode(i, QHeaderView.ResizeToContents)
        self.speed_table.horizontalHeader().setSectionResizeMode(self.speed_table.columnCount() - 1, QHeaderView.Stretch)
        self.speed_table.verticalHeader().setVisible(False)
        self.speed_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.speed_table.doubleClicked.connect(self.copy_table_cell)
        self.speed_table.setStyleSheet(TABLE_STYLE)
        main.addWidget(self.speed_table, 1)

    def auto_uppercase(self, text):
        if text != text.upper():
            self.input_region.setText(text.upper())

    def _format_region_stats(self, results: List[Dict]) -> List[str]:
        region_stats = {}
        for r in results:
            code = r.get('iata_code')
            if code and code.upper() != 'UNKNOWN':
                code = code.upper()
                name = r.get('chinese_name', code)
                key = (code, name)
                region_stats[key] = region_stats.get(key, 0) + 1

        lines = []
        for (code, name), cnt in sorted(region_stats.items(), key=lambda x: x[1], reverse=True):
            lines.append(f"  {code}  {name}: {cnt}")
        return lines

    def update_ui_state(self, busy=False):
        self.btn_ipv4.setEnabled(not busy)
        self.btn_ipv6.setEnabled(not busy)
        self.btn_load_ipv4_scan.setEnabled(not busy)
        self.btn_load_ipv6_scan.setEnabled(not busy)
        self.btn_stop.setEnabled(busy)

        has_results = bool(self.scan_results)
        self.btn_area.setEnabled(not busy and has_results)
        self.btn_full.setEnabled(not busy and has_results)
        self.btn_export.setEnabled(not busy and (has_results or bool(self.speed_results)))

    def load_ipv4_scan_results(self):
        if self.scanning or self.speed_testing:
            CustomMessageBox.warning(self, "提示", "请先停止当前任务")
            return
        self._load_scan_results(4)

    def load_ipv6_scan_results(self):
        if self.scanning or self.speed_testing:
            CustomMessageBox.warning(self, "提示", "请先停止当前任务")
            return
        self._load_scan_results(6)

    def _load_scan_results(self, ip_version: int):
        ip_label = "IPv4" if ip_version == 4 else "IPv6"
        history = get_history_list(ip_version, "scan")
        if not history:
            CustomMessageBox.information(
                self, "提示",
                f"未找到{ip_label}扫描结果\n请先执行一次{ip_label}扫描"
            )
            return

        if len(history) == 1:
            self._do_load_scan(history[0]['filepath'], ip_label, ip_version)
            return

        dialog = HistorySelectDialog(ip_label, "扫描", history, self)
        if dialog.exec() == QDialog.Accepted and dialog.selected_filepath:
            self._do_load_scan(dialog.selected_filepath, ip_label, ip_version)

    def _do_load_scan(self, filepath: str, ip_label: str, ip_version: int):
        data = load_results_from_file(filepath)
        if data is None or not data.get('results'):
            CustomMessageBox.warning(self, "错误", "加载失败：文件损坏或结果为空")
            return

        results = data['results']
        save_time = data.get('save_time', '未知')

        self.scan_results = results
        self.current_ip_version = ip_version

        port_from_result = results[0].get('port', 443) if results else 443
        self.current_scan_port = port_from_result
        self.combo_port.setCurrentText(str(port_from_result))

        self.status_display.clear()
        self.status_display.append(f"✅ 已加载{ip_label}扫描结果")
        self.status_display.append(f"  保存时间: {save_time}")
        self.status_display.append(f"  结果数量: {len(results)} 个IP")

        region_lines = self._format_region_stats(results)
        if region_lines:
            self.status_display.append("  地区分布:")
            for line in region_lines[:15]:
                self.status_display.append(line)

        latencies = [r.get('latency', 0) for r in results if r.get('latency')]
        if latencies:
            self.status_display.append(f"  延迟: {min(latencies):.1f}ms ~ {max(latencies):.1f}ms (平均 {sum(latencies)/len(latencies):.1f}ms)")

        self.status_display.append("=" * 30)
        self.status_display.append("输入地区码 → 点击「地区测速」")

        self.status_label.setText(f"已加载{ip_label}结果 ({len(results)}个)")
        self.speed_label.setText(f"保存时间: {save_time}")
        self.update_ui_state(busy=False)

    def start_ipv4_scan(self):
        if self.scanning or self.speed_testing:
            return
        self.current_ip_version = 4
        port = int(self.combo_port.currentText())
        threshold = self.input_threshold.value()
        workers = self.input_workers.value()
        self.current_scan_port = port

        scanner = IPv4Scanner(
            port=port,
            max_workers=workers,
            latency_threshold=threshold,
        )
        self._start_scan(scanner, "IPv4")

    def start_ipv6_scan(self):
        if self.scanning or self.speed_testing:
            return
        self.current_ip_version = 6
        port = int(self.combo_port.currentText())
        threshold = self.input_threshold.value()
        workers = self.input_workers.value()
        self.current_scan_port = port

        scanner = IPv6Scanner(
            port=port,
            max_workers=workers,
            latency_threshold=threshold,
        )
        self._start_scan(scanner, "IPv6")

    def _start_scan(self, scanner: BaseScanner, label: str):
        self.scanning = True
        self.update_ui_state(busy=True)
        self.scan_results = []
        self.speed_results = []
        self.speed_table.setRowCount(0)

        self.status_display.clear()
        self.status_display.append(f"正在开始{label}扫描...")
        self.status_display.append("=" * 25)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"{label}扫描中...")
        self.speed_label.setText("速度: 0 IP/秒")

        self.scan_worker = ScanWorker(scanner)
        self.scan_worker.progress_update.connect(self.update_progress)
        self.scan_worker.status_message.connect(self.status_message)
        self.scan_worker.scan_completed.connect(self.scan_finished)
        self.scan_worker.finished.connect(lambda: setattr(self, 'scan_worker', None))
        self.scan_worker.start()

    def scan_finished(self, results):
        self.scan_results = results

        if results:
            saved = save_results_to_file(results, self.current_ip_version, "scan")
            ip_label = "IPv4" if self.current_ip_version == 4 else "IPv6"
            if saved:
                self.status_display.append(f"✅ {ip_label}扫描结果已自动保存")

            region_lines = self._format_region_stats(results)
            if region_lines:
                self.status_display.append("地区分布:")
                for line in region_lines[:15]:
                    self.status_display.append(line)

            self.status_display.append(f"扫描完成: {len(results)} 个可用IP")
        else:
            self.status_display.append("扫描完成: 未找到可用IP")

        self.scanning = False
        self.progress_bar.setValue(100)
        self.status_label.setText(f"扫描完成 ({len(results)}个IP)" if results else "扫描完成")
        self.update_ui_state(busy=False)

    def update_progress(self, completed, total, success, speed):
        if total > 0:
            self.progress_bar.setValue(int(completed / total * 100))
        self.status_label.setText(f"进度: {completed}/{total}")
        self.speed_label.setText(f"速度: {speed:.0f} IP/s | 成功: {success}")

    def status_message(self, msg):
        self.status_display.append(msg)
        sb = self.status_display.verticalScrollBar()
        sb.setValue(sb.maximum())

    def start_region_speed_test(self):
        if self.speed_testing:
            return
        if not self.scan_results:
            CustomMessageBox.warning(self, "提示", "请先扫描或加载扫描结果")
            return
        region_code = self.input_region.text().strip().upper()
        if not region_code:
            CustomMessageBox.warning(self, "提示", "请输入地区码（如 HKG, NRT, SIN）")
            return
        matched = [r for r in self.scan_results if r.get('iata_code') and r['iata_code'].upper() == region_code]
        if not matched:
            available = sorted(set(r.get('iata_code', '').upper() for r in self.scan_results if r.get('iata_code')))
            CustomMessageBox.warning(
                self, "提示",
                f"未找到地区码 {region_code} 的IP\n可用地区码: {', '.join(available[:30])}"
            )
            return
        self._start_speed_test(region_code)

    def start_full_speed_test(self):
        if self.speed_testing:
            return
        if not self.scan_results:
            CustomMessageBox.warning(self, "提示", "请先扫描或加载扫描结果")
            return
        self._start_speed_test(region_code=None)

    def _start_speed_test(self, region_code=None):
        self.speed_testing = True
        self.update_ui_state(busy=True)
        self.speed_results = []
        self.speed_table.setRowCount(0)

        max_count = self.input_speed_count.value()
        port = int(self.combo_port.currentText())
        self.current_scan_port = port

        self.speed_test_worker = SpeedTestWorker(
            self.scan_results, region_code, max_count, port
        )
        self.speed_test_worker.progress_update.connect(self.update_speed_progress)
        self.speed_test_worker.status_message.connect(self.status_message)
        self.speed_test_worker.speed_test_completed.connect(self.speed_test_finished)
        self.speed_test_worker.finished.connect(lambda: setattr(self, 'speed_test_worker', None))
        self.speed_test_worker.start()

    def update_speed_progress(self, current, total, speed):
        if total > 0:
            self.progress_bar.setValue(int(current / total * 100))
        self.status_label.setText(f"测速进度: {current}/{total}")

    def speed_test_finished(self, results):
        self.speed_results = results
        self.speed_testing = False
        self.progress_bar.setValue(100)
        self.update_ui_state(busy=False)

        if results:
            save_results_to_file(results, self.current_ip_version, "speed")
            self._populate_speed_table(results)
            self.status_label.setText(f"测速完成 ({len(results)}个IP)")
        else:
            self.status_label.setText("测速完成: 无结果")

    def _populate_speed_table(self, results):
        self.speed_table.setRowCount(len(results))
        for i, r in enumerate(results):
            rank_item = QTableWidgetItem(str(i + 1))
            rank_item.setTextAlignment(Qt.AlignCenter)
            if i == 0:
                rank_item.setForeground(QColor("#FFD700"))
            elif i == 1:
                rank_item.setForeground(QColor("#C0C0C0"))
            elif i == 2:
                rank_item.setForeground(QColor("#CD7F32"))
            self.speed_table.setItem(i, 0, rank_item)

            self.speed_table.setItem(i, 1, QTableWidgetItem(r.get('ip', '')))

            code = r.get('iata_code', '')
            name = r.get('chinese_name', code)
            self.speed_table.setItem(i, 2, QTableWidgetItem(f"{name}({code})"))

            latency = r.get('latency', 0)
            latency_item = QTableWidgetItem(f"{latency:.1f}ms")
            latency_item.setTextAlignment(Qt.AlignCenter)
            if latency < 100:
                latency_item.setForeground(QColor("#22C55E"))
            elif latency < 200:
                latency_item.setForeground(QColor("#F97316"))
            else:
                latency_item.setForeground(QColor("#EF4444"))
            self.speed_table.setItem(i, 3, latency_item)

            speed = r.get('download_speed', 0)
            speed_item = QTableWidgetItem(f"{speed:.2f} MB/s")
            speed_item.setTextAlignment(Qt.AlignCenter)
            if speed >= 10:
                speed_item.setForeground(QColor("#22C55E"))
            elif speed >= 5:
                speed_item.setForeground(QColor("#F97316"))
            else:
                speed_item.setForeground(QColor("#EF4444"))
            self.speed_table.setItem(i, 4, speed_item)

            port_item = QTableWidgetItem(str(r.get('port', '')))
            port_item.setTextAlignment(Qt.AlignCenter)
            self.speed_table.setItem(i, 5, port_item)

            self.speed_table.setItem(i, 6, QTableWidgetItem(r.get('test_type', '')))

    def confirm_stop_all_tasks(self):
        if not self.scanning and not self.speed_testing:
            return
        
        dialog = QDialog(self)
        dialog.setWindowTitle("确认停止")
        dialog.setFixedSize(400, 200)
        dialog.setModal(True)
        dialog.setStyleSheet(f"""
            QDialog {{
                background: #F9FAFB;
                border-radius: 12px;
                font-family: "{FONT_FAMILY}";
            }}
        """)
        
        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        header_frame = QFrame()
        header_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
                stop:0 #1E3A5F, stop:1 #2563EB);
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
            }
        """)
        header_layout = QVBoxLayout(header_frame)
        header_layout.setContentsMargins(20, 16, 20, 16)
        header_layout.setSpacing(4)
        
        header_title = QLabel("⚠️ 确认停止任务")
        header_title.setFont(QFont(FONT_FAMILY, 12))  # 优化：提取字体计算
        header_title.setStyleSheet("color: white; font-weight: bold; background: transparent; border: none;")
        header_layout.addWidget(header_title)
        
        header_subtitle = QLabel("正在运行的任务将被中断")
        header_subtitle.setFont(FONT_SMALL)
        header_subtitle.setStyleSheet("color: rgba(255,255,255,180); background: transparent; border: none;")
        header_layout.addWidget(header_subtitle)
        
        layout.addWidget(header_frame)
        
        content_frame = QFrame()
        content_frame.setStyleSheet("QFrame { background: #F9FAFB; border: none; }")
        content_layout = QVBoxLayout(content_frame)
        content_layout.setContentsMargins(24, 20, 24, 20)
        content_layout.setSpacing(16)
        
        msg_label = QLabel("确定要停止当前正在运行的任务吗？\n未完成的进度将会丢失。")
        msg_label.setFont(QFont(FONT_FAMILY, 10))  # 优化：提取字体计算
        msg_label.setStyleSheet("color: #374151; background: transparent; border: none;")
        msg_label.setAlignment(Qt.AlignCenter)
        content_layout.addWidget(msg_label)
        
        layout.addWidget(content_frame)
        
        btn_frame = QFrame()
        btn_frame.setStyleSheet("QFrame { background: #F9FAFB; border: none; }")
        btn_layout = QHBoxLayout(btn_frame)
        btn_layout.setContentsMargins(24, 0, 24, 24)
        btn_layout.setSpacing(12)
        btn_layout.addStretch()
        
        cancel_btn = QPushButton("取消")
        cancel_btn.setFixedSize(100, 36)
        cancel_btn.setFont(FONT_BTN)
        cancel_btn.setCursor(Qt.PointingHandCursor)
        cancel_btn.setStyleSheet(f"""
            QPushButton {{
                background: #E5E7EB;
                color: #374151;
                border-radius: 8px;
                font-family: "{FONT_FAMILY}";
                border: none;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: #D1D5DB;
            }}
            QPushButton:pressed {{
                background: #9CA3AF;
            }}
        """)
        cancel_btn.clicked.connect(dialog.reject)
        
        confirm_btn = QPushButton("停止任务")
        confirm_btn.setFixedSize(100, 36)
        confirm_btn.setFont(FONT_BTN)
        confirm_btn.setCursor(Qt.PointingHandCursor)
        confirm_btn.setStyleSheet(f"""
            QPushButton {{
                background: #EF4444;
                color: white;
                border-radius: 8px;
                font-family: "{FONT_FAMILY}";
                border: none;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background: #DC2626;
            }}
            QPushButton:pressed {{
                background: #B91C1C;
            }}
        """)
        confirm_btn.clicked.connect(dialog.accept)
        
        btn_layout.addWidget(cancel_btn)
        btn_layout.addWidget(confirm_btn)
        layout.addWidget(btn_frame)
        
        result = dialog.exec()
        
        if result == QDialog.Accepted:
            self.stop_all_tasks()

    def stop_all_tasks(self):
        if self.scan_worker:
            self.scan_worker.stop()
        if self.speed_test_worker:
            self.speed_test_worker.stop()
        self.scanning = False
        self.speed_testing = False
        self.status_display.append("⚠️ 所有任务已停止")
        self.status_label.setText("已停止")
        self.update_ui_state(busy=False)

    def copy_table_cell(self, index):
        item = self.speed_table.item(index.row(), index.column())
        if item:
            QApplication.clipboard().setText(item.text())
            self.status_display.append(f"已复制: {item.text()}")

    def export_results(self):
        has_scan = bool(self.scan_results)
        has_speed = bool(self.speed_results)
        if not has_scan and not has_speed:
            CustomMessageBox.warning(self, "提示", "没有可导出的结果")
            return
        dialog = ExportSelectDialog(has_scan, has_speed, self)
        if dialog.exec() != QDialog.Accepted or not dialog.choice:
            return
        choice = dialog.choice
        timestamp_str = datetime.now().strftime('%Y%m%d_%H%M%S')
        saved_files = []
        try:
            if choice in ("scan", "both") and has_scan:
                scan_path, _ = QFileDialog.getSaveFileName(
                    self, "保存扫描结果",
                    f"cf_scan_{timestamp_str}.csv",
                    "CSV文件 (*.csv);;JSON文件;;所有文件 (*)"
                )
                if scan_path:
                    self._write_export_file(scan_path, "scan", self.scan_results)
                    saved_files.append(scan_path)
            if choice in ("speed", "both") and has_speed:
                speed_path, _ = QFileDialog.getSaveFileName(
                    self, "保存测速结果",
                    f"cf_speed_{timestamp_str}.csv",
                    "CSV文件;;JSON文件;;所有文件 (*)"
                )
                if speed_path:
                    self._write_export_file(speed_path, "speed", self.speed_results)
                    saved_files.append(speed_path)
            if saved_files:
                msg = "已导出:\n" + "\n".join(saved_files)
                self.status_display.append(f"✅ {msg}")
                CustomMessageBox.information(self, "导出成功", msg)
        except Exception as e:
            CustomMessageBox.critical(self, "错误", f"导出失败: {str(e)}")

    def _write_export_file(self, filepath: str, result_type: str, results: List[Dict]):
        if filepath.endswith('.json'):
            export_data = {
                'export_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                'result_type': result_type,
                'count': len(results),
                'results': results,
            }
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, ensure_ascii=False, indent=2)
        else:
            with open(filepath, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                if result_type == "speed":
                    writer.writerow(["排名", "IP地址", "地区码", "地区", "延迟", "下载速度", "端口", "测速类型"])
                    for i, r in enumerate(results):
                        writer.writerow([
                            i + 1, r.get('ip', ''), r.get('iata_code', ''),
                            r.get('chinese_name', ''), r.get('latency', 0),
                            r.get('download_speed', 0), r.get('port', ''),
                            r.get('test_type', '')
                        ])
                else:
                    writer.writerow(["IP地址", "地区码", "地区", "延迟", "IP版本", "端口", "扫描时间"])
                    for r in results:
                        writer.writerow([
                            r.get('ip', ''), r.get('iata_code', ''),
                            r.get('chinese_name', ''), r.get('latency', 0),
                            r.get('ip_version', ''), r.get('port', ''),
                            r.get('scan_time', '')
                        ])


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = CloudflareScanUI()
    window.show()
    sys.exit(app.exec())
