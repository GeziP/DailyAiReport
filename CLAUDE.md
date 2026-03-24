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
├── config.py           # 配置管理，从环境变量读取 QQ_EMAIL, QQ_EMAIL_AUTH_CODE, ZHIPU_API_KEY
├── email_client.py     # IMAP 邮件客户端，连接 QQ 邮箱获取邮件
├── newsletter_parser.py# HTML 解析，提取正文和链接
├── ai_summarizer.py    # 智谱 GLM-4 API 封装
└── main.py             # 主程序入口，串联所有模块
```

关键配置：
- Newsletter 源：`config/newsletters.yaml`，YAML 格式，支持 enabled 开关
- 输出模板：`templates/summary.md.j2`（Jinja2）
- 输出目录：`output/YYYY-MM-DD.md`

## GitHub Actions

定时任务：`.github/workflows/daily-summary.yml`
- UTC 23:00 = 北京时间早 7:00
- 需要配置 Secrets: `QQ_EMAIL`, `QQ_EMAIL_AUTH_CODE`, `ZHIPU_API_KEY`
- 支持手动触发：`workflow_dispatch`

## 扩展 Newsletter

编辑 `config/newsletters.yaml`：
```yaml
newsletters:
  - name: "Newsletter 名称"
    sender: "发件人邮箱"
    enabled: true
```