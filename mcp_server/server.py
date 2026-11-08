"""
Servidor MCP (Model Context Protocol) para MIRA.
Soporta comunicación stdio compatible con el estándar MCP y API directa para el backend.
"""

import sys
import json
from typing import Dict, Any
from mcp_server.tools import MCP_TOOLS_SPEC, execute_tool

class MCPServer:
    def __init__(self):
        self.tools = {t["name"]: t for t in MCP_TOOLS_SPEC}

    def list_tools(self) -> Dict[str, Any]:
        return {"tools": MCP_TOOLS_SPEC}

    def call_tool(self, name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        result = execute_tool(name, arguments)
        is_error = "error" in result if isinstance(result, dict) else False
        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, ensure_ascii=False, indent=2)
                }
            ],
            "isError": is_error,
            "raw_data": result
        }

    def run_stdio(self):
        """
        Bucle JSON-RPC 2.0 por stdio para clientes MCP estándar.
        """
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue
            try:
                request = json.loads(line)
                req_id = request.get("id")
                method = request.get("method")
                params = request.get("params", {})

                if method == "tools/list":
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": self.list_tools()
                    }
                elif method == "tools/call":
                    tool_name = params.get("name")
                    arguments = params.get("arguments", {})
                    tool_res = self.call_tool(tool_name, arguments)
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "result": tool_res
                    }
                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": req_id,
                        "error": {"code": -32601, "message": f"Método no soportado: {method}"}
                    }
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
            except Exception as e:
                err_response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32603, "message": str(e)}
                }
                sys.stdout.write(json.dumps(err_response) + "\n")
                sys.stdout.flush()

if __name__ == "__main__":
    server = MCPServer()
    server.run_stdio()

