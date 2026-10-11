---
name: mcd-whiz
description: 麦麦精算师——基于麦当劳官方 MCP（M-China/mcd-mcp-server）的多目标最优点餐助手。当用户想点麦当劳、比价、算热量/营养、凑积分、领麦麦省券、做点餐决策、用会员卡/积分省钱时使用。输入预算/健身目标/忌口/场景，自动编排麦当劳 MCP 工具（query-meals、list-nutrition-foods、calculate-price、query-store-coupons、available-coupons、query-my-coupons、query-my-account、mall-points-products 等），输出「最省钱 / 最控卡 / 最值积分 / 会员卡×套餐联动 / 活动推荐 / 盲盒」套餐方案，并支持一键领券与代下单（支付由用户完成）。
---

# 麦麦精算师 (MCD Whiz)

把"今天吃什么麦当劳"变成一道可计算的题。一个基于麦当劳中国官方 MCP 的 Agent Skill，
覆盖 **省钱 / 控卡 / 凑积分 / 会员卡×套餐 / 活动推荐 / 盲盒** 六种决策模式，把分散的 MCP 工具编排成一条用户愿意每天用的闭环。

## 它能做什么

| 模式 | 你说 | 它做 | 主要依赖的 MCP 工具 |
|------|------|------|---------------------|
| 省钱 | "50 块怎么点最划算" | 比对用券/不用券/麦麦省券多套方案，挑最优组合 | query-meals, calculate-price, query-store-coupons, available-coupons, auto-bind-coupons |
| 控卡 | "减脂期 600 大卡、蛋白 30g" | 基于真实营养数据推荐达标套餐 | list-nutrition-foods, query-meals, calculate-price |
| 积分 | "我有 3200 积分换什么最值" | 用真实菜单价估算"到手价值/积分"，找最值兑换 | query-my-account, mall-points-products, mall-product-detail |
| 会员 | "我是会员，这套餐怎么最省" | 卡包券 + 积分券替换单品 + 过期积分急救，算出会员到手价 | query-my-account, query-my-coupons, mall-points-products, query-meals |
| 活动 | "最近有什么活动别错过" | 活动日历分「进行中/即将开始」并给参与路径 | campaign-calendar, query-party-city/store/date/session, party-order-create |
| 盲盒 | "30 块、不要香菜，随便来" | 随机生成套餐 + 一句麦门文案 | query-meals, calculate-price |

## 工作流程（Agent 必读）

1. **澄清意图与约束**：确认模式、预算、目标（热量/蛋白）、忌口、场景（外送 / 到店 / 团餐）。
2. **按模式调工具**：工具映射见 `MCP_INTEGRATION.md`。先 `query-nearby-stores` / `query-meals` 拿菜单，再按需取营养、券、积分。
3. **金额校验**：用 `calculate-price` 计算应付；**注意单位坑——仅 `calculate-price` 返回"分"（整数），展示前 ÷100；`query-meals`/`query-order`/商城订单返回的金额已是"元"字符串，直接展示**。积分字段不参与金额换算。
4. **输出方案**：给出套餐明细、原价、优惠、应付、热量/营养、省钱值，让用户一眼看懂。
5. **领券与下单**：需领券调用 `auto-bind-coupons`；需下单调用 `create-order` 并**返回支付链接**，明确告知"支付由你在链接或麦当劳 App 自行完成，我不代付"。

## 安全与合规（必须遵守）

- 任何情况下**不在回答、日志、命令参数或文件中暴露 `MCD_MCP_TOKEN`**。
- 展示手机号时**脱敏**（如 `152****6666`）；新增地址前明确告知用户将向麦当劳发送姓名/手机号/详细地址。
- 价格单位按工具区分（见上），不要一概 ÷100。
- 仅个人**非商业用途**；遵循《麦当劳 MCP 服务规则》与《使用条款》。

## 离线演示

无 Token 也能体验核心逻辑：

```bash
python mcd_whiz.py --demo            # 跑全部模式的内置示例
python mcd_whiz.py --mode saver --budget 50
python mcd_whiz.py --mode macro --kcal 600 --protein 30
python mcd_whiz.py --mode points --balance 3200
python mcd_whiz.py --mode member     # 会员卡×套餐联动（离线样本）
```

接入真实麦当劳 MCP（含会员/积分真实数据）见 `MCP_INTEGRATION.md`；参赛信息见 `CONTEST.md`。

接入真实麦当劳 MCP 见 `MCP_INTEGRATION.md`；参赛信息见 `CONTEST.md`。
