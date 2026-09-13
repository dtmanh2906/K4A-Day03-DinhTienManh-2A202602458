"""Starter provider adapters, extended with native tool-result history.
Live failures raise errors; never silently replace live responses with Mock.
"""
import json
import os
import re
from datetime import date, timedelta

class BaseLLMProvider:
    is_mock = False

    def reset(self):
        self.history = []
        self.observations = []

    def generate(self, prompt, system_prompt=""):
        raise NotImplementedError()

    def generate_with_tools(self, prompt, tools_schema, system_prompt=""):
        raise NotImplementedError()

    def add_tool_results(self, results):
        raise NotImplementedError()

class MockOfflineProvider(BaseLLMProvider):
    """Deterministic HR fixture, NOT an LLM or live API evaluation."""
    is_mock = True
    model_name = "HR-Offline-Mock"

    def __init__(self):
        self.reset()

    def generate(self, prompt, system_prompt=""):
        return "[Mock Baseline] Tôi không có công cụ tra cứu hồ sơ hoặc tạo đơn."

    def add_tool_results(self, results):
        self.observations.extend(results)

    def generate_with_tools(self, prompt, tools_schema, system_prompt=""):
        def final(text):
            return {"type": "text", "content": text}
        def call(name, args):
            return {"type": "tool_call", "calls": [{"id": f"mock-{len(self.observations)+1}",
                     "tool_name": name, "arguments": args}]}
        employee = re.search(r"\bNV\d+\b", prompt, re.I)
        if not employee:
            return final("Tôi có thể tra cứu ngày phép, bảo hiểm và tạo đơn mô phỏng. Vui lòng cung cấp mã nhân viên nếu cần tra cứu.")
        employee_id = employee.group().upper()
        if not self.observations:
            return call("hr_query", {"employee_id": employee_id})
        last = self.observations[-1]["observation"]
        if last["status"] != "SUCCESS":
            return final(last.get("message", last["status"]))
        if self.observations[-1]["tool_name"] == "create_leave_request":
            return final(f'{last["message"]} Mã đơn {last["request_id"]}, {last["days"]} ngày, trạng thái {last["approval_status"]}.')
        wants_leave = "tạo đơn" in prompt.lower()
        if wants_leave:
            dates = re.findall(r"\d{4}-\d{2}-\d{2}", prompt)
            reason = re.search(r"lý do\s*:\s*(.+?)(?:\.$|$)", prompt, re.I)
            if len(dates) != 2 or not reason:
                return final("Vui lòng cung cấp ngày bắt đầu, kết thúc dạng YYYY-MM-DD và lý do.")
            start, end = (date.fromisoformat(d) for d in dates)
            days = sum((start+timedelta(days=i)).weekday() < 5 for i in range(max(0, (end-start).days+1)))
            if days > last["data"]["available_days"]:
                return final("Không đủ ngày phép, chưa tạo đơn.")
            return call("create_leave_request", {"employee_id": employee_id,
                        "start_date": dates[0], "end_date": dates[1], "reason": reason.group(1)})
        data = last["data"]
        return final(f'{employee_id}: còn {data["available_days"]} ngày phép. {data["insurance_policy"]}')

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key=None, model=None):
        from openai import OpenAI
        self.model_name = model or os.getenv("LLM_MODEL") or "gpt-4o-mini"
        self.client = OpenAI(api_key=api_key or os.getenv("OPENAI_API_KEY"), timeout=60, max_retries=1)
        self.reset()

    def generate(self, prompt, system_prompt=""):
        response = self.client.chat.completions.create(model=self.model_name,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}])
        return response.choices[0].message.content or ""

    def generate_with_tools(self, prompt, tools_schema, system_prompt=""):
        if not self.history:
            self.history = [{"role": "system", "content": system_prompt}, {"role": "user", "content": prompt}]
        response = self.client.chat.completions.create(model=self.model_name, messages=self.history,
            tools=[{"type": "function", "function": t} for t in tools_schema], parallel_tool_calls=False)
        msg = response.choices[0].message
        self.history.append(msg.model_dump(exclude_none=True))
        if msg.tool_calls:
            return {"type": "tool_call", "calls": [
                {"id": c.id, "tool_name": c.function.name, "arguments": json.loads(c.function.arguments)}
                for c in msg.tool_calls]}
        return {"type": "text", "content": msg.content or ""}

    def add_tool_results(self, results):
        for r in results:
            self.history.append({"role": "tool", "tool_call_id": r["id"],
                                 "content": json.dumps(r["observation"], ensure_ascii=False)})

class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key=None, model=None):
        from google import genai
        self.model_name = model or os.getenv("LLM_MODEL") or "gemini-2.5-flash"
        self.client = genai.Client(api_key=api_key or os.getenv("GEMINI_API_KEY"),
                                  http_options={"timeout": 60000})
        self.reset()

    def generate(self, prompt, system_prompt=""):
        return self.client.models.generate_content(model=self.model_name, contents=prompt,
            config={"system_instruction": system_prompt}).text or ""

    def generate_with_tools(self, prompt, tools_schema, system_prompt=""):
        from google.genai import types
        if not self.history:
            self.history = [types.Content(role="user", parts=[types.Part.from_text(text=prompt)])]
        response = self.client.models.generate_content(model=self.model_name, contents=self.history,
            config=types.GenerateContentConfig(system_instruction=system_prompt,
                tools=[types.Tool(function_declarations=tools_schema)],
                automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True)))
        if not response.candidates or not response.candidates[0].content:
            raise RuntimeError("Gemini returned no content.")
        # Preserve complete model content, including any opaque thought signatures.
        self.history.append(response.candidates[0].content)
        if response.function_calls:
            return {"type": "tool_call", "calls": [
                {"id": c.id or f"gemini-{len(self.history)}-{i}", "native_id": c.id,
                 "tool_name": c.name, "arguments": dict(c.args or {})}
                for i, c in enumerate(response.function_calls)]}
        return {"type": "text", "content": response.text or ""}

    def add_tool_results(self, results):
        from google.genai import types
        parts = [types.Part(function_response=types.FunctionResponse(
            id=r.get("native_id"), name=r["tool_name"], response=r["observation"])) for r in results]
        self.history.append(types.Content(role="user", parts=parts))

def get_llm_provider():
    provider_type = os.getenv("LLM_PROVIDER", "mock").strip().lower()
    if provider_type == "mock":
        return MockOfflineProvider()
    if provider_type not in ("gemini", "openai"):
        raise ValueError("LLM_PROVIDER phải là mock, gemini hoặc openai.")
    key = os.getenv("GEMINI_API_KEY" if provider_type == "gemini" else "OPENAI_API_KEY", "")
    if not key or key.startswith("your_"):
        raise ValueError("Chưa có API key hợp lệ. Điền .env hoặc chọn --mock để kiểm tra offline.")
    return GeminiProvider() if provider_type == "gemini" else OpenAIProvider()
