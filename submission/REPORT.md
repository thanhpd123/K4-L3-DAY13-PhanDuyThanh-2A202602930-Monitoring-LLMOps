# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Phan Duy Thành
- **MSSV:** 2A202602930
- **Lớp:** K4-L3B
- **Repository URL:** `https://github.com/thanhpd123/K4-L3-DAY13-PhanDuyThanh-2A202602930-Monitoring-LLMOps`
- **Commit SHA cuối:** điền sau khi commit cuối cùng
- **Challenge ID:** chưa có — Lab Coach chưa release `config/challenge.json` cho lớp, nên mục 7 dưới đây là điều tra practice chứ không phải challenge chính thức.
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602930`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence                               | Đường dẫn                                 |
| -------------------------------------- | ----------------------------------------- |
| Pytest cuối                            | `evidence/01-pytest.png`                  |
| Log validator                          | `evidence/02-log-validator.png`           |
| Dashboard validator                    | `evidence/03-dashboard-validator.png`     |
| Structured log                         | `evidence/04-structured-log.png`          |
| PII redaction                          | `evidence/05-pii-redaction.png`           |
| Trace list                             | `evidence/06-trace-list.png`              |
| Trace waterfall                        | `evidence/07-trace-waterfall.png`         |
| Trace metadata                         | `evidence/08-trace-metadata.png`          |
| Prompt versions                        | `evidence/09-prompt-versions.png`         |
| Prompt rollback                        | `evidence/10-prompt-rollback.png`         |
| Dashboard runtime                      | `evidence/11-dashboard-overview.png`      |
| Incident metric                        | `evidence/12-incident-metric.png`         |
| Incident log                           | `evidence/13-incident-log.png`            |
| Incident trace                         | `evidence/14-incident-trace.png`          |
| Trace metadata (API Langfuse)          | `evidence/08-trace-metadata.txt`          |
| Incident trace metadata (API Langfuse) | `evidence/14-incident-trace-metadata.txt` |

> Nguồn của ảnh `11-dashboard-overview.png` là `dashboard/index.html`, sinh bằng `scripts/build_dashboard.py` đọc trực tiếp `data/logs.jsonl`.

## 3. Kết quả kỹ thuật

| Nội dung                | Baseline          | Kết quả cuối                                                    | Nhận xét                                                                                                                                                                                                      |
| ----------------------- | ----------------- | --------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `validate_logs.py`      | 30/100            | **100/100**                                                     | Baseline mất điểm ở 3 nhóm: log API không có `correlation_id`, thiếu metadata ngữ cảnh, và log cũ chưa đi qua scrubber. Sau CP1 cả 4 mục của validator đều PASSED.                                            |
| `validate_dashboard.py` | 6/6               | 6/6 (chưa đổi)                                                  | Validator chỉ kiểm tra hợp đồng 6 panel trong `config/dashboard.yaml`, không kiểm tra dữ liệu hiển thị. Dashboard runtime được hoàn thiện ở CP2.                                                              |
| `pytest`                | 22 passed         | **26 passed**                                                   | Thêm 4 test cho CCCD, thẻ thanh toán, địa chỉ Việt Nam và CMND/hộ chiếu.                                                                                                                                      |
| Số traces hợp lệ        | 0                 | **≥ 10**, có trace cho cả `baseline`, `production`, `candidate` | Langfuse đã ghi trace của cả ba label; metadata mỗi trace có `correlation_id` + `prompt_name/label/version`. Em đối chiếu chéo bằng API observations của Langfuse chứ không chỉ nhìn UI.                      |
| Số PII leak             | 0                 | **0**                                                           | Validator tự quét lại JSON thô bằng detector riêng, nên kết quả 0 leak là bằng chứng độc lập chứ không phải do app tự khai báo.                                                                               |
| Latency P95 / TTFT P95  | 1996 ms / chưa đo | **153 ms / 51 ms** (run sạch 20 request)                        | Con số cuối lấy từ `/metrics` sau 20 request không có sự cố. Khi bật incident `rag_slow`, P95 nhảy lên 2653 ms nhưng TTFT P95 vẫn 51 ms — đây là bằng chứng định vị lỗi nằm ở bước retrieval, không phải LLM. |
| Retrieval success rate  | 100% (9/9)        | 100% (run sạch) → 93% trong cửa sổ có sự cố                     | 4 request lỗi `RuntimeError` làm retrieval success giảm còn 93%, đồng thời error rate trong cửa sổ đo được 6,67% — đã vượt ngưỡng 2% của guardrail.                                                           |

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
  Project cá nhân `day13-k4-l3b-2A202602930`, trang Tracing lọc `Is Root Observation = True`, `Name = lab-agent-run`, `Environment = dev`. Ngoài việc xem trên UI, em truy vấn API observations của Langfuse để đối chiếu `trace_id` với `correlation_id` trong log, nên trace chắc chắn thuộc workload do chính em chạy.
- **Cấu trúc root/retrieval/generation observations:**
  `@observe` trên `LabAgent.run` tạo root `lab-agent-run` (type agent, trace name `day13-agent-request`); `retrieve()` được bọc `as_type="retriever"`; `FakeLLM.generate()` được bọc `as_type="generation"` và tự gọi `update_current_generation(model, usage_details, cost_details)`. Cả ba đều để `capture_input=False, capture_output=False` nên Langfuse không lưu nội dung thô của người dùng — chỉ có `query_preview` đã scrub, `doc_count`, `ttft_ms`, token và cost. Cây trace đọc được là: `day13-agent-request` → `lab-agent-run` → (`retrieval`, `generation`).
- **Cách nối trace với log:**
  `correlation_id` sinh ở middleware được bind vào structlog và truyền xuống `LabAgent.run`, tại đó ghi vào trace metadata (`metadata.correlation_id`). Đã đối chiếu thực tế: `trace_id c5870547c480b4a09e6a4e1539d35478` ↔ `correlation_id req-499f4ec5`. Trên Langfuse chỉ cần search `metadata.correlation_id:req-...` là ra đúng request cần điều tra.
- **Prompt name:** `day13-chat`, giữ đúng ba biến `{{feature}}`, `{{docs}}`, `{{message}}`.
- **Version/label baseline:** version **1** (54 ký tự), labels `baseline` + `production`.
- **Version/label candidate:** version **3** (101 ký tự, thêm ràng buộc "trả lời tối đa 3 bullet, mỗi bullet dưới 20 từ"), label `candidate`. Version 2 đã được tạo nhưng trùng nội dung version 1 (cùng 54 ký tự) nên không dùng làm candidate — phải tạo version 3 mới có khác biệt thật để so sánh.
- **Trace ID của mỗi version:**
  - v1 / `baseline`: `c5870547c480b4a09e6a4e1539d35478` (ứng với `req-499f4ec5`) và `4fe9a94c0b3f1b4963637907de427a88` (`req-96218184`).
  - v3 / `candidate`: `292b06a766321ad28f1c20cf7235e385` (`req-1777839b`) và `3ec93168c9e886d3efdfc770b14b2868` (`req-06ba8957`).
- **Số liệu so sánh trên cùng một bộ 10 input:**

  | Chỉ số                 | `baseline` (v1) | `candidate` (v3) | Thay đổi   |
  | ---------------------- | --------------- | ---------------- | ---------- |
  | Tổng input token       | 338             | 456              | **+34,9%** |
  | Tổng cost (10 request) | $0,017634       | $0,022578        | **+28,0%** |
  | Latency mỗi request    | ~152 ms         | ~152 ms          | không đổi  |
  | Quality proxy          | 0,8–0,9         | 0,8–0,9          | không đổi  |

  Đọc theo hướng vận hành: prompt v3 làm chi phí mỗi request tăng gần 30% mà không cải thiện latency hay quality, nên đủ căn cứ để rollback.
- **Cách promote và rollback `production`:**
  Label `production` chỉ trỏ tới một version tại mỗi thời điểm. Promote = mở prompt labels của version mới, tick `production`, Save (Langfuse tự gỡ label khỏi version cũ). Rollback = mở prompt labels của version 1, tick `production`, Save. App không cần sửa code vì chỉ đọc `LANGFUSE_PROMPT_NAME` và `LANGFUSE_PROMPT_LABEL` từ `.env`. Em đã chạy thử promote/rollback theo đúng cơ chế này và chụp lại ở evidence `09` và `10`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:**
  Dashboard runtime là `dashboard/index.html`, sinh bằng `scripts/build_dashboard.py` đọc trực tiếp `data/logs.jsonl` và đọc ngưỡng/đơn vị/time range từ `config/dashboard.yaml`. Sáu panel: Latency (P50/P95/P99 + TTFT P95), Traffic (request/phút), Errors (error rate + breakdown `error_type` + retrieval success), Cost (tổng theo phút), Tokens (in/out) và Quality (mean `quality_score`). Mỗi panel hiển thị đơn vị, ngưỡng, trạng thái ĐẠT/VƯỢT ngưỡng và sparkline theo phút; vì ngưỡng được đọc từ contract nên dashboard không thể lệch hợp đồng chấm điểm.
- **SLO và lý do chọn:**
  SLO `fast_successful_requests`: 99,5% request có `latency_ms ≤ 3000` trong cửa sổ 28 ngày. Ngưỡng 3000 ms chọn từ baseline thật của bài: P50 ≈ 152 ms, P95 ≈ 153 ms, TTFT P95 ≈ 51 ms — rộng hơn tail latency bình thường nhưng vẫn bắt được sự cố retrieval chậm (khi bật `rag_slow`, P95 nhảy lên 2653 ms, tức gần 90% ngưỡng).
- **Cách tính error budget:**
  SLO 99,5% ⇒ error budget 0,5%. Với 10.000 request, tối đa 50 request được phép lỗi hoặc chậm hơn 3000 ms. Trong cửa sổ điều tra của buổi lab, error rate đo được 6,67% (4 lỗi/60 request) — vượt xa 0,5%, nghĩa là chỉ vài phút sự cố retrieval cũng đã tiêu hết error budget của cả cửa sổ 28 ngày, nên hệ thống phải dừng mọi thay đổi rủi ro cho tới khi hồi phục.
- **Ba alert và runbook tương ứng:**
  1. `HighLatencyP95` — warning, `p95(latency_ms) > 3000` liên tục **5 phút**, Slack `#k4-l3b-alerts`, owner `student-2A202602930`, runbook `docs/alerts.md#alert-1`.
  2. `RetrievalFailureSpike` — critical, `error_rate > 2%` hoặc `retrieval success < 90%` liên tục **10 phút**, cùng kênh/owner, runbook `docs/alerts.md#alert-2`.
  3. `CostAndTokenSpike` — warning, tổng `cost_usd > 2,5` hoặc `tokens_out` tăng gấp 3 lần baseline liên tục **15 phút**, cùng kênh/owner, runbook `docs/alerts.md#alert-3`.

  Cả ba đều symptom-based (mô tả triệu chứng thấy được trên dashboard, không gọi tên hàm nội bộ), đều có `duration` để tránh báo động vì vài request lẻ, và đều ghi rõ ba bước kiểm tra + mitigation trong `docs/alerts.md`.

