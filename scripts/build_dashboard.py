"""Dựng dashboard runtime 6 panel từ structured log của ứng dụng.

Nguồn dữ liệu duy nhất là ``data/logs.jsonl`` (đúng như ``config/dashboard.yaml``
quy định). Script này chỉ dùng thư viện chuẩn + PyYAML đã có trong requirements
nên không cần cài thêm gì.

Cách dùng::

    python scripts/build_dashboard.py

Kết quả là ``dashboard/index.html`` — mở bằng trình duyệt để xem dashboard và
chụp evidence ``submission/evidence/11-dashboard-overview.png``.

Ngưỡng/đơn vị/time range không hard-code trong script mà đọc từ
``config/dashboard.yaml`` để dashboard runtime luôn khớp hợp đồng chấm điểm.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.cli import configure_utf8_stdio  # noqa: E402  (cần sys.path ở trên)

LOG_PATH = Path("data/logs.jsonl")
CONTRACT_PATH = REPO_ROOT / "config" / "dashboard.yaml"
CHALLENGE_PATH = REPO_ROOT / "config" / "challenge.json"
OUT_PATH = REPO_ROOT / "dashboard" / "index.html"

# Log ghi theo UTC; hiển thị theo giờ Việt Nam cho dễ đọc khi chụp evidence.
LOCAL_TZ = timezone(timedelta(hours=7))


def load_records(path: Path) -> list[dict]:
    """Đọc log JSONL, chỉ giữ bản ghi do API sinh ra (service == "api")."""
    if not path.exists():
        raise FileNotFoundError(f"Không thấy {path}. Hãy chạy API rồi load test trước.")

    records: list[dict] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError:
            continue
        if record.get("service") != "api":
            continue
        try:
            record["_ts"] = datetime.fromisoformat(str(record["ts"]).replace("Z", "+00:00"))
        except (KeyError, ValueError):
            continue
        records.append(record)

    if not records:
        raise ValueError("Chưa có bản ghi API nào trong data/logs.jsonl")
    return records


def percentile(values: list[float], rank: float) -> float:
    """Percentile nội suy tuyến tính (giống cách dashboard vận hành vẫn dùng)."""
    if not values:
        return 0.0
    ordered = sorted(values)
    if len(ordered) == 1:
        return float(ordered[0])
    position = (len(ordered) - 1) * (rank / 100)
    low, high = math.floor(position), math.ceil(position)
    if low == high:
        return float(ordered[int(position)])
    return ordered[low] + (ordered[high] - ordered[low]) * (position - low)


def mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def per_minute(records: list[dict], value_of) -> list[tuple[str, float]]:
    buckets: dict[str, float] = defaultdict(float)
    for record in records:
        key = record["_ts"].astimezone(LOCAL_TZ).strftime("%H:%M")
        value = value_of(record)
        if value is not None:
            buckets[key] += value
    return sorted(buckets.items())


def load_challenge(path: Path) -> dict | None:
    """Đọc config/challenge.json nếu có (file này không được commit).

    Dùng để hiển thị ngưỡng latency của challenge bên cạnh ngưỡng SLO,
    vì challenge có ngưỡng riêng (ví dụ 2000ms) chặt hơn SLO 3000ms.
    """
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def build_panels(records: list[dict], contract: dict, span_minutes: float, challenge: dict | None) -> list[dict]:
    panels_by_id = {panel["id"]: panel for panel in contract["dashboard"]["panels"]}
    received = [r for r in records if r.get("event") == "request_received"]
    sent = [r for r in records if r.get("event") == "response_sent"]
    failed = [r for r in records if r.get("event") == "request_failed"]

    latency = [r["latency_ms"] for r in sent if isinstance(r.get("latency_ms"), (int, float))]
    ttft = [r["ttft_ms"] for r in sent if isinstance(r.get("ttft_ms"), (int, float))]
    # tool_success xuất hiện ở cả response_sent (true) và request_failed (false),
    # nên retrieval success phải tính trên toàn bộ bản ghi có trường này.
    tool_flags = [r["tool_success"] for r in records if isinstance(r.get("tool_success"), bool)]
    costs = [r["cost_usd"] for r in sent if isinstance(r.get("cost_usd"), (int, float))]
    qualities = [r["quality_score"] for r in sent if isinstance(r.get("quality_score"), (int, float))]
    tokens_in = sum(r.get("tokens_in") or 0 for r in sent)
    tokens_out = sum(r.get("tokens_out") or 0 for r in sent)

    latency_p95 = percentile(latency, 95)
    # Tốc độ request tính trên khoảng thời gian thực có dữ liệu (không phải cả
    # cửa sổ 60 phút) để phản ánh đúng lưu lượng của buổi lab đang chạy.
    traffic_rate = len(received) / max(span_minutes, 1.0)
    error_rate = (len(failed) / len(received) * 100) if received else 0.0
    retrieval_success = (
        sum(1 for flag in tool_flags if flag) / len(tool_flags) * 100 if tool_flags else 0.0
    )
    error_types = Counter(r.get("error_type") or "unknown" for r in failed)

    def threshold_text(panel_id: str, value: float) -> tuple[str, bool]:
        threshold = panels_by_id[panel_id]["threshold"]
        ok = value <= threshold["value"] if threshold["operator"] == "lte" else value >= threshold["value"]
        return f"{threshold['aggregation']} {threshold['operator']} {threshold['value']:g}", ok

    latency_rule, latency_ok = threshold_text("latency", latency_p95)
    latency_detail = (
        f"P50 {percentile(latency, 50):,.0f} ms · P95 {latency_p95:,.0f} ms · "
        f"P99 {percentile(latency, 99):,.0f} ms · TTFT P95 {percentile(ttft, 95):,.0f} ms"
    )
    if challenge and isinstance(challenge.get("latency_threshold_ms"), (int, float)):
        limit = challenge["latency_threshold_ms"]
        verdict = "VƯỢT" if latency_p95 > limit else "ĐẠT"
        latency_detail += (
            f" · ngưỡng challenge ({challenge.get('challenge_id', 'challenge')}): "
            f"p95 ≤ {limit:,.0f} ms → {verdict}"
        )
    traffic_rule, traffic_ok = threshold_text("traffic", traffic_rate)
    errors_rule, errors_ok = threshold_text("errors", error_rate)
    cost_rule, cost_ok = threshold_text("cost", sum(costs))
    tokens_rule, tokens_ok = threshold_text("tokens", max(tokens_in, tokens_out))
    quality_rule, quality_ok = threshold_text("quality", mean(qualities))

    return [
        {
            "id": "latency",
            "title": panels_by_id["latency"]["title"],
            "question": "Request có chậm không? P50/P95/P99 và TTFT đang ở mức nào?",
            "value": f"{latency_p95:,.0f} ms (P95)",
            "detail": latency_detail,
            "unit": panels_by_id["latency"]["unit"],
            "rule": latency_rule,
            "ok": latency_ok,
            "series": per_minute(sent, lambda r: r.get("latency_ms")),
        },
        {
            "id": "traffic",
            "title": panels_by_id["traffic"]["title"],
            "question": "Hệ thống đang nhận bao nhiêu request theo thời gian?",
            "value": f"{traffic_rate:,.2f} req/phút",
            "detail": (
                f"{len(received)} request trong {span_minutes:,.1f} phút có dữ liệu "
                f"(cửa sổ dashboard {contract['dashboard']['time_range_minutes']} phút)"
            ),
            "unit": panels_by_id["traffic"]["unit"],
            "rule": traffic_rule,
            "ok": traffic_ok,
            "series": per_minute(received, lambda _: 1),
        },
        {
            "id": "errors",
            "title": panels_by_id["errors"]["title"],
            "question": "Error rate có tăng không, retrieval có đang fail không?",
            "value": f"{error_rate:,.2f} % error rate",
            "detail": (
                f"{len(failed)} lỗi / {len(received)} request · "
                f"retrieval success {retrieval_success:,.0f}% · "
                f"breakdown {dict(error_types) or 'không có lỗi'}"
            ),
            "unit": panels_by_id["errors"]["unit"],
            "rule": errors_rule,
            "ok": errors_ok,
            "series": per_minute(failed, lambda _: 1),
        },
        {
            "id": "cost",
            "title": panels_by_id["cost"]["title"],
            "question": "Chi phí có tăng bất thường không?",
            "value": f"${sum(costs):,.6f}",
            "detail": f"trung bình ${mean(costs):,.6f} mỗi request",
            "unit": panels_by_id["cost"]["unit"],
            "rule": cost_rule,
            "ok": cost_ok,
            "series": per_minute(sent, lambda r: r.get("cost_usd")),
        },
        {
            "id": "tokens",
            "title": panels_by_id["tokens"]["title"],
            "question": "Input/output token có dài bất thường không?",
            "value": f"{tokens_in:,} in / {tokens_out:,} out",
            "detail": f"tổng {tokens_in + tokens_out:,} token trên {len(sent)} phản hồi",
            "unit": panels_by_id["tokens"]["unit"],
            "rule": tokens_rule,
            "ok": tokens_ok,
            "series": per_minute(sent, lambda r: (r.get("tokens_in") or 0) + (r.get("tokens_out") or 0)),
        },
        {
            "id": "quality",
            "title": panels_by_id["quality"]["title"],
            "question": "Quality proxy có giảm dưới mức chấp nhận được không?",
            "value": f"{mean(qualities):,.3f} / 1",
            "detail": f"trung bình trên {len(qualities)} phản hồi đã chấm",
            "unit": panels_by_id["quality"]["unit"],
            "rule": quality_rule,
            "ok": quality_ok,
            "series": per_minute(sent, lambda r: r.get("quality_score")),
        },
    ]


def sparkline(series: list[tuple[str, float]]) -> str:
    if not series:
        return '<p class="muted">Chưa có dữ liệu trong cửa sổ này</p>'
    peak = max(value for _, value in series) or 1
    bars = "".join(
        f'<div class="bar" style="height:{max(3, round(value / peak * 100))}%" '
        f'title="{label}: {value:,.4g}"></div>'
        for label, value in series
    )
    first, last = series[0][0], series[-1][0]
    return (
        f'<div class="chart">{bars}</div>'
        f'<div class="axis"><span>{first}</span><span>{last}</span></div>'
    )


def render(records: list[dict], contract: dict, panels: list[dict], window_start, window_end, challenge: dict | None) -> str:
    total = len(records)
    cards = []
    for panel in panels:
        status_class = "ok" if panel["ok"] else "bad"
        status_text = "ĐẠT NGƯỠNG" if panel["ok"] else "VƯỢT NGƯỠNG"
        cards.append(
            f"""
        <section class="card" id="{panel['id']}">
          <header>
            <h2>{panel['title']}</h2>
            <span class="pill {status_class}">{status_text}</span>
          </header>
          <p class="question">{panel['question']}</p>
          <p class="value">{panel['value']}</p>
          <p class="detail">{panel['detail']}</p>
          {sparkline(panel['series'])}
          <footer>
            <span>Đơn vị: <strong>{panel['unit']}</strong></span>
            <span>Ngưỡng: <strong>{panel['rule']}</strong></span>
          </footer>
        </section>"""
        )

    generated_at = datetime.now(LOCAL_TZ).strftime("%Y-%m-%d %H:%M:%S")
    challenge_meta = ""
    if challenge:
        challenge_meta = (
            f"<span>Challenge: <strong>{challenge.get('challenge_id', 'không rõ')}</strong>"
            f" — {challenge.get('incident', 'không rõ')} (ngưỡng latency "
            f"{challenge.get('latency_threshold_ms', '?')} ms)</span>"
        )
    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8" />
  <title>{contract['dashboard']['title']} — dashboard runtime</title>
  <style>
    :root {{ color-scheme: dark; }}
    * {{ box-sizing: border-box; }}
    body {{ margin: 0; padding: 28px 32px 48px; background: #0f172a; color: #e2e8f0;
           font-family: "Segoe UI", system-ui, sans-serif; }}
    h1 {{ margin: 0 0 6px; font-size: 26px; }}
    .meta {{ display: flex; flex-wrap: wrap; gap: 18px; margin: 12px 0 26px;
             font-size: 14px; color: #94a3b8; }}
    .meta strong {{ color: #e2e8f0; }}
    .grid {{ display: grid; grid-template-columns: repeat(3, minmax(280px, 1fr)); gap: 18px; }}
    .card {{ background: #16233b; border: 1px solid #23324e; border-radius: 12px;
             padding: 16px 18px 14px; display: flex; flex-direction: column; gap: 8px; }}
    .card header {{ display: flex; justify-content: space-between; align-items: center; gap: 10px; }}
    .card h2 {{ margin: 0; font-size: 15px; text-transform: uppercase; letter-spacing: .04em; color: #cbd5f5; }}
    .pill {{ font-size: 11px; font-weight: 700; padding: 3px 9px; border-radius: 999px; white-space: nowrap; }}
    .pill.ok {{ background: #14532d; color: #86efac; }}
    .pill.bad {{ background: #7f1d1d; color: #fecaca; }}
    .question {{ margin: 0; font-size: 13px; color: #94a3b8; min-height: 34px; }}
    .value {{ margin: 0; font-size: 24px; font-weight: 700; color: #f8fafc; }}
    .detail {{ margin: 0; font-size: 12.5px; color: #cbd5f5; min-height: 32px; }}
    .chart {{ display: flex; align-items: flex-end; gap: 3px; height: 62px;
              padding: 6px 8px; background: #0b1120; border-radius: 8px; }}
    .bar {{ flex: 1; min-width: 4px; background: linear-gradient(180deg, #60a5fa, #2563eb);
            border-radius: 3px 3px 0 0; }}
    .axis {{ display: flex; justify-content: space-between; font-size: 11px; color: #64748b; }}
    footer {{ display: flex; justify-content: space-between; gap: 12px; font-size: 12px;
              color: #94a3b8; border-top: 1px solid #23324e; padding-top: 8px; }}
    .muted {{ color: #64748b; font-size: 12px; }}
  </style>
</head>
<body>
  <h1>{contract['dashboard']['title']} — Dashboard runtime</h1>
  <div class="meta">
    <span>Nguồn dữ liệu: <strong>{contract['dashboard']['panels'][0]['source']}</strong></span>
    <span>Time range: <strong>{window_start} → {window_end} (UTC+7, {contract['dashboard']['time_range_minutes']} phút)</strong></span>
    <span>Refresh: <strong>{contract['dashboard']['refresh_seconds']}s</strong></span>
    <span>Bản ghi API trong cửa sổ: <strong>{total}</strong></span>
    <span>Dựng lúc: <strong>{generated_at}</strong></span>
    {challenge_meta}
  </div>
  <div class="grid">{''.join(cards)}
  </div>
</body>
</html>
"""


def main() -> int:
    configure_utf8_stdio()
    parser = argparse.ArgumentParser(description="Dựng dashboard runtime 6 panel của Day 13")
    parser.add_argument("--log", type=Path, default=LOG_PATH)
    parser.add_argument("--contract", type=Path, default=CONTRACT_PATH)
    parser.add_argument("--out", type=Path, default=OUT_PATH)
    args = parser.parse_args()

    contract = yaml.safe_load(args.contract.read_text(encoding="utf-8"))
    challenge = load_challenge(CHALLENGE_PATH)
    records = load_records(args.log)

    latest = max(record["_ts"] for record in records)
    window_start_dt = latest - timedelta(minutes=contract["dashboard"]["time_range_minutes"])
    windowed = [record for record in records if record["_ts"] >= window_start_dt]
    earliest = min(record["_ts"] for record in windowed)
    span_minutes = max((latest - earliest).total_seconds() / 60, 1.0)

    panels = build_panels(windowed, contract, span_minutes, challenge)
    html = render(
        windowed,
        contract,
        panels,
        window_start_dt.astimezone(LOCAL_TZ).strftime("%H:%M:%S"),
        latest.astimezone(LOCAL_TZ).strftime("%H:%M:%S"),
        challenge,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(html, encoding="utf-8")

    print(f"Đã dựng dashboard: {args.out}")
    print(f"Bản ghi trong cửa sổ: {len(windowed)} (tổng {len(records)})")
    for panel in panels:
        state = "ĐẠT" if panel["ok"] else "VƯỢT"
        print(f"  [{state}] {panel['id']:<8} {panel['value']:<28} ngưỡng {panel['rule']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
