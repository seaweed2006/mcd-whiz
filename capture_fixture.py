#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抓取一次「真实麦当劳 MCP」的数据，存成离线快照 fixtures/real_snapshot.json。

为什么需要它：
  评委/观众没有麦当劳 MCP Token，无法跑 --live，
  就看不到"这玩意是不是真的接了麦当劳 MCP"——本作品的核心卖点无法验证。
  存一份真实数据快照后，任何人执行 `python mcd_whiz.py --demo-real`
  即可**离线回放真实数据跑完全流程**，证明数据是真的。

用法：
  set MCD_MCP_TOKEN=你的Token           (Windows CMD)
  $env:MCD_MCP_TOKEN="你的Token"         (PowerShell)
  python capture_fixture.py

安全：只保存菜单/营养/券/积分商城等公开业务数据；Token 与手机号不写入快照。
"""
import base64
import datetime
import json
import os
import re
import sys

PROXY = None
for k in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
    if os.environ.get(k):
        PROXY = os.environ[k]
        break

import mcd_whiz as M
from mcp_client import McpClient

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
OUT_FILE = os.path.join(OUT_DIR, "real_snapshot.json")


def scrub(obj):
    """脱敏：移除任何看起来像凭据/手机号的字段。"""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if re.search(r"token|secret|password|phone|mobile|手机", str(k), re.I):
                continue
            out[k] = scrub(v)
        return out
    if isinstance(obj, list):
        return [scrub(x) for x in obj]
    if isinstance(obj, str):
        s = re.sub(r"\b1[3-9]\d{9}\b", "1XXXXXXXXXX", obj)          # 手机号
        s = re.sub(r"\b(mm|ghp|sk)[A-Za-z0-9_\-]{16,}\b", "***REDACTED***", s)  # 各类 Token
        return s
    return obj


def main():
    token = os.environ.get("MCD_MCP_TOKEN") or (sys.argv[1] if len(sys.argv) > 1 else "")
    if not token:
        print("❌ 缺少 Token：请设置环境变量 MCD_MCP_TOKEN，或作为参数传入")
        return 1

    print(">>> 连接真实麦当劳 MCP ...")
    c = McpClient(token=token)
    c.initialize()
    tools = c.list_tools()
    tool_names = [t.get("name") for t in tools] if isinstance(tools, list) else []

    print(">>> 抓取真实菜单 / 营养 / 门店 ...")
    items, n_meals, n_nutri, store = M.fetch_real_items(c)

    snap = {
        "_meta": {
            "captured_at": datetime.datetime.now().isoformat(timespec="seconds"),
            "source": "麦当劳官方 MCP (M-China/mcd-mcp-server) 真实调用",
            "endpoint": "https://mcp.mcd.cn",
            "store_code": store,
            "tool_count": len(tool_names),
            "tools": tool_names,
            "note": "本快照为真实业务数据，已脱敏（不含 Token/手机号）。用于 --demo-real 离线回放。",
        },
        "items": [scrub(i) for i in items],
        "counts": {"meals": n_meals, "nutrition": n_nutri, "items_total": len(items)},
    }

    # 尽力抓取：券 / 积分 / 会员（任一失败不阻断）
    for label, tool, args, key in (
        ("门店券", "query-store-coupons", {}, "store_coupons"),
        ("我的券包", "query-my-coupons", {}, "my_coupons"),
        ("我的账户", "query-my-account", {}, "my_account"),
        ("积分商城", "mall-points-products", {}, "mall_products"),
    ):
        try:
            txt, _ = M._tool_text(c, tool, args)
            snap[key] = scrub(txt)[:4000]
            print(f"   ✅ {label}")
        except Exception as e:
            snap[key] = None
            print(f"   ⚠️ {label} 抓取失败（不影响主流程）：{e}")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(snap, f, ensure_ascii=False, indent=2)

    priced = [i for i in items if i.get("price") is not None]
    print(f"\n✅ 快照已保存：{OUT_FILE}")
    print(f"   门店 {store} | 工具 {len(tool_names)} 个 | 餐品 {len(items)} 件（有价 {len(priced)} 件）")
    print(f"   现在任何人无需 Token 即可回放：python mcd_whiz.py --demo-real")
    return 0


if __name__ == "__main__":
    sys.exit(main())
