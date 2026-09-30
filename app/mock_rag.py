from __future__ import annotations

import time

from .incidents import STATE
from .pii import summarize_text
from .tracing import get_langfuse_client, observe

CORPUS = {
    "refund": ["Refunds are available within 7 days with proof of purchase."],
    "monitoring": ["Metrics detect incidents, logs identify affected requests, traces localize the root cause."],
    "policy": ["Do not expose PII in logs. Use sanitized summaries only."],
}


# capture_input/output=False: không đẩy câu hỏi thô của người dùng lên Langfuse;
# chỉ ghi preview đã scrub và số tài liệu bằng update_current_span bên dưới.
@observe(name="retrieval", as_type="retriever", capture_input=False, capture_output=False)
def retrieve(message: str) -> list[str]:
    client = get_langfuse_client()
    if STATE["tool_fail"]:
        # Span retrieval được đánh dấu lỗi kèm lý do, phục vụ điều tra incident.
        client.update_current_span(
            status_message="Vector store timeout",
            metadata={"tool_success": False, "error_type": "RuntimeError"},
        )
        raise RuntimeError("Vector store timeout")
    if STATE["rag_slow"]:
        time.sleep(2.5)
    lowered = message.lower()
    docs = next((value for key, value in CORPUS.items() if key in lowered), None)
    if docs is None:
        docs = ["No domain document matched. Use general fallback answer."]
    client.update_current_span(
        metadata={
            "query_preview": summarize_text(message),
            "doc_count": len(docs),
            "tool_success": True,
        }
    )
    return docs
