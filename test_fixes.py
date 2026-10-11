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


if __name__ == "__main__":
    print("运行回归测试：验证外部代码审查提出的 7 类问题是否修复\n")
    unittest.main(verbosity=2)
