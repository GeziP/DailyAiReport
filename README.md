# Daily AI Podcast - AI 日报自动生成

自动聚合 AI 信息源，使用 AI 智能总结，生成多平台适配的日报文章。

**核心功能：**
- 📰 多信息源聚合（Newsletter 邮件、AI Builders 动态）
- 🤖 AI 智能总结与改写
- 📝 自动生成小红书、微信公众号风格文章
- 🖼️ AI 生成封面配图
- ⏰ GitHub Actions 定时自动运行

---

## 致谢

本项目灵感来源于 [@zarazhangrui](https://github.com/zarazhangrui) 的 [follow-builders](https://github.com/zarazhangrui/follow-builders) skill，用于追踪顶尖 AI Builders 的动态。感谢开源社区的贡献！

---

## 使用方式

本项目支持多种信息源，你可以根据需求选择：

### 方式一：Newsletter 邮件订阅（默认）

通过邮箱订阅 AI Newsletter，程序自动从邮箱获取并总结。

**优点：** 信息来源权威、更新稳定、内容质量高
**适合：** 有稳定 Newsletter 订阅习惯的用户

**配置：**
```env
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
IMAP_USER=your_email@gmail.com
IMAP_PASSWORD=your_password
```

**推荐订阅的 AI Newsletter：**
| Newsletter | 订阅地址 | 特点 |
|------------|---------|------|
| Lenny's Newsletter | [lenny.substack.com](https://lenny.substack.com) | 产品和技术洞察 |
| TLDR AI | [tldr.tech/ai](https://tldr.tech/ai) | 每日 AI 新闻摘要 |
| The Batch | [deeplearning.ai](https://deeplearning.ai/the-batch/) | DeepLearning.ai 出品 |
| Ben's Bites | [bensbites.com](https://bensbites.com) | AI 产品和趋势 |
| Import AI | [jackclark.net](https://jackclark.net) | 深度 AI 分析 |

### 方式二：AI Builders 动态追踪

追踪顶尖 AI Builders（创业者、研究者、工程师）在 X/Twitter 和播客的动态。

**优点：** 信息最前沿、观点独特、行业趋势洞察
**适合：** 关注 AI 行业动态的开发者和创业者

**依赖：**
```bash
# 安装 follow-builders skill
git clone https://github.com/zarazhangrui/follow-builders.git ~/.claude/skills/follow-builders
cd ~/.claude/skills/follow-builders/scripts && npm install
```

**追踪的 Builders（可自定义）：**
- Andrej Karpathy (@karpathy) - AI 研究者
- Sam Altman (@sama) - OpenAI CEO
- Yann LeCun (@ylecun) - Meta AI 首席科学家
- Aravind Srinivas (@aravind_srinivas) - Perplexity CEO
- Guillermo Rauch (@rauchg) - Vercel CEO

**播客：**
- Latent Space - AI 工程播客
- The AI Podcast - NVIDIA 出品

### 方式三：扩展其他信息源（进阶）

项目架构支持扩展，你可以添加新的信息源模块：

**可扩展方向：**
| 信息源 | 实现方式 | 参考 |
|--------|---------|------|
| RSS Feed | 添加 `rss_fetcher.py` | feedparser 库 |
| API 直接调用 | 添加 `api_fetcher.py` | 各厂商 API 文档 |
| Web Scraping | 添加 `web_scraper.py` | BeautifulSoup |
| Telegram/Discord | 添加 `bot_listener.py` | 官方 Bot API |

**扩展指南：**
1. 在 `src/` 下创建新的信息获取模块
2. 在 `main.py` 中调用并合并内容
3. 更新 `config/` 添加相应配置文件

---

## 快速开始

### 1. 克隆仓库

```bash
git clone https://github.com/GeziP/DailyAiPodcast.git
cd DailyAiPodcast
```

### 2. 安装依赖

```bash
pip install -r requirements.txt

# 如果使用 AI Builders 功能，还需安装 Node.js 依赖
# (见上方「方式二」)
```

### 3. 配置环境变量

```bash
cp .env.example .env
```

编辑 `.env` 文件，根据你选择的方式配置：

**必填配置：**
```env
# AI API（必须）
AI_API_KEY=your_api_key
AI_BASE_URL=https://api.openai.com/v1
AI_MODEL=gpt-4o-mini

# 邮箱配置（如果使用 Newsletter 邮件方式）
IMAP_SERVER=imap.gmail.com
IMAP_PORT=993
IMAP_USER=your_email@gmail.com
IMAP_PASSWORD=your_password
```

### 4. 配置信息源

根据使用方式编辑相应配置：

**Newsletter 邮件：** 编辑 `config/newsletters.yaml`
**AI Builders：** 编辑 `config/follow-builders-sources.json`

### 5. 本地运行测试

```bash
python -m src.main
```

输出文件将生成在 `output/` 目录。

---

## AI API 配置

支持任意 OpenAI 兼容接口：

| 平台 | Base URL | 模型示例 | 价格参考 |
|------|----------|----------|----------|
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini`, `gpt-4o` | $0.15/1M tokens |
| 阿里云通义千问 | `https://dashscope.aliyuncs.com/compatible-mode/v1` | `qwen-plus`, `qwen-turbo` | ¥0.004/千tokens |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4` | `glm-4-flash`, `glm-4` | 免费/付费 |
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` | ¥1/百万tokens |
| SiliconFlow | `https://api.siliconflow.cn/v1` | 多模型 | 按模型定价 |

**选择建议：**
- **性价比：** DeepSeek、阿里云通义千问
- **质量稳定：** OpenAI GPT-4o
- **国内友好：** 智谱 GLM、阿里云

---

## 邮箱配置

支持任意 IMAP 邮箱：

| 邮箱 | IMAP 服务器 | 端口 | 备注 |
|------|-------------|------|------|
| Gmail | `imap.gmail.com` | 993 | 需开启 IMAP |
| Outlook | `outlook.office365.com` | 993 | - |
| QQ 邮箱 | `imap.qq.com` | 993 | 使用授权码 |
| 163 邮箱 | `imap.163.com` | 993 | 使用授权码 |

> **注意：** 国内邮箱（QQ、163）需使用「授权码」而非密码，在邮箱设置中获取。

---

## GitHub Actions 部署

### 1. 推送代码到 GitHub

```bash
git push origin main
```

### 2. 配置 Secrets

Settings → Secrets and variables → Actions → New repository secret

**必填：**
| Secret | 说明 |
|--------|------|
| `AI_API_KEY` | AI API 密钥 |
| `IMAP_USER` | 邮箱地址（Newsletter 方式） |
| `IMAP_PASSWORD` | 邮箱密码/授权码 |

**可选：**
| Secret | 说明 | 默认值 |
|--------|------|--------|
| `AI_BASE_URL` | API 端点 | OpenAI |
| `AI_MODEL` | 模型 | `gpt-4o-mini` |
| `IMAGE_API_KEY` | 图片生成密钥 | 使用 AI_API_KEY |

### 3. 定时运行

默认北京时间早上 7:00 自动运行，可在 workflow 文件修改。

### 4. 查看结果

Actions 运行完成后，下载 Artifact 查看生成的日报文件。

---

## 输出文件

每天生成以下文件（保存在 `output/` 目录）：

**Newsletter 总结：**
- `YYYY-MM-DD.md` - 原始总结
- `YYYY-MM-DD-xiaohongshu.md` - 小红书风格
- `YYYY-MM-DD-wechat.md` - 微信公众号风格

**AI Builders Digest：**
- `YYYY-MM-DD-builders.md` - Builders 动态总结
- `YYYY-MM-DD-builders-xiaohongshu.md` - 小红书风格
- `YYYY-MM-DD-builders-wechat.md` - 微信公众号风格（专用排版）

**封面图（需配置图片 API）：**
- `*-cover.png` - 各平台封面图

---

## 目录结构

```
DailyAiPodcast/
├── src/                     # 核心模块
│   ├── config.py            # 配置管理
│   ├── email_client.py      # 邮件获取
│   ├── newsletter_parser.py # 内容解析
│   ├── ai_summarizer.py     # AI 总结
│   ├── article_generator.py # 文章生成
│   ├── image_generator.py   # 封面图生成
│   ├── builders_digest.py   # Builders 动态
│   └── main.py              # 主程序
├── config/                  # 配置文件
│   ├── newsletters.yaml     # Newsletter 配置
│   └── follow-builders-sources.json  # Builders 配置
├── templates/               # 模板文件
├── output/                  # 输出目录
├── .github/workflows/       # GitHub Actions
└── requirements.txt
```

---

## 自定义扩展

### 添加新的 Newsletter

编辑 `config/newsletters.yaml`：

```yaml
newsletters:
  - name: "Newsletter 名称"
    sender: "发件人邮箱"
    enabled: true
```

### 添加新的 Builders

编辑 `config/follow-builders-sources.json`：

```json
{
  "x_accounts": [
    {
      "name": "Builder 名称",
      "handle": "twitter_handle",
      "bio": "简介"
    }
  ],
  "podcasts": [
    {
      "name": "播客名称",
      "url": "播客地址"
    }
  ]
}
```

### 添加新信息源模块

1. 创建 `src/your_source.py`
2. 实现 `fetch()` 方法返回内容
3. 在 `main.py` 中调用并合并

---

## 常见问题

**Q: 邮箱密码填了还是连不上？**
A: 国内邮箱需要授权码，在邮箱设置中开启 IMAP 并获取授权码。

**Q: AI API 费用多少？**
A: 每次运行约调用 5-10 次 API，使用 gpt-4o-mini 约 $0.01/天。

**Q: 图片生成失败？**
A: 确保配置了支持图片生成的 API（如 OpenAI DALL-E），部分国内 API 不支持。

**Q: Builders Digest 没有 output？**
A: 检查 follow-builders skill 是否正确安装，Node.js 依赖是否安装。

**Q: 如何只使用一种信息源？**
A: 在配置文件中将其他信息源设为 `enabled: false`，或在 `.env` 中不配置相应参数。

---

## License

MIT License - 欢迎自由使用和二次开发

---

## 贡献

欢迎提交 Issue 和 PR，分享你的扩展模块或改进建议！