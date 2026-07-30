"""
core/mcp_manager.py
====================
JARVIS ke liye MCP (Model Context Protocol) CLIENT manager.

Kya karta hai:
  1. `config/mcp_servers.json` se configured MCP servers ko launch + connect
     karta hai (stdio transport — har server ek local child process hota hai).
  2. Har server se uske tools discover karta hai (session.list_tools()).
  3. Sab tools ko JARVIS ke TOOL_DECLARATIONS format mein convert karta hai
     (Gemini Live schema — uppercase types: OBJECT/STRING/NUMBER/etc.),
     naam collision avoid karne ke liye "serverName__toolName" prefix ke sath.
  4. main.py ke _execute_tool() dispatch chain ke andar `mcp_manager.owns(name)`
     check karke `await mcp_manager.call_tool(name, args)` route karta hai.

Requirements:
    pip install mcp

Wiring (main.py mein already integrate ki hui hai — dekho comments jahan
"MCP INTEGRATION" likha hai):
    self.mcp_manager = McpManager()
    await self.mcp_manager.connect_all()
    TOOL_DECLARATIONS.extend(self.mcp_manager.get_tool_declarations())
    ...
    elif self.mcp_manager.owns(name):
        result = await self.mcp_manager.call_tool(name, args)
"""

import os
import json
from contextlib import AsyncExitStack
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from core.paths import CONFIG_DIR

MCP_CONFIG_PATH = CONFIG_DIR / "mcp_servers.json"
TOOL_SEP = "__"

_TYPE_MAP = {
    "object": "OBJECT",
    "string": "STRING",
    "number": "NUMBER",
    "integer": "INTEGER",
    "boolean": "BOOLEAN",
    "array": "ARRAY",
}


def _json_schema_to_gemini(schema: dict) -> dict:
    """MCP tool ka inputSchema (standard lowercase JSON Schema) JARVIS ke
    Gemini Live TOOL_DECLARATIONS format (uppercase types) mein convert karta hai.
    Recursive hai taake nested properties/items bhi sahi convert hon."""
    if not isinstance(schema, dict):
        return {"type": "OBJECT", "properties": {}}

    out = {}
    for key, value in schema.items():
        if key in ("$schema", "additionalProperties", "title"):
            continue
        if key == "type" and isinstance(value, str):
            out["type"] = _TYPE_MAP.get(value.lower(), value.upper())
        elif key == "properties" and isinstance(value, dict):
            out["properties"] = {k: _json_schema_to_gemini(v) for k, v in value.items()}
        elif key == "items" and isinstance(value, dict):
            out["items"] = _json_schema_to_gemini(value)
        else:
            out[key] = value

    out.setdefault("type", "OBJECT")
    return out


class McpManager:
    """Multiple MCP servers manage karta hai aur unke tools JARVIS ke
    dispatch system mein plug karta hai."""

    def __init__(self, config_path: Path = MCP_CONFIG_PATH):
        self.config_path = config_path
        self._stack = AsyncExitStack()
        self.sessions = {}          # server_name -> ClientSession
        self.tools_by_server = {}   # server_name -> [mcp Tool objects]
        self.tool_index = {}        # "server__tool" -> (server_name, original_name)
        self._connected = False

    def _load_config(self) -> list:
        if not self.config_path.exists():
            print(f"[MCP] Config nahi mila ({self.config_path}) — koi MCP server load nahi hoga.")
            return []
        try:
            data = json.loads(self.config_path.read_text(encoding="utf-8"))
        except Exception as e:
            print(f"[MCP] Config parse error: {e}")
            return []
        return data.get("servers", [])

    async def connect_all(self):
        """JARVIS boot hote hi ek dafa call karo (main.py ke run() mein already ho chuka hai).
        Ek server fail ho to baaki par asar nahi — JARVIS partial functionality ke sath chalta rahega."""
        if self._connected:
            return
        self._connected = True

        for cfg in self._load_config():
            if cfg.get("enabled") is False:
                continue
            name = cfg.get("name", "unnamed")
            try:
                await self._connect_one(cfg)
                n = len(self.tools_by_server.get(name, []))
                print(f"[MCP] ✅ Connected: {name} ({n} tools)")
            except Exception as e:
                print(f"[MCP] ❌ FAILED to connect '{name}': {e}")

    async def _connect_one(self, cfg: dict):
        name = cfg["name"]
        env = {**os.environ, **cfg.get("env", {})}
        params = StdioServerParameters(
            command=cfg["command"],
            args=cfg.get("args", []),
            env=env,
        )

        read, write = await self._stack.enter_async_context(stdio_client(params))
        session = await self._stack.enter_async_context(ClientSession(read, write))
        await session.initialize()

        tools_result = await session.list_tools()

        self.sessions[name] = session
        self.tools_by_server[name] = tools_result.tools

        for tool in tools_result.tools:
            prefixed = f"{name}{TOOL_SEP}{tool.name}"
            self.tool_index[prefixed] = (name, tool.name)

    def get_tool_declarations(self) -> list:
        """JARVIS ke TOOL_DECLARATIONS list mein `.extend()` karne ke liye ready format."""
        declarations = []
        for server_name, tools in self.tools_by_server.items():
            for tool in tools:
                prefixed = f"{server_name}{TOOL_SEP}{tool.name}"
                declarations.append({
                    "name": prefixed,
                    "description": f"[{server_name}] {tool.description or ''}".strip(),
                    "parameters": _json_schema_to_gemini(tool.inputSchema or {}),
                })
        return declarations

    def owns(self, tool_name: str) -> bool:
        """main.py ke _execute_tool() dispatch chain mein:
        `elif self.mcp_manager.owns(name):`"""
        return tool_name in self.tool_index

    async def call_tool(self, prefixed_name: str, args: dict) -> str:
        """Gemini se aaya function-call yahan route hota hai asal MCP server tak."""
        if prefixed_name not in self.tool_index:
            return f"Sir, unknown MCP tool: {prefixed_name}"

        server_name, original_name = self.tool_index[prefixed_name]
        session = self.sessions.get(server_name)
        if session is None:
            return f"Sir, MCP server '{server_name}' connected nahi hai."

        try:
            result = await session.call_tool(original_name, arguments=args or {})
        except Exception as e:
            return f"Sir, MCP tool '{prefixed_name}' fail hua: {e}"

        texts = [block.text for block in result.content if hasattr(block, "text")]
        return "\n".join(texts) if texts else "Done."

    async def shutdown(self):
        """JARVIS band hote waqt call karo — sab child processes cleanly close ho jate hain."""
        await self._stack.aclose()
        self.sessions.clear()
        self.tools_by_server.clear()
        self.tool_index.clear()
        self._connected = False
