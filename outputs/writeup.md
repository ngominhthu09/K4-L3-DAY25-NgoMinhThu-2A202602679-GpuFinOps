# Lab 25 — GPU FinOps: phân tích kết quả

## M1 — Hiệu suất GPU

GPU-Util cao nhất là `gpu-h100-4`: **98.2% util nhưng MFU chỉ 0.194**. GPU-Util báo GPU bận, không chứng minh các đơn vị tính toán đang xử lý FLOPs hữu ích; memory stall, chờ dữ liệu hoặc overhead có thể khiến GPU bận mà MFU vẫn thấp. `gpu-a10g-1` cũng bị flag với util 96.9% và MFU 0.268. Chi phí idle ước tính **$600/tháng**, bằng khoảng **2.2%** baseline $27,133. Cần profile hai GPU bị flag trước khi đổi phần cứng.

## M2 — Chi phí inference

Với 7,533,027 token, inference giảm từ **$48.87/ngày, $6.488/1M token** xuống **$8.48/ngày, $1.126/1M token**, tiết kiệm **82.6%**. Tách lever tuần tự (cascade trước, rồi cache, rồi batch) cho kết quả: cascade **$37.40/ngày**, cache **$1.20/ngày**, batch **$1.79/ngày**; cascade đóng góp nhiều nhất vì route traffic sang model nhỏ giảm giá đầu vào/đầu ra.

Discount stack lý tưởng bằng **0.05** vì batch multiplier 0.50 nhân cache multiplier 0.10. Batch không phù hợp request tương tác có SLA latency thấp vì gom request có thể tăng thời gian chờ.

## M3 — Chiến lược mua GPU

Các job interruptible (`job-train-llm`, `job-train-embed`, `job-finetune`, `job-dev-sandbox`, `job-batch-eval`) được chọn spot vì có thể checkpoint và chấp nhận bị thu hồi. Effective hours cao hơn job hours vì mô hình cộng 3% checkpoint overhead và thời gian chạy lại kỳ vọng do interruption. Các job inference chạy ổn định được chọn reserved; riêng `job-infer-chat` đạt 24 giờ/ngày nên commitment hợp lý nếu nhu cầu này duy trì đủ lâu. Tổng purchasing giảm từ **$25,667** xuống **$15,627/tháng (39.1%)**. Trước cam kết dài hạn, cần xác nhận thời hạn nhu cầu thực sự khớp với reserved term.

## M4 — Phân bổ chi phí

Team có chi phí cao nhất là **assistant: $2.59/ngày**, khoảng **30.6%** tổng chi phí theo team ($8.47/ngày). Tag coverage **92%**, vượt ngưỡng 80% nên gate chargeback mở. FOCUS chuẩn hóa trường chi phí để so sánh/phân bổ nhất quán khi dùng nhiều cloud provider.

## M5 — Tổng hợp và sustainability

Chi phí tháng giảm từ **$27,133** xuống **$14,626**, tiết kiệm **$12,507 (46.1%)**. Lever lớn nhất là purchasing (**$10,040/tháng**), tiếp theo inference (**$1,212**), right-sizing util-lies (**$655**) và tắt idle GPUs (**$600**). Báo cáo ước tính **0.24 Wh/query**, **0.091 gCO2e/query**; europe-north1 là vùng sạch nhất trong catalog.

## Hai extension đã làm

**Ngân sách reasoning.** Reasoning là **201 request (8.4%)**, 1,241,156 token, **$1.40** optimized API cost và **29,787.7 Wh**; nhóm non-reasoning là 2,199 request, 6,291,871 token, **$7.09** và **1,887.6 Wh**. Reasoning chiếm 16.5% API cost dù chỉ 8.4% request. So với chạy các reasoning request như query thường, phần năng lượng tăng thêm là **29,415.4 Wh**, tương ứng **$3.5298** tiền điện theo giá us-east-1. Với cap yêu cầu **10%**, traffic hiện tại đã thấp hơn ngưỡng: trước/sau vẫn **$8.48** API cost và **31,675.3 Wh** tổng năng lượng; savings là **$0 và 0 Wh**. Catalog không có phụ phí API riêng cho reasoning, nên không giả định savings API khi cap.

**Carbon-aware scheduling.** So sánh cùng GPU-hours tích lũy của các job interruptible trong `workloads.csv` (không nhân thành tháng 30 ngày): chuyển từ us-east-1 sang europe-north1 giảm **626,150 gCO2e (92.1%)**, tiền điện giảm **$214.68 xuống $161.01**. So sánh đủ 5 vùng cho thấy **us-east-wa rẻ nhất** ($98.39), còn **europe-north1 sạch nhất** (53,670 gCO2e; giá điện $161.01). Đây là trade-off chi phí/carbon; giả định job di chuyển vùng không đổi GPU-hours, chưa tính latency và data residency.

## Ba khuyến nghị

1. Profile hai GPU có util cao/MFU thấp rồi tối ưu kernel, memory access hoặc right-size dựa trên benchmark throughput.
2. Duy trì cascade, cache và batch cho request phù hợp; theo dõi riêng $/1M token và latency SLA.
3. Dùng spot cho job checkpointable; cân nhắc vùng sạch hơn cho job có thể di chuyển sau khi kiểm tra latency, vị trí dữ liệu và cam kết giá.

Số liệu là mô phỏng theo snapshot tháng 6/2026. Chi tiết lever, FOCUS export và bảng vùng nằm trong các output đi kèm.
