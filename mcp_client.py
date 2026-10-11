#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦当劳官方 MCP 客户端（Streamable HTTP 协议，零依赖）

仅用 Python 标准库实现，连接 https://mcp.mcd.cn：
  - initialize 握手（捕获 Mcp-Session-Id）
  - tools/list 列出全部可用工具及其参数 schema
  - tools/call 调用任意工具

鉴权：请求头 Authorization: Bearer <MCP_TOKEN>
限流：官方 600 次/分钟，脚本已内置简单间隔控制。

用法（在代码里）：
  from mcp_client import McpClient
  c = McpClient(token="你的麦当劳MCP Token")
  c.initialize()
  tools = c.list_tools()
  r = c.call_tool("list-nutrition-foods", {})
"""

import json
import os
import time
import urllib.request
import urllib.error

DEFAULT_BASE = "https://mcp.mcd.cn"
DEFAULT_PROXY = "http://127.0.0.1:65182"   # 本机出网代理（无网环境可改/留空）


class McpClient:
    def __init__(self, token=None, base_url=DEFAULT_BASE, proxy=None):
        self.base_url = base_url
        self.token = token or os.environ.get("MCD_MCP_TOKEN", "")
        self.proxy = proxy if proxy is not None else os.environ.get("MCD_PROXY", DEFAULT_PROXY)
        self.session_id = None
        self._id = 0
        self._last_call = 0.0

    # ---------- 底层 ----------
    def _next_id(self):
        self._id += 1
        return self._id

    def _opener(self):
        handlers = []
        if self.proxy:
            handlers.append(urllib.request.ProxyHandler({"http": self.proxy, "https": self.proxy}))
        return urllib.request.build_opener(*handlers)

    @staticmethod
    def _parse(body, content_type):
        if "text/event-stream" in (content_type or ""):
            for line in body.splitlines():
                if line.startswith("data:"):
                    chunk = line[5:].strip()
                    if chunk:
                        try:
                            return json.loads(chunk)
                        except Exception:
                            pass
            return {}
        try:
            return json.loads(body) if body.strip() else {}
        except Exception:
            return {"raw": body}

    def _post(self, payload, min_interval=0.2):
        # 简单限流：两次调用之间至少间隔 min_interval 秒
        now = time.time()
        wait = min_interval - (now - self._last_call)
        if wait > 0:
            time.sleep(wait)
        self._last_call = time.time()

        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.base_url, data=data, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Accept", "application/json, text/event-stream")
        if self.token:
            req.add_header("Authorization", "Bearer " + self.token)
        if self.session_id:
            req.add_header("Mcp-Session-Id", self.session_id)

        try:
            with self._opener().open(req, timeout=30) as r:
                sid = r.headers.get("mcp-session-id") or r.headers.get("Mcp-Session-Id")
                if sid:
                    self.session_id = sid
                ct = r.headers.get("Content-Type", "")
                body = r.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            return {"error": {"code": e.code, "message": body[:500]}}
        return self._parse(body, ct)

    # ---------- MCP 协议 ----------
    def initialize(self):
        resp = self._post({
            "jsonrpc": "2.0", "id": self._next_id(), "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "mcd-whiz", "version": "1.0.0"},
            },
        })
        # 发送 initialized 通知（不需要响应）
        self._post({"jsonrpc": "2.0", "method": "notifications/initialized", "params": {}})
        return resp

    def list_tools(self):
        resp = self._post({"jsonrpc": "2.0", "id": self._next_id(), "method": "tools/list", "params": {}})
        return (resp.get("result") or {}).get("tools", [])

    def call_tool(self, name, arguments=None):
        return self._post({
            "jsonrpc": "2.0", "id": self._next_id(), "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        })

    # ---------- 便捷封装 ----------
    def tool_names(self):
        return [t["name"] for t in self.list_tools()]

    def safe_demo(self):
        """调用一批只读工具，返回真实数据摘要（用于验证连接 + 演示）。"""
        out = {}
        read_only = [
            "now-time-info",
            "list-nutrition-foods",
            "campaign-calendar",
            "query-my-account",
            "mall-points-products",
        ]
        available = set(self.tool_names())
        for name in read_only:
            if name in available:
                r = self.call_tool(name, {})
                out[name] = self._summarize(r)
        return out

    @staticmethod
    def _summarize(resp):
        if "error" in resp:
            return {"error": resp["error"]}
        res = (resp.get("result") or {})
        content = res.get("content") or []
        text = ""
        for c in content:
            if c.get("type") == "text":
                text += c.get("text", "")
        return {"isError": res.get("isError", False), "text": text[:800]}


if __name__ == "__main__":
    import sys
    tok = os.environ.get("MCD_MCP_TOKEN", "")
    if not tok:
        print("未设置 MCD_MCP_TOKEN，无法连接真实 MCP。请先配置 Token。")
        sys.exit(1)
    c = McpClient(token=tok)
    print(">>> initialize ...")
    c.initialize()
    tools = c.list_tools()
    print(f">>> 已连接，可用工具 {len(tools)} 个：")
    for t in tools:
        print("  -", t["name"], ":", (t.get("description") or "")[:40])
    print("\n>>> 只读工具真实数据抽样：")
    for name, s in c.safe_demo().items():
        print(f"\n[{name}]")
        if "error" in s:
            print("  错误:", s["error"])
        else:
            print("  isError:", s.get("isError"), "| 数据:", s.get("text", "")[:300])