## 7. Điều tra challenge

> Trạng thái: Lab Coach chưa release `config/challenge.json` cho lớp, nên phần điều tra dưới đây được thực hiện bằng practice scenario có sẵn của bài (`--scenario`), không phải challenge chính thức. Toàn bộ số liệu vẫn là số thật chạy trên chính hệ thống của bài.

- **Challenge ID:** chưa có (chưa được release).
- **Khoảng thời gian điều tra:** 03:47–03:55 ngày 30/09/2026 (giờ Việt Nam), với hai scenario `rag_slow` và `tool_fail`.
- **Triệu chứng từ metrics:**
  Trước sự cố: P50 152 ms, P95 153 ms, TTFT P95 51 ms, error rate 0%. Sau khi bật `rag_slow`: P50 vẫn 152 ms nhưng **P95 nhảy lên 2653 ms** và P99 2654 ms, trong khi **TTFT P95 gần như không đổi (51 ms)**. Sau đó bật `tool_fail`: error rate lên **6,67%** (vượt ngưỡng 2%), `error_breakdown = {RuntimeError: 4}` và retrieval success tụt từ 100% xuống ~93%.
  Việc TTFT đứng yên là mấu chốt: nếu LLM chậm thì TTFT phải tăng; TTFT không tăng nghĩa là thời gian bị tiêu ở bước lấy context.
