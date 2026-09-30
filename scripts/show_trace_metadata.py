"""In metadata của trace trên Langfuse để làm bằng chứng (evidence 08/14).

UI observation của Langfuse v4 chỉ render ``input``/``output`` nên metadata
(correlation_id, prompt name/label/version, doc_count, token, cost) phải đọc
qua API observations.

Cách dùng::

    # trace mới nhất do chính mình vừa tạo
    python scripts/show_trace_metadata.py

    # một trace cụ thể (ví dụ trace của sự cố)
    python scripts/show_trace_metadata.py --trace-id bb42da6cee7c1e5b1ce360e0243be93e

Kết hợp lưu ra file để nộp kèm::

    python scripts/show_trace_metadata.py | Tee-Object submission/evidence/08-trace-metadata.txt
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio  # noqa: E402  (cần sys.path ở trên)

FIELDS = "core,basic,metadata,usage,model,prompt"
ROOT_NAME = "lab-agent-run"

# Các key do SDK/OTel tự thêm vào, trong đó có public key của Langfuse.
# Không được để lộ trong evidence nên lọc bỏ trước khi in.
INFRA_PREFIXES = ("scope.", "resourceAttributes.")


def _client():
    from dotenv import load_dotenv
    from langfuse import get_client

    load_dotenv(REPO_ROOT / ".env")
    return get_client()


def _fetch(client, hours: int, limit: int):
    now = dt.datetime.now(dt.timezone.utc)
    response = client.api.observations.get_many(
        fields=FIELDS,
        limit=limit,
        from_start_time=now - dt.timedelta(hours=hours),
        to_start_time=now,
    )
    return response.data


def _safe_metadata(value):
    """Bỏ các key hạ tầng (public key, resource attributes) khỏi metadata."""
    if not isinstance(value, dict):
        return value
    return {
        key: item
        for key, item in value.items()
        if not key.startswith(INFRA_PREFIXES)
    }


def _dump(observation) -> str:
    payload = {
        "model": getattr(observation, "model", None),
        "usage": getattr(observation, "usage_details", None),
        "cost": getattr(observation, "total_cost", None),
        "metadata": _safe_metadata(observation.metadata),
    }
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str)


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="In metadata trace từ Langfuse")
    parser.add_argument("--trace-id", help="Trace ID cần xem; bỏ trống để lấy trace mới nhất")
    parser.add_argument("--hours", type=int, default=6, help="Cửa sổ thời gian tìm kiếm (giờ)")
    parser.add_argument("--limit", type=int, default=200, help="Số observation lấy về")
    args = parser.parse_args()

    observations = _fetch(_client(), args.hours, args.limit)
    roots = [item for item in observations if item.name == ROOT_NAME]
    print(f"Tong observation trong {args.hours} gio: {len(observations)}")
    print(f"Root observation '{ROOT_NAME}': {len(roots)}")

    if not roots:
        print("Khong tim thay root observation nao. Hay chay API + load_test truoc.")
        return 1

    trace_id = args.trace_id or roots[0].trace_id
    rows = [item for item in observations if item.trace_id == trace_id]
    print(f"\nTRACE {trace_id} ({len(rows)} span)")
    for observation in rows:
        print(f"\n--- {observation.type} | {observation.name} ---")
        print(_dump(observation))

    root = next((item for item in rows if item.name == ROOT_NAME), None)
    safe_root_metadata = _safe_metadata(root.metadata) if root else None
    if isinstance(safe_root_metadata, dict):
        print("\n--- TOM TAT NOI LOG VOI TRACE ---")
        for key in ("correlation_id", "prompt_name", "prompt_label", "prompt_version", "prompt_source"):
            print(f"{key}: {safe_root_metadata.get(key)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
