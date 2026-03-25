# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# 安装依赖
pip install -r requirements.txt

# 本地运行（需要先配置 .env）
python -m src.main

# 创建 .env 配置
cp .env.example .env
```

## Architecture

数据流水线架构：邮件获取 → 内容解析 → AI 总结 → Markdown 输出

```
src/
├── config.py           # 配置管理，从环境变量读取邮箱和 AI API 配置
├── email_client.py     # IMAP 邮件客户端，支持任意邮箱
├── newsletter_parser.py# HTML 解析，提取正文和链接
├── ai_summarizer.py    # AI API 封装（OpenAI 兼容接口）
└── main.py             # 主程序入口，串联所有模块
```

## 配置

### 环境变量

**邮箱配置（支持任意 IMAP 邮箱）：**
- `IMAP_SERVER` - IMAP 服务器地址（如 `imap.qq.com`, `imap.gmail.com`）
- `IMAP_PORT` - IMAP 端口（默认 993）
- `IMAP_USER` - 邮箱地址
- `IMAP_PASSWORD` - 密码或授权码

**AI API 配置（支持 OpenAI 兼容接口）：**
- `AI_API_KEY` - API 密钥
- `AI_BASE_URL` - API 端点（如 `https://api.openai.com/v1`）
- `AI_MODEL` - 模型名称（如 `gpt-4o-mini`, `qwen-plus`）

**向后兼容：** 旧变量名 `QQ_EMAIL`, `QQ_EMAIL_AUTH_CODE`, `ANTHROPIC_API_KEY` 等仍然支持。

### 其他配置
- Newsletter 源：`config/newsletters.yaml`，YAML 格式，支持 enabled 开关
- 输出模板：`templates/summary.md.j2`（Jinja2）
- 输出目录：`output/YYYY-MM-DD.md`

## GitHub Actions

定时任务：`.github/workflows/daily-summary.yml`
- UTC 23:00 = 北京时间早 7:00
- 需要配置 Secrets: `IMAP_USER`, `IMAP_PASSWORD`, `AI_API_KEY` 等
- 支持手动触发：`workflow_dispatch`

## 扩展 Newsletter

编辑 `config/newsletters.yaml`：
```yaml
newsletters:
  - name: "Newsletter 名称"
    sender: "发件人邮箱"
    enabled: true
```