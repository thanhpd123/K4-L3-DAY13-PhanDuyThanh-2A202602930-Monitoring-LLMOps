# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Chỉ cần 3 output text và 5 ảnh runtime; dùng đường dẫn tương đối, ví dụ `evidence/03-incident-trace.png`.

## 1. Thông tin học viên

- **Họ và tên:** Phan Duy Thành
- **MSSV:** 2A202602930
- **Lớp:** K4-L3B
- **Repository URL:** `https://github.com/thanhpd123/K4-L3-DAY13-PhanDuyThanh-2A202602930-Monitoring-LLMOps`
- **Commit SHA cuối:** điền sau commit cuối cùng
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` (incident `rag_slow`, cohort K4, seed 1312)
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602930`

## 2. Evidence index

Giữ đúng ba output text và năm ảnh dưới đây. Không tách thêm ảnh; nếu cần giải thích, ghi bằng chữ trong các mục sau.

| Evidence                                    | Đường dẫn                            |
| ------------------------------------------- | ------------------------------------ |
| Pytest cuối                                 | `evidence/pytest.txt`                |
| Log validator                               | `evidence/log-validator.txt`         |
| Dashboard validator                         | `evidence/dashboard-validator.txt`   |
| Structured log + incident log               | `evidence/01-incident-log.png`       |
| Trace list                                  | `evidence/02-trace-list.png`         |
| Trace waterfall + metadata + incident trace | `evidence/03-incident-trace.png`     |
| Prompt versions + promote/rollback          | `evidence/04-prompt-versioning.png`  |
| Dashboard + incident metric                 | `evidence/05-dashboard-incident.png` |

## 3. Kết quả kỹ thuật

| Nội dung                | Baseline          | Kết quả cuối                                                                                            | Nhận xét                                                                                                                                               |
| ----------------------- | ----------------- | ------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `validate_logs.py`      | 30/100            | **100/100**                                                                                             | 0 bản ghi thiếu trường bắt buộc, 0 bản ghi thiếu metadata, 0 PII leak. Baseline mất điểm vì log API chưa có `correlation_id`, thiếu metadata ngữ cảnh. |
| `validate_dashboard.py` | 6/6               | 6/6                                                                                                     | Đây là kiểm tra hợp đồng 6 panel; bằng chứng dữ liệu thật nằm ở `05-dashboard-incident.png`.                                                           |
| `pytest`                | 22 passed         | **26 passed**                                                                                           | Thêm 4 test PII (CCCD, thẻ, địa chỉ VN, CMND/hộ chiếu); các test adapter Langfuse vẫn xanh sau khi tách span.                                          |
| Số traces hợp lệ        | 0                 | **107 trace** (root observation `lab-agent-run`, có trace của cả `baseline`, `production`, `candidate`) | Trace do chính em tạo trong project Langfuse cá nhân; metadata có `correlation_id` + `prompt_name/label/version`.                                      |
| Số PII leak             | 0                 | **0**                                                                                                   | Validator quét độc lập JSON thô bằng detector riêng, không dựa vào lời khai của app.                                                                   |
| Latency P95 / TTFT P95  | 1996 ms / chưa đo | **153 ms / 51 ms** (baseline sạch) → **2653 ms / 50 ms** (khi chạy challenge)                           | TTFT gần như không đổi trong khi P95 tăng 17 lần là bằng chứng định vị lỗi ở bước retrieval, không phải LLM.                                           |
| Retrieval success rate  | 100%              | **100%** trong lần chạy challenge (lỗi xảy ra ở practice `tool_fail` không thuộc challenge)             | Mọi request challenge đều có `tool_success = true`, lỗi thuần latency.                                                                                 |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:**
  Middleware xóa context cũ trước (vì `contextvars` được tái sử dụng giữa các request), sau đó dùng lại `x-request-id` nếu client gửi đúng định dạng cho phép, ngược lại sinh mới theo format `req-<8-hex>`. ID được bind vào structlog nên mọi log line của request tự mang theo, đồng thời lưu vào `request.state` để handler/agent dùng lại và trả về header `x-request-id` cùng `x-response-time-ms`.
  Kiểm chứng: request challenge trả `x-request-id` trùng với `correlation_id` trong cả hai sự kiện `request_received` và `response_sent`.
- **Các metadata được ghi vào structured log:**
  Các trường bắt buộc `ts`, `level`, `service`, `event`, `correlation_id`; ngữ cảnh request `user_id_hash` (SHA-256 rút gọn 12 ký tự, không ghi user_id thô), `session_id`, `feature`, `model`, `env`; riêng `response_sent` ghi thêm `latency_ms`, `ttft_ms`, `tokens_in`, `tokens_out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`. Đây cũng là nguồn dữ liệu cho 6 panel dashboard.
