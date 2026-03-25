# AI Newsletter 每日总结

自动从邮箱获取订阅的 AI Newsletter 邮件，使用 AI 进行智能总结，生成 Markdown 格式的每日摘要，并自动适配小红书和微信公众号的文章风格，支持 AI 生成封面配图。

## 功能特点

- 📧 支持任意 IMAP 邮箱（QQ、Gmail、Outlook 等）
- 🤖 支持任意 OpenAI 兼容 API（OpenAI、阿里云通义千问、智谱 GLM、DeepSeek 等）
- 📝 自动生成多平台适配文章（原始总结 + 小红书 + 微信公众号）
- 🖼️ 支持 AI 生成封面配图（小红书 + 微信公众号）
- 📅 按日期存放 Markdown 输出文件
- ⏰ GitHub Actions 定时自动运行（北京时间早上 7:00）
- ⚙️ YAML 配置文件，方便添加新的 Newsletter 源

## 输出文件

每天最多生成 5 个文件：

| 文件 | 说明 |
|------|------|
| `YYYY-MM-DD.md` | 原始 Newsletter 总结 |
| `YYYY-MM-DD-xiaohongshu.md` | 小红书风格文章（emoji 丰富、互动引导） |
| `YYYY-MM-DD-xiaohongshu-cover.png` | 小红书封面图（需配置图片 API） |
| `YYYY-MM-DD-wechat.md` | 微信公众号风格文章（专业排版、结构完整） |
| `YYYY-MM-DD-wechat-cover.png` | 微信公众号封面图（需配置图片 API） |

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/your-username/DailyAiPodcast.git
cd DailyAiPodcast
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置环境变量

复制 `.env.example` 为 `.env`，填入你的配置：

```bash
cp .env.example .env
```

编辑 `.env` 文件：

```env
# 邮箱配置（支持任意 IMAP 邮箱）
IMAP_SERVER=imap.qq.com
IMAP_PORT=993
IMAP_USER=your_email@example.com
IMAP_PASSWORD=your_password_or_auth_code

# AI API 配置（支持 OpenAI 兼容接口）
AI_API_KEY=your_api_key
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini

# 图片生成配置（可选，用于生成封面图）
IMAGE_API_KEY=your_image_api_key
IMAGE_BASE_URL=https://api.openai.com/v1
IMAGE_MODEL=dall-e-3
```

#### 常用邮箱 IMAP 配置

| 邮箱 | IMAP 服务器 | 端口 |
|------|-------------|------|
| QQ 邮箱 | `imap.qq.com` | 993 |
| Gmail | `imap.gmail.com` | 993 |
| Outlook | `outlook.office365.com` | 993 |
| 163 邮箱 | `imap.163.com` | 993 |

> **注意**：QQ 邮箱、163 邮箱需要使用授权码而非密码登录。

#### 常用 AI API 配置

| 平台 | Base URL | 模型示例 |
|------|----------|----------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini`, `gpt-4o` |
| 阿里云通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus`, `qwen-turbo` |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash`, `glm-4` |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |

### 4. 配置 Newsletter 源

编辑 `config/newsletters.yaml`，添加你订阅的 Newsletter：

```yaml
newsletters:
  - name: "Lenny's Newsletter"
    sender: "lenny@lennynewsletter.com"
    enabled: true

  - name: "Another Newsletter"
    sender: "example@newsletter.com"
    enabled: true
```

### 5. 本地运行测试

```bash
python -m src.main
```

输出文件将生成在 `output/` 目录下。

## GitHub Actions 部署

### 1. 推送代码到 GitHub

```bash
git add .
git commit -m "Initial commit"
git push origin main
```

### 2. 配置 GitHub Secrets

在 GitHub 仓库页面：

Settings → Secrets and variables → Actions → New repository secret

#### 必填 Secrets

| Secret 名称 | 说明 |
|------------|------|
| `IMAP_USER` | 邮箱地址 |
| `IMAP_PASSWORD` | 邮箱密码或授权码 |
| `AI_API_KEY` | AI API 密钥 |

#### 可选 Secrets

| Secret 名称 | 说明 | 默认值 |
|------------|------|--------|
| `IMAP_SERVER` | IMAP 服务器地址 | `imap.qq.com` |
| `IMAP_PORT` | IMAP 端口 | `993` |
| `AI_BASE_URL` | API 端点 | `https://api.openai.com/v1` |
| `AI_MODEL` | 模型名称 | `gpt-4o-mini` |
| `IMAGE_API_KEY` | 图片生成 API 密钥 | 使用 `AI_API_KEY` |
| `IMAGE_BASE_URL` | 图片生成 API 端点 | 使用 `AI_BASE_URL` |
| `IMAGE_MODEL` | 图片模型 | `dall-e-3` |

### 3. 手动触发测试

Actions → Daily AI Newsletter Summary → Run workflow

### 4. 查看结果

运行完成后，在 Actions 页面下载 Artifact 查看生成的文件。

## 目录结构

```
DailyAiPodcast/
├── src/
│   ├── __init__.py
│   ├── config.py             # 配置管理
│   ├── email_client.py       # IMAP 邮件客户端
│   ├── newsletter_parser.py  # 邮件内容解析
│   ├── ai_summarizer.py      # AI 总结（OpenAI 兼容接口）
│   ├── article_generator.py  # 多平台文章生成
│   ├── image_generator.py    # 封面图生成
│   └── main.py               # 主程序
├── config/
│   └── newsletters.yaml      # Newsletter 配置
├── templates/
│   └── summary.md.j2         # Markdown 模板
├── output/                   # 输出目录
├── .github/workflows/
│   └── daily-summary.yml     # GitHub Actions
├── requirements.txt
├── .env.example
└── README.md
```

## 扩展 Newsletter

只需编辑 `config/newsletters.yaml` 即可添加新的 Newsletter：

```yaml
newsletters:
  - name: "Newsletter 名称"
    sender: "发件人邮箱"
    enabled: true  # 设为 false 可临时禁用
```

## 注意事项

1. 部分邮箱（QQ、163 等）需要使用授权码而非密码
2. AI API 有调用成本，注意使用量
3. GitHub Actions 定时任务可能有几分钟延迟
4. 小红书和微信文章生成需要额外的 AI API 调用
5. 封面配图需要配置支持图片生成的 API（如 OpenAI DALL-E），阿里云通义千问暂不支持

## License

MIT