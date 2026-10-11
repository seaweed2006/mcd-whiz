# 麦麦精算师 (MCD Whiz)

> 基于 **麦当劳中国官方 MCP（M-China/mcd-mcp-server）** 的多目标最优点餐 Agent Skill。
> 把"今天吃什么麦当劳"变成一道可计算的题：省钱 / 控卡 / 凑积分 / 盲盒，一套搞定。
> **2026 麦当劳程序员创意开发大赛（M-CODE）参赛作品。**

---

## 🤔 为什么做这个

麦当劳 MCP 已经放出几十个工具（菜单、营养、优惠券、积分商城、点餐、活动日历……），
但普通用户面对的是一堆按钮和价格，算不清"怎么点最划算""减脂期能吃啥""积分换啥最值"。
现有参赛作品多是单一角度（人格卡 / 卡路里 / 纯下单 / 省钱）。

**麦麦精算师**的差异点：用**一个 Skill 把多个 MCP 工具编排成五种决策模式**——
恰好覆盖官方建议的三大方向（套餐定制 / 省钱 / 活动推荐）再加积分与盲盒，
即实用又有分享点，且**零依赖离线可跑**。

## ✨ 功能

| 模式 | 输入 | 输出 | 核心 MCP 工具 |
|------|------|------|---------------|
| 💰 省钱 | 预算 | 用券/不用券最优组合 + 省钱率 | query-meals, calculate-price, query-store-coupons, available-coupons, auto-bind-coupons |
| 🥗 控卡 | 减脂/增肌目标、热量、蛋白 | 达标套餐 + 营养明细 | list-nutrition-foods, query-meals, calculate-price |
| 🎟️ 积分 | 积分余额 | 价值/积分最高的兑换 | query-my-account, mall-points-products, mall-product-detail |
| 📅 活动 | "最近有啥活动" | 进行中/即将开始的营销活动 + 参与路径 | campaign-calendar, query-party-*, party-order-create |
| 🎲 盲盒 | 预算、忌口 | 随机套餐 + 麦门文案 | query-meals, calculate-price |

## 🚀 快速开始

### 1. 离线体验（无需 Token）
```bash
python mcd_whiz.py --demo
python mcd_whiz.py --mode saver --budget 50
python mcd_whiz.py --mode macro --kcal 600 --protein 30
python mcd_whiz.py --mode points --balance 3200
```

### 2. 接入真实麦当劳 MCP
见 [MCP_INTEGRATION.md](./MCP_INTEGRATION.md)。在 WorkBuddy / Cherry Studio / Cursor / Trae / VSCode 中
配置 `mcp.mcd.cn` + 你的 Token 后即可让 Agent 调用真实菜单、券与积分。

### 3. 作为 WorkBuddy Skill 使用
把本仓库放到 WorkBuddy 的 Skills 目录（`~/.workbuddy/skills/mcd-whiz` 或项目级 `skills/`），
SKILL.md 会被自动识别。

## 🗂 目录结构
```
mcd-whiz/
├── SKILL.md              # Skill 定义（Agent 行为 + 安全合规）
├── mcd_whiz.py           # 离线演示脚本（零依赖）
├── MCP_INTEGRATION.md    # 麦当劳 MCP 接入说明
├── CONTEST.md            # 参赛声明 / 报名信息
└── README.md             # 本文件
```

## ⚠️ 合规说明
- 仅个人**非商业用途**，遵循《麦当劳 MCP 服务规则》与《使用条款》。
- 支付由用户在麦当劳链接/App 自行完成，Skill 不代付。
- Token 不落盘、不出现在任何输出中。

## 📜 License
MIT（示例代码与文档）；麦当劳 MCP 服务的使用受官方条款约束。
