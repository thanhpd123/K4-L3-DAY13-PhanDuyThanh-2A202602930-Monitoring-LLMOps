from __future__ import annotations

import hashlib
import re

PII_PATTERNS: dict[str, str] = {
    # Thứ tự trong dict rất quan trọng: pattern dài/cụ thể phải chạy trước pattern ngắn,
    # nếu không số CCCD sẽ bị dán nhầm nhãn thành số điện thoại hoặc số tài khoản.
    "email": r"[\w\.-]+@[\w\.-]+\.\w+",
    "phone_vn": r"(?<!\d)(?:\+84|0)(?:[ .-]?\d){9}(?!\d)",
    "credit_card": r"\b\d{4}[- ]?\d{4}[- ]?\d{4}[- ]?\d{4}\b",
    "cccd": r"\b\d{12}\b",
    "cmnd": r"\b\d{9}\b",
    "passport_vn": r"\b[A-Z]\d{7}\b",
    "bank_account_vn": r"\b\d{10,14}\b",
    # Nhận cả dạng có dấu và không dấu, vì người dùng thường gõ không dấu khi chat.
    "address_vn": r"(?i)\b(?:địa chỉ|dia chi|đ/c|address)\b\s*[:：]?\s*[^\n,;]{5,}",
}


def scrub_text(text: str) -> str:
    """Thay mọi PII tìm thấy bằng token [REDACTED_<LOAI>] trước khi ghi log."""
    safe = text
    for name, pattern in PII_PATTERNS.items():
        safe = re.sub(pattern, f"[REDACTED_{name.upper()}]", safe)
    return safe


def summarize_text(text: str, max_len: int = 80) -> str:
    safe = scrub_text(text).strip().replace("\n", " ")
    return safe[:max_len] + ("..." if len(safe) > max_len else "")


def hash_user_id(user_id: str) -> str:
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:12]
