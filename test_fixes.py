#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
麦麦精算师 · 回归测试（针对外部代码审查提出的 7 类问题）

背景：外部 AI（Kimi）对 mcd_whiz.py 做了一轮代码审查，提出 2 个诚实性硬伤、
3 个崩溃路径、1 个关键词误分类与若干健壮性问题。本文件把每一条都变成
**可执行的断言**，任何人（包括评审、包括其他 AI）运行即可客观验证修复是否生效：

    python test_fixes.py

零依赖，仅用标准库 unittest。
"""
import datetime
import json
import unittest

import mcd_whiz as M


class TestHonestyPointsNotFree(unittest.TestCase):
    """🔴 严重1：积分不能当免费钱（否则"最省"结论会反向）"""

    def test_vpp_estimation(self):
        # 薯条券 1200 分抵 ¥12 → 1 分 ≈ ¥0.01
        mall = [{"name": "薯条(中)兑换券", "point": 1200, "price": 12.0}]
        self.assertAlmostEqual(M._estimate_vpp(mall), 0.01, places=4)

    def test_redeem_rejected_when_points_cost_exceeds_saving(self):
        """花 2100 积分(≈¥21) 只省 ¥6 现金 → 净亏，必须拒绝推荐"""
        mall = [{"name": "板烧鸡腿堡兑换券", "point": 2100, "price": 15.0}]
        combo = [{"name": "板烧鸡腿堡", "price": 21.0}]
        plan = M._member_redeem_plan(combo, balance=9999, mall_food=mall, vpp=0.01)
        self.assertIsNone(plan, "积分成本高于省下的现金时不应推荐（否则结论反向）")

    def test_redeem_accepted_when_truly_cheaper(self):
        """花 200 积分(≈¥2) 省 ¥6 → 净赚 ¥4，应推荐"""
        mall = [{"name": "板烧鸡腿堡兑换券", "point": 200, "price": 15.0}]
        combo = [{"name": "板烧鸡腿堡", "price": 21.0}]
        plan = M._member_redeem_plan(combo, balance=9999, mall_food=mall, vpp=0.01)
        self.assertIsNotNone(plan)
        self.assertAlmostEqual(plan["net_saved"], 4.0, places=2)
        self.assertAlmostEqual(plan["points_value_cost"], 2.0, places=2)


class TestMemberScoring(unittest.TestCase):
    """🔴 严重2：评分应最小化净支出，且必须是一顿正餐（含主食）"""

    def test_budget_search_returns_a_meal_not_a_cone(self):
        """预算 30 不应退化成只买一个圆筒冰淇淋(¥5)"""
        out = M.mode_member(budget=30)
        self.assertTrue(out["combo"], "应给出组合")
        kinds = [M._classify(n) for n in out["combo"]]
        self.assertIn("main", kinds, "预算最优解必须包含主食，否则不是一顿饭")

    def test_effective_price_not_exceeds_budget(self):
        out = M.mode_member(budget=30)
        self.assertLessEqual(out["member_effective_price"], 30)


class TestKeywordClassification(unittest.TestCase):
    """🔴 严重3：关键词误分类"""

    def test_congee_is_not_main(self):
        """皮蛋瘦肉粥不应被判定为主食（MAIN_KW 已移除泛化的"肉"）"""
        self.assertNotEqual(M._classify("皮蛋瘦肉粥"), "main")
        self.assertNotIn("肉", M.MAIN_KW)

    def test_ice_cream_allowed_for_elderly(self):
        """圆筒冰淇淋应可通过银发软食筛选（AVOID 已改为"冰镇/冰饮"而非单字"冰"）"""
        name = "圆筒冰淇淋"
        self.assertTrue(any(k in name for k in M.ELDER_SOFT_KW))
        self.assertFalse(any(k in name for k in M.ELDER_AVOID_KW),
                         "tips 推荐圆筒冰淇淋，算法就不该把它排除")

    def test_mcflurry_not_double_counted(self):
        """麦旋风只能归一类（小食），不能同时是饮料"""
        self.assertEqual(M._classify("麦旋风"), "side")


class TestCrashPaths(unittest.TestCase):
    """🟠 高4：真实数据下的崩溃路径"""

    def test_zero_price_no_zero_division(self):
        items = [{"name": "赠品", "price": 0, "energy": 0, "protein": 0},
                 {"name": "吉士汉堡", "price": 13.0, "energy": 312, "protein": 16}]
        out = M.mode_saver(30, items=items)   # 不应抛 ZeroDivisionError
        self.assertIn("items", out)

    def test_low_budget_gives_friendly_message(self):
        out = M.mode_saver(1, items=[{"name": "巨无霸", "price": 24.0,
                                      "energy": 563, "protein": 28}])
        self.assertIn("verdict", out)
        self.assertIn("预算", out["verdict"])

    def test_macro_missing_nutrition_fields(self):
        """真实 MCP 数据可能缺 energy/protein 字段，不应 KeyError"""
        items = [{"name": "新品A", "price": 20.0}, {"name": "新品B", "price": 15.0}]
        out = M.mode_macro(600, 30, items=items)
        self.assertIn("items", out)

    def test_macro_empty_pool(self):
        out = M.mode_macro(600, 30, items=[])
        self.assertIn("verdict", out)

    def test_points_none_price(self):
        """积分商城带 None 价格不应 TypeError"""
        products = [{"name": "实物周边", "point": 5000, "price": None,
                     "cat": "实物", "status": 2}]
        out = M.mode_points(balance=6000, products=products)
        self.assertIsInstance(out, dict)


class TestReproducibility(unittest.TestCase):
    """🟡 中6：demo 必须可复现（截图/录屏/评委复跑）"""

    def test_surprise_reproducible_with_same_seed(self):
        import random
        random.seed(42)
        a = M.mode_surprise(30)
        random.seed(42)
        b = M.mode_surprise(30)
        self.assertEqual(a["items"], b["items"])

    def test_activity_defaults_to_today(self):
        out = M.mode_activity()
        self.assertIsInstance(out, dict)
        # 不再硬编码 2026-10-11：不传 today 时用系统当天，故不应抛错且返回结构完整
        self.assertIn("ongoing", out)
        self.assertIn("upcoming", out)


class TestShareCounts(unittest.TestCase):
    """🟠 高5：分享篮计数不能重复"""

    def test_counts_sum_equals_basket_size(self):
        out = M.mode_share(80, people=2, scenario="family")
        total = sum(out["counts"].values())
        self.assertEqual(total, len(out["basket"]), "分类计数加总必须等于实际件数")

    def test_family_tip_is_consistent_with_budget_left(self):
        """预算花满时不能再说"可加购开心乐园餐"（Kimi 第三轮观察）"""
        for budget in (30, 40, 60, 90):
            out = M.mode_share(budget, people=2, scenario="family")
            self.assertAlmostEqual(out["budget_left"], round(budget - out["pay"], 2), places=2)
            if out["budget_left"] <= 0:
                self.assertIn("已用满", out["tips"])
            else:
                self.assertNotIn("已用满", out["tips"])


class TestRound2HonestReplay(unittest.TestCase):
    """🔴 第二轮-必修1：--demo-real 不得"零虚构"，缺失段必须如实标注占位"""

    def test_coupons_parsed_from_official_markdown(self):
        """官方 query-my-coupons 返回的是 Markdown，必须真解析出 13 张，不能是 0"""
        md = ("# 您的优惠券列表\n\n共 13 张可用优惠券 | 第 1/1 页\n\n"
              "## 中薯条买一送一\n- **优惠**: ¥13.5 (用券价格)\n- **标签**: 到店专用\n")
        r = M._parse_my_coupons(md)
        self.assertTrue(r["ok"])
        self.assertEqual(r["count"], 13)
        self.assertEqual(r["items"][0]["name"], "中薯条买一送一")
        self.assertAlmostEqual(r["items"][0]["value"], 13.5)

    def test_coupons_unparseable_is_minus_one_not_zero(self):
        """解析失败必须返回 -1 + 原因，不能静默变成"你卡包里 0 张券" """
        r = M._parse_my_coupons("这不是券列表，只是一段乱码")
        self.assertEqual(r["count"], -1)
        self.assertFalse(r["ok"])
        self.assertIn("解析失败", r["parse_note"])

    def test_member_wallet_none_when_count_unknown(self):
        """券数未知时 member 模式输出 None + 说明，而不是 0 张"""
        out = M.mode_member(budget=30, coupons={"count": -1, "samples": [], "parse_note": "解析失败"})
        self.assertIsNone(out["member_wallet_coupons"])
        self.assertIn("未知", out["wallet_note"])

    def test_snapshot_split_public_private(self):
        """快照必须按隐私拆分：private 段不随仓库公开"""
        import os
        d = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")
        self.assertTrue(os.path.isfile(os.path.join(d, "real_snapshot_public.json")),
                        "公开快照应随仓库提交，评委才能复现")
        pub = json.load(open(os.path.join(d, "real_snapshot_public.json"), encoding="utf-8"))
        for k in ("my_account", "my_coupons"):
            self.assertNotIn(k, pub, "公开快照不得包含个人账户/卡包券")
        gi = open(os.path.join(os.path.dirname(d), ".gitignore"), encoding="utf-8").read()
        self.assertIn("real_snapshot_private.json", gi, "私有快照必须被 .gitignore 忽略")

    def test_snapshot_header_prints_filename_only(self):
        """回放头部只打印文件名：绝对路径在 Windows 下会带上 C:\\Users\\<你的名字>"""
        import os
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            M.run_snapshot_replay()
        out = buf.getvalue()
        self.assertNotIn(":\\", out.split("快照文件")[1].split("\n")[0],
                         "不应打印快照绝对路径（会泄露本机用户名）")
        self.assertIn("real_snapshot_public.json", out)

    def test_load_snapshot_returns_three_values(self):
        snap, path, merged = M.load_snapshot()
        self.assertIsInstance(snap, dict)
        self.assertIsInstance(path, str)
        self.assertIsInstance(merged, bool)


class TestRound2Parsers(unittest.TestCase):
    """🟡 第二轮-中：解析器健壮性（截断 / 数组 / 名称匹配）"""

    def test_extract_json_array_branch(self):
        self.assertEqual(M._extract_json('noise [{"a": 1}, {"a": 2}] noise'), [{"a": 1}, {"a": 2}])

    def test_truncated_array_salvage(self):
        txt = 'xx ## Original Response {"data": [{"spuName":"A","point":"100"},{"spuName":"B","po'
        arr, note = M._loads_truncated_array(txt)
        self.assertIsInstance(arr, list)
        self.assertEqual(len(arr), 1, "应抢救出 1 条完整记录")
        self.assertIn("截断", note)

    def test_mall_products_ex_reports_note(self):
        products, note = M._parse_mall_products_ex("")
        self.assertEqual(products, [])
        self.assertIn("无原文", note)

    def test_combo_not_fuzzy_matched(self):
        """套餐/三件套禁止模糊匹配营养（会把三件套错配成单个汉堡的营养）"""
        nutri = {"巨无霸": {"name": "巨无霸", "energy_kcal": 563, "protein": 28,
                            "fat": 30, "carb": 43, "sodium": 1040}}
        by_norm = {M._norm_name("巨无霸"): nutri["巨无霸"]}
        n, how = M._match_nutrition("巨无霸三件套", nutri, by_norm)
        self.assertIsNone(n)
        self.assertEqual(how, "skip_combo")

    def test_fuzzy_match_recovers_normalized_name(self):
        nutri = {"板烧鸡腿堡": {"name": "板烧鸡腿堡", "energy_kcal": 508, "protein": 28,
                                "fat": 21, "carb": 49, "sodium": 1050}}
        by_norm = {M._norm_name("板烧鸡腿堡"): nutri["板烧鸡腿堡"]}
        n, how = M._match_nutrition("板烧鸡腿堡辣味版", nutri, by_norm)
        self.assertIsNotNone(n, "归一化仍不相等时应退到包含匹配，真实数据里这种写法很常见")
        self.assertEqual(how, "fuzzy")


class TestRound2PointsHonesty(unittest.TestCase):
    """🔴 第二轮：积分估值不得靠名义价值凑数"""

    def test_one_point_activity_gets_no_nominal_value(self):
        """1 积分的"应援资格"活动不能被算成 ¥3（会把 vpp 抬到 300/百积分）"""
        v, src = M._mall_value({"name": "为随心配五大巨星应援1积分兑换活动", "point": 1, "price": 0}, {})
        self.assertIsNone(v)
        self.assertIn("无法估算", src)

    def test_coupon_with_embedded_price_deducts_it(self):
        """券名自带到手价时，价值 = 菜单价 − 到手价"""
        v, src = M._mall_value({"name": "18.8元麦辣鸡腿汉堡两件套", "point": 50, "price": 0},
                               {"麦辣鸡腿汉堡": 22.5})
        self.assertAlmostEqual(v, 3.7, places=2)
        self.assertIn("到手价", src)

    def test_points_mode_reports_unvalued(self):
        out = M.mode_points(balance=3000, products=[
            {"name": "1积分兑换活动", "point": 1, "price": 0, "status": 2},
            {"name": "板烧鸡腿堡兑换券", "point": 2100, "price": 15.0, "status": 2},
        ], meals=[{"name": "板烧鸡腿堡", "price": 21.0}])
        self.assertEqual(out["best_value_overall"]["name"], "板烧鸡腿堡兑换券")
        self.assertEqual(out["unvalued_count"], 1)
        self.assertIn("不按名义价值凑数", out["value_note"])

    def test_redeem_plan_deducts_embedded_topup(self):
        """商城 price=0 但券名写"18.8元"时，必须按 18.8 计为现金支出，不能当白拿"""
        plan = M._member_redeem_plan(
            [{"name": "麦辣鸡腿汉堡", "price": 22.5}], balance=9999,
            mall_food=[{"name": "18.8元麦辣鸡腿汉堡两件套", "point": 50, "price": 0}], vpp=0.047)
        self.assertIsNotNone(plan)
        self.assertAlmostEqual(plan["cash_topup"], 18.8, places=2)
        self.assertIn("券名解析", plan["cash_topup_source"])
        self.assertAlmostEqual(plan["net_saved"], round(22.5 - 18.8 - 50 * 0.047, 2), places=2)


class TestRound3SurpriseBudget(unittest.TestCase):
    """🟠 第三轮：盲盒退化路径不看总价 → 预算 30 开出 ¥31.5（真实数据可复现）"""

    def _real_items(self):
        snap, _p, _m = M.load_snapshot()
        return [i for i in snap["items"] if (i.get("price") or 0) > 0]

    def test_surprise_never_exceeds_budget_real_data(self):
        """多预算 × 多种子：盲盒总价必须始终 ≤ 预算"""
        import random
        items = self._real_items()
        bad = []
        for seed in range(60):
            for budget in (12, 15, 20, 30, 45, 60):
                random.seed(seed)
                out = M.mode_surprise(budget, items=items)
                if out["price"] > budget + 1e-9:
                    bad.append((seed, budget, out["price"]))
        self.assertEqual(bad, [], "以下组合超出预算：%s" % bad[:5])

    def test_surprise_never_exceeds_budget_offline(self):
        import random
        bad = []
        for seed in range(60):
            for budget in (15, 20, 25, 30, 50):
                random.seed(seed)
                out = M.mode_surprise(budget)
                if out["price"] > budget + 1e-9:
                    bad.append((seed, budget, out["price"]))
        self.assertEqual(bad, [], "以下组合超出预算：%s" % bad[:5])

    def test_surprise_always_returns_something(self):
        """预算 ≥ 最便宜单品时必须给出非空组合"""
        items = self._real_items()
        out = M.mode_surprise(15, items=items)
        self.assertTrue(out["items"])

    def test_quote_matches_basket(self):
        """「麦旋风+薯条」不该配「自律即自由」这类违和文案"""
        picks = [{"name": "泷愿成真麦旋风——大米风味", "price": 22.0, "energy": None},
                 {"name": "月下相思扭扭薯", "price": 9.5, "energy": None}]
        q = M._surprise_quote(picks)
        self.assertNotIn("自律", q)
        self.assertNotIn("狠人", q)


class TestRound2Robustness(unittest.TestCase):
    """🟠 第二轮-必修2：单个工具/阶段挂掉不能让整个流程崩"""

    def test_tool_text_swallows_exception(self):
        class Boom:
            def call_tool(self, name, args):
                raise RuntimeError("网络不通")
        txt, err = M._tool_text(Boom(), "query-meals", {})
        self.assertEqual(txt, "")
        self.assertIn("EXCEPTION", str(err))

    def test_low_sodium_near_limit_not_claimed_safe(self):
        """795mg 贴 800mg 线时不能宣告"适合控钠人群" """
        items = [{"name": "麦香鱼", "price": 20.0, "energy": 350, "protein": 16, "sodium": 795}]
        out = M.mode_elderly(60, items=items, low_sodium=True)
        joined = " ".join(out["tips"])
        self.assertIn("贴线", joined)
        self.assertNotIn("适合控钠人群", joined)


if __name__ == "__main__":
    print("运行回归测试：验证三轮外部代码审查提出的问题是否修复\n")
    unittest.main(verbosity=2)
