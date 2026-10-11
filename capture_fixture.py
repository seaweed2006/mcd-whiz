#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
抓取一次「真实麦当劳 MCP」的数据，存成离线快照 fixtures/*.json。

为什么需要它：
  评委/观众没有麦当劳 MCP Token，无法跑 --live，
  就看不到"这玩意是不是真的接了麦当劳 MCP"——本作品的核心卖点无法验证。
  存一份真实数据快照后，任何人执行 `python mcd_whiz.py --demo-real`
  即可**离线回放真实数据跑完全流程**，证明数据是真的。

产出两份（隐私分级）：
  · real_snapshot_public.json   菜单 / 营养 / 门店 / 积分商城目录 —— 可公开，随仓库提交
  · real_snapshot_private.json  我的积分账户 / 卡包券            —— 只留本地，.gitignore 已忽略
  回放时优先读 public，本地有 private 就合并进来（评委端没有 private 会自动降级并如实标注）。

用法：
  set MCD_MCP_TOKEN=你的Token           (Windows CMD)
  $env:MCD_MCP_TOKEN="你的Token"         (PowerShell)
  python capture_fixture.py

安全：只保存菜单/营养/券/积分商城等业务数据；Token 与手机号不写入快照。
"""
import datetime
import json
import os
import re
import sys

import mcd_whiz as M
from mcp_client import McpClient

OUT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
OUT_PUBLIC = os.path.join(OUT_DIR, M.SNAPSHOT_PUBLIC)
OUT_PRIVATE = os.path.join(OUT_DIR, M.SNAPSHOT_PRIVATE)

# 各段原文最多保存多少字符（防止快照过大；mall 这类长列表尤其明显）
RAW_CAP = {
    "store_coupons": 8000,
    "mall_products": 60000,
    "my_coupons": 20000,
    "my_account": 8000,
}


def scrub(obj):
    """脱敏：移除任何看起来像凭据/手机号的字段。"""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if re.search(r"token|secret|password", str(k), re.I):
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
    stats = {}
    items, n_meals, n_nutri, store = M.fetch_real_items(c, stats=stats)
    if stats:
        print("   菜单↔营养表匹配：精确 %d / 归一化 %d / 模糊 %d / 套餐跳过 %d / 未命中 %d"
              % (stats.get("exact", 0), stats.get("norm", 0), stats.get("fuzzy", 0),
                 stats.get("skip_combo", 0), stats.get("miss", 0)))

    meta_common = {
        "captured_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "source": "麦当劳官方 MCP (M-China/mcd-mcp-server) 真实调用",
        "endpoint": "https://mcp.mcd.cn",
        "store_code": store,
        "tool_count": len(tool_names),
        "tools": tool_names,
        "match_stats": stats,
    }

    public = {
        "_meta": dict(meta_common, **{
            "privacy": "公开段：仅含菜单/营养/门店/积分商城目录，可随仓库发布",
            "note": "真实业务数据，已脱敏（不含 Token/手机号）。用于 --demo-real 离线回放。",
        }),
        "items": [scrub(i) for i in items],
        "counts": {"meals": n_meals, "nutrition": n_nutri, "items_total": len(items)},
    }
    private = {
        "_meta": dict(meta_common, **{
            "privacy": "私有段：含个人账户/卡包券，请勿提交仓库（.gitignore 已忽略）",
        }),
    }

    # 尽力抓取：券 / 积分 / 会员（任一失败不阻断）
    for label, tool, args, key, bucket in (
        ("门店券", "query-store-coupons", {}, "store_coupons", public),
        ("积分商城", "mall-points-products", {"catRuleIds": "1>4"}, "mall_products", public),
        ("我的券包", "query-my-coupons", {}, "my_coupons", private),
        ("我的账户", "query-my-account", {}, "my_account", private),
    ):
        try:
            txt, _ = M._tool_text(c, tool, args)
            bucket[key] = scrub(txt)[:RAW_CAP.get(key, 8000)]
            print(f"   ✅ {label}（{len(bucket[key])} 字符 → {'public' if bucket is public else 'private'}）")
        except Exception as e:
            bucket[key] = None
            print(f"   ⚠️ {label} 抓取失败（不影响主流程）：{e}")

    os.makedirs(OUT_DIR, exist_ok=True)
    with open(OUT_PUBLIC, "w", encoding="utf-8") as f:
        json.dump(public, f, ensure_ascii=False, indent=2)
    with open(OUT_PRIVATE, "w", encoding="utf-8") as f:
        json.dump(private, f, ensure_ascii=False, indent=2)

    priced = [i for i in items if (i.get("price") or 0) > 0]
    print(f"\n✅ 公开快照：{OUT_PUBLIC}")
    print(f"✅ 私有快照：{OUT_PRIVATE}（勿提交，.gitignore 已忽略）")
    print(f"   门店 {store} | 工具 {len(tool_names)} 个 | 餐品 {len(items)} 件（有价 {len(priced)} 件）")
    print("   现在任何人无需 Token 即可回放：python mcd_whiz.py --demo-real")
    return 0


if __name__ == "__main__":
    sys.exit(main())