- **Cách bảo đảm PII được scrub trước khi ghi:**
  Hai lớp phòng vệ độc lập. Lớp 1 ở tầng ứng dụng: `summarize_text()` scrub rồi mới cắt ngắn nên log chỉ chứa preview an toàn. Lớp 2 ở tầng logging: processor `scrub_event` chạy ngay trước `JsonlFileProcessor` (sau `format_exc_info`) nên mọi chuỗi cuối cùng, kể cả traceback, đều bị thay bằng `[REDACTED_<LOẠI>]` trước khi chạm file. Pattern gồm email, số điện thoại VN (cả `+84` và các kiểu phân cách), CCCD 12 số, thẻ thanh toán, CMND 9 số, hộ chiếu, số tài khoản và địa chỉ — sắp theo thứ tự pattern cụ thể trước pattern ngắn để không dán nhầm nhãn.
- **Cách kiểm chứng kết quả:**
  `log-validator.txt` cho 100/100 với 0 PII leak; request thật chứa email/số điện thoại/CCCD chỉ còn `[REDACTED_EMAIL]`, `[REDACTED_PHONE_VN]`, `[REDACTED_CCCD]`; và trong trace metadata trên Langfuse, `query_preview` cũng đã là `[REDACTED_EMAIL]` — tức PII không lên được hệ thống quan sát, chứ không chỉ không xuống file log.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:**
  Project `day13-k4-l3b-2A202602930`, trang Traces lọc `Is Root Observation = True`, `Name = lab-agent-run`, `Environment = dev` — ảnh `02-trace-list.png` thấy tên project và 107 trace. Em kiểm tra chéo bằng API observations của Langfuse để chắc chắn trace ứng với đúng `correlation_id` trong log của mình.
- **Cấu trúc root/retrieval/generation observations:**
  `@observe` trên `LabAgent.run` tạo root `lab-agent-run` (agent, trace name `day13-agent-request`); `retrieve()` được bọc `as_type="retriever"`; `FakeLLM.generate()` được bọc `as_type="generation"` và tự gọi `update_current_generation(model, usage_details, cost_details)`. Cả ba đặt `capture_input=False, capture_output=False` nên Langfuse không lưu nội dung thô của người dùng — chỉ có `query_preview` đã scrub, `doc_count`, `ttft_ms`, token và cost.
- **Cách nối trace với log:**
  `correlation_id` từ middleware được truyền vào `LabAgent.run` và ghi vào trace metadata (`metadata.correlation_id`). Đã đối chiếu thật: `trace_id bad7b8995ae76ef45e49133446d1614f` ↔ `correlation_id req-2d85f516`; `trace_id c5870547c480b4a09e6a4e1539d35478` ↔ `correlation_id req-499f4ec5`.
- **Prompt name:** `day13-chat`, giữ đúng ba biến `{{feature}}`, `{{docs}}`, `{{message}}`.
- **Version/label baseline:** version **1** (54 ký tự), labels `baseline` + `production`.
- **Version/label candidate:** version **3** (101 ký tự, thêm ràng buộc trả lời tối đa 3 bullet), label `candidate`. Version 2 được tạo nhưng trùng nội dung version 1 nên không dùng làm candidate.
- **Trace ID của mỗi version:**
  - v1 / `baseline`: `c5870547c480b4a09e6a4e1539d35478` (`req-499f4ec5`), `4fe9a94c0b3f1b4963637907de427a88` (`req-96218184`).
  - v1 / `production` (lần chạy challenge): `bad7b8995ae76ef45e49133446d1614f` (`req-2d85f516`).
  - v3 / `candidate`: `292b06a766321ad28f1c20cf7235e385` (`req-1777839b`), `3ec93168c9e886d3efdfc770b14b2868` (`req-06ba8957`).
- **Số liệu so sánh trên cùng một bộ 10 input:**

  | Chỉ số                 | `baseline` (v1) | `candidate` (v3) | Thay đổi   |
  | ---------------------- | --------------- | ---------------- | ---------- |
  | Tổng input token       | 338             | 456              | **+34,9%** |
  | Tổng cost (10 request) | $0,017634       | $0,022578        | **+28,0%** |
  | Latency mỗi request    | ~152 ms         | ~152 ms          | không đổi  |
  | Quality proxy          | 0,8–0,9         | 0,8–0,9          | không đổi  |

  Đọc theo hướng vận hành: prompt v3 làm chi phí mỗi request tăng gần 30% mà không cải thiện latency hay quality, nên đủ căn cứ để rollback.
