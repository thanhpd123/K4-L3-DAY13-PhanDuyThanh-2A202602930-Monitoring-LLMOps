# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: độ trễ P95 của `response_sent.latency_ms` thuộc SLO `fast_successful_requests` (99.5% request ≤ 3000ms)
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` liên tục 5 phút
- Ảnh hưởng tới người dùng: người dùng chờ lâu hơn 3 giây trước khi thấy câu trả lời; nếu kéo dài, họ sẽ bỏ ngang hoặc gửi lại request gây tăng tải.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel **Latency** trên dashboard, xác nhận P95/P99 và TTFT tăng, ghi lại khoảng thời gian bắt đầu xấu.
  2. Lọc `data/logs.jsonl` trong khoảng đó, chọn một `correlation_id` có `latency_ms` cao và `tool_name` tương ứng.
  3. Tìm trace cùng `correlation_id` trên Langfuse, so sánh thời lượng span `retrieval` với `generation` để biết bước nào chậm.
- Mitigation tạm thời: nếu span chậm là `retrieval`, tạm giảm tải hoặc tắt scenario đang gây chậm; nếu span chậm là `generation`, rollback `production` về prompt version trước đó và theo dõi lại P95 trong 10 phút.
- Owner: `student-2A202602930`

## Alert 2

- Tên: `RetrievalFailureSpike`
- Severity: `critical`
- Duration: `10m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: error rate của `request_failed / request_received` và retrieval success của `response_sent.tool_success`; guardrail `error_rate_pct_max = 2` và `retrieval_success_rate_pct_min = 90`
- Điều kiện và thời gian duy trì: `error_rate_pct > 2` hoặc `retrieval_success_rate_pct < 90` liên tục 10 phút
- Ảnh hưởng tới người dùng: câu trả lời thiếu context (RAG trả fallback) hoặc request lỗi hẳn 500, người dùng không nhận được thông tin cần thiết.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel **Errors** trên dashboard, xem error rate, breakdown `error_type` và retrieval success rate.
  2. Lọc log `event == "request_failed"` trong khoảng đó, lấy `correlation_id` và `error_type` (ví dụ `RuntimeError`) để biết loại lỗi.
  3. Mở trace cùng `correlation_id`, kiểm tra metadata/status của span `retrieval` để xác nhận lỗi phát sinh tại bước truy xuất chứ không phải ở LLM.
- Mitigation tạm thời: nếu nguyên nhân là vector store timeout, dừng scenario đang gây lỗi, xác nhận retrieval success trở lại trên 90% rồi mới mở lại traffic; nếu lỗi do prompt mới, rollback `production`.
- Owner: `student-2A202602930`

## Alert 3

- Tên: `CostAndTokenSpike`
- Severity: `warning`
- Duration: `15m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: tổng `cost_usd` và `tokens_out` của `response_sent`; guardrail `daily_cost_usd_max = 2.5`
- Điều kiện và thời gian duy trì: `sum(cost_usd) > 2.5 USD` hoặc `tokens_out` tăng gấp 3 lần baseline trong 15 phút
- Ảnh hưởng tới người dùng: chi phí trên mỗi câu trả lời tăng vọt, ngân sách ngày bị vượt và có thể phải hạ trần token làm giảm chất lượng câu trả lời.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel **Cost** và **Tokens**, so tổng và trung bình mỗi request với baseline đã ghi trong báo cáo.
  2. Lọc log `response_sent` có `cost_usd`/`tokens_out` cao bất thường, lấy `correlation_id` và `prompt_version` liên quan.
  3. Mở trace cùng `correlation_id`, xem span `generation` để đối chiếu prompt version/label đang chạy với số token thực tế.
- Mitigation tạm thời: nếu mức tăng trùng với prompt version mới đang được promote, rollback label `production` về version cũ; nếu do scenario `cost_spike`, tắt scenario và xác nhận cost trung bình trở về mức cũ.
- Owner: `student-2A202602930`
