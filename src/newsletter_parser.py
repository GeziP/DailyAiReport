"""邮件内容解析模块"""

import re
from bs4 import BeautifulSoup
from dataclasses import dataclass
from typing import Optional


@dataclass
class ParsedContent:
    """解析后的内容"""
    title: str
    summary: str
    main_content: str
    links: list[dict[str, str]]  # [{title, url}]


class NewsletterParser:
    """Newsletter 内容解析器"""

    # 常见的无关内容模式
    IGNORE_PATTERNS = [
        r"unsubscribe",
        r"unsubscribe here",
        r"click here to unsubscribe",
        r"view in browser",
        r"view online",
        r"share this",
        r"forward to a friend",
        r"follow us on",
        r"© \d{4}",
        r"privacy policy",
        r"terms of service",
        r"you received this email",
        r"you're receiving this",
        r"no longer want",
        r"update your preferences",
        r"manage your subscription",
    ]

    # 临时清理模式（编译为正则）
    _ignore_regex = None

    @classmethod
    def _get_ignore_regex(cls):
        """获取编译后的忽略正则"""
        if cls._ignore_regex is None:
            pattern = "|".join(cls.IGNORE_PATTERNS)
            cls._ignore_regex = re.compile(pattern, re.IGNORECASE)
        return cls._ignore_regex

    @classmethod
    def parse(cls, html_content: str, subject: str = "") -> ParsedContent:
        """
        解析 HTML 邮件内容

        Args:
            html_content: HTML 内容
            subject: 邮件主题

        Returns:
            ParsedContent 对象
        """
        if not html_content:
            return ParsedContent(
                title=subject,
                summary="",
                main_content="",
                links=[]
            )

        soup = BeautifulSoup(html_content, "lxml")

        # 移除脚本和样式
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()

        # 尝试提取标题
        title = cls._extract_title(soup) or subject

        # 提取主要文本内容
        main_content = cls._extract_main_content(soup)

        # 提取链接
        links = cls._extract_links(soup)

        # 生成摘要（前 500 字符）
        summary = main_content[:500].strip()
        if len(main_content) > 500:
            summary += "..."

        return ParsedContent(
            title=title,
            summary=summary,
            main_content=main_content,
            links=links
        )

    @classmethod
    def _extract_title(cls, soup: BeautifulSoup) -> Optional[str]:
        """提取标题"""
        # 尝试从 h1 标签提取
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        # 尝试从 title 标签提取
        title = soup.find("title")
        if title:
            text = title.get_text(strip=True)
            # 清理常见的邮件标题后缀
            for suffix in [" - Substack", " | Substack", " Newsletter"]:
                text = text.replace(suffix, "")
            return text

        return None

    @classmethod
    def _extract_main_content(cls, soup: BeautifulSoup) -> str:
        """提取主要内容文本"""
        # 尝试找到主要内容区域
        content_areas = []

        # 常见的内容容器类名
        content_classes = [
            "post-content", "content", "article-content",
            "email-content", "body-content", "main-content",
            "post", "article", "entry-content"
        ]

        for class_name in content_classes:
            container = soup.find(class_=class_name)
            if container:
                content_areas.append(container)

        # 如果没有找到特定容器，使用整个 body
        if not content_areas:
            body = soup.find("body")
            if body:
                content_areas.append(body)

        # 提取文本
        texts = []
        for area in content_areas:
            # 获取段落文本
            for p in area.find_all(["p", "h1", "h2", "h3", "h4", "h5", "h6", "li"]):
                text = p.get_text(strip=True)
                if text and not cls._get_ignore_regex().search(text):
                    texts.append(text)

        return "\n\n".join(texts)

    @classmethod
    def _extract_links(cls, soup: BeautifulSoup) -> list[dict[str, str]]:
        """提取主要链接"""
        links = []
        seen_urls = set()

        for a in soup.find_all("a", href=True):
            url = a["href"]
            title = a.get_text(strip=True)

            # 跳过空标题或无意义链接
            if not title or len(title) < 3:
                continue

            # 跳过追踪链接和无关链接
            ignore_url_patterns = [
                "unsubscribe", "preferences", "mailto:",
                "#", "javascript:", "tracking"
            ]
            if any(p in url.lower() for p in ignore_url_patterns):
                continue

            # 去重
            if url in seen_urls:
                continue
            seen_urls.add(url)

            # 跳过忽略模式匹配的链接
            if cls._get_ignore_regex().search(title):
                continue

            links.append({
                "title": title,
                "url": url
            })

            # 限制链接数量
            if len(links) >= 20:
                break

        return links

    @classmethod
    def clean_text(cls, text: str) -> str:
        """清理文本内容"""
        if not text:
            return ""

        # 移除多余空白
        text = re.sub(r"\s+", " ", text)

        # 移除常见的无关行
        lines = text.split("\n")
        cleaned_lines = []

        for line in lines:
            line = line.strip()
            if line and not cls._get_ignore_regex().search(line):
                cleaned_lines.append(line)

        return "\n".join(cleaned_lines)