- **Log line và correlation ID liên quan:**
  - Request chậm: `correlation_id=req-30d656eb`, `event=response_sent`, `latency_ms=2653`, `ttft_ms=50`, `tool_name=retrieval`, `tool_success=true`.
  - Request lỗi: `correlation_id=req-833948fb`, `event=request_failed`, `error_type=RuntimeError`, `tool_name=retrieval`, `tool_success=false`, `payload.detail="Vector store timeout"`.
- **Trace ID và span gây ảnh hưởng:**
  `trace_id=bb42da6cee7c1e5b1ce360e0243be93e` (ứng với `req-30d656eb`). Trong waterfall, span **`retrieval` chiếm gần trọn ~2,5 giây**, còn span `generation` giữ nguyên như bình thường; ở request lỗi, span `retrieval` mang status lỗi `Vector store timeout`.
- **Root cause:** lỗi nằm ở bước retrieval — vector store trả chậm ~2,5 giây và có lúc timeout. Không phải LLM (TTFT không đổi) và cũng không phải prompt (cùng một version cho cả request nhanh lẫn request chậm trong cùng khoảng thời gian).
- **Fix action:** tắt scenario đang gây lỗi rồi chạy lại cùng concurrency để xác nhận P95 về ~153 ms và error rate về 0; nếu sự cố xuất phát từ prompt mới thì rollback label `production` về version cũ.
- **Preventive measure:** giữ alert `HighLatencyP95` (P95 > 3000 ms trong 5 phút) và `RetrievalFailureSpike` (error rate > 2% hoặc retrieval success < 90% trong 10 phút); panel **Errors** luôn hiển thị retrieval success kèm error breakdown; runbook bắt đầu bằng đúng ba bước "xem dashboard → lọc log lấy `correlation_id` → mở trace so sánh span retrieval/generation".

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
  Em tách child observation bằng cách bọc `@observe` lên chính `retrieve()` và `FakeLLM.generate()` thay vì gọi `start_as_current_observation` ngay trong `LabAgent.run`. Cách này vẫn cho đúng cây span `agent → retriever/generation`, nhưng không phá test contract `tests/test_agent_prompt_trace.py` (test dùng client giả chỉ hỗ trợ `get_prompt` và `update_current_span`). Đổi lại, em phải đưa đơn giá token vào `mock_llm.py` thành hằng số dùng chung để log cost và trace cost không lệch nhau.
