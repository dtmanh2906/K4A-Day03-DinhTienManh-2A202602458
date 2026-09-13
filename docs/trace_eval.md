# BÁO CÁO LAB 3 — HR ASSISTANT

**Họ và tên:** Đinh Tiến Mạnh (theo tên repository; học viên kiểm tra lại dấu).
**Mã học viên:** 2A202602458
**Chủ đề:** Trợ lý Nhân sự — tra cứu ngày phép, bảo hiểm và tạo đơn nghỉ phép.
**Repository:** https://github.com/dtmanh2906/K4A-Day03-DinhTienManh-2A202602458

## 1. BẢNG CHẤM ĐIỂM AGENTIC FIT SCORING MATRIX

| Tiêu chí | Điểm | Giải trình |
| :--- | :---: | :--- |
| Multi-step Reasoning | 4/5 | Tra cứu nhân viên và phép khả dụng, xem khoảng nghỉ, tạo đơn, đọc kết quả rồi thông báo. |
| Tool Interaction | 5/5 | Số phép, bảo hiểm và mã đơn phải lấy từ Tool qua MCP; chatbot không có quyền truy cập dữ liệu này. |
| Dynamic Decision | 5/5 | Không tìm thấy nhân viên thì dừng; thiếu thông tin thì hỏi; thiếu phép thì từ chối; đủ phép mới tạo đơn. |
| Long Horizon Goal | 2/5 | Giữ mục tiêu trong vài vòng ReAct; không có lập kế hoạch dài hạn hoặc bộ nhớ bền vững. |
| **Tổng** | **16/20** | Phù hợp Agent cho chuỗi tra cứu → hành động. Giới thiệu khả năng chỉ cần chatbot. |

### Thiết kế và phạm vi

- Hai Tool: `hr_query(employee_id)` và `create_leave_request(employee_id, start_date, end_date, reason)`.
- Giữ các module starter: app → provider → MCPAcademicServer → dispatch_tool_call → Tool.
- Giữ tên lớp MCPAcademicServer để tương thích import; đổi tên server thành hr-assistant-mcp-server.
- MCP vẫn là mô phỏng trong cùng tiến trình như starter, không phải MCP server triển khai đầy đủ qua mạng.
- Có JSON-RPC envelope 2.0 với id, server, tool, result theo yêu cầu codelab.
- Sửa thêm providers.py vì Mock ban đầu chỉ hiểu học vụ; adapter ban đầu không giữ lịch sử Tool và âm thầm fallback Mock khi lỗi API.
- Gemini giữ nguyên model Content khi trả function response; OpenAI giữ assistant tool_calls và trả tool_call_id tương ứng. Xử lý tất cả Tool Call trả về.
- Chỉ ghi tóm tắt hành động có thể quan sát vào trường thought; không giả lập hoặc thu thập chuỗi suy nghĩ nội bộ của LLM.
- NV001 có 12 ngày phép; NV002 có 1 ngày. Mọi hồ sơ và chính sách bảo hiểm đều là dữ liệu giả lập, không phải chính sách VinFast.
- Nghỉ phép tính thứ Hai–thứ Sáu, gồm hai đầu, chưa xét ngày lễ. Chỉ nhận khoảng trong cùng năm; không áp dụng kiểm tra ngày quá khứ để fixture lab tái chạy được.
- Đơn mới là PENDING_APPROVAL, giữ chỗ số phép trong bộ nhớ. Chống đơn trùng và chồng ngày trong phiên chạy.
- Dữ liệu reset giữa các test và khi khởi động lại. Chưa có lưu trữ bền vững, xác thực hay hệ thống HR thật.
- Interactive xử lý từng câu độc lập; người dùng cần nhập đủ dữ liệu trong mỗi câu.

## 2. TRÍCH XUẤT KẾT QUẢ WATERFALL TRACE LOG

**Trạng thái API thật: CHƯA CHẠY. Không có bằng chứng nghiệm thu API thật ở thời điểm bàn giao.**

File `trace_waterfall_mock.json` là kết quả chạy Mock thực tế ngày 13/09/2026 với Python 3.12.14.
File `trace_waterfall_starter.json` giữ nguyên log học vụ cũ lấy từ repo; không dùng làm bằng chứng bài HR.
File `trace_waterfall.json` chỉ được sinh sau khi chạy API thật; mọi sự kiện có nhãn mode/provider/model.

Chuỗi TC04 quan sát được trong Mock:

1. hr_query(NV001) → SUCCESS, available_days = 12.
2. create_leave_request(NV001, 2026-09-21, 2026-09-23, du lịch) → SUCCESS, LR-0001, 3 ngày, PENDING_APPROVAL.
3. Provider nhận Observation và trả lời cuối có mã đơn.

Không dán đoạn Mock vào vị trí bằng chứng API thật.
Sau khi chạy lệnh nghiệm thu trong `HUONG_DAN_CHAY_HR.md`, thay đoạn này bằng trích đoạn TC04 thực tế
từ `trace_waterfall.json`, gồm TOOL_EXECUTION và FINAL_ANSWER, provider/model/mode và latency.
Nếu có ERROR hoặc MAX_ITERATIONS, cần sửa rồi chạy lại trước khi xác nhận đạt.

## 3. TỔNG KẾT KẾT QUẢ NGHIỆM THU & NỘP BÀI

| Test | Nội dung | Tool kỳ vọng | Mock | API thật |
| :--- | :--- | :--- | :---: | :---: |
| TC01 | Giới thiệu khả năng | Không gọi | PASS | Chưa chạy |
| TC02 | Ngày phép và bảo hiểm NV001 | hr_query | PASS | Chưa chạy |
| TC03 | Nghỉ 15–16/09/2026, việc gia đình | hr_query → create_leave_request | PASS | Chưa chạy |
| TC04 | Đủ phép thì nghỉ 21–23/09/2026, du lịch | hr_query → create_leave_request | PASS | Chưa chạy |
| TC05 | Nhân viên không tồn tại | hr_query → NOT_FOUND | PASS | Chưa chạy |

- **Mock:** 5/5 test, 6 lượt gọi Tool, 5 câu trả lời cuối, 5 phản hồi baseline.
- **Kiểm tra hồi quy:** 12/12 PASS; gồm số phép, ngày sai, trùng/chồng đơn, thiếu dữ liệu, lỗi provider và giới hạn vòng lặp.
- **So sánh baseline:** Mock baseline chỉ báo không có quyền tra cứu; Mock Agent có dữ liệu Tool và mã đơn. Đây là kiểm tra logic, chưa đánh giá năng lực LLM thật.
- **API thật:** chưa chạy; chưa xác minh SDK thực tế hoặc chất lượng câu trả lời live. Việc cài requirements.txt chưa được cho phép trong phiên làm bài.
- **Đánh giá tự động:** kiểm tra thứ tự Tool, status, tham số ngày/lý do và một số bằng chứng trong câu trả lời. Cần đọc lại câu trả lời live để đánh giá bảo hiểm, chống bịa và trạng thái chờ duyệt; PASS cấu trúc chưa đủ để kết luận toàn bộ nội dung đúng.
- [x] Hoàn thiện code HR, JSON Schema, ReAct loop và test cases.
- [x] Chạy Mock và kiểm tra hồi quy.

**Kết quả live cần điền sau chạy:** 5/5 PASS; 6 lượt Tool.
**GitHub:** bản sửa hiện ở máy cục bộ, chưa commit/push.

Tham khảo triển khai: [Gemini function calling](https://ai.google.dev/gemini-api/docs/function-calling),
[OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling).
