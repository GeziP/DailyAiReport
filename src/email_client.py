"""IMAP 邮件客户端 - 支持 QQ 邮箱"""

import imaplib
import email
from email.header import decode_header
from email.message import Message
from datetime import datetime, timedelta
from typing import Optional
from dataclasses import dataclass

from .config import Config


@dataclass
class EmailMessage:
    """邮件数据类"""
    message_id: str  # 用于去重
    subject: str
    sender: str
    sender_name: str
    date: datetime
    body_text: str
    body_html: str


class EmailClient:
    """IMAP 邮件客户端"""

    def __init__(self):
        self.connection: Optional[imaplib.IMAP4_SSL] = None

    def connect(self) -> bool:
        """连接到 IMAP 服务器"""
        try:
            self.connection = imaplib.IMAP4_SSL(
                Config.IMAP_SERVER,
                Config.IMAP_PORT
            )
            self.connection.login(
                Config.QQ_EMAIL,
                Config.QQ_EMAIL_AUTH_CODE
            )
            return True
        except Exception as e:
            print(f"连接 IMAP 服务器失败: {e}")
            return False

    def disconnect(self):
        """断开连接"""
        if self.connection:
            try:
                self.connection.close()
                self.connection.logout()
            except:
                pass
            self.connection = None

    def _decode_header_value(self, value: str) -> str:
        """解码邮件头部值"""
        if not value:
            return ""

        decoded_parts = decode_header(value)
        result = []
        for part, encoding in decoded_parts:
            if isinstance(part, bytes):
                result.append(part.decode(encoding or "utf-8", errors="ignore"))
            else:
                result.append(part)
        return "".join(result)

    def _get_email_body(self, msg: Message) -> tuple[str, str]:
        """提取邮件正文（纯文本和 HTML）"""
        body_text = ""
        body_html = ""

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                charset = part.get_content_charset() or "utf-8"

                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        content = payload.decode(charset, errors="ignore")
                        if content_type == "text/plain":
                            body_text = content
                        elif content_type == "text/html":
                            body_html = content
                except Exception:
                    pass
        else:
            content_type = msg.get_content_type()
            charset = msg.get_content_charset() or "utf-8"
            try:
                payload = msg.get_payload(decode=True)
                if payload:
                    content = payload.decode(charset, errors="ignore")
                    if content_type == "text/plain":
                        body_text = content
                    elif content_type == "text/html":
                        body_html = content
            except Exception:
                pass

        return body_text, body_html

    def _parse_sender(self, sender: str) -> tuple[str, str]:
        """解析发件人，返回 (邮箱, 名称)"""
        if not sender:
            return "", ""

        sender = self._decode_header_value(sender)

        # 格式: "Name <email@example.com>" 或 "email@example.com"
        if "<" in sender and ">" in sender:
            name = sender.split("<")[0].strip().strip('"')
            email_addr = sender.split("<")[1].split(">")[0].strip()
            return email_addr, name
        else:
            return sender.strip(), sender.strip()

    def fetch_emails_by_sender(
        self,
        sender_email: str,
        since_date: Optional[datetime] = None,
        before_date: Optional[datetime] = None
    ) -> list[EmailMessage]:
        """
        获取指定发件人在日期范围内的邮件

        Args:
            sender_email: 发件人邮箱地址
            since_date: 开始日期（含），默认昨天
            before_date: 结束日期（不含），默认明天

        Returns:
            邮件列表
        """
        if not self.connection:
            raise RuntimeError("未连接到 IMAP 服务器")

        # 默认读取昨天和今天的邮件（避免遗漏）
        if since_date is None:
            since_date = datetime.now() - timedelta(days=1)
        if before_date is None:
            before_date = datetime.now() + timedelta(days=1)

        emails = []

        try:
            self.connection.select("INBOX")

            # IMAP 日期格式: 24-Mar-2026
            since_str = since_date.strftime("%d-%b-%Y")
            before_str = before_date.strftime("%d-%b-%Y")

            # 使用 SINCE 和 BEFORE 搜索日期范围
            status, messages = self.connection.search(
                None,
                f'SINCE "{since_str}"',
                f'BEFORE "{before_str}"'
            )

            if status != "OK":
                return emails

            email_ids = messages[0].split()

            for email_id in email_ids:
                status, msg_data = self.connection.fetch(email_id, "(RFC822)")
                if status != "OK":
                    continue

                raw_email = msg_data[0][1]
                msg = email.message_from_bytes(raw_email)

                # 解析发件人
                sender_header = msg.get("From", "")
                sender_addr, sender_name = self._parse_sender(sender_header)

                # 检查发件人是否匹配
                if sender_email.lower() not in sender_addr.lower():
                    continue

                # 获取 Message-ID 用于去重
                message_id = msg.get("Message-ID", "")

                # 解析主题
                subject = self._decode_header_value(msg.get("Subject", ""))

                # 解析日期
                date_header = msg.get("Date", "")
                try:
                    parsed_date = email.utils.parsedate_to_datetime(date_header)
                except:
                    parsed_date = datetime.now()

                # 获取正文
                body_text, body_html = self._get_email_body(msg)

                emails.append(EmailMessage(
                    message_id=message_id,
                    subject=subject,
                    sender=sender_addr,
                    sender_name=sender_name,
                    date=parsed_date,
                    body_text=body_text,
                    body_html=body_html
                ))

        except Exception as e:
            print(f"获取邮件失败: {e}")

        return emails

    def fetch_emails_by_senders(
        self,
        sender_emails: list[str],
        since_date: Optional[datetime] = None,
        before_date: Optional[datetime] = None
    ) -> dict[str, list[EmailMessage]]:
        """
        获取多个发件人在日期范围内的邮件

        Args:
            sender_emails: 发件人邮箱列表
            since_date: 开始日期（含），默认昨天
            before_date: 结束日期（不含），默认明天

        Returns:
            {发件人邮箱: 邮件列表}
        """
        result = {}

        for sender in sender_emails:
            emails = self.fetch_emails_by_sender(sender, since_date, before_date)
            if emails:
                result[sender] = emails

        return result

    def fetch_today_emails(self) -> dict[str, list[EmailMessage]]:
        """
        获取昨天和今天所有已配置 Newsletter 的邮件

        Returns:
            {发件人邮箱: 邮件列表}
        """
        import yaml

        # 加载 Newsletter 配置
        with open(Config.NEWSLETTERS_CONFIG, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)

        # 获取已启用的发件人列表
        senders = [
            nl["sender"] for nl in config.get("newsletters", [])
            if nl.get("enabled", True)
        ]

        return self.fetch_emails_by_senders(senders)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
        return False