- **Một lỗi/blocker đã gặp:**
  Ban đầu app luôn rơi vào `local-fallback` vì prompt `day13-chat` chưa tồn tại trên Langfuse (404 mỗi request), và sau đó version 2 được tạo nhưng trùng nội dung version 1 nên hai label cho ra kết quả giống hệt nhau, không thể so sánh. Một lỗi nữa ở phía em là panel Errors tính retrieval success chỉ từ `response_sent`, nên khi có request lỗi qua `request_failed` thì panel vẫn hiển thị 100% — sai so với hợp đồng.
- **Cách tìm nguyên nhân và xử lý:**
  Với prompt: em truy vấn trực tiếp Langfuse để xem mỗi label đang trỏ tới version nào và độ dài prompt từng version, nhờ đó phát hiện version 2 dài đúng 54 ký tự như version 1 và tạo version 3 thật khác. Với panel Errors: em đối chiếu lại câu `query` trong `config/dashboard.yaml` ("count(tool_success == true) / count(tool_success != null)") và sửa cách tính cho đúng — lấy `tool_success` trên toàn bộ bản ghi chứ không chỉ trên `response_sent`.
- **Cách hiểu luồng Metrics → Logs → Traces:**
  Metrics (dashboard) nói hệ thống đang xấu ở *chỉ số nào* và *khoảng thời gian nào*; log nói *request cụ thể nào* bị ảnh hưởng qua `correlation_id`; trace nói *bước nào* gây ra vấn đề. Trong lần điều tra này, metrics chỉ ra P95 tăng 17 lần, log cho một `correlation_id` cụ thể, và trace kết luận span `retrieval` chiếm gần trọn 2,5 giây. Ba nguồn phải cùng chỉ về một nguyên nhân thì kết luận mới hợp lệ.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
  Prompt là một phần của hệ thống chứ không phải text phụ trợ: cùng một input nhưng đổi sang version 3 là cost tăng ~28% mà quality và latency không đổi. Không có `prompt_version` trong trace thì không thể quy trách nhiệm cho version nào. SLO/error budget cho biết khi nào được phép tiếp tục thay đổi và khi nào phải dừng lại; rollback bằng label là cách khôi phục nhanh nhất mà không cần deploy code.
- **Điều quan trọng nhất đã học:**
  Việc "che PII trước khi ghi log" và "ghi đủ metadata ngữ cảnh" không phải hai việc đối lập — chính vì có `correlation_id` và metadata an toàn mà em mới truy ngược được từ log sang trace; và cũng nhờ scrubber hai lớp mà có thể chia sẻ log/trace làm bằng chứng mà không lo lộ dữ liệu người dùng.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**
  `config/challenge.json` chưa được release nên mục 7 là điều tra practice; khi có file chính thức em sẽ chạy lại `scripts/inject_incident.py` và `scripts/load_test.py --challenge --concurrency 5` rồi cập nhật lại mục này. Với mock LLM, câu trả lời là chuỗi cố định nên chênh lệch cost giữa hai prompt version chỉ đến từ input token; trên LLM thật, phần output token cũng sẽ thay đổi theo prompt.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
