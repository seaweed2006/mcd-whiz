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
import itertools
import json
import os
import random
import re
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

# 样本麦麦商城兑换（value 单位：元）。券名与 MENU 同名 → 演示"同品积分券替换"
MALL = [
    {"name": "薯条(中)兑换券", "points": 1200, "value": 12.0},
    {"name": "麦辣鸡翅兑换券", "points": 1800, "value": 18.0},
    {"name": "巨无霸兑换券", "points": 2400, "value": 24.0},
    {"name": "麦旋风兑换券", "points": 1500, "value": 15.0},
    {"name": "吉士汉堡兑换券", "points": 1200, "value": 8.0},
    {"name": "板烧鸡腿堡兑换券", "points": 2100, "value": 15.0},
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
    return round(sum(i["price"] for i in items if i.get("price") is not None), 2)


def _best_coupon(total, coupons=None):
    cps = coupons if coupons is not None else COUPONS
    best = None
    for c in cps:
        if total >= c["threshold"]:
            if best is None or c["minus"] > best["minus"]:
                best = c
    return best


def mode_saver(budget, items=None, coupons=None):
    src = items if items is not None else MENU
    cps = coupons if coupons is not None else COUPONS
    # 贪心：单价热量性价比高 + 在预算内尽量凑满减
    cand = [m for m in src if m["price"] <= budget]
    # 以"能量/价格"排序挑主食，再补一杯（无营养数据者按 1/价格 兜底，仍可入选）
    cand.sort(key=lambda m: ((m["energy"] or 1) / m["price"]), reverse=True)
    picks = []
    spent = 0.0
    for m in cand:
        if spent + m["price"] <= budget:
            picks.append(m)
            spent += m["price"]
    total = _combo_price(picks)
    coupon = _best_coupon(total, cps) if cps else None
    pay = round(total - coupon["minus"], 2) if coupon else total
    save = round(total - pay, 2)
    return {
        "items": [p["name"] for p in picks],
        "original": total,
        "coupon": coupon["name"] if coupon else "无可用券（可 auto-bind-coupons 一键领）",
        "pay": pay,
        "saved": save,
        "save_rate": f"{round(save / total * 100, 1)}%" if total else "0%",
    }


def mode_macro(kcal, protein, items=None):
    # 暴力搜 1~2 件组合，最小化 |热量-目标| 与 |蛋白-目标|
    pool = items if items is not None else MENU
    best = None
    for a in pool:
        for b in pool:
            its = [a] if a is b else [a, b]
            e = sum(i["energy"] for i in its)
            p = sum(i["protein"] for i in its)
            cost = abs(e - kcal) + abs(p - protein) * 5
            if best is None or cost < best["cost"]:
                best = {"items": its, "cost": cost}
    its = best["items"]
    total = _combo_price(its)
    e = sum(i["energy"] for i in its)
    p = sum(i["protein"] for i in its)
    return {
        "items": [i["name"] for i in its],
        "energy": e,
        "protein": p,
        "price": total,
        "target": f"{kcal}kcal / {protein}g 蛋白",
    }


def mode_points(balance=None, products=None, expire_soon=0.0, meals=None):
    """积分模式：用真实积分余额 + 真实积分商城，算出"最值兑换"。
    products 为 _parse_mall_products 的结果；balance/expire_soon 来自 _parse_my_account；
    meals 为带价格的真实餐品，用于把"食品券"名称匹配到菜单价，估算真实到手价值。
    价值估算优先级：①券名含某餐品名→用该餐品菜单价；②商城标注金额(price)作弱代理；
    ③1积分兑换活动→给名义价值。vpp = 价值/积分*100（每百积分到手价值）。"""
    if products is None:
        products = [{"name": m["name"], "point": m["points"], "price": m["value"],
                     "cat": "商品券", "status": 2} for m in MALL]
    if balance is None:
        balance = 3200.0
    meal_by_name = {}
    if meals:
        for m in meals:
            if m.get("price") is not None:
                meal_by_name[m["name"]] = m["price"]

    def est_value(p):
        nm = p["name"]
        for mn, mp in meal_by_name.items():
            if mn in nm or nm in mn:
                return mp
        if p["price"] > 0:
            return p["price"]
        if p["point"] <= 1:
            return 3.0
        return 0.0

    on = [p for p in products if p.get("status") == 2 and p["point"] > 0]
    for p in on:
        v = est_value(p)
        p["value"] = v
        p["vpp"] = round(v / p["point"] * 100, 2) if p["point"] else 0.0
    on.sort(key=lambda p: p["vpp"], reverse=True)
    afford = [p for p in on if p["point"] <= balance]
    afford.sort(key=lambda p: p["vpp"], reverse=True)
    best = on[0] if on else None
    best_afford = afford[0] if afford else None
    return {
        "available_points": balance,
        "expire_this_month": expire_soon,
        "best_value_overall": {k: best[k] for k in ("name", "point", "price", "value", "vpp")} if best else None,
        "best_affordable_now": {k: best_afford[k] for k in ("name", "point", "price", "value", "vpp")} if best_afford else None,
        "affordable_count": len(afford),
        "tip": ("⚠️ 本月 %.1f 积分将过期，优先兑换低分商品别浪费" % expire_soon) if expire_soon > 0
               else "积分长期有效，可攒着换高价值商品",
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


def mode_surprise(budget, avoid="", items=None):
    """盲盒模式：在预算内随机生成一套「像真实点单」的组合。
    优先「1 主食 + 1 小食」随机配对；若预算/品类不够则退化为随机 1~2 件。
    传入真实门店价 items 时即为「接真实数据的盲盒」（run_live 默认如此）。"""
    src = items if items is not None else MENU
    pool = [m for m in src if m.get("price") is not None and m["price"] <= budget
            and (not avoid or avoid not in m["name"])]
    if not pool:
        return {"items": [], "price": 0.0, "quote": "预算内无可选餐品，调高预算或放宽条件试试～"}
    mains = [m for m in pool if any(k in m["name"] for k in MAIN_KW)]
    sides = [m for m in pool if any(k in m["name"] for k in SIDE_KW)]
    picks = None
    if mains and sides:
        main = random.choice(mains)
        ok_sides = [s for s in sides if s["name"] != main["name"]
                    and main["price"] + s["price"] <= budget]
        if ok_sides:
            picks = [main, random.choice(ok_sides)]
    if not picks:
        picks = random.sample(pool, min(2, len(pool)))
    total = _combo_price(picks)
    lines = [
        "今天你是「佛系麦门弟子」🍟",
        "今天你是「狠人麦霸」🍔",
        "今天你是「自律即自由」🥗",
        "今天你是「快乐水续命派」🥤",
    ]
    return {"items": [p["name"] for p in picks], "price": total, "quote": random.choice(lines)}


SAUCE_KW = ["酱", "蘸", "风味", "配料", "调料", "葱", "香菜"]
DRINK_KW = ["可乐", "咖啡", "豆浆", "茶", "橙", "汁", "牛奶", "旋", "汽", "柠檬", "苹果", "沙拉"]
SIDE_KW = ["薯条", "鸡翅", "鸡块", "鸡米", "玉米", "派", "麦乐", "nugget", "杯", "圆筒", "旋风", "圣代"]
MAIN_KW = ["堡", "腿", "鸡", "牛", "虾", "排", "饭", "卷", "肉", "鱼", "猪"]


def _is_excluded(n):
    return any(k in n for k in SAUCE_KW + DRINK_KW)


def _member_redeem_plan(combo, balance, mall_food):
    """对给定套餐找一张积分券替换其中单品，返回省现金的方案或 None。
    mall_food 为积分商城食品券列表（含 point/price/name）；balance 为可用积分。"""
    if not combo or not mall_food:
        return None
    # 先精确匹配同名单品
    for item in combo:
        hit = next((f for f in mall_food
                    if item["name"] in f["name"] or f["name"] in item["name"]), None)
        if hit and hit.get("point", 0) <= balance:
            saved = round((item.get("price") or 0) - hit.get("price", 0), 2)
            if saved > 0:
                return {"replace_item": item["name"], "with_coupon": hit["name"],
                        "cost_points": hit["point"], "cash_topup": hit.get("price"),
                        "cash_saved": saved}
    # 退而求其次：仅当某券名能匹配到套餐里某单品时，才做同品替换（避免"把汉堡换成薯条"的误导）
    ok = [f for f in mall_food if f.get("point", 0) > 0 and f["point"] <= balance]
    ok.sort(key=lambda f: (f["price"] / f["point"]) if f["point"] else 0, reverse=True)
    for f in ok:
        match = next((m for m in combo if m["name"] in f["name"] or f["name"] in m["name"]), None)
        if match:
            saved = round((match.get("price", 0) - f.get("price", 0)), 2)
            if saved > 0:
                return {"replace_item": match["name"], "with_coupon": f["name"],
                        "cost_points": f["point"], "cash_topup": f.get("price"),
                        "cash_saved": saved}
    return None


def _member_combo_search(budget, items, balance, mall_food, coupon_pool=None):
    """预算内搜最优会员套餐：枚举 1~3 件组合，最大化到手食物价值 + 会员折扣。
    返回最优方案 dict；无解返回 None。coupon_pool 缺省用全局 COUPONS 作卡包满减代理。"""
    priced = [m for m in items if m.get("price") is not None and m["price"] > 0]
    if not priced:
        return None
    cps = coupon_pool if coupon_pool is not None else COUPONS
    # 价值排序（能量/价格 高者优先），限定候选规模避免组合爆炸
    priced.sort(key=lambda m: ((m.get("energy") or 1) / m["price"]), reverse=True)
    top = priced[:14]
    best = None
    for r in (1, 2, 3):
        for combo in itertools.combinations(top, r):
            cash = round(sum(m["price"] for m in combo), 2)
            if cash > budget:
                continue
            coupon = _best_coupon(cash, cps)
            coupon_minus = coupon["minus"] if coupon else 0.0
            redeem = _member_redeem_plan(list(combo), balance, mall_food)
            redeem_saved = redeem["cash_saved"] if redeem else 0.0
            eff = round(cash - coupon_minus - redeem_saved, 2)
            if eff < 0:
                eff = 0.0
            # 评分：到手食物价值优先，再比会员净省（券+积分）
            score = cash * 100 + redeem_saved * 10 - coupon_minus
            if best is None or score > best["score"]:
                best = {
                    "combo": list(combo), "cash": cash,
                    "coupon": coupon["name"] if coupon else None,
                    "coupon_minus": coupon_minus,
                    "redeem": redeem, "eff": eff, "score": score,
                }
    return best


def mode_member(budget=None, balance=None, expire_soon=0.0, meals=None, coupons=None, mall_food=None):
    """会员卡 × 套餐 联动模式。
    把「会员积分余额 + 卡包券 + 积分商城食品券」与「套餐价」编排成一条省钱闭环：
      · 给定 budget → 在预算内搜最优组合（最大化到手食物价值 + 会员折扣），对应
        "今天 30 块、我是会员怎么点最省"；
      · 不给定 budget → 自动选最便宜主食+小食作为代表套餐，演示联动逻辑。
    会员折扣含：②卡包满减券叠加；③积分券替换单品省现金；④本月过期积分急救。
    coupons 来自 _parse_my_coupons；mall_food 为积分商城食品券列表（含 point/price/name）；
    meals 为带价格的真实餐品（price 不为 None）。"""
    if meals is None:
        meals = MENU
    if balance is None:
        balance = 3200.0
    if coupons is None:
        coupons = {"count": 0, "samples": []}
    if mall_food is None:
        mall_food = [{"name": m["name"], "point": m["points"], "price": m["value"]} for m in MALL]

    wallet = coupons.get("count", 0)
    wallet_samples = coupons.get("samples", [])

    # ④ 本月过期积分急救（两种模式都给提示）
    expire_tip = ""
    if expire_soon > 0:
        low = [f for f in mall_food if f.get("point", 0) > 0 and f["point"] <= expire_soon]
        low.sort(key=lambda f: f["point"])
        if low:
            expire_tip = "本月 %.1f 积分将过期 → 立即兑换「%s」(%.0f 积分)" % (
                expire_soon, low[0]["name"], low[0]["point"])
        else:
            expire_tip = "本月 %.1f 积分将过期，但不足以兑换任何商品，下单攒更多积分再换" % expire_soon

    # ---- 预算模式：在预算内搜最优会员套餐 ----
    if budget is not None:
        search = _member_combo_search(budget, meals, balance, mall_food)
        if search:
            coupon = search["coupon"]
            redeem = search["redeem"]
            eff = search["eff"]
            saved = round(search["cash"] - eff, 2)
            return {
                "budget": budget,
                "combo": [m["name"] for m in search["combo"]],
                "combo_cash": search["cash"],
                "member_wallet_coupons": wallet,
                "wallet_samples": wallet_samples,
                "applied_coupon": coupon if coupon else "无可用券（可 auto-bind-coupons 一键领）",
                "coupon_minus": search["coupon_minus"],
                "points_redeem_plan": redeem,
                "expire_rescue": expire_tip,
                "member_effective_price": eff,
                "member_saved": saved,
                "verdict": ("预算 ¥%.2f 内，会员这样点最省：到手食物值 ¥%.2f，卡包券+积分券折后实付 ¥%.2f（省 ¥%.2f）"
                            % (budget, search["cash"], eff, saved)),
            }
        # 预算内无解（预算极低）：退化为「最便宜单品」
        cheapest = min([m for m in meals if m.get("price") is not None and m["price"] > 0],
                       key=lambda m: m["price"], default=None)
        if cheapest:
            return {
                "budget": budget, "combo": [cheapest["name"]], "combo_cash": cheapest["price"],
                "member_wallet_coupons": wallet, "wallet_samples": wallet_samples,
                "applied_coupon": "无可用券", "coupon_minus": 0.0, "points_redeem_plan": None,
                "expire_rescue": expire_tip, "member_effective_price": cheapest["price"],
                "member_saved": 0.0,
                "verdict": "预算 ¥%.2f 仅够单点「%s」(¥%.2f)，会员折扣暂不够门槛" % (budget, cheapest["name"], cheapest["price"]),
            }
        return {"verdict": "无可用餐品数据，请先拉取真实菜单或检查离线样本"}

    # ---- 非预算模式：自动选最便宜主食+小食作代表套餐 ----
    priced = [m for m in meals if m.get("price") is not None and not _is_excluded(m["name"])]
    side_items = [m for m in priced if any(k in m["name"] for k in SIDE_KW)]
    main_candidates = [m for m in priced if any(k in m["name"] for k in MAIN_KW)]
    if not main_candidates:
        main_candidates = [m for m in priced if m not in side_items]
    mains = sorted(main_candidates, key=lambda m: m["price"])
    sides = sorted(side_items, key=lambda m: m["price"])
    main = mains[0] if mains else (priced[0] if priced else None)
    side = sides[0] if sides else None
    combo = [m for m in (main, side) if m]
    combo_cash = round(sum(m["price"] for m in combo), 2)

    redeem_plan = _member_redeem_plan(combo, balance, mall_food)
    net = combo_cash
    if redeem_plan:
        net = round(combo_cash - redeem_plan["cash_saved"], 2)
    saved = round(combo_cash - net, 2)

    return {
        "combo": [m["name"] for m in combo],
        "combo_cash": combo_cash,
        "member_wallet_coupons": wallet,
        "wallet_samples": wallet_samples,
        "points_redeem_plan": redeem_plan,
        "expire_rescue": expire_tip,
        "member_effective_price": net,
        "member_saved": saved,
        "verdict": ("会员身份让这套餐实际到手 ¥%.2f（省 ¥%.2f）：卡包券叠加 + 积分券替换单品"
                    % (net, saved)) if saved > 0 else "先用积分把过期分救回来，再谈省钱",
    }


# ---------------------------------------------------------------------------
# 真实数据解析（来自麦当劳官方 MCP 工具返回）
# ---------------------------------------------------------------------------
def _extract_json(text):
    """从 MCP 工具返回的"包装文本"中提取真正的 JSON 对象。"""
    if "## Original Response" in text:
        text = text.split("## Original Response", 1)[1]
    s = text.find("{")
    e = text.rfind("}")
    if s != -1 and e != -1 and e > s:
        try:
            return json.loads(text[s:e + 1])
        except Exception:
            return None
    return None


def _parse_nutrition(text):
    """list-nutrition-foods -> 餐品营养列表。data 为带表头的文本表。"""
    obj = _extract_json(text)
    if not obj:
        return []
    data = obj.get("data")
    if not isinstance(data, str):
        return []
    out = []
    for ln in data.splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("[") or ln.startswith("{") or "productName" in ln:
            continue
        parts = [p.strip() for p in ln.split(",")]
        if len(parts) < 9:
            continue
        name = ",".join(parts[:-8]) if len(parts) > 9 else parts[0]
        # 列序：名称,描述(null),千焦Kj,千卡Kcal,蛋白,脂肪,碳水,钠,钙
        try:
            kcal = float(parts[-6]); protein = float(parts[-5])
            fat = float(parts[-4]); carb = float(parts[-3])
        except ValueError:
            continue
        out.append({"name": name, "energy_kcal": kcal, "protein": protein,
                    "fat": fat, "carb": carb})
    return out


def _parse_meals(text):
    """query-meals -> 餐品列表（code/name/price）。data.meals 为 code->详情 映射。"""
    obj = _extract_json(text)
    if not obj:
        return []
    data = obj.get("data", {})
    if not isinstance(data, dict):
        return []
    meals_map = data.get("meals", {})
    out = []
    for code, m in meals_map.items():
        if not isinstance(m, dict):
            continue
        name = m.get("name", "")
        raw = str(m.get("currentPrice", "0") or "0").replace("¥", "").strip()
        try:
            price = float(raw)
        except ValueError:
            price = 0.0
        out.append({"code": code, "name": name, "price": price})
    return out


def _parse_my_account(text):
    """query-my-account -> 积分账户。返回可用积分 / 本月过期积分等。"""
    obj = _extract_json(text)
    if not obj:
        return None
    d = obj.get("data")
    if isinstance(d, str):
        try:
            d = json.loads(d)
        except Exception:
            return None
    if not isinstance(d, dict):
        return None
    def f(k):
        try:
            return float(d.get(k, 0) or 0)
        except Exception:
            return 0.0
    return {
        "available": f("availablePoint"),
        "accumulative": f("accumulativePoint"),
        "expire_this_month": f("currentMouthExpirePoint"),
        "expired": f("expiredPoint"),
        "currency": d.get("currency", "积分"),
    }


def _parse_mall_products(text):
    """mall-points-products -> 积分商城商品列表。含 point(积分)/price(金额)/status。"""
    obj = _extract_json(text)
    if not obj:
        return []
    data = obj.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except Exception:
            return []
    if not isinstance(data, list):
        return []
    out = []
    for x in data:
        if not isinstance(x, dict):
            continue
        def num(k):
            try:
                return float(x.get(k) or 0)
            except Exception:
                return 0.0
        out.append({
            "name": x.get("spuName", ""),
            "spu_id": x.get("spuId"),
            "point": num("point"),
            "price": num("price"),
            "cat": x.get("catName", ""),
            "status": x.get("status"),
            "selling": x.get("selling", ""),
        })
    return out


def _parse_my_coupons(text):
    """query-my-coupons -> 会员卡包券。轻量解析：返回数量与样例名。"""
    obj = _extract_json(text)
    names, count = [], 0
    if obj:
        # 常见字段：couponName / couponTitle / name
        raw = json.dumps(obj, ensure_ascii=False)
        import re as _re
        names = list(dict.fromkeys(_re.findall(r'"(?:couponName|couponTitle|name)"\s*:\s*"([^"]{1,40})"', raw)))[:5]
        # 用 couponId / couponCode 出现次数估算张数（每张含一个唯一 id）
        ids = _re.findall(r'"(?:couponId|couponCode|id)"\s*:\s*"?(\d{4,})', raw)
        count = len(set(ids)) if ids else (len(names) or 0)
    return {"count": count, "samples": names}


def _tool_text(client, name, args):
    r = client.call_tool(name, args)
    res = (r.get("result") or {})
    txt = ""
    for cc in (res.get("content") or []):
        if cc.get("type") == "text":
            txt += cc.get("text", "")
    return txt, (res.get("isError", False))


def _get_a_store(client):
    """取一个真实门店（演示默认用上海人民广场附近）。返回 (storeCode, storeName)。"""
    t, e = _tool_text(client, "query-nearby-stores",
                      {"beType": 1, "searchType": 2, "city": "上海", "keyword": "人民广场"})
    if e:
        return None, None
    obj = _extract_json(t)
    if not obj:
        return None, None
    data = obj.get("data")
    stores = data if isinstance(data, list) else (data.get("data") if isinstance(data, dict) else None)
    if not isinstance(stores, list) or not stores:
        return None, None
    s0 = stores[0]
    return str(s0.get("storeCode")), s0.get("storeName")


def fetch_real_items(client):
    """拉取真实菜单+营养并合并为统一餐品列表（价格来自菜单，热量/蛋白来自营养表）。"""
    store_code, store_name = _get_a_store(client)
    meals = []
    if store_code:
        meals_txt, e = _tool_text(client, "query-meals",
                                  {"storeCode": store_code, "orderType": 1, "beType": 1})
        if not e:
            meals = _parse_meals(meals_txt)
    nutri_txt, _ = _tool_text(client, "list-nutrition-foods", {})
    nutri = _parse_nutrition(nutri_txt)
    by_name = {n["name"]: n for n in nutri}
    items = []
    meal_names = set()
    for m in meals:
        n = by_name.get(m["name"])
        items.append({
            "code": m["code"], "name": m["name"], "price": m["price"],
            "energy": n["energy_kcal"] if n else None,
            "protein": n["protein"] if n else None,
            "fat": n["fat"] if n else None,
            "carb": n["carb"] if n else None,
        })
        meal_names.add(m["name"])
    # 以营养表补齐（套餐/组合餐在营养表里没有同名项，这里用个体项补足控卡池）
    for n in nutri:
        if n["name"] not in meal_names:
            items.append({
                "code": "", "name": n["name"], "price": None,
                "energy": n["energy_kcal"], "protein": n["protein"],
                "fat": n["fat"], "carb": n["carb"],
            })
    return items, len(meals), len(nutri), store_name


def run_live(token):
    """连接真实麦当劳 MCP：握手、列工具、校验五模式工具，并用真实数据跑省钱/控卡/盲盒。"""
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
    print(f"✅ 已连接。当前可用工具 {len(names)} 个（前 10）：")
    for n in names[:10]:
        print("   -", n)
    if len(names) > 10:
        print(f"   …（共 {len(names)} 个）")

    # 六模式 → 真实工具映射（只校验"工具是否可用"，不触发任何写操作）
    mapping = {
        "省钱 saver": ["query-meals", "calculate-price", "query-store-coupons", "available-coupons", "query-my-coupons"],
        "控卡 macro": ["list-nutrition-foods", "query-meals", "calculate-price"],
        "积分 points": ["query-my-account", "mall-points-products", "mall-product-detail"],
        "会员 member": ["query-my-account", "query-my-coupons", "mall-points-products", "query-meals"],
        "活动 activity": ["campaign-calendar", "query-party-city", "query-party-store", "party-order-create"],
        "盲盒 surprise": ["query-meals", "calculate-price"],
    }
    print("\n>>> 六模式所需工具可用性：")
    for mode, need in mapping.items():
        ok = [t for t in need if t in names]
        miss = [t for t in need if t not in names]
        flag = "✅ 全部就绪" if not miss else f"⚠️ 缺 {miss}"
        print(f"  [{mode}] {flag}")

    # ---- 拉取真实菜单 + 营养，跑真·省钱/控卡/盲盒 ----
    print("\n>>> 拉取真实菜单与营养数据（query-nearby-stores + query-meals + list-nutrition-foods）...")
    items, n_meals, n_nutri, store_name = fetch_real_items(c)
    if n_meals:
        print(f"  已定位门店：{store_name}（演示默认上海人民广场附近）")
    print(f"  真实餐品（含价格+营养）合并得到 {len(items)} 项（菜单 {n_meals} / 营养 {n_nutri}）")
    if not items:
        print("  ⚠️ 真实数据解析为空，改用内置样本演示。")
        items = MENU

    print("\n========== 真实数据驱动的五模式 ==========")
    price_items = [i for i in items if i["price"] is not None]
    macro_items = [i for i in items if i["energy"] is not None and i["protein"] is not None]
    print(f"（省钱/盲盒用 {len(price_items)} 个真实价格餐品；控卡用 {len(macro_items)} 个真实营养餐品）")
    print("\n[真实·省钱] 预算 50 元：")
    print(json.dumps(mode_saver(50, items=price_items), ensure_ascii=False, indent=2))
    print("\n[真实·控卡] 目标 600 kcal / 30 g 蛋白：")
    print(json.dumps(mode_macro(600, 30, items=macro_items), ensure_ascii=False, indent=2))
    print("\n[真实·盲盒] 预算 30 元：")
    print(json.dumps(mode_surprise(30, items=price_items), ensure_ascii=False, indent=2))

    # ---- 积分模式：真实账户 + 真实积分商城 ----
    print("\n>>> 拉取真实积分账户与积分商城（query-my-account + mall-points-products）...")
    acc_txt, _ = _tool_text(c, "query-my-account", {})
    mall_txt, _ = _tool_text(c, "mall-points-products", {"catRuleIds": "1>4"})
    account = _parse_my_account(acc_txt)
    mall_products = _parse_mall_products(mall_txt)
    balance = account["available"] if account else 0.0
    expire_soon = account["expire_this_month"] if account else 0.0
    if account:
        print(f"  积分账户：可用 {balance} {account['currency']}｜本月将过期 {expire_soon}")
    print(f"  积分商城（食品券类目）商品 {len(mall_products)} 个")
    print("\n[真实·积分] 最值兑换：")
    print(json.dumps(mode_points(balance=balance, products=mall_products, expire_soon=expire_soon, meals=price_items),
                     ensure_ascii=False, indent=2))

    # ---- 会员卡 × 套餐 联动模式 ----
    print("\n>>> 拉取会员卡包券（query-my-coupons）...")
    coup_txt, _ = _tool_text(c, "query-my-coupons", {})
    coupons = _parse_my_coupons(coup_txt)
    print(f"  卡包券 {coupons['count']} 张，示例：{coupons['samples']}")
    print("\n[真实·会员卡×套餐] 联动省钱（自动套餐）：")
    print(json.dumps(mode_member(balance=balance, expire_soon=expire_soon, meals=price_items,
                                 coupons=coupons, mall_food=mall_products),
                     ensure_ascii=False, indent=2))
    print("\n[真实·会员卡×套餐] 预算内最优（--mode member --budget 30，真实门店价）：")
    print(json.dumps(mode_member(budget=30, balance=balance, expire_soon=expire_soon, meals=price_items,
                                 coupons=coupons, mall_food=mall_products),
                     ensure_ascii=False, indent=2))

    # 活动模式：真实 campaign-calendar 抽样
    print("\n[真实·活动] 当前营销活动（campaign-calendar）：")
    cal_txt, err = _tool_text(c, "campaign-calendar", {})
    print(cal_txt[:600] if cal_txt else ("  (isError=%s)" % err))

    print("\n--- 真实接入验证完成（全程只读：未执行下单/领券等任何写操作）---")


def main():
    ap = argparse.ArgumentParser(description="麦麦精算师：离线演示 + 真实MCP接入")
    ap.add_argument("--mode", choices=["saver", "macro", "points", "activity", "surprise", "member"], default="saver")
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
        print("\n=== [积分] 余额3200（离线样本） ===")
        print(json.dumps(mode_points(3200), ensure_ascii=False, indent=2))
        print("\n=== [会员卡×套餐] 联动（离线样本·自动套餐） ===")
        print(json.dumps(mode_member(), ensure_ascii=False, indent=2))
        print("\n=== [会员卡×套餐] 预算内最优（--mode member --budget 30） ===")
        print(json.dumps(mode_member(budget=30), ensure_ascii=False, indent=2))
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
    elif args.mode == "member":
        out = mode_member(budget=args.budget)
    else:
        out = mode_surprise(args.budget, args.avoid)
    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
