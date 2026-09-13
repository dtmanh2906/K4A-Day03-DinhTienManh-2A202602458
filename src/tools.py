"""HR tools; fictional in-memory data for the lab only."""
import json
from datetime import date, timedelta

TOOLS_SCHEMA = [
    {"name": "hr_query", "description": "Tra cứu ngày phép và chính sách bảo hiểm mô phỏng theo mã nhân viên.",
     "parameters": {"type": "object", "properties": {
         "employee_id": {"type": "string", "description": "Mã nhân viên, ví dụ NV001"}},
         "required": ["employee_id"]}},
    {"name": "create_leave_request", "description": "Tạo đơn nghỉ phép mô phỏng chờ duyệt. Tra cứu hr_query trước, chỉ tạo khi người dùng yêu cầu.",
     "parameters": {"type": "object", "properties": {
         "employee_id": {"type": "string", "description": "Mã nhân viên"},
         "start_date": {"type": "string", "description": "Ngày bắt đầu YYYY-MM-DD"},
         "end_date": {"type": "string", "description": "Ngày kết thúc YYYY-MM-DD, tính cả hai đầu"},
         "reason": {"type": "string", "description": "Lý do do người dùng cung cấp"}},
         "required": ["employee_id", "start_date", "end_date", "reason"]}}
]
MOCK_DATABASE = {
    "NV001": {"full_name": "Nguyễn Văn An", "leave_balance": 12, "manager": "Trần Minh Hà"},
    "NV002": {"full_name": "Lê Thị Bình", "leave_balance": 1, "manager": "Trần Minh Hà"}
}
LEAVE_REQUESTS = []
INSURANCE_POLICY = "Dữ liệu lab: gói BH-LAB hỗ trợ khám tại cơ sở liên kết; gửi hồ sơ cho HR kiểm tra. Không phải chính sách thực tế của VinFast."

def result(status, **kwargs):
    return json.dumps({"status": status, "data_source": "fictional_hr_lab", **kwargs}, ensure_ascii=False)

def execute_hr_query(employee_id):
    employee_id = employee_id.strip().upper()
    employee = MOCK_DATABASE.get(employee_id)
    if not employee:
        return result("NOT_FOUND", message=f"Không tìm thấy nhân viên {employee_id}.")
    reserved = sum(r["days"] for r in LEAVE_REQUESTS if r["employee_id"] == employee_id)
    return result("SUCCESS", employee_id=employee_id, data={**employee,
        "available_days": employee["leave_balance"] - reserved, "reserved_days": reserved,
        "insurance_policy": INSURANCE_POLICY,
        "leave_policy": "Tính thứ Hai–thứ Sáu; chưa xét ngày lễ. Đơn chờ duyệt giữ chỗ phép trong phiên chạy."})

def execute_create_leave_request(employee_id, start_date, end_date, reason):
    employee_id = employee_id.strip().upper()
    lookup = json.loads(execute_hr_query(employee_id))
    if lookup["status"] != "SUCCESS":
        return json.dumps(lookup, ensure_ascii=False)
    try:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
        if start.isoformat() != start_date or end.isoformat() != end_date or end < start or start.year != end.year:
            raise ValueError()
    except ValueError:
        return result("INVALID_ARGUMENTS", message="Ngày phải đúng YYYY-MM-DD, cùng năm, kết thúc không trước bắt đầu.")
    days = sum((start + timedelta(days=i)).weekday() < 5 for i in range((end-start).days + 1))
    if not days:
        return result("INVALID_ARGUMENTS", message="Khoảng nghỉ không có ngày làm việc.")
    for request in LEAVE_REQUESTS:
        if request["employee_id"] == employee_id:
            if request["start_date"] == start_date and request["end_date"] == end_date and request["reason"] == reason.strip():
                return result("SUCCESS", **request, duplicate=True, message="Đơn đã tồn tại, không tạo trùng.")
            if start_date <= request["end_date"] and end_date >= request["start_date"]:
                return result("OVERLAP", message="Khoảng nghỉ trùng đơn đang chờ duyệt.")
    if days > lookup["data"]["available_days"]:
        return result("INSUFFICIENT_BALANCE", requested_days=days,
                      available_days=lookup["data"]["available_days"], message="Không đủ ngày phép; chưa tạo đơn.")
    request = {"request_id": f"LR-{len(LEAVE_REQUESTS)+1:04d}", "employee_id": employee_id,
               "start_date": start_date, "end_date": end_date, "reason": reason.strip(),
               "days": days, "approval_status": "PENDING_APPROVAL"}
    LEAVE_REQUESTS.append(request)
    return result("SUCCESS", **request, message="Đã tạo đơn mô phỏng chờ quản lý duyệt, chưa được phê duyệt nghỉ phép.")

TOOL_ROUTER = {"hr_query": execute_hr_query, "create_leave_request": execute_create_leave_request}

def dispatch_tool_call(tool_name, arguments):
    if not isinstance(tool_name, str) or tool_name not in TOOL_ROUTER:
        return result("UNKNOWN_TOOL", message="Công cụ không tồn tại.")
    schema = next(t["parameters"] for t in TOOLS_SCHEMA if t["name"] == tool_name)
    if (not isinstance(arguments, dict) or set(arguments) != set(schema["required"])
            or any(not isinstance(v, str) or not v.strip() for v in arguments.values())):
        return result("INVALID_ARGUMENTS", message="Cần đủ tham số chuỗi không rỗng, không có trường lạ.")
    return TOOL_ROUTER[tool_name](**arguments)