- **Cách promote và rollback `production`:**
  Label `production` chỉ trỏ tới một version tại mỗi thời điểm. Promote = mở prompt labels của version mới, tick `production`, Save. Rollback = mở prompt labels của version 1, tick `production`, Save. App không cần sửa code vì chỉ đọc `LANGFUSE_PROMPT_NAME` và `LANGFUSE_PROMPT_LABEL` từ `.env`; trace metadata sau rollback ghi lại đúng `prompt_version` đang phục vụ. Bằng chứng gộp trong ảnh `04-prompt-versioning.png`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:**
  Dashboard runtime là `dashboard/index.html`, sinh bằng `scripts/build_dashboard.py` đọc trực tiếp `data/logs.jsonl` và lấy ngưỡng/đơn vị/time range từ `config/dashboard.yaml`: Latency (P50/P95/P99 + TTFT P95), Traffic (request/phút), Errors (error rate + breakdown `error_type` + retrieval success), Cost, Tokens, Quality. Mỗi panel ghi rõ đơn vị, ngưỡng, trạng thái ĐẠT/VƯỢT ngưỡng và sparkline theo phút; dashboard còn hiển thị thêm challenge id và ngưỡng latency của challenge để đối chiếu.
- **SLO và lý do chọn:**
  SLO `fast_successful_requests`: 99,5% request có `latency_ms ≤ 3000` trong cửa sổ 28 ngày. Ngưỡng 3000 ms chọn từ baseline thật của bài (P50 ≈ 152 ms, P95 ≈ 153 ms, TTFT P95 ≈ 51 ms) — rộng hơn tail latency bình thường nhưng vẫn bắt được sự cố retrieval.
- **Cách tính error budget:**
  SLO 99,5% ⇒ error budget 0,5%, tức với 10.000 request chỉ được phép tối đa 50 request lỗi hoặc chậm hơn 3000 ms. Trong challenge, P95 đo được 2653 ms: vượt ngưỡng challenge 2000 ms, và nếu số request đủ lớn thì phần vượt 3000 ms sẽ ăn hết error budget chỉ trong vài phút.
