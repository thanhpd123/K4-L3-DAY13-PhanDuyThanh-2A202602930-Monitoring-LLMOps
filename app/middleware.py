from __future__ import annotations

import re
import time
import uuid

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from structlog.contextvars import bind_contextvars, clear_contextvars

REQUEST_ID_HEADER = "x-request-id"

# Chỉ chấp nhận x-request-id do client gửi nếu nó đúng định dạng an toàn;
# nếu không ta tự sinh ID mới để tránh log bị chèn chuỗi lạ.
SAFE_REQUEST_ID = re.compile(r"^[A-Za-z0-9._:\-]{1,128}$")


def new_correlation_id() -> str:
    """Sinh correlation ID mới theo đúng format req-<8-char-hex>."""
    return f"req-{uuid.uuid4().hex[:8]}"


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # 1) Xóa context cũ trước. contextvars được tái sử dụng giữa các request nên
        #    nếu không xóa, request sau sẽ thừa hưởng user/session của request trước.
        clear_contextvars()

        # 2) Tái sử dụng x-request-id nếu client/gateway đã gửi, ngược lại tự sinh mới.
        incoming_request_id = (request.headers.get(REQUEST_ID_HEADER) or "").strip()
        correlation_id = (
            incoming_request_id
            if SAFE_REQUEST_ID.match(incoming_request_id)
            else new_correlation_id()
        )

        # 3) Bind vào structlog: từ đây mọi log line của request đều mang correlation_id.
        bind_contextvars(correlation_id=correlation_id)

        request.state.correlation_id = correlation_id
        
        start = time.perf_counter()
        response = await call_next(request)
        
        # 4) Trả ID và thời gian xử lý về response để client đối chiếu với log/trace.
        elapsed_ms = (time.perf_counter() - start) * 1000
        response.headers[REQUEST_ID_HEADER] = correlation_id
        response.headers["x-response-time-ms"] = f"{elapsed_ms:.2f}"

        return response
