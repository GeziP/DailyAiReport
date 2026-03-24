# AI Newsletter 每日总结

自动从 QQ 邮箱获取订阅的 AI Newsletter 邮件，使用智谱 GLM 进行智能总结，生成 Markdown 格式的每日摘要。

## 功能特点

- 📧 支持 QQ 邮箱 IMAP 协议读取邮件
- 🤖 使用智谱 GLM-4 进行内容总结
- 📅 按日期存放 Markdown 输出文件
- ⏰ GitHub Actions 定时自动运行（北京时间早上 7:00）
- ⚙️ YAML 配置文件，方便添加新的 Newsletter 源

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
# QQ 邮箱配置
QQ_EMAIL=your_email@qq.com
QQ_EMAIL_AUTH_CODE=your_authorization_code

# 智谱 GLM API 配置
ZHIPU_API_KEY=your_api_key
```

#### 获取 QQ 邮箱授权码

1. 登录 [QQ 邮箱网页版](https://mail.qq.com)
2. 设置 → 账户 → POP3/IMAP/SMTP 服务
3. 开启 IMAP/SMTP 服务
4. 点击"生成授权码"，发送短信验证后获得

#### 获取智谱 GLM API Key

1. 注册 [智谱开放平台](https://open.bigmodel.cn)
2. 进入控制台 → API Keys
3. 创建新的 API Key

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

添加以下 Secrets：

| Secret 名称 | 说明 |
|------------|------|
| `QQ_EMAIL` | QQ 邮箱地址 |
| `QQ_EMAIL_AUTH_CODE` | QQ 邮箱授权码 |
| `ZHIPU_API_KEY` | 智谱 GLM API Key |

### 3. 手动触发测试

Actions → Daily AI Newsletter Summary → Run workflow

### 4. 查看结果

运行完成后，在 Actions 页面下载 Artifact 查看生成的 Markdown 文件。

## 目录结构

```
DailyAiPodcast/
├── src/
│   ├── __init__.py
│   ├── config.py             # 配置管理
│   ├── email_client.py       # IMAP 邮件客户端
│   ├── newsletter_parser.py  # 邮件内容解析
│   ├── ai_summarizer.py      # 智谱 GLM 总结
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

1. 确保 Gmail 已设置自动转发到 QQ 邮箱
2. QQ 邮箱授权码不是 QQ 密码
3. 智谱 GLM API 有免费额度，每日使用量需注意
4. GitHub Actions 定时任务可能有几分钟延迟

## License

MIT