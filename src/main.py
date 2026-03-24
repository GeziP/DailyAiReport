"""AI Newsletter 每日总结 - 主程序"""

import sys
from datetime import datetime
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

from .config import Config
from .email_client import EmailClient
from .newsletter_parser import NewsletterParser
from .ai_summarizer import AISummarizer


def load_newsletters_config() -> list[dict]:
    """加载 Newsletter 配置"""
    with open(Config.NEWSLETTERS_CONFIG, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return [
        nl for nl in config.get("newsletters", [])
        if nl.get("enabled", True)
    ]


def get_newsletter_name(sender: str, newsletters: list[dict]) -> str:
    """根据发件人邮箱获取 Newsletter 名称"""
    for nl in newsletters:
        if nl["sender"].lower() in sender.lower():
            return nl["name"]
    return "Unknown Newsletter"


def main():
    """主程序入口"""
    print("=" * 50)
    print("AI Newsletter 每日总结")
    print("=" * 50)

    # 验证配置
    try:
        Config.validate()
    except ValueError as e:
        print(f"配置错误: {e}")
        sys.exit(1)

    # 确保输出目录存在
    Config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 加载 Newsletter 配置
    newsletters_config = load_newsletters_config()
    if not newsletters_config:
        print("警告: 没有配置任何 Newsletter")
        sys.exit(0)

    print(f"已配置 {len(newsletters_config)} 个 Newsletter 源")

    # 获取今天的邮件
    print("\n正在获取邮件...")
    all_emails = {}

    with EmailClient() as client:
        if not client.connection:
            print("错误: 无法连接到邮件服务器")
            sys.exit(1)

        for nl in newsletters_config:
            sender = nl["sender"]
            name = nl["name"]
            print(f"  检查: {name} ({sender})")

            emails = client.fetch_emails_by_sender(sender)
            if emails:
                all_emails[sender] = {
                    "name": name,
                    "emails": emails
                }
                print(f"    找到 {len(emails)} 封邮件")
            else:
                print(f"    未找到邮件")

    if not all_emails:
        print("\n今日未收到任何 Newsletter 邮件")
        # 仍然生成空的总结文件
        summaries = []
    else:
        # 解析和总结邮件
        print("\n正在解析和总结邮件...")
        summarizer = AISummarizer()
        summaries = []

        for sender, data in all_emails.items():
            name = data["name"]
            emails = data["emails"]

            # 合并同一天的邮件内容
            all_content = []
            all_links = []

            for email in emails:
                # 优先使用 HTML 内容，否则使用纯文本
                content = email.body_html or email.body_text
                if content:
                    parsed = NewsletterParser.parse(content, email.subject)
                    if parsed.main_content:
                        all_content.append(parsed.main_content)
                    if parsed.links:
                        all_links.extend(parsed.links)

            if all_content:
                combined_content = "\n\n---\n\n".join(all_content)
                print(f"  总结: {name}")

                summary = summarizer.summarize(combined_content, name)

                summaries.append({
                    "name": name,
                    "summary": summary or "（总结生成失败）",
                    "links": all_links[:10]  # 限制链接数量
                })

    # 生成 Markdown 文件
    print("\n正在生成 Markdown 文件...")

    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")

    # 准备模板数据
    template_data = {
        "date": date_str,
        "newsletters": summaries,
        "generated_at": today.strftime("%Y-%m-%d %H:%M:%S"),
        "source_count": len(all_emails)
    }

    # 渲染模板
    env = Environment(loader=FileSystemLoader(Config.TEMPLATES_DIR))
    template = env.get_template("summary.md.j2")
    output_content = template.render(**template_data)

    # 写入文件
    output_file = Config.OUTPUT_DIR / f"{date_str}.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(output_content)

    print(f"\n完成! 输出文件: {output_file}")
    print("=" * 50)

    return 0


if __name__ == "__main__":
    sys.exit(main())