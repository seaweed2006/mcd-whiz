# 麦麦精算师 (MCD Whiz)

> 基于 **麦当劳中国官方 MCP（M-China/mcd-mcp-server）** 的多目标最优点餐 Agent Skill。
> 把"今天吃什么麦当劳"变成一道可计算的题：省钱 / 控卡 / 凑积分 / 会员卡×套餐 / 盲盒 / 亲子闺蜜共享 / 银发适老 / 好兄弟蛋白质，一套搞定。
> **2026 麦当劳程序员创意开发大赛（M-CODE）参赛作品。**

---

## 🤔 为什么做这个

麦当劳 MCP 已经放出几十个工具（菜单、营养、优惠券、积分商城、点餐、活动日历……），
但普通用户面对的是一堆按钮和价格，算不清"怎么点最划算""减脂期能吃啥""积分换啥最值"。
现有参赛作品多是单一角度（人格卡 / 卡路里 / 纯下单 / 省钱）。

**麦麦精算师**的差异点：用**一个 Skill 把多个 MCP 工具编排成九种决策模式**——
恰好覆盖官方建议的三大方向（套餐定制 / 省钱 / 活动推荐）再加积分、会员卡联动、盲盒、亲子/闺蜜共享、银发适老（软糯）与好兄弟蛋白质活动，
即实用又有分享点，且**零依赖离线可跑**。

## ✨ 功能

| 模式 | 输入 | 输出 | 核心 MCP 工具 |
|------|------|------|---------------|
| 💰 省钱 | 预算 | 用券/不用券最优组合 + 省钱率 | query-meals, calculate-price, query-store-coupons, available-coupons, auto-bind-coupons |
| 🥗 控卡 | 减脂/增肌目标、热量、蛋白 | 达标套餐 + 营养明细 | list-nutrition-foods, query-meals, calculate-price |
| 🎟️ 积分 | 积分余额 | 用真实菜单价估算"到手价值/积分"，最值兑换 | query-my-account, mall-points-products, mall-product-detail |
| 🪪 会员 | "我是会员，今天 30 块怎么点最省" | 预算内搜最优组合 + 卡包券 + 积分券替换单品 + 过期积分急救 → 会员到手价 | query-my-account, query-my-coupons, mall-points-products, query-meals |
| 📅 活动 | "最近有啥活动" | 进行中/即将开始的营销活动 + 参与路径 | campaign-calendar, query-party-*, party-order-create |
| 🎲 盲盒 | 预算、忌口 | 随机套餐 + 麦门文案 | query-meals, calculate-price |
| 👨‍👩‍👧 亲子/闺蜜 | 人数、预算、场景(family/friends) | 按"每人主食+饮料 + 共享小食"拼分享篮，亲子避辛辣、闺蜜偏拍照甜品 | query-meals, calculate-price, query-store-coupons |
| 👵 银发适老 | 预算、是否年轻人同行 | 筛选天然软糯单品（麦香鱼/板烧堡/玉米杯/苹果片/圆筒），避辣避骨；可加年轻人常规主食 | query-meals, list-nutrition-foods, calculate-price |
| 💪 好兄弟 | 人数、预算 | 2 男高蛋白局：每人高蛋白堡 + 共享鸡翅鸡块，报告合计蛋白 | query-meals, calculate-price, query-store-coupons |

## 🚀 快速开始

### 1. 离线体验（无需 Token）
```bash
python mcd_whiz.py --demo
python mcd_whiz.py --mode saver --budget 50
python mcd_whiz.py --mode macro --kcal 600 --protein 30
python mcd_whiz.py --mode points --balance 3200
python mcd_whiz.py --mode member     # 会员卡×套餐联动（离线样本·自动套餐）
python mcd_whiz.py --mode member --budget 30   # 预算内搜最优会员套餐（如"今天30块怎么点最省"）
python mcd_whiz.py --mode share --scenario family --people 2 --budget 60   # 亲子共享篮
python mcd_whiz.py --mode share --scenario friends --people 2 --budget 60  # 闺蜜共享篮
python mcd_whiz.py --mode elderly --budget 40                # 银发适老·软糯（老人单独）
python mcd_whiz.py --mode elderly --budget 60 --companion    # 年轻人带老人同行（加一份常规主食）
python mcd_whiz.py --mode bros --people 2 --budget 80        # 好兄弟蛋白质局（2 男）
```

### 2. 接入真实麦当劳 MCP（真实数据驱动）
先复制 `.env.example` 为 `.env` 填入你的 Token（`.env` 已被 `.gitignore` 忽略，不会泄露）：
```bash
cp .env.example .env        # 然后编辑 .env 填入 MCD_MCP_TOKEN
python mcd_whiz.py --live   # 连接 mcp.mcd.cn，用真实数据跑三模式
```
`--live` 会做这些（**全程只读，绝不下单/领券**）：
1. 与官方 MCP 握手、列出全部工具（35 个），并校验九模式所需工具是否就绪；
2. 取一个真实门店 → 拉**真实菜单价格**（`query-nearby-stores` + `query-meals`）；
3. 拉**真实营养数据**（`list-nutrition-foods`，160+ 餐品的热量/蛋白/脂肪/碳水）；
4. 用上述真实数据**实算**各模式：省钱（含麦麦省满减）、控卡（按热量/蛋白目标配餐）、盲盒、亲子/闺蜜、银发适老、好兄弟蛋白质；
5. 拉**真实积分账户 + 积分商城**（`query-my-account` + `mall-points-products`，按类目筛食品券），用真实菜单价估算"到手价值/积分"算出最值兑换；
6. 拉**会员卡包券**（`query-my-coupons`），把"积分券替换套餐单品 + 过期积分急救"编排成会员到手价；
7. 抽样**真实活动日历**（`campaign-calendar` 当日活动）。
> 控卡/省钱/盲盒/积分/会员/亲子/银发/好兄弟的算法与离线版一致，只是输入换成了官方实时数据；活动模式直接展示官方活动文案。

也可以直接传 Token（不写文件）：
```bash
python mcd_whiz.py --live --token "你的麦当劳MCP_Token"
```
在 WorkBuddy / Cherry Studio / Cursor / Trae / VSCode 中配置 `mcp.mcd.cn` + 你的 Token，
即可让 Agent 调用真实菜单、券与积分（详见 [MCP_INTEGRATION.md](./MCP_INTEGRATION.md)）。

### 3. 作为 WorkBuddy Skill 使用
把本仓库放到 WorkBuddy 的 Skills 目录（`~/.workbuddy/skills/mcd-whiz` 或项目级 `skills/`），
SKILL.md 会被自动识别。

## 🗂 目录结构
```
mcd-whiz/
├── SKILL.md              # Skill 定义（Agent 行为 + 安全合规）
├── mcd_whiz.py           # 离线演示 + 真实MCP接入入口（零依赖）
├── mcp_client.py         # 麦当劳官方 MCP 客户端（Streamable HTTP，零依赖）
├── MCP_INTEGRATION.md    # 麦当劳 MCP 接入说明（端点/工具映射/单位坑）
├── CONTEST.md            # 参赛声明 / 报名信息
├── .env.example          # Token 配置样例（复制为 .env 使用）
├── .gitignore            # 忽略 .env 等密钥，防泄露
└── README.md             # 本文件
```

## ⚠️ 合规说明
- 仅个人**非商业用途**，遵循《麦当劳 MCP 服务规则》与《使用条款》。
- 支付由用户在麦当劳链接/App 自行完成，Skill 不代付。
- Token 不落盘、不出现在任何输出中。

## 📜 License
MIT（示例代码与文档）；麦当劳 MCP 服务的使用受官方条款约束。
