"""AI 日报自动生成 - 主程序

融合 AI Newsletter + AI Builders 动态到统一日报
"""

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional, List
from concurrent.futures import ThreadPoolExecutor, as_completed

import yaml
from jinja2 import Environment, FileSystemLoader
from openai import OpenAI
import httpx

from .config import Config
from .email_client import EmailClient
from .newsletter_parser import NewsletterParser
from .ai_summarizer import AISummarizer
from .article_generator import ArticleGenerator
from .image_generator import ImageGenerator
from .wechat_image_inserter import WeChatImageInserter
from .wechat_publisher import WeChatPublisher, markdown_to_wechat_html
from .builders_digest import generate_builders_digest
from .email_sender import send_daily_summary
from .recommender import generate_recommendations, RecommendedSource


# 按主题整合所有 Newsletter 的提示词
MERGE_SYSTEM_PROMPT = """你是一个 Newsletter 内容整理者。你的任务是将多个 Newsletter 的内容按主题合并整理。

## 核心原则

1. **按主题整合**：将所有 Newsletter 的内容按主题归类，不要按来源分开
   - 例如：模型发布、产品动态、人员变动、行业观点、技术突破等
   - 同一主题的内容放在一起，只标注来源名称

2. **详细呈现**：每个观点、细节、引用都要完整保留
   - 原文有100字就呈现100字
   - 不要用"详见"、"等"这类缩写词

3. **不做价值判断**：只呈现事实，不说"为什么重要"

## 输出格式

### 今日概览
[一句话说明内容范围，列出2-3个核心主题]

### 主要内容

#### **[主题标题]**

[详细呈现该主题的所有内容，引用用*斜体*]

*来源：AINews、The AI Break*

---

#### **[主题标题]**

[详细呈现该主题的所有内容...]

*来源：Lenny's Newsletter*

---

### 参考来源

[按 Newsletter 分组列出链接]"""


