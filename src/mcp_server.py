"""Starter MCP simulation: in-process boundary, no network transport."""
import json
from tools import TOOLS_SCHEMA, dispatch_tool_call

class MCPAcademicServer:
    # Preserve starter import compatibility.
    def __init__(self, server_name="hr-assistant-mcp-server"):
        self.server_name = server_name
        self.version = "2026.1.0"
        self.request_id = 0

    def list_tools(self):
        return TOOLS_SCHEMA

    def call_tool(self, tool_name, arguments):
        self.request_id += 1
        return {"jsonrpc": "2.0", "id": self.request_id, "server": self.server_name,
                "tool": tool_name, "result": json.loads(dispatch_tool_call(tool_name, arguments))}

if __name__ == "__main__":
    server = MCPAcademicServer()
    assert len(server.list_tools()) == 2
    response = server.call_tool("hr_query", {"employee_id": "NV001"})
    assert response["result"]["status"] == "SUCCESS"
    print("MCP SERVER PASS | 2 tools |", server.server_name, server.version)
    print(json.dumps(response, ensure_ascii=True))
