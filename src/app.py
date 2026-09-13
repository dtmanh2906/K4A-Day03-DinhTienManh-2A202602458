"""Lab core: baseline -> provider -> MCP -> observation -> provider -> final."""
import argparse
import json
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
try:
    from dotenv import load_dotenv
except ImportError:
    # Offline verification is dependency-free; live runs require requirements.txt.
    if "--mock" not in sys.argv and (BASE_DIR / ".env").exists():
        raise SystemExit("Cài requirements.txt để đọc .env, hoặc chạy --mock.")
else:
    load_dotenv(BASE_DIR / ".env")
from mcp_server import MCPAcademicServer
from prompts import CHATBOT_BASELINE_PROMPT, REACT_AGENT_SYSTEM_PROMPT, MAX_ITERATIONS
from providers import get_llm_provider, MockOfflineProvider
from tools import LEAVE_REQUESTS

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

def load_test_cases():
    with (BASE_DIR / "config/test_cases.json").open(encoding="utf-8-sig") as f:
        return json.load(f)

def save_waterfall_trace(trace_data, filename="trace_waterfall.json"):
    path = BASE_DIR / "docs" / filename
    path.write_text(json.dumps(trace_data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Trace: {path}")

def run_baseline_chatbot(user_query, provider):
    response = provider.generate(user_query, system_prompt=CHATBOT_BASELINE_PROMPT)
    print("BASELINE:", response)
    return response

def run_react_agent(user_query, provider, mcp_server, case_id="interactive"):
    provider.reset()
    logs = []
    common = {"case_id": case_id, "run_id": str(uuid.uuid4()), "query": user_query,
              "provider": type(provider).__name__, "model": provider.model_name,
              "mode": "mock" if provider.is_mock else "live",
              "started_at": datetime.now(timezone.utc).isoformat()}
    for step in range(1, MAX_ITERATIONS + 1):
        start = time.perf_counter()
        try:
            response = provider.generate_with_tools(user_query, mcp_server.list_tools(),
                                                   system_prompt=REACT_AGENT_SYSTEM_PROMPT)
            llm_ms = round((time.perf_counter()-start)*1000, 3)
            if response.get("type") == "text":
                if not response.get("content", "").strip():
                    raise ValueError("Empty final answer")
                logs.append({**common, "step": step, "action_type": "FINAL_ANSWER",
                    "thought": "Mô hình trả lời sau các quan sát hiện có (nhãn sự kiện, không phải suy nghĩ nội bộ).",
                    "output": response["content"], "latency_ms": llm_ms})
                print(f'{case_id} FINAL: {response["content"]}')
                return logs
            if response.get("type") != "tool_call" or not response.get("calls"):
                raise ValueError("Invalid provider response")
            results = []
            for call in response["calls"]:
                tool_start = time.perf_counter()
                mcp_result = mcp_server.call_tool(call["tool_name"], call["arguments"])
                tool_ms = round((time.perf_counter()-tool_start)*1000, 3)
                observation = mcp_result["result"]
                results.append({**call, "observation": observation})
                logs.append({**common, "step": step, "action_type": "TOOL_EXECUTION",
                    "thought": f'Mô hình chọn công cụ {call["tool_name"]} (tóm tắt hành động).',
                    "tool_call_id": call["id"], "tool_name": call["tool_name"],
                    "arguments": call["arguments"], "observation": observation,
                    "mcp_response": mcp_result, "llm_latency_ms": llm_ms,
                    "tool_latency_ms": tool_ms, "latency_ms": tool_ms + llm_ms})
            provider.add_tool_results(results)
        except Exception as exc:
            # Do not serialize exception text, which can contain credentials or request URLs.
            logs.append({**common, "step": step, "action_type": "ERROR",
                         "error_type": type(exc).__name__,
                         "output": "Lỗi provider/giao thức. Kiểm tra key, model, quota và kết nối; không fallback Mock.",
                         "latency_ms": round((time.perf_counter()-start)*1000, 3)})
            return logs
    logs.append({**common, "step": MAX_ITERATIONS, "action_type": "MAX_ITERATIONS",
                 "output": "Đã đạt giới hạn vòng lặp, chưa có câu trả lời cuối."})
    return logs

def evaluate(tc, logs):
    tools = [e for e in logs if e["action_type"] == "TOOL_EXECUTION"]
    final = logs[-1] if logs else {}
    checks = {
        "final_answer": final.get("action_type") == "FINAL_ANSWER",
        "tool_sequence": [e["tool_name"] for e in tools] == tc["expected_tools"],
        "statuses": [e["observation"]["status"] for e in tools] == tc["expected_statuses"],
        "answer_evidence": all(s.lower() in final.get("output", "").lower()
                               for s in tc["expected_answer_contains"])
    }
    if tc["id"] in ("TC03", "TC04") and tools:
        expected = ("2026-09-15", "2026-09-16", "việc gia đình") if tc["id"] == "TC03" else ("2026-09-21", "2026-09-23", "du lịch")
        args = tools[-1]["arguments"]
        checks["leave_arguments"] = (args.get("employee_id") == "NV001" and
            (args.get("start_date"), args.get("end_date"), args.get("reason", "").rstrip(".")) == expected)
    return {"case_id": tc["id"], "passed": all(checks.values()), "checks": checks}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--interactive", action="store_true")
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--require-live", action="store_true")
    args = parser.parse_args()
    if args.mock and args.require_live:
        parser.error("--mock không dùng cùng --require-live")
    try:
        provider = MockOfflineProvider() if args.mock else get_llm_provider()
    except Exception as exc:
        print("Cấu hình provider không hợp lệ:", type(exc).__name__, "| Kiểm tra .env hoặc dùng --mock.")
        return 1
    if args.require_live and provider.is_mock:
        print("Yêu cầu API thật nhưng provider đang là Mock.")
        return 1
    print(f"Provider: {type(provider).__name__} | Model: {provider.model_name}")
    server = MCPAcademicServer()
    traces, summary = [], []
    if args.interactive:
        print("Mỗi câu hỏi là một phiên ReAct riêng; hãy nhập đủ dữ liệu. exit/quit để thoát.")
        while True:
            try:
                query = input("Bạn: ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if query.lower() in ("exit", "quit"):
                break
            if query:
                traces.extend(run_react_agent(query, provider, server))
        if traces:
            save_waterfall_trace(traces, "trace_interactive_mock.json" if provider.is_mock else "trace_interactive.json")
        return 0
    tests = load_test_cases() if args.all else [load_test_cases()[1]]
    for tc in tests:
        LEAVE_REQUESTS.clear()  # Isolate fixtures so repeated suites remain reproducible.
        baseline_start = time.perf_counter()
        try:
            baseline = run_baseline_chatbot(tc["question"], provider)
            traces.append({"case_id": tc["id"], "query": tc["question"],
                "provider": type(provider).__name__, "model": provider.model_name,
                "mode": "mock" if provider.is_mock else "live", "action_type": "BASELINE",
                "output": baseline, "latency_ms": round((time.perf_counter()-baseline_start)*1000, 3)})
        except Exception as exc:
            traces.append({"case_id": tc["id"], "action_type": "BASELINE_ERROR",
                "mode": "mock" if provider.is_mock else "live", "error_type": type(exc).__name__})
        logs = run_react_agent(tc["question"], provider, server, tc["id"])
        traces.extend(logs)
        evaluation = evaluate(tc, logs)
        evaluation["checks"]["baseline"] = not any(e["action_type"] == "BASELINE_ERROR" and
            e["case_id"] == tc["id"] for e in traces)
        evaluation["passed"] = all(evaluation["checks"].values())
        summary.append(evaluation)
    passed = sum(s["passed"] for s in summary)
    all_pass = passed == len(tests)
    filename = "trace_waterfall_mock.json" if provider.is_mock else "trace_waterfall.json"
    save_waterfall_trace(traces, filename)
    report = {"mode": "mock" if provider.is_mock else "live", "provider": type(provider).__name__,
              "passed": passed, "total": len(tests), "results": summary,
              "note": "Kiểm tra cấu trúc và bằng chứng cơ bản; đọc lại câu trả lời để đánh giá nội dung."}
    save_waterfall_trace(report, "test_results_mock.json" if provider.is_mock else "test_results_live.json")
    print(f'{"MOCK OFFLINE" if provider.is_mock else "LIVE"}: {passed}/{len(tests)} PASS')
    return 0 if all_pass else 1

if __name__ == "__main__":
    sys.exit(main())
