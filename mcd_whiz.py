#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦麦精算师 (MCD Whiz)
------------------------------------------------------------------
两种运行模式：
  · 离线演示（默认）：内置样本数据，演示五种决策模式核心算法。
  · 真实接入（--live）：连接麦当劳官方 MCP（https://mcp.mcd.cn），
    用 MCD_MCP_TOKEN 调真实工具。详见 MCP_INTEGRATION.md。
各模式→真实工具映射见 SKILL.md / README.md。
依赖：Python 3.7+ 标准库，零第三方依赖（--live 走 mcp_client.py，同为stdlib）。
"""
import argparse
import json
import os
import random
import sys

# ---------------------------------------------------------------------------
# 内置样本数据（演示用，非实时；真实数据来自麦当劳官方 MCP 工具）
# price 单位：元；energy 单位：kcal；protein/fat/carb 单位：g
# ---------------------------------------------------------------------------
MENU = [
    {"code": "P01", "name": "板烧鸡腿堡", "price": 21.0, "energy": 508, "protein": 28, "fat": 21, "carb": 49},
    {"code": "P02", "name": "巨无霸", "price": 24.0, "energy": 563, "protein": 28, "fat": 30, "carb": 43},
    {"code": "P03", "name": "麦辣鸡腿堡", "price": 22.0, "energy": 519, "protein": 26, "fat": 26, "carb": 45},
    {"code": "P04", "name": "吉士汉堡", "price": 13.0, "energy": 312, "protein": 16, "fat": 14, "carb": 31},
    {"code": "P05", "name": "薯条(中)", "price": 12.0, "energy": 329, "protein": 4, "fat": 16, "carb": 42},
    {"code": "P06", "name": "麦辣鸡翅(2块)", "price": 18.0, "energy": 350, "protein": 22, "fat": 23, "carb": 12},
    {"code": "P07", "name": "玉米杯", "price": 10.0, "energy": 115, "protein": 4, "fat": 2, "carb": 23},
    {"code": "P08", "name": "苹果片", "price": 9.0, "energy": 53, "protein": 0, "fat": 0, "carb": 14},
    {"code": "P09", "name": "豆浆", "price": 8.0, "energy": 95, "protein": 6, "fat": 3, "carb": 11},
    {"code": "P10", "name": "可乐(中)", "price": 10.0, "energy": 144, "protein": 0, "fat": 0, "carb": 36},
    {"code": "P11", "name": "麦旋风(奥利奥)", "price": 15.0, "energy": 320, "protein": 6, "fat": 12, "carb": 48},
    {"code": "P12", "name": "鲜煮咖啡", "price": 14.0, "energy": 5, "protein": 0, "fat": 0, "carb": 0},
]

# 样本优惠券：满减
COUPONS = [
    {"name": "麦麦省-满30减8", "threshold": 30.0, "minus": 8.0},
    {"name": "麦麦省-满50减15", "threshold": 50.0, "minus": 15.0},
    {"name": "会员券-满25减5", "threshold": 25.0, "minus": 5.0},
]

# 样本麦麦商城兑换（value 单位：元）
MALL = [
    {"name": "薯条(中)兑换券", "points": 1200, "value": 12.0},
    {"name": "麦辣鸡翅兑换券", "points": 1800, "value": 18.0},
    {"name": "巨无霸兑换券", "points": 2400, "value": 24.0},
    {"name": "麦旋风兑换券", "points": 1500, "value": 15.0},
    {"name": "实物-麦麦公仔", "points": 5000, "value": 39.0},
]

# 样本营销活动日历（真实数据来自 campaign-calendar 工具）
CAMPAIGNS = [
    {"name": "1024程序员节 · M-CODE", "start": "2026-10-24", "end": "2026-10-26",
     "benefit": "巨无霸三件套优惠券", "how": "App/小程序问答获取；GitHub 认证程序员免答题直领"},
    {"name": "会员日 · 麦麦省", "start": "2026-10-15", "end": "2026-10-17",
     "benefit": "多档满减券", "how": "auto-bind-coupons 一键领取"},
    {"name": "疯狂星期四", "start": "2026-10-08", "end": "2026-10-08",
     "benefit": "指定餐品限时优惠", "how": "周四当日下单自动生效"},
    {"name": "麦麦生日会（主题活动）", "start": "2026-11-01", "end": "2026-11-30",
     "benefit": "生日主题派对场次", "how": "query-party-store 查门店 → party-order-create 预约"},
]


def _combo_price(items):
    return round(sum(i["price"] for i in items), 2)


def _best_coupon(total):
    best = None
    for c in COUPONS:
        if total >= c["threshold"]:
            if best is None or c["minus"] > best["minus"]:
                best = c
    return best


def mode_saver(budget):
    # 贪心：单价热量性价比高 + 在预算内尽量凑满减
    cand = [m for m in MENU if m["price"] <= budget]
    # 以"能量/价格"排序挑主食，再补一杯
    cand.sort(key=lambda m: m["energy"] / m["price"], reverse=True)
    picks = []
    spent = 0.0
    for m in cand:
        if spent + m["price"] <= budget:
            picks.append(m)
            spent += m["price"]
    total = _combo_price(picks)
    coupon = _best_coupon(total)
    pay = round(total - coupon["minus"], 2) if coupon else total
    save = round(total - pay, 2)
    return {
        "items": [p["name"] for p in picks],
        "original": total,
        "coupon": coupon["name"] if coupon else "无可用券",
        "pay": pay,
        "saved": save,
        "save_rate": f"{round(save / total * 100, 1)}%" if total else "0%",
    }


def mode_macro(kcal, protein):
    # 暴力搜 1~2 件组合，最小化 |热量-目标| 与 |蛋白-目标|
    best = None
    pool = MENU
    for a in pool:
        for b in pool:
            items = [a] if a is b else [a, b]
            e = sum(i["energy"] for i in items)
            p = sum(i["protein"] for i in items)
            cost = abs(e - kcal) + abs(p - protein) * 5
            if best is None or cost < best["cost"]:
                best = {"items": items, "cost": cost}
    items = best["items"]
    total = _combo_price(items)
    e = sum(i["energy"] for i in items)
    p = sum(i["protein"] for i in items)
    return {
        "items": [i["name"] for i in items],
        "energy": e,
        "protein": p,
        "price": total,
        "target": f"{kcal}kcal / {protein}g 蛋白",
    }


def mode_points(balance):
    ok = [m for m in MALL if m["points"] <= balance]
    ok.sort(key=lambda m: m["value"] / m["points"], reverse=True)
    if not ok:
        return {"tip": "积分不足，去签到/下单攒积分吧", "best": None}
    best = ok[0]
    return {
        "best": best["name"],
        "cost_points": best["points"],
        "value": best["value"],
        "value_per_100": round(best["value"] / best["points"] * 100, 2),
        "all_affordable": [m["name"] for m in ok],
    }


def mode_activity(today="2026-10-11", horizon=30):
    # 按日期把活动分成「进行中 / 即将开始（horizon 天内）」，给出参与方式
    import datetime
    t = datetime.date.fromisoformat(today)
    ongoing, upcoming = [], []
    for c in CAMPAIGNS:
        s = datetime.date.fromisoformat(c["start"])
        e = datetime.date.fromisoformat(c["end"])
        if s <= t <= e:
            ongoing.append(c)
        elif 0 < (s - t).days <= horizon:
            c = dict(c, days_left=(s - t).days)
            upcoming.append(c)
    upcoming.sort(key=lambda c: c["days_left"])
    return {"ongoing": ongoing, "upcoming": upcoming, "tip": "领券别忘 auto-bind-coupons 一键全领"}


def mode_surprise(budget, avoid=""):
    pool = [m for m in MENU if m["price"] <= budget and (not avoid or avoid not in m["name"])]
    picks = random.sample(pool, min(2, len(pool)))
    total = _combo_price(picks)
    lines = [
        "今天你是「佛系麦门弟子」🍟",
        "今天你是「狠人麦霸」🍔",
        "今天你是「自律即自由」🥗",
        "今天你是「快乐水续命派」🥤",
    ]
    return {"items": [p["name"] for p in picks], "price": total, "quote": random.choice(lines)}


def run_live(token):
    """连接真实麦当劳 MCP：握手、列出工具、跑只读工具抽样，并打印五种模式的工具映射。"""
    try:
        from mcp_client import McpClient
    except ImportError:
        print("缺少 mcp_client.py，无法进行真实接入。")
        sys.exit(1)
    if not token:
        print("未提供麦当劳 MCP Token。请设置环境变量 MCD_MCP_TOKEN，或加 --token <你的Token>。")
        sys.exit(1)

    print(">>> 正在连接麦当劳官方 MCP (https://mcp.mcd.cn) ...\n")
    c = McpClient(token=token)
    c.initialize()
    tools = c.list_tools()
    names = [t["name"] for t in tools]
    print(f"✅ 已连接。当前可用工具 {len(names)} 个：")
    for n in names:
        print("   -", n)

    # 五种模式 → 真实工具映射（只校验“工具是否可用”，不触发任何写操作）
    mapping = {
        "省钱 saver": ["query-meals", "calculate-price", "query-store-coupons", "available-coupons", "query-my-coupons"],
        "控卡 macro": ["list-nutrition-foods", "query-meals", "calculate-price"],
        "积分 points": ["query-my-account", "mall-points-products", "mall-product-detail"],
        "活动 activity": ["campaign-calendar", "query-party-city", "query-party-store", "party-order-create"],
        "盲盒 surprise": ["query-meals", "calculate-price"],
    }
    print("\n>>> 五种模式所需工具可用性：")
    for mode, need in mapping.items():
        ok = [t for t in need if t in names]
        miss = [t for t in need if t not in names]
        flag = "✅ 全部就绪" if not miss else f"⚠️ 缺 {miss}"
        print(f"  [{mode}] {flag}")

    # 只读工具真实数据抽样（安全，均为查询类，不会下单/领券）
    print("\n>>> 只读工具真实数据抽样：")
    demo = c.safe_demo()
    for name, s in demo.items():
        print(f"\n  [{name}]")
        if "error" in s:
            print("    错误:", s["error"])
        else:
            print("    isError:", s.get("isError"), "| 数据:", (s.get("text") or "")[:260])
    print("\n--- 真实接入验证完成（未执行任何写操作：下单/领券需用户显式确认）---")


def main():
    ap = argparse.ArgumentParser(description="麦麦精算师：离线演示 + 真实MCP接入")
    ap.add_argument("--mode", choices=["saver", "macro", "points", "activity", "surprise"], default="saver")
    ap.add_argument("--budget", type=float, default=50.0)
    ap.add_argument("--kcal", type=float, default=600.0)
    ap.add_argument("--protein", type=float, default=30.0)
    ap.add_argument("--balance", type=float, default=3200.0)
    ap.add_argument("--avoid", type=str, default="")
    ap.add_argument("--demo", action="store_true", help="跑全部模式内置示例（离线）")
    ap.add_argument("--today", type=str, default="2026-10-11")
    ap.add_argument("--horizon", type=int, default=30)
    ap.add_argument("--live", action="store_true", help="连接真实麦当劳 MCP（需 MCD_MCP_TOKEN 或 --token）")
    ap.add_argument("--token", type=str, default=None, help="麦当劳 MCP Token（也可走环境变量 MCD_MCP_TOKEN）")
    args = ap.parse_args()

    if args.live:
        run_live(args.token or os.environ.get("MCD_MCP_TOKEN", ""))
        return

    if args.demo:
        print("=== [省钱] 预算50 ===")
        print(json.dumps(mode_saver(50), ensure_ascii=False, indent=2))
        print("\n=== [控卡] 600kcal/30g蛋白 ===")
        print(json.dumps(mode_macro(600, 30), ensure_ascii=False, indent=2))
        print("\n=== [积分] 余额3200 ===")
        print(json.dumps(mode_points(3200), ensure_ascii=False, indent=2))
        print("\n=== [活动] 2026-10-11 起30天 ===")
        print(json.dumps(mode_activity(args.today, args.horizon), ensure_ascii=False, indent=2))
        print("\n=== [盲盒] 预算30 ===")
        print(json.dumps(mode_surprise(30), ensure_ascii=False, indent=2))
        return

    if args.mode == "saver":
        out = mode_saver(args.budget)
    elif args.mode == "macro":
        out = mode_macro(args.kcal, args.protein)
    elif args.mode == "points":
        out = mode_points(args.balance)
    elif args.mode == "activity":
        out = mode_activity(args.today, args.horizon)
    else:
        out = mode_surprise(args.budget, args.avoid)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
