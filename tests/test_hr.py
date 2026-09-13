"""Dependency-free regression checks for HR rules and ReAct control flow."""
import contextlib
import io
import json
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from tools import dispatch_tool_call, LEAVE_REQUESTS
from mcp_server import MCPAcademicServer
from providers import MockOfflineProvider
from app import run_react_agent, evaluate, load_test_cases
from prompts import MAX_ITERATIONS

class HRTests(unittest.TestCase):
    def setUp(self):
        LEAVE_REQUESTS.clear()

    def tool(self, name="create_leave_request", **kwargs):
        return json.loads(dispatch_tool_call(name, kwargs))

    def leave(self, **changes):
        args = dict(employee_id="NV001", start_date="2026-09-15", end_date="2026-09-16", reason="Gia đình")
        args.update(changes)
        return self.tool(**args)

    def test_schema_validation(self):
        for args in ({}, {"employee_id": 42}, {"employee_id": " "},
                     {"employee_id": "NV001", "extra": "x"}):
            self.assertEqual(self.tool("hr_query", **args)["status"], "INVALID_ARGUMENTS")
        self.assertEqual(self.tool("unknown")["status"], "UNKNOWN_TOOL")

    def test_unknown_employee(self):
        self.assertEqual(self.leave(employee_id="NV999")["status"], "NOT_FOUND")
        self.assertEqual(LEAVE_REQUESTS, [])

    def test_invalid_dates(self):
        for start, end in [("2026-02-30", "2026-03-01"), ("2026-09-17", "2026-09-16"),
                           ("2026-09-19", "2026-09-20"), ("2026-12-31", "2027-01-01")]:
            self.assertEqual(self.leave(start_date=start, end_date=end)["status"], "INVALID_ARGUMENTS")
        self.assertEqual(LEAVE_REQUESTS, [])

    def test_insufficient_balance(self):
        self.assertEqual(self.leave(employee_id="NV002")["status"], "INSUFFICIENT_BALANCE")
        self.assertEqual(LEAVE_REQUESTS, [])

    def test_duplicate_and_overlap(self):
        first, second = self.leave(), self.leave()
        self.assertEqual(first["request_id"], second["request_id"])
        self.assertTrue(second["duplicate"])
        self.assertEqual(len(LEAVE_REQUESTS), 1)
        self.assertEqual(self.leave(end_date="2026-09-17")["status"], "OVERLAP")
        self.assertEqual(self.tool("hr_query", employee_id="NV001")["data"]["available_days"], 10)

    def test_weekend_excluded(self):
        self.assertEqual(self.leave(start_date="2026-09-18", end_date="2026-09-21")["days"], 2)

    def test_mcp_envelope(self):
        server = MCPAcademicServer()
        first = server.call_tool("hr_query", {"employee_id": "NV001"})
        second = server.call_tool("hr_query", {"employee_id": "NV999"})
        self.assertEqual(first["jsonrpc"], "2.0")
        self.assertGreater(second["id"], first["id"])
        self.assertEqual(second["result"]["status"], "NOT_FOUND")

    def run_agent(self, query, provider=None):
        with contextlib.redirect_stdout(io.StringIO()):
            return run_react_agent(query, provider or MockOfflineProvider(), MCPAcademicServer())

    def test_five_cases(self):
        for case in load_test_cases():
            LEAVE_REQUESTS.clear()
            self.assertTrue(evaluate(case, self.run_agent(case["question"]))["passed"], case["id"])

    def test_missing_details_no_write(self):
        logs = self.run_agent("Tạo đơn cho NV001.")
        self.assertEqual(len(LEAVE_REQUESTS), 0)
        self.assertIn("cung cấp", logs[-1]["output"])

    def test_dynamic_rejection(self):
        logs = self.run_agent("Tạo đơn cho NV002 từ 2026-09-15 đến 2026-09-16, lý do: gia đình.")
        self.assertEqual(len(LEAVE_REQUESTS), 0)
        self.assertEqual([e["tool_name"] for e in logs if e["action_type"] == "TOOL_EXECUTION"], ["hr_query"])

    def test_provider_failure_not_final(self):
        class Broken(MockOfflineProvider):
            def generate_with_tools(self, *args, **kwargs):
                raise RuntimeError("secret should not be logged")
        logs = self.run_agent("test", Broken())
        self.assertEqual(logs[-1]["action_type"], "ERROR")
        self.assertNotIn("secret", json.dumps(logs))

    def test_iteration_limit(self):
        class Looper(MockOfflineProvider):
            def generate_with_tools(self, *args, **kwargs):
                return {"type": "tool_call", "calls": [{"id": "x", "tool_name": "hr_query",
                                                       "arguments": {"employee_id": "NV001"}}]}
        logs = self.run_agent("test", Looper())
        self.assertEqual(logs[-1]["action_type"], "MAX_ITERATIONS")
        self.assertEqual(len(logs), MAX_ITERATIONS + 1)

if __name__ == "__main__":
    unittest.main()
