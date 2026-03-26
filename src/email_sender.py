"""邮件发送模块 - 发送每日总结"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import Optional, List

from .config import Config


class EmailSender:
    """邮件发送器 - 发送每日总结到指定邮箱"""

    def __init__(self):
        # SMTP 配置（通常与 IMAP 使用同一服务器）
        self.smtp_server = Config.SMTP_SERVER or Config.IMAP_SERVER.replace("imap.", "smtp.")
        self.smtp_port = Config.SMTP_PORT
        self.sender = Config.IMAP_USER
        self.password = Config.IMAP_PASSWORD

    def send_summary(
        self,
        to_email: str,
        subject: str,
        content: str,
        content_type: str = "html",
        attachments: Optional[List[Path]] = None
    ) -> bool:
        """
        发送总结邮件

        Args:
            to_email: 收件人邮箱
            subject: 邮件主题
            content: 邮件内容
            content_type: 内容类型 ("html" 或 "plain")
            attachments: 附件文件路径列表

        Returns:
            发送成功返回 True，失败返回 False
        """
        if not self.sender or not self.password:
            print("错误: 邮箱配置不完整，无法发送邮件")
            return False

        try:
            msg = MIMEMultipart()
            msg['From'] = self.sender
            msg['To'] = to_email
            msg['Subject'] = subject

            # 正文
            msg.attach(MIMEText(content, content_type, 'utf-8'))

            # 附件
            if attachments:
                for file_path in attachments:
                    if file_path and file_path.exists():
                        with open(file_path, 'rb') as f:
                            part = MIMEBase('application', 'octet-stream')
                            part.set_payload(f.read())
                            encoders.encode_base64(part)
                            part.add_header(
                                'Content-Disposition',
                                f'attachment; filename="{file_path.name}"'
                            )
                            msg.attach(part)

            # 发送邮件
            with smtplib.SMTP_SSL(self.smtp_server, self.smtp_port) as server:
                server.login(self.sender, self.password)
                server.sendmail(self.sender, to_email, msg.as_string())

            print(f"邮件发送成功: {to_email}")
            return True

        except smtplib.SMTPAuthenticationError:
            print("错误: 邮箱认证失败，请检查邮箱地址和授权码")
            return False
        except smtplib.SMTPException as e:
            print(f"邮件发送失败 (SMTP错误): {e}")
            return False
        except Exception as e:
            print(f"邮件发送失败: {e}")
            return False

    def send_to_recipients(
        self,
        subject: str,
        content: str,
        content_type: str = "html",
        attachments: Optional[List[Path]] = None
    ) -> int:
        """
        发送邮件给配置中的所有收件人

        Args:
            subject: 邮件主题
            content: 邮件内容
            content_type: 内容类型
            attachments: 附件列表

        Returns:
            成功发送的数量
        """
        recipients = Config.EMAIL_RECIPIENTS
        if not recipients:
            print("警告: 未配置邮件收件人 (EMAIL_RECIPIENTS)")
            return 0

        success_count = 0
        for email in recipients:
            if self.send_summary(email, subject, content, content_type, attachments):
                success_count += 1

        return success_count


def markdown_to_html(markdown_content: str, title: str = "") -> str:
    """
    将 Markdown 内容转换为简单的 HTML

    Args:
        markdown_content: Markdown 文本
        title: 文章标题

    Returns:
        HTML 字符串
    """
    import re

    html = markdown_content

    # 标题
    html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
    html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
    html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)

    # 粗体
    html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
    html = re.sub(r'__(.+?)__', r'<strong>\1</strong>', html)

    # 斜体
    html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
    html = re.sub(r'_(.+?)_', r'<em>\1</em>', html)

    # 链接
    html = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', html)

    # 列表
    html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)

    # 代码块
    html = re.sub(r'```(\w*)\n(.*?)```', r'<pre><code class="\1">\2</code></pre>', html, flags=re.DOTALL)

    # 行内代码
    html = re.sub(r'`([^`]+)`', r'<code>\1</code>', html)

    # 段落
    lines = html.split('\n')
    paragraphs = []
    for line in lines:
        line = line.strip()
        if not line:
            paragraphs.append('')
        elif not line.startswith('<'):
            paragraphs.append(f'<p>{line}</p>')
        else:
            paragraphs.append(line)
    html = '\n'.join(paragraphs)

    # 包裹在 HTML 模板中
    html_template = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <title>{title}</title>
    <style>
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            line-height: 1.6;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            color: #333;
        }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #3498db; padding-bottom: 10px; }}
        h2 {{ color: #34495e; margin-top: 30px; }}
        h3 {{ color: #7f8c8d; }}
        a {{ color: #3498db; text-decoration: none; }}
        a:hover {{ text-decoration: underline; }}
        code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; }}
        pre {{ background: #f4f4f4; padding: 15px; border-radius: 5px; overflow-x: auto; }}
        li {{ margin: 5px 0; }}
        .footer {{
            margin-top: 30px;
            padding-top: 20px;
            border-top: 1px solid #eee;
            color: #888;
            font-size: 12px;
        }}
    </style>
</head>
<body>
{html}
<div class="footer">
    <p>由 DailyAiPodcast 自动生成</p>
</div>
</body>
</html>"""

    return html_template


def send_daily_summary(
    date_str: str,
    summary_file: Path,
    attachments: Optional[List[Path]] = None
) -> bool:
    """
    发送每日总结邮件

    Args:
        date_str: 日期字符串 (YYYY-MM-DD)
        summary_file: 总结文件路径
        attachments: 附加的附件列表

    Returns:
        发送成功返回 True
    """
    if not summary_file.exists():
        print(f"总结文件不存在: {summary_file}")
        return False

    # 读取总结内容
    with open(summary_file, 'r', encoding='utf-8') as f:
        markdown_content = f.read()

    # 转换为 HTML
    html_content = markdown_to_html(markdown_content, f"AI Newsletter 每日总结 - {date_str}")

    # 发送邮件
    sender = EmailSender()
    subject = f"📬 AI Newsletter 每日总结 - {date_str}"

    success_count = sender.send_to_recipients(
        subject=subject,
        content=html_content,
        content_type="html",
        attachments=attachments
    )

    return success_count > 0