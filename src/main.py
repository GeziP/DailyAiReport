"""AI 日报自动生成 - 主程序

融合 AI Newsletter + AI Builders 动态到统一日报
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List

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
from .recommender import generate_recommendations, RecommendedSource


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


def fetch_newsletter_summaries(
    newsletters_config: list[dict]
) -> tuple[list[dict], list[dict]]:
    """
    获取 Newsletter 邮件并生成总结

    Returns:
        (summaries, all_links)
    """
    print("\n正在获取邮件...")
    all_emails = {}
    all_links = []

    since_date = datetime.now(timezone.utc) - timedelta(hours=24)
    print(f"搜索时间范围: {since_date.strftime('%Y-%m-%d %H:%M')} UTC 至今")

    with EmailClient() as client:
        if not client.connection:
            print("错误: 无法连接到邮件服务器")
            return [], []

        for nl in newsletters_config:
            sender = nl["sender"]
            name = nl["name"]
            print(f"  检查: {name} ({sender})")

            emails = client.fetch_emails_by_sender(sender)

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
        return [], []

    # 解析和总结邮件
    print("\n正在解析和总结邮件...")
    summarizer = AISummarizer()
    summaries = []

    for sender, data in all_emails.items():
        name = data["name"]
        emails = data["emails"]

        all_content = []
        email_links = []

        for email_msg in emails:
            content = email_msg.body_html or email_msg.body_text
            if content:
                parsed = NewsletterParser.parse(content, email_msg.subject)
                if parsed.main_content:
                    all_content.append(parsed.main_content)
                if parsed.links:
                    email_links.extend(parsed.links)

        if all_content:
            combined_content = "\n\n---\n\n".join(all_content)
            print(f"  总结: {name}")

            summary = summarizer.summarize(combined_content, name)

            summaries.append({
                "name": name,
                "summary": summary or "（总结生成失败）",
                "links": email_links
            })
            all_links.extend(email_links)

    return summaries, all_links


def build_unified_report(
    date_str: str,
    newsletter_summaries: list[dict],
    builders_digest: Optional[str],
    recommendations: Optional[List[RecommendedSource]]
) -> tuple[str, list[dict]]:
    """
    构建统一日报内容

    Returns:
        (unified_content, all_links)
    """
    parts = []
    all_links = []

    # 今日概览
    overview_parts = []
    if newsletter_summaries:
        overview_parts.append(f"涉及 **{len(newsletter_summaries)} 个 Newsletter**")
    if builders_digest:
        overview_parts.append("**AI Builders 动态**")
    if recommendations:
        overview_parts.append(f"发现 **{len(recommendations)} 个新优质来源**")

    if overview_parts:
        overview = "、".join(overview_parts)
        parts.append(f"## 今日概览\n\n{overview}")

    # Newsletter 精选
    if newsletter_summaries:
        parts.append("\n## 一、AI Newsletter 精选\n")
        for summary in newsletter_summaries:
            parts.append(f"### {summary['name']}\n")
            parts.append(summary.get('summary', '（无内容）'))
            parts.append("\n")
            if summary.get('links'):
                parts.append("**相关链接：**\n")
                for link in summary['links']:
                    parts.append(f"- {link['title']}: {link['url']}\n")
                    all_links.append(link)

    # Builders 动态
    if builders_digest:
        parts.append("\n## 二、AI Builders 动态\n")
        parts.append(builders_digest)

    # 推荐内容
    if recommendations:
        parts.append("\n## 三、新发现的优质来源\n")

        builders = [r for r in recommendations if r.type == "builder"]
        podcasts = [r for r in recommendations if r.type == "podcast"]

        if builders:
            parts.append("### 推荐关注的 Builder\n")
            for rec in builders:
                parts.append(f"- **{rec.name}** ({rec.platform}): {rec.reason}\n")

        if podcasts:
            parts.append("\n### 推荐订阅的播客\n")
            for rec in podcasts:
                parts.append(f"- **{rec.name}** ({rec.platform}): {rec.reason}\n")

    # 参考来源
    if all_links:
        parts.append("\n## 参考来源\n")
        for i, link in enumerate(all_links, 1):
            parts.append(f"\n[{i}] {link['title']}\n{link['url']}\n")

    parts.append(f"\n---\n*生成时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

    return "".join(parts), all_links


def main():
    """主程序入口"""
    print("=" * 50)
    print("AI 日报自动生成")
    print("=" * 50)

    # 验证配置
    try:
        Config.validate()
    except ValueError as e:
        print(f"配置错误: {e}")
        sys.exit(1)

    # 确保输出目录存在
    Config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")

    # ========== 1. 获取 Newsletter 总结 ==========
    print("\n" + "=" * 50)
    print("AI Newsletter 获取与总结")
    print("=" * 50)

    newsletters_config = load_newsletters_config()
    if newsletters_config:
        print(f"已配置 {len(newsletters_config)} 个 Newsletter 源")
        newsletter_summaries, newsletter_links = fetch_newsletter_summaries(
            newsletters_config
        )
    else:
        print("警告: 没有配置任何 Newsletter")
        newsletter_summaries = []
        newsletter_links = []

    # ========== 2. 获取 AI Builders 动态 ==========
    print("\n" + "=" * 50)
    print("AI Builders 动态获取")
    print("=" * 50)

    builders_digest = generate_builders_digest()
    if builders_digest:
        print("Builders Digest 生成成功")
    else:
        print("没有新的 Builders 动态")

    # ========== 3. 生成 Builder/播客推荐 ==========
    print("\n" + "=" * 50)
    print("Builder/播客推荐")
    print("=" * 50)

    recommendations = generate_recommendations()

    # ========== 4. 构建统一日报 ==========
    print("\n" + "=" * 50)
    print("构建统一日报")
    print("=" * 50)

    unified_content, all_links = build_unified_report(
        date_str,
        newsletter_summaries,
        builders_digest,
        recommendations
    )

    if not unified_content or len(unified_content.strip()) < 50:
        print("没有内容需要处理")
        return 0

    # 保存统一日报
    output_file = Config.OUTPUT_DIR / f"{date_str}.md"
    with open(output_file, "w", encoding="utf-8") as f:
        f.write(f"# AI 日报 - {date_str}\n\n{unified_content}")
    print(f"统一日报: {output_file}")

    # ========== 5. 生成多平台文章 ==========
    print("\n正在生成多平台文章...")
    article_gen = ArticleGenerator()

    # 生成小红书文章
    xhs_content = article_gen.generate_unified_xiaohongshu(unified_content)
    xhs_file = None
    article_title = f"{date_str} AI 日报"

    if xhs_content:
        xhs_file = Config.OUTPUT_DIR / f"{date_str}-xiaohongshu.md"
        with open(xhs_file, "w", encoding="utf-8") as f:
            f.write(xhs_content)
        print(f"  小红书文章: {xhs_file}")

    # 生成微信公众号文章
    wechat_content = article_gen.generate_unified_wechat(unified_content)
    wechat_file = None

    if wechat_content:
        wechat_file = Config.OUTPUT_DIR / f"{date_str}-wechat.md"
        with open(wechat_file, "w", encoding="utf-8") as f:
            f.write(wechat_content)
        print(f"  微信公众号文章: {wechat_file}")

    # ========== 6. 生成封面图 ==========
    print("\n正在生成封面图...")
    image_gen = ImageGenerator()

    xhs_cover = image_gen.generate_xiaohongshu_cover(article_title, date_str)
    if xhs_cover and xhs_file:
        with open(xhs_file, "r", encoding="utf-8") as f:
            content = f.read()
        with open(xhs_file, "w", encoding="utf-8") as f:
            f.write(f"![小红书封面](./{xhs_cover.name})\n\n{content}")

    wechat_cover = image_gen.generate_wechat_cover(article_title, date_str)
    if wechat_cover and wechat_file:
        with open(wechat_file, "r", encoding="utf-8") as f:
            content = f.read()
        with open(wechat_file, "w", encoding="utf-8") as f:
            f.write(f"![微信公众号封面](./{wechat_cover.name})\n\n{content}")

    print("=" * 50)

    # ========== 7. 发送邮件推送 ==========
    if Config.EMAIL_RECIPIENTS:
        print("\n" + "=" * 50)
        print("邮件推送")
        print("=" * 50)

        attachments = []
        if output_file and output_file.exists():
            attachments.append(output_file)
        if xhs_file and xhs_file.exists():
            attachments.append(xhs_file)
        if wechat_file and wechat_file.exists():
            attachments.append(wechat_file)

        send_daily_summary(
            date_str=date_str,
            summary_file=output_file,
            builders_file=None,  # 已融合到统一日报
            recommendations_file=None,
            attachments=attachments if attachments else None
        )
        print("=" * 50)

    return 0


if __name__ == "__main__":
    sys.exit(main())