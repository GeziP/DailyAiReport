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

数据流水线架构：

```
并行执行:
  ├── Newsletter 邮件获取 → 内容解析 → AI 总结（各 Newsletter）→ 按主题整合
  └── Builders Digest（推文 + 播客）→ AI 总结
        ↓
智能推荐新来源 → 加入追踪列表
        ↓
构建统一日报 → 多平台文章生成（小红书、微信公众号）→ 封面图生成 → 邮件推送
```

```
src/
├── __init__.py              # 包初始化
├── config.py                # 配置管理，从环境变量读取邮箱、AI API、图片 API 配置
├── email_client.py          # IMAP 邮件客户端，支持任意邮箱
├── email_sender.py          # SMTP 邮件推送
├── newsletter_parser.py     # HTML 解析，提取正文和链接
├── ai_summarizer.py         # AI 总结（深入展开，关键字加粗，OpenAI 兼容接口）
├── article_generator.py     # 多平台文章生成（小红书、微信公众号）
├── image_generator.py       # 封面图生成（DALL-E 等，可选）
├── builders_digest.py       # AI Builders 动态（调用 follow-builders 获取推文和播客）
├── recommender.py           # 智能推荐新来源，自动加入 watchlist
└── main.py                  # 主程序入口，并行获取数据 → 整合 → 生成 → 推送
```

## 配置

### 环境变量

**邮箱配置（支持任意 IMAP 邮箱）：**
- `IMAP_SERVER` - IMAP 服务器地址（如 `imap.qq.com`, `imap.gmail.com`）
- `IMAP_PORT` - IMAP 端口（默认 993）
- `IMAP_USER` - 邮箱地址
- `IMAP_PASSWORD` - 密码或授权码

**SMTP 配置（邮件推送，通常与 IMAP 同服务器）：**
- `SMTP_SERVER` - SMTP 服务器地址（可选，默认与 IMAP 同）
- `SMTP_PORT` - SMTP 端口（可选，默认 465）
- `EMAIL_RECIPIENTS` - 收件人列表，逗号分隔

**AI API 配置（支持 OpenAI 兼容接口）：**
- `AI_API_KEY` - API 密钥
- `AI_BASE_URL` - API 端点（如 `https://api.openai.com/v1`）
- `AI_MODEL` - 模型名称（如 `gpt-4o-mini`, `qwen-plus`）

**图片生成配置（可选）：**
- `IMAGE_API_KEY` - 图片 API 密钥（不配置则使用 AI_API_KEY）
- `IMAGE_BASE_URL` - 图片 API 端点（不配置则使用 AI_BASE_URL）
- `IMAGE_MODEL` - 图片模型（默认 `dall-e-3`）

**向后兼容：** 旧变量名 `QQ_EMAIL`, `QQ_EMAIL_AUTH_CODE`, `ANTHROPIC_API_KEY` 等仍然支持。

### 其他配置
- Newsletter 源：`config/newsletters.yaml`，YAML 格式，支持 enabled 开关
- Builders 源：`config/follow-builders-sources.json`，自定义追踪的 X 账号和播客
- 推荐追踪列表：`config/watchlist.yaml`，推荐来源自动写入
- 输出模板：`templates/summary.md.j2`、`templates/unified_report.md.j2`（Jinja2）
- 输出目录：`output/YYYY-MM-DD.md`

## GitHub Actions

定时任务：`.github/workflows/daily-summary.yml`
- UTC 08:00 = 北京时间下午 16:00
- 上游 follow-builders feed 在 UTC 06:00 生成，日报在 2 小时后触发
- 需要配置 Secrets: `IMAP_USER`, `IMAP_PASSWORD`, `AI_API_KEY` 等
- 支持手动触发：`workflow_dispatch`

## 时间窗口

- Newsletter 邮件：获取触发时刻往前 24 小时的邮件，IMAP 搜索额外往前推 1 天作为安全边界
- Builders 推文/播客：消费上游 follow-builders 的 feed 快照（UTC 06:00 生成，lookback 24h）
- 日报日期和生成时间统一使用北京时间（UTC+8）

## 扩展 Newsletter

编辑 `config/newsletters.yaml`：
```yaml
newsletters:
  - name: "Newsletter 名称"
    sender: "发件人邮箱"
    enabled: true
```
