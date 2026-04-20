# ☁️ CloudTrace 云迹

[![Python 3.6+](https://img.shields.io/badge/Python-3.6%2B-blue.svg)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**CloudTrace 云迹** 是一款带有现代化图形界面的 Cloudflare IP 扫描与测速工具。  

它融合了 [XIU2/CloudflareSpeedTest](https://github.com/XIU2/CloudflareSpeedTest) 的高效测速逻辑与 [xiaolin-007/CloudFlareScan](https://github.com/xiaolin-007/CloudFlareScan) 的美观 UI 设计理念，并在此基础上实现了**全异步高并发扫描**、**完善的 Win7 兼容性**以及**内置的历史记录管理**。

---

## ✨ 功能特性

- 🖥️ **现代化图形界面**：深色主题设计，交互逻辑清晰，告别枯燥的命令行。
- 🚀 **全异步高并发**：基于 `asyncio` + `aiohttp`，扫描阶段可同时测试数百个 IP，极速筛选。
- 🌍 **IPv4 / IPv6 双栈支持**：全面支持 Cloudflare 官方 IPv4 与 IPv6 CIDR 段的随机扫描。
- 📍 **IATA 机场代码识别**：自动获取 IP 的 Cloudflare 节点机场代码，并翻译为中文地名（如 HKG -> 香港）。
- ⚡ **一键测速**：内置下载测速功能，支持按地区码测速与全局测速。
- 💾 **历史记录管理**：自动保存扫描与测速结果，自动清理超量文件，支持随时加载历史记录。
- 🛡️ **Win7 完美兼容**：底层针对 Windows 7 的 TLS 1.2 强制校验和事件循环策略进行了深度修复。
- 📤 **灵活导出**：支持将结果导出为 CSV 或 JSON 格式。

---

## 📸 程序截图

![主界面截图]()
![测速结果截图]()

---

## 🛠️ 安装与运行

### 环境要求
- Python 3.6 及以上版本
- Windows 7 / 10 / 11 或其他主流操作系统

### 安装步骤

1. 克隆本项目：
   ```bash
   git clone https://github.com/zrf-code/CloudTrace.git
   cd CloudTrace
   ```

2. 安装依赖：
   ```bash
   pip install -r requirements.txt
   ```

3. 运行程序：
   ```bash
   python CloudTrace.py
   ```

---

## 📖 使用说明

1. **开始扫描**：选择点击「IPv4 扫描」或「IPv6 扫描」，程序将从 Cloudflare 官方 IP 段中随机抽取 IP 进行延迟测试。
2. **加载历史**：若之前有扫描记录，可点击「加载 IPv4/v6 扫描结果」直接导入，无需重新扫描。
3. **地区测速**：在「地区码」输入框填写 3 位 IATA 代码（如 `HKG`、`NRT`、`LAX`），点击「地区测速」仅对该地区的 IP 进行下载测速。
4. **完全测速**：不填地区码，直接点击「完全测速」，将对延迟最低的前 N 个 IP 进行测速。
5. **导出结果**：测速完成后，点击「导出结果」可保存为 CSV 或 JSON 文件。

### 参数说明

| 参数 | 说明 |
| :--- | :--- |
| **地区码** | Cloudflare 节点代码，如 HKG(香港)、NRT(东京)、LAX(洛杉矶) |
| **数量** | 参与下载测速的 IP 数量（从延迟最低的 IP 中选取） |
| **端口** | 测速目标端口，可选 443, 2053, 2083, 2087, 2096, 8443 |
| **并发** | 扫描阶段的最大并发连接数，默认 200 |
| **阈值** | 延迟过滤阈值，超过此数值的 IP 将被丢弃，默认 230 |

---

## ⚙️ Win7 兼容说明

在 Windows 7 环境下运行 PySide6 与异步网络程序通常会遇到 SSL 握手失败或事件循环崩溃的问题。本项目已在底层进行了适配：
- 强制使用 `WindowsSelectorEventLoopPolicy` 替代默认的 Proactor 策略。
- 针对 Win7 的 SSL 上下文进行了修补，强制使用 TLS 1.2 协议。
- 关闭了 Qt 的高 DPI 缩放，避免在 Win7 上出现界面渲染错乱。

---

## 📂 目录结构

```text
CloudTrace/
├── CloudTrace.py             # 主程序代码
├── requirements.txt          # 依赖列表
├── README.md                 # 说明文档
└── CloudTrace_history/       # 结果自动保存目录（运行后自动生成）
    ├── ipv4_scan_latest.json # 最新的 IPv4 扫描结果
	├── ipv6_scan_latest.json # 最新的 IPv6 扫描结果
    └── ...                   # 带时间戳的历史备份文件
```

---

## 🙏 致谢

本项目在开发过程中参考了以下优秀开源项目，特此感谢：

- **[XIU2/CloudflareSpeedTest](https://github.com/XIU2/CloudflareSpeedTest)**：提供了优秀的 Cloudflare IP 测速逻辑与思路。
- **[xiaolin-007/CloudFlareScan](https://github.com/xiaolin-007/CloudFlareScan)**：提供了现代化的 GUI 界面设计灵感。

---

## 📜 开源许可

本项目基于 [MIT License](LICENSE) 开源，欢迎 Star、Fork 和 PR。