- **Ba alert và runbook tương ứng:**
  1. `HighLatencyP95` — warning, `p95(latency_ms) > 3000` liên tục **5 phút**, Slack `#k4-l3b-alerts`, owner `student-2A202602930`, runbook `docs/alerts.md#alert-1`.
  2. `RetrievalFailureSpike` — critical, `error_rate > 2%` hoặc `retrieval success < 90%` liên tục **10 phút**, cùng kênh/owner, runbook `docs/alerts.md#alert-2`.
  3. `CostAndTokenSpike` — warning, tổng `cost_usd > 2,5` hoặc `tokens_out` tăng gấp 3 lần baseline liên tục **15 phút**, cùng kênh/owner, runbook `docs/alerts.md#alert-3`.

  Cả ba đều symptom-based, có `duration`, có kênh Slack và ba bước kiểm tra + mitigation trong `docs/alerts.md`.

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` — cohort K4, incident `rag_slow`, affected feature `monitoring`, seed 1312, `latency_threshold_ms` 2000.
- **Khoảng thời gian điều tra:** 11:40:31–11:40:42 ngày 30/09/2026 (giờ Việt Nam), chạy `inject_incident.py` rồi `load_test.py --challenge --concurrency 5` (5 request).
- **Triệu chứng từ metrics:**
  Baseline sạch: P50 152 ms, P95 153 ms, TTFT P95 51 ms. Sau challenge: **P95 2653 ms** (tăng 17 lần), P99 2653 ms, nhưng **TTFT P95 vẫn 50 ms**. Đối chiếu ngưỡng: challenge yêu cầu p95 ≤ **2000 ms** → **VƯỢT**; SLO nội bộ 3000 ms cũng gần bị vượt. Phía client, thời gian chờ thực tế còn tệ hơn: 7.974 ms đến 13.286 ms cho 5 request chạy đồng thời.
  Mấu chốt: TTFT không đổi nghĩa là LLM vẫn trả token đầu gần như tức thì, thời gian bị tiêu hết ở bước lấy context.
- **Log line và correlation ID liên quan:**
  `correlation_id=req-2d85f516` (request chậm nhất của challenge): `event=response_sent`, `feature=monitoring`, `model=claude-sonnet-4-5`, `env=dev`, `latency_ms=2653`, `ttft_ms=50`, `tool_name=retrieval`, `tool_success=true`. Các request còn lại: `req-47792576` (2651 ms), `req-0d51e8f4` (2653 ms), `req-112b337e` (2652 ms), `req-0f842398` (2653 ms).
- **Trace ID và span gây ảnh hưởng:**
  `trace_id bad7b8995ae76ef45e49133446d1614f` (ứng với `req-2d85f516`). Trong waterfall, span **`retrieval` chiếm gần trọn 2,5 giây**, span `generation` và TTFT giữ nguyên như bình thường → điểm nghẽn nằm ở retrieval. Metadata trace còn xác nhận `prompt_label=production`, `prompt_version=1`, `doc_count=1` — tức prompt không phải nguyên nhân.
- **Root cause:** bước retrieval bị chậm một cách hệ thống: hàm `retrieve()` gọi `time.sleep()` blocking (mô phỏng vector store chậm) trong khi server là async, nên mỗi request giữ event loop khoảng 2,5 giây và các request đồng thời bị xếp hàng. Đó là lý do log ghi `latency_ms ≈ 2653 ms` nhưng người dùng thực tế chờ tới hơn 13 giây khi chạy concurrency 5. Không phải LLM (TTFT không đổi) và cũng không phải prompt (cùng version 1 cho mọi request).
- **Fix action:** tắt incident bằng `python scripts/inject_incident.py --disable`, chạy lại cùng concurrency để xác nhận P95 trở về ~153 ms và không còn request quá 2000 ms.
- **Preventive measure:** giữ alert `HighLatencyP95` (P95 > 3000 ms trong 5 phút) và `RetrievalFailureSpike`; thêm cảnh báo sớm ở ngưỡng challenge 2000 ms; thay blocking call bằng async I/O hoặc đẩy sang thread pool cùng timeout cho vector store; và đưa load test `--concurrency` vào kiểm tra định kỳ vì đây là loại lỗi chỉ lộ ra khi có tải đồng thời.

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
  Em tách child observation bằng cách bọc `@observe` lên chính `retrieve()` và `FakeLLM.generate()` thay vì gọi `start_as_current_observation` trong `LabAgent.run`. Cách này vẫn cho đúng cây span `agent → retriever/generation` nhưng không phá test contract của repo (test dùng client giả chỉ có `get_prompt` và `update_current_span`). Đổi lại em phải đưa đơn giá token vào `mock_llm.py` thành hằng số dùng chung để log cost và trace cost không lệch nhau.
- **Một lỗi/blocker đã gặp:**
  App luôn rơi vào `local-fallback` vì prompt `day13-chat` chưa tồn tại trên Langfuse (404 mỗi request); sau đó version 2 được tạo nhưng trùng nội dung version 1 nên hai label cho kết quả giống hệt, không thể so sánh. Ngoài ra, panel Errors ban đầu tính retrieval success chỉ từ `response_sent`, nên khi request lỗi qua `request_failed` thì panel vẫn báo 100% — sai so với hợp đồng `count(tool_success != null)`.
- **Cách tìm nguyên nhân và xử lý:**
  Với prompt: truy vấn trực tiếp Langfuse để xem mỗi label trỏ tới version nào và độ dài từng version, nhờ đó phát hiện version 2 trùng nội dung và tạo version 3 thật khác. Với panel Errors: đối chiếu lại câu `query` trong `config/dashboard.yaml` rồi sửa cách tính cho lấy `tool_success` trên toàn bộ bản ghi. Với incident: so TTFT với latency để loại trừ LLM trước khi mở trace.
- **Cách hiểu luồng Metrics → Logs → Traces:**
  Metrics nói hệ thống xấu ở chỉ số nào và từ lúc nào; log cho một request cụ thể qua `correlation_id`; trace chỉ ra bước nào gây ra vấn đề. Trong challenge này: P95 nhảy 17 lần → `req-2d85f516` → span `retrieval` chiếm 2,5 giây. Ba nguồn cùng chỉ về một nguyên nhân thì kết luận mới hợp lệ.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
  Prompt là một phần của hệ thống: cùng input nhưng đổi sang version 3 là cost tăng ~28% mà quality và latency không đổi. Không có `prompt_version` trong trace thì không thể quy trách nhiệm cho version nào. SLO/error budget cho biết khi nào còn được phép thay đổi; rollback bằng label là cách khôi phục nhanh nhất mà không cần deploy code.
- **Điều quan trọng nhất đã học:**
  Một chỉ số trung bình đẹp có thể che lấp lỗi chỉ xuất hiện khi có tải đồng thời: log ghi 2653 ms nhưng người dùng thực tế chờ 13 giây. Và việc đo đúng chỗ (TTFT so với latency, server-side so với client-side) quan trọng không kém việc có trace.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:**
  Với mock LLM, câu trả lời là chuỗi cố định nên chênh lệch cost giữa hai prompt version chỉ đến từ input token — trên LLM thật phần output token cũng sẽ thay đổi theo prompt. Ngoài ra dashboard hiển thị `latency_ms` do server tự đo; muốn thấy độ trễ người dùng thật khi concurrency cao thì cần bổ sung số đo phía client (load test) như một chỉ số riêng.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Có đúng 3 file text và 5 ảnh runtime theo hướng dẫn.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