def load_newsletters_config() -> list[dict]:
    """加载 Newsletter 配置"""
    with open(Config.NEWSLETTERS_CONFIG, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    return [
        nl for nl in config.get("newsletters", [])
        if nl.get("enabled", True)
    ]


def merge_newsletter_summaries(summaries: list[dict]) -> Optional[str]:
    """
    将多个 Newsletter 总结按主题整合

    Args:
        summaries: 各 Newsletter 的总结列表

    Returns:
        按主题整合后的内容
    """
    if not summaries:
        return None

    # 合并所有总结内容
    combined_content = "\n\n---\n\n".join([
        f"## {s['name']}\n\n{s.get('summary', '（无内容）')}"
        for s in summaries
    ])

    print("  正在按主题整合 Newsletter 内容...")

    http_client = httpx.Client(
        timeout=httpx.Timeout(300.0, connect=30.0)
    )
    client = OpenAI(
        api_key=Config.AI_API_KEY,
        base_url=Config.AI_BASE_URL,
        http_client=http_client
    )

    user_prompt = f"""请将以下 Newsletter 内容按主题整合，不要按来源分开：

---
{combined_content}
---

要求：
1. 按主题归类，同一主题的内容放在一起
2. 详细呈现每个观点，不要精简
3. 标注每个内容的来源名称
4. 不要说明"为什么重要"
"""

    try:
        response = client.chat.completions.create(
            model=Config.AI_MODEL,
            messages=[
                {"role": "system", "content": MERGE_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt}
            ],
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"Newsletter 整合失败: {e}")
        return None


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
    merged_newsletter: Optional[str],  # 已按主题整合的 Newsletter 内容
    newsletter_links: list[dict],
    builders_digest: Optional[str],
    recommendations: Optional[List[RecommendedSource]]
) -> tuple[str, list[dict]]:
    """
    构建统一日报内容

    Args:
        merged_newsletter: 按主题整合后的 Newsletter 内容
        newsletter_links: 所有 Newsletter 的链接
        builders_digest: Builders Digest 内容
        recommendations: 推荐内容

    Returns:
        (unified_content, all_links)
    """
    parts = []
    all_links = newsletter_links.copy()

    # 今日概览
    overview_parts = []
    if merged_newsletter:
        overview_parts.append("AI Newsletter 精选")
    if builders_digest:
        overview_parts.append("**AI Builders 动态**")
    if recommendations:
        overview_parts.append(f"发现 **{len(recommendations)} 个新优质来源**")

    if overview_parts:
        overview = "、".join(overview_parts)
        parts.append(f"## 今日概览\n\n{overview}")

    # Newsletter 精选（已按主题整合）
    if merged_newsletter:
        parts.append("\n## 一、AI Newsletter 精选\n")
        parts.append(merged_newsletter)

        # 链接单独处理
        if newsletter_links:
            parts.append("\n### Newsletter 链接汇总\n")
            for link in newsletter_links[:20]:  # 限制链接数量避免太长
                parts.append(f"- {link['title']}: {link['url']}\n")

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

    # ========== 1. 并行获取 Newsletter 和 Builders Digest ==========
    print("\n" + "=" * 50)
    print("并行获取 Newsletter 和 Builders Digest")
    print("=" * 50)

    newsletters_config = load_newsletters_config()

    newsletter_summaries = []
    newsletter_links = []
    builders_digest = None

    with ThreadPoolExecutor(max_workers=2) as executor:
        # 提交两个并行任务
        newsletter_future = executor.submit(
            fetch_newsletter_summaries, newsletters_config
        ) if newsletters_config else None

        builders_future = executor.submit(generate_builders_digest)

        # 等待 Newsletter 结果
        if newsletter_future:
            print("\n[Newsletter] 正在获取和总结...")
            try:
                newsletter_summaries, newsletter_links = newsletter_future.result()
                print(f"[Newsletter] 完成: {len(newsletter_summaries)} 个总结")
            except Exception as e:
                print(f"[Newsletter] 失败: {e}")
        else:
            print("警告: 没有配置任何 Newsletter")

        # 等待 Builders Digest 结果
        print("\n[Builders] 正在获取和总结...")
        try:
            builders_digest = builders_future.result()
            if builders_digest:
                print("[Builders] ✓ Builders Digest 已生成")
            else:
                print("[Builders] ⚠ Builders Digest 未生成")
        except Exception as e:
            print(f"[Builders] 失败: {e}")

    # ========== 2. 按主题整合 Newsletter 内容 ==========
    merged_newsletter = None
    if newsletter_summaries:
        print("\n" + "=" * 50)
        print("按主题整合 Newsletter 内容")
        print("=" * 50)
        merged_newsletter = merge_newsletter_summaries(newsletter_summaries)
        if merged_newsletter:
            print("Newsletter 内容已按主题整合")
        else:
            print("整合失败，使用原始分来源格式")
            # 回退：使用原始分来源格式
            merged_newsletter = "\n\n".join([
                f"### {s['name']}\n{s.get('summary', '（无内容）')}"
                for s in newsletter_summaries
            ])
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
        merged_newsletter,
        newsletter_links,
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

    # ========== 4. 生成多平台文章 ==========
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

    # ========== 5. 生成封面图 ==========
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

    # ========== 5b. 为微信公众号日报各章节配图 ==========
    print("\n" + "=" * 50)
    print("微信公众号日报章节配图")
    print("=" * 50)

    if wechat_file and wechat_file.exists():
        try:
            wechat_inserter = WeChatImageInserter()
            with open(wechat_file, "r", encoding="utf-8") as f:
                wechat_md = f.read()

            enriched_wechat = wechat_inserter.process_wechat_article(
                wechat_md, date_str, Config.OUTPUT_DIR
            )

            with open(wechat_file, "w", encoding="utf-8") as f:
                f.write(enriched_wechat)
            print(f"  微信公众号配图完成: {wechat_file}")
        except ValueError as e:
            # 通常是 MANUS_API_KEY 未配置
            print(f"  微信公众号配图跳过（{e}）")
            print("  请在 GitHub Secrets 中配置 MANUS_API_KEY")
        except Exception as e:
            print(f"  微信公众号配图失败（不影响其他输出）: {e}")
    else:
        print("  微信公众号文章不存在，跳过配图")

    print("=" * 50)

    # ========== 5c. 将微信公众号日报发布为草稿 ==========
    print("\n" + "=" * 50)
    print("微信公众号草稿发布")
    print("=" * 50)

    if wechat_file and wechat_file.exists() and Config.WECHAT_APP_ID and Config.WECHAT_APP_SECRET:
        try:
            publisher = WeChatPublisher()
            with open(wechat_file, "r", encoding="utf-8") as f:
                wechat_md = f.read()

            # 找封面图
            cover_candidates = list(Config.OUTPUT_DIR.glob(f"{date_str}-wechat-cover.*"))
            cover_path = cover_candidates[0] if cover_candidates else None

            draft_media_id = publisher.publish_to_draft(
                markdown_content=wechat_md,
                date_str=date_str,
                output_dir=Config.OUTPUT_DIR,
                cover_image_path=cover_path,
            )

            if draft_media_id:
                # 同时保存一份 HTML 版本供参考
                html_file = Config.OUTPUT_DIR / f"{date_str}-wechat.html"
                from .wechat_publisher import markdown_to_wechat_html
                html_content = markdown_to_wechat_html(wechat_md)
                with open(html_file, "w", encoding="utf-8") as f:
                    f.write(f"""<!DOCTYPE html>
<html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><title>微信公众号日报 {date_str}</title></head>
<body>{html_content}</body></html>""")
                print(f"  HTML 预览已保存: {html_file}")
        except ValueError as e:
            print(f"  微信草稿发布跳过（{e}）")
        except Exception as e:
            print(f"  微信草稿发布失败（不影响其他输出）: {e}")
    else:
        if not (Config.WECHAT_APP_ID and Config.WECHAT_APP_SECRET):
            # 即使不发布草稿，也生成 HTML 预览
            if wechat_file and wechat_file.exists():
                try:
                    with open(wechat_file, "r", encoding="utf-8") as f:
                        wechat_md = f.read()
                    html_file = Config.OUTPUT_DIR / f"{date_str}-wechat.html"
                    html_content = markdown_to_wechat_html(wechat_md)
                    with open(html_file, "w", encoding="utf-8") as f:
                        f.write(f"""<!DOCTYPE html>
<html lang=\"zh-CN\"><head><meta charset=\"utf-8\"><title>微信公众号日报 {date_str}</title></head>
<body>{html_content}</body></html>""")
                    print(f"  微信公众号 HTML 预览已生成（未配置 WECHAT_APP_ID，跳过发布草稿）: {html_file}")
                except Exception as e:
                    print(f"  HTML 预览生成失败: {e}")
        else:
            print("  微信公众号文章不存在，跳过草稿发布")

    print("=" * 50)

    # ========== 6. 发送邮件推送 ==========
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
        # 附上微信公众号 HTML 预览文件（如果存在）
        html_preview = Config.OUTPUT_DIR / f"{date_str}-wechat.html"
        if html_preview.exists():
            attachments.append(html_preview)

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