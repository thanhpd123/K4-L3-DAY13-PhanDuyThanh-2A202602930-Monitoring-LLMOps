# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Phan Duy Thành
- **MSSV:** 2A202602930
- **Lớp:** K4-L3B
- **Repository URL:** `https://github.com/thanhpd123/K4-L3-DAY13-PhanDuyThanh-2A202602930-Monitoring-LLMOps`
- **Commit SHA cuối:**
- **Challenge ID:**
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602930`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence            | Đường dẫn                             |
| ------------------- | ------------------------------------- |
| Pytest cuối         | `evidence/01-pytest.png`              |
| Log validator       | `evidence/02-log-validator.png`       |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log      | `evidence/04-structured-log.png`      |
| PII redaction       | `evidence/05-pii-redaction.png`       |
| Trace list          | `evidence/06-trace-list.png`          |
| Trace waterfall     | `evidence/07-trace-waterfall.png`     |
| Trace metadata      | `evidence/08-trace-metadata.png`      |
| Prompt versions     | `evidence/09-prompt-versions.png`     |
| Prompt rollback     | `evidence/10-prompt-rollback.png`     |
| Dashboard runtime   | `evidence/11-dashboard-overview.png`  |
| Incident metric     | `evidence/12-incident-metric.png`     |
| Incident log        | `evidence/13-incident-log.png`        |
| Incident trace      | `evidence/14-incident-trace.png`      |

## 3. Kết quả kỹ thuật

| Nội dung                | Baseline          | Kết quả cuối     | Nhận xét                                                                                                                                                                   |
| ----------------------- | ----------------- | ---------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `validate_logs.py`      | 30/100            | **100/100**      | Baseline mất điểm ở 3 nhóm: log API không có `correlation_id`, thiếu metadata ngữ cảnh, và log cũ chưa đi qua scrubber. Sau CP1 cả 4 mục của validator đều PASSED.         |
| `validate_dashboard.py` | 6/6               | 6/6 (chưa đổi)   | Validator chỉ kiểm tra hợp đồng 6 panel trong `config/dashboard.yaml`, không kiểm tra dữ liệu hiển thị. Dashboard runtime được hoàn thiện ở CP2.                           |
| `pytest`                | 22 passed         | **26 passed**    | Thêm 4 test cho CCCD, thẻ thanh toán, địa chỉ Việt Nam và CMND/hộ chiếu.                                                                                                   |
| Số traces hợp lệ        | 0                 | sẽ đo ở CP2      | Trace đã được gửi lên project Langfuse cá nhân, nhưng prompt `day13-chat` chưa tồn tại nên app còn dùng prompt local fallback; phải tạo prompt trước khi đếm trace hợp lệ. |
| Số PII leak             | 0                 | **0**            | Validator tự quét lại JSON thô bằng detector riêng, nên kết quả 0 leak là bằng chứng độc lập chứ không phải do app tự khai báo.                                            |
| Latency P95 / TTFT P95  | 1996 ms / chưa đo | 1614 ms / 50 ms  | Số cuối lấy từ `/metrics` sau 13 request. Baseline chưa có snapshot P95 nên em ghi lại giá trị cao nhất của 9 request làm mốc tham chiếu.                                  |
| Retrieval success rate  | 100% (9/9)        | **100% (13/13)** | Mọi request đều có `tool_success = true` trong log `response_sent`.                                                                                                        |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:**
  Middleware chạy theo thứ tự: xóa context cũ trước (vì `contextvars` được tái sử dụng giữa các request, nếu không xóa thì request sau sẽ thừa hưởng thông tin của request trước) → nếu client/gateway đã gửi `x-request-id` hợp định dạng thì dùng lại, nếu thiếu thì sinh mới theo format `req-<8-hex>` → bind vào structlog để mọi log line của request tự động mang theo ID → lưu vào `request.state` để handler và agent dùng lại → trả ID kèm thời gian xử lý về header `x-request-id` và `x-response-time-ms`.
  Kiểm chứng: request thật trả về `x-request-id: req-fb6a5884` và hai log line `request_received`, `response_sent` của cùng request đều có `correlation_id: req-fb6a5884`. Khi chủ động gửi header `x-request-id: req-aaaaaaaa`, hệ thống giữ nguyên ID đó thay vì sinh mới — đúng hành vi cần thiết khi ID xuất phát từ gateway hoặc service phía trước.
- **Các metadata được ghi vào structured log:**
  Ngoài các trường bắt buộc (`ts`, `level`, `service`, `event`, `correlation_id`), mọi log line của API đều mang ngữ cảnh request: `user_id_hash` (SHA-256 rút gọn 12 ký tự, không bao giờ ghi `user_id` thô), `session_id`, `feature`, `model`, `env`. Riêng sự kiện `response_sent` ghi thêm các chỉ số vận hành: `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`. Đây chính là dữ liệu nguồn cho 6 panel của dashboard nên phải đủ ngay từ CP1.
- **Cách bảo đảm PII được scrub trước khi ghi:**
  Em dùng hai lớp phòng vệ độc lập. Lớp thứ nhất ở tầng ứng dụng: nội dung người dùng nhập và câu trả lời được rút gọn qua `summarize_text()` (đã scrub trước khi cắt ngắn), nên log chỉ chứa preview an toàn. Lớp thứ hai ở tầng ghi log: processor `scrub_event` được đặt ngay trước `JsonlFileProcessor` — tức sau bước `format_exc_info` — nên mọi chuỗi ở dạng cuối cùng, kể cả traceback, đều bị thay bằng token `[REDACTED_<LOẠI>]` trước khi chạm vào file. Việc scrub đi sâu vào dict/list lồng nhau giúp không sót PII nằm trong `payload` nhiều tầng.
  Bộ pattern hiện có: email, số điện thoại Việt Nam (cả `+84` và các kiểu phân cách dấu cách/dấu chấm/gạch ngang), CCCD 12 số, thẻ thanh toán, CMND 9 số, hộ chiếu, số tài khoản và địa chỉ. Thứ tự khai báo pattern được giữ có chủ đích: pattern cụ thể phải chạy trước pattern ngắn, nếu không số CCCD sẽ bị dán nhầm nhãn.
- **Cách kiểm chứng kết quả:**
  Thứ nhất, gửi request thật chứa cả email, số điện thoại và CCCD rồi đọc `data/logs.jsonl`: giá trị nhạy cảm được thay bằng `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CCCD]`, không còn chuỗi gốc. Thứ hai, chạy `python scripts/validate_logs.py` sau khi đã dọn log cũ: 20 bản ghi, 0 bản ghi thiếu trường bắt buộc, 0 bản ghi thiếu metadata, 12 correlation ID duy nhất, 0 PII leak, điểm cuối 100/100. Thứ ba, `python -m pytest -q` cho 26 test pass, trong đó có các test riêng cho email, số điện thoại, CCCD, thẻ, địa chỉ, CMND và hộ chiếu.

> Ghi chú về cách đo: `validate_logs.py` đọc **toàn bộ** `data/logs.jsonl`, nên log sinh trước khi sửa code vẫn bị tính. Em đã chuyển file log baseline ra ngoài repo trước khi đo lại để con số 100/100 phản ánh đúng hành vi mới.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:**
- **Cấu trúc root/retrieval/generation observations:**
- **Cách nối trace với log:**
- **Prompt name:**
- **Version/label baseline:**
- **Version/label candidate:**
- **Trace ID của mỗi version:**
- **Cách promote và rollback `production`:**

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:**
- **SLO và lý do chọn:**
- **Cách tính error budget:**
- **Ba alert và runbook tương ứng:**

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:**
- **Khoảng thời gian điều tra:**
- **Triệu chứng từ metrics:**
- **Log line và correlation ID liên quan:**
- **Trace ID và span gây ảnh hưởng:**
- **Root cause:**
- **Fix action:**
- **Preventive measure:**

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
- **Một lỗi/blocker đã gặp:**
- **Cách tìm nguyên nhân và xử lý:**
- **Cách hiểu luồng Metrics → Logs → Traces:**
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
- **Điều quan trọng nhất đã học:**
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
