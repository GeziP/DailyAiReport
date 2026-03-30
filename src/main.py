"""AI Newsletter 每日总结 - 主程序"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader

from .config import Config
from .email_client import EmailClient
from .newsletter_parser import NewsletterParser
from .ai_summarizer import AISummarizer
from .article_generator import ArticleGenerator
from .image_generator import ImageGenerator
from .builders_digest import generate_builders_digest
from .email_sender import send_daily_summary
from .recommender import generate_recommendations
from .wechat_draft import WechatDraftClient


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

    # 搜索过去 24 小时的邮件
    # 使用 SINCE 搜索昨天到今天的邮件，避免遗漏
    since_date = datetime.now(timezone.utc) - timedelta(hours=24)
    print(f"\n搜索时间范围: {since_date.strftime('%Y-%m-%d %H:%M')} UTC 至今")

    # 获取邮件
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

            # 过滤：只保留过去 24 小时内的邮件
            new_emails = [
                e for e in emails
                if e.date and e.date.astimezone(timezone.utc) >= since_date
            ]

            if new_emails:
                all_emails[sender] = {
                    "name": name,
                    "emails": new_emails
                }
                print(f"    找到 {len(new_emails)} 封新邮件")
            else:
                print(f"    无新邮件")

    if not all_emails:
        print("\n没有新邮件需要处理")
        summaries = []
    else:
        # 解析和总结邮件
        print("\n正在解析和总结邮件...")
        summarizer = AISummarizer()
        summaries = []

        for sender, data in all_emails.items():
            name = data["name"]
            emails = data["emails"]

            # 合并邮件内容
            all_content = []
            all_links = []

            for email_msg in emails:
                # 优先使用 HTML 内容，否则使用纯文本
                content = email_msg.body_html or email_msg.body_text
                if content:
                    parsed = NewsletterParser.parse(content, email_msg.subject)
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

    # 生成多平台文章
    print("\n正在生成多平台文章...")
    article_gen = ArticleGenerator()

    # 提取标题用于图片生成
    article_title = f"{date_str} AI Newsletter 每日资讯"

    # 生成小红书文章
    xhs_content = article_gen.generate_xiaohongshu(summaries, date_str)
    xhs_file = None
    if xhs_content:
        xhs_file = Config.OUTPUT_DIR / f"{date_str}-xiaohongshu.md"
        # 从内容中提取标题
        for line in xhs_content.split('\n'):
            if line.startswith('## ') and '标题' in line:
                next_line = xhs_content.split('\n')[xhs_content.split('\n').index(line) + 1]
                if next_line and not next_line.startswith('#'):
                    article_title = next_line.strip()
                break
        with open(xhs_file, "w", encoding="utf-8") as f:
            f.write(xhs_content)
        print(f"  小红书文章: {xhs_file}")

    # 生成微信公众号文章
    wechat_content = article_gen.generate_wechat(summaries, date_str)
    wechat_file = None
    if wechat_content:
        wechat_file = Config.OUTPUT_DIR / f"{date_str}-wechat.md"
        with open(wechat_file, "w", encoding="utf-8") as f:
            f.write(wechat_content)
        print(f"  微信公众号文章: {wechat_file}")

    # 生成封面图
    print("\n正在生成封面图...")
    image_gen = ImageGenerator()

    # 生成小红书封面图
    xhs_cover = image_gen.generate_xiaohongshu_cover(article_title, date_str)
    if xhs_cover and xhs_file:
        # 在 Markdown 开头嵌入图片引用
        with open(xhs_file, "r", encoding="utf-8") as f:
            content = f.read()
        with open(xhs_file, "w", encoding="utf-8") as f:
            f.write(f"![小红书封面](./{xhs_cover.name})\n\n{content}")

    # 生成微信公众号封面图
    wechat_cover = image_gen.generate_wechat_cover(article_title, date_str)
    if wechat_cover and wechat_file:
        # 在 Markdown 开头嵌入图片引用
        with open(wechat_file, "r", encoding="utf-8") as f:
            content = f.read()
        with open(wechat_file, "w", encoding="utf-8") as f:
            f.write(f"![微信公众号封面](./{wechat_cover.name})\n\n{content}")

    # 发布微信公众号草稿
    wechat_client = WechatDraftClient()
    if wechat_client.should_publish() and wechat_file:
        print("\n正在发布微信公众号草稿...")
        wechat_client.publish_draft(wechat_file, wechat_cover)

    print("=" * 50)

    # ========== 生成 AI Builders Digest ==========
    print("\n" + "=" * 50)
    print("AI Builders Digest 生成")
    print("=" * 50)

    builders_digest = generate_builders_digest()
    builders_file = None

    if builders_digest:
        # 保存 Builders Digest 原始摘要
        builders_file = Config.OUTPUT_DIR / f"{date_str}-builders.md"
        with open(builders_file, "w", encoding="utf-8") as f:
            f.write(builders_digest)
        print(f"  Builders Digest: {builders_file}")

        # 生成 Builders Digest 多平台文章
        print("\n正在生成 Builders Digest 多平台文章...")

        builders_xhs_file = None
        builders_wechat_file = None

        # 生成小红书文章
        builders_xhs = article_gen.generate_xiaohongshu_from_content(
            builders_digest, "AI Builders"
        )
        if builders_xhs:
            builders_xhs_file = Config.OUTPUT_DIR / f"{date_str}-builders-xiaohongshu.md"
            with open(builders_xhs_file, "w", encoding="utf-8") as f:
                f.write(builders_xhs)
            print(f"  Builders 小红书文章: {builders_xhs_file}")

        # 生成微信公众号文章
        builders_wechat = article_gen.generate_wechat_from_content(
            builders_digest, "AI Builders"
        )
        if builders_wechat:
            builders_wechat_file = Config.OUTPUT_DIR / f"{date_str}-builders-wechat.md"
            with open(builders_wechat_file, "w", encoding="utf-8") as f:
                f.write(builders_wechat)
            print(f"  Builders 微信公众号文章: {builders_wechat_file}")

        # 生成封面图
        builders_title = f"{date_str} AI Builders 动态"
        builders_xhs_cover = image_gen.generate_xiaohongshu_cover(builders_title, date_str)
        if builders_xhs_cover and builders_xhs_file:
            with open(builders_xhs_file, "r", encoding="utf-8") as f:
                content = f.read()
            with open(builders_xhs_file, "w", encoding="utf-8") as f:
                f.write(f"![小红书封面](./{builders_xhs_cover.name})\n\n{content}")

        builders_wechat_cover = image_gen.generate_wechat_cover(builders_title, date_str)
        if builders_wechat_cover and builders_wechat_file:
            with open(builders_wechat_file, "r", encoding="utf-8") as f:
                content = f.read()
            with open(builders_wechat_file, "w", encoding="utf-8") as f:
                f.write(f"![微信公众号封面](./{builders_wechat_cover.name})\n\n{content}")

            # 发布 Builders 微信公众号草稿
            if wechat_client.should_publish():
                print("\n正在发布 Builders 微信公众号草稿...")
                wechat_client.publish_draft(builders_wechat_file, builders_wechat_cover)

    print("=" * 50)

    # ========== 生成 Builder/播客推荐 ==========
    recommendations = generate_recommendations()
    rec_report = None
    if recommendations:
        from .recommender import SourceRecommender
        recommender = SourceRecommender()
        rec_report = recommender.save_recommendations_report(
            recommendations, Config.OUTPUT_DIR, date_str
        )
        if rec_report:
            print(f"推荐报告已保存: {rec_report}")

    # ========== 发送邮件推送 ==========
    if Config.EMAIL_RECIPIENTS:
        print("\n" + "=" * 50)
        print("邮件推送")
        print("=" * 50)

        # 收集附件
        attachments = []
        if output_file and output_file.exists():
            attachments.append(output_file)
        if xhs_file and xhs_file.exists():
            attachments.append(xhs_file)
        if wechat_file and wechat_file.exists():
            attachments.append(wechat_file)
        if builders_file and builders_file.exists():
            attachments.append(builders_file)
        if rec_report and rec_report.exists():
            attachments.append(rec_report)

        # 发送总结邮件
        send_daily_summary(
            date_str=date_str,
            summary_file=output_file,
            builders_file=builders_file,
            recommendations_file=rec_report,
            attachments=attachments if attachments else None
        )
        print("=" * 50)

    return 0


if __name__ == "__main__":
    sys.exit(main())