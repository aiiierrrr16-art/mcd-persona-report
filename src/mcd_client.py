"""极简麦当劳 MCP 客户端（Streamable HTTP / JSON-RPC）。

零第三方依赖，仅用标准库。
用法:
    from mcd_client import McdClient
    client = McdClient(token="YOUR_MCP_TOKEN")
    result = client.call_tool("order-list", {})
"""
import json
import re
import time
import urllib.request
import urllib.error

MCP_URL = "https://mcp.mcd.cn"


class McdClient:
    def __init__(self, token: str, url: str = MCP_URL):
        self.token = token
        self.url = url
        self._req_id = 0
        self._initialized = False

    def _post(self, payload: dict) -> dict:
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            self.url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            },
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            raw = resp.read().decode("utf-8")
        return self._parse(raw)

    @staticmethod
    def _parse(raw: str) -> dict:
        """兼容纯 JSON 与 SSE (event: message / data: {...}) 两种返回。"""
        raw = raw.strip()
        if raw.startswith("{"):
            return json.loads(raw)
        blocks = re.findall(r"^data:\s*(\{.*)$", raw, re.MULTILINE)
        if not blocks:
            raise ValueError(f"无法解析 MCP 响应: {raw[:200]}")
        return json.loads(blocks[-1])

    def _ensure_init(self):
        if self._initialized:
            return
        self._post({
            "jsonrpc": "2.0", "id": self._next_id(), "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26", "capabilities": {},
                "clientInfo": {"name": "mcd-persona-report", "version": "1.0.0"},
            },
        })
        try:  # 通知消息可能不需要应答，失败忽略
            self._post({"jsonrpc": "2.0", "method": "notifications/initialized"})
        except Exception:
            pass
        self._initialized = True

    def _next_id(self) -> int:
        self._req_id += 1
        return self._req_id

    def call_tool(self, name: str, arguments: dict | None = None,
                  retries: int = 2) -> dict:
        """调用工具，返回 content[0].text 解析后的 JSON 或纯文本。"""
        self._ensure_init()
        payload = {
            "jsonrpc": "2.0", "id": self._next_id(),
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments or {}},
        }
        last_err = None
        for attempt in range(retries + 1):
            try:
                resp = self._post(payload)
                break
            except (urllib.error.URLError, TimeoutError, OSError) as e:
                last_err = e
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
        else:
            raise RuntimeError(f"MCP 调用 {name} 失败: {last_err}")

        if "error" in resp:
            raise RuntimeError(f"MCP 错误: {resp['error']}")
        content = resp.get("result", {}).get("content", [])
        if not content:
            return {}
        text = content[0].get("text", "")
        try:
            return json.loads(text)
        except (json.JSONDecodeError, TypeError):
            pass
        # 服务器可能在 JSON 前附加说明文档，提取其中的业务 JSON（含 "success" 字段）
        pos = text.find('{"success"')
        if pos >= 0:
            try:
                return json.JSONDecoder().raw_decode(text[pos:])[0]
            except json.JSONDecodeError:
                pass
        return {"_raw_text": text}
