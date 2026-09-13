# Chạy Lab 3 — HR Assistant

Mở terminal PowerShell tại thư mục repository đã sửa. Không clone lại từ GitHub trước khi push,
vì bản sửa hiện chỉ nằm trong thư mục bàn giao trên máy.

## 1. Kiểm tra Mock miễn phí

Dùng Python 3.10–3.12:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe src/mcp_server.py
.\.venv\Scripts\python.exe src/app.py --all --mock
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Mock không cần thư viện bên ngoài. Kỳ vọng: MCP SERVER PASS, 5/5 PASS, 12 tests OK.
Log nằm ở docs/trace_waterfall_mock.json và docs/test_results_mock.json.
Mock dùng quy tắc cố định, không chứng minh khả năng suy luận của LLM.

## 2. Chuẩn bị API thật

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Chỉ copy nếu chưa có .env để tránh ghi đè cấu hình riêng.
Mở .env và chọn **một** cấu hình dưới đây, không gửi API key vào chat.

Gemini (model mặc định của starter):

```dotenv
LLM_PROVIDER=gemini
GEMINI_API_KEY=THAY_BANG_KEY_CUA_BAN
LLM_MODEL=gemini-2.5-flash
```

Hoặc OpenAI (model mặc định của starter):

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=THAY_BANG_KEY_CUA_BAN
LLM_MODEL=gpt-4o-mini
```

Nếu model starter không còn khả dụng với tài khoản, đặt LLM_MODEL thành model hỗ trợ function calling
mà tài khoản của bạn được phép sử dụng. Các tên trên chưa được nghiệm thu live trong lần bàn giao này.
Biến môi trường đã đặt trong terminal được ưu tiên hơn .env; kiểm tra LLM_PROVIDER/LLM_MODEL nếu chọn sai provider.

## 3. Sinh trace nghiệm thu

```powershell
.\.venv\Scripts\python.exe src/app.py --all --require-live
```

Chương trình từ chối Mock khi có --require-live. Lỗi API được ghi ERROR, không tự fallback về Mock.
Lệnh gọi API có thể phát sinh phí theo tài khoản. Mỗi test có một lần baseline và tối đa 5 vòng Agent.

Kiểm tra:

- Provider đầu màn hình phải là GeminiProvider hoặc OpenAIProvider.
- docs/test_results_live.json phải có mode=live, passed=5, total=5.
- docs/trace_waterfall.json chứa TC01–TC05, mode=live, provider/model,
  Tool arguments, Observation, latency và Final Answer; không có ERROR/MAX_ITERATIONS.
- TC04 phải tra cứu rồi tạo đơn đúng ngày, lý do, trạng thái chờ duyệt; câu trả lời cuối dùng mã đơn do Tool trả.
- TC05 báo không tìm thấy nhân viên, không bịa hồ sơ. TC02 trả chính sách có nguồn dữ liệu lab.
- Log xuất ngay cả khi thất bại để phục vụ debug; sự tồn tại của file không đồng nghĩa PASS.

Mỗi lần --all ghi đè log của cùng chế độ. Có thể sao lưu log trước lần chạy mới.
Mỗi test reset đơn mô phỏng, nên TC03 và TC04 cùng có mã LR-0001 là bình thường.

Thử CLI:

```powershell
.\.venv\Scripts\python.exe src/app.py --interactive --require-live
```

Ví dụ: Tạo đơn cho NV001 từ 2026-09-15 đến 2026-09-16, lý do: việc gia đình.
Mỗi câu là một phiên ReAct độc lập, hãy nhập đủ thông tin; exit để thoát.
Log interactive riêng, không ghi đè bộ trace nghiệm thu.

## 4. Báo cáo và nộp bài

Mở docs/trace_eval.md, điền bằng chứng TC04 từ log API thật và kết quả kiểm thử live.
Kiểm tra lại họ tên, mã học viên và đánh dấu những bước đã thực hiện.

```powershell
git status
git diff --check
git add src config/test_cases.json docs tests
git commit -m "feat: complete HR Assistant Lab 3 with MCP ReAct loop"
git push origin main
```

.env đã được .gitignore loại trừ. Chưa có thao tác push trong lần bàn giao.
Cuối cùng nộp link repository cá nhân lên LMS.

## Xử lý lỗi

- Thiếu module: cài requirements.txt bằng đúng Python của .venv.
- Sai key/model, hết quota hoặc lỗi mạng: xem cấu hình tài khoản; lỗi không chuyển thành Mock.
- Không thấy trace live: có thể chương trình dừng ngay ở bước cấu hình trước khi chạy test.
- Test live FAIL: xem checks trong test_results_live.json và Observation tương ứng, chỉnh rồi chạy lại.
- Cài SDK và kiểm tra API thật chưa được thực hiện trong phiên này; Mock đã chạy trên Python 3.12.14.
