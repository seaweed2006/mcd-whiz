# 麦麦精算师 (MCD Whiz)

> 基于 **麦当劳中国官方 MCP（M-China/mcd-mcp-server）** 的多目标最优点餐 Agent Skill。
> 把"今天吃什么麦当劳"变成一道可计算的题：省钱 / 控卡 / 凑积分 / 会员卡×套餐 / 盲盒 / 亲子闺蜜共享 / 银发适老 / 好兄弟蛋白质，一套搞定。
> **2026 麦当劳程序员创意开发大赛（M-CODE）参赛作品。**

**🎯 参赛一屏速览**：`python mcd_whiz.py --demo`（零依赖离线可跑）｜**`python mcd_whiz.py --demo-real`（真实 MCP 数据离线回放，无需 Token）**｜`python mcd_whiz.py --live`（有 Token 时直连真实 MCP）｜视觉展示页：[`showcase.html`](showcase.html)

> **🔍 评委如何验证"真的接了麦当劳 MCP"？** 没有 Token 也能验：本仓库附带一次真实调用的**数据快照**
> （`fixtures/real_snapshot_public.json`，含门店、35 个工具、239 件真实餐品与营养数据，
> 抓取时间 2026-10-11）。任何人执行 `python mcd_whiz.py --demo-real`，
> 即可**离线用真实数据跑完全部九模式**，并逐段打印数据来源。
>
> **诚实边界（重要）**：快照按隐私拆两份 —— `real_snapshot_public.json`（菜单/营养/门店/商城目录，随仓库公开）
> 与 `real_snapshot_private.json`（我的积分账户/卡包券，**本地保留，已 gitignore**）。
> 回放时每一段都会标注是「真实快照」还是「⚠️ 该段使用占位数据」，**不把占位数据说成真实数据**。

**一个 Skill 编排 35 个官方 MCP 工具 → 9 种决策模式**（覆盖官方三大方向：套餐定制 / 省钱 / 活动推荐）。已接真实数据、全程只读、支付由用户完成。

⭐ **如果这个项目对你有用，欢迎点个 Star**——本作品参赛 2026 麦当劳程序员创意开发大赛（M-CODE，2026.10.09–10.25）。📄 参赛声明见 [`CONTEST_DECLARATION.md`](CONTEST_DECLARATION.md) ｜ 完整开发过程见 [`DEVELOPMENT_LOG.md`](DEVELOPMENT_LOG.md)。基于腾讯 WorkBuddy 协作开发。

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
| 💰 省钱 | 预算 | 按「能量/价格」性价比贪心把预算装满 → 叠加最优满减券，报告原价 / 券后价 / 省钱率（**定位如实说明**：目标是"预算内吃到最多"，不是"花最少的钱"） | query-meals, calculate-price, query-store-coupons, available-coupons, auto-bind-coupons |
| 🥗 控卡 | 减脂/增肌目标、热量、蛋白 | 达标套餐 + 营养明细 | list-nutrition-foods, query-meals, calculate-price |
| 🎟️ 积分 | 积分余额 | 用真实菜单价估算"到手价值/积分"，最值兑换 | query-my-account, mall-points-products, mall-product-detail |
| 🪪 会员 | "我是会员，今天 30 块怎么点最省" | 预算内搜最优组合 + 卡包券 + 积分券替换单品 + 过期积分急救 → 会员到手价 | query-my-account, query-my-coupons, mall-points-products, query-meals |
| 📅 活动 | "最近有啥活动" | 进行中/即将开始的营销活动 + 参与路径 | campaign-calendar, query-party-*, party-order-create |
| 🎲 盲盒 | 预算、忌口 | 随机套餐 + 麦门文案 | query-meals, calculate-price |
| 👨‍👩‍👧 亲子/闺蜜 | 人数、预算、场景(family/friends) | 按"每人主食+饮料 + 共享小食"拼分享篮，亲子避辛辣、闺蜜偏拍照甜品 | query-meals, calculate-price, query-store-coupons |
| 👵 银发适老 | 预算、`--companion`、`--low-sodium` | 筛选天然软糯单品（麦香鱼/板烧堡/玉米杯/苹果片/圆筒），避辣避骨；`--low-sodium` 优先低钠并报告本餐钠摄入（控钠人群） | query-meals, list-nutrition-foods, calculate-price |
| 💪 好兄弟 | 人数、预算、`--protein`(人均目标) | 2 男高蛋白局：每人高蛋白堡 + 共享鸡翅鸡块；`--protein` 定人均蛋白目标，预算内尽量凑够并报告达标/缺口 | query-meals, calculate-price, query-store-coupons |

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
python mcd_whiz.py --mode elderly --budget 40 --low-sodium   # 银发·低钠优先（报告本餐钠摄入，控钠人群）
python mcd_whiz.py --mode bros --people 2 --budget 80        # 好兄弟蛋白质局（2 男）
python mcd_whiz.py --mode bros --people 2 --budget 80 --protein 40  # 好兄弟·人均蛋白目标40g（达标优先）
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
> ⚠️ 命令行 `--token` 会出现在系统进程列表并留在 shell 历史里，**优先用环境变量 `MCD_MCP_TOKEN`**；
> 若用了 `--token`，程序会先打印这条提醒。

**健壮性**：`--live` 按阶段做了降级保护 —— 某个 MCP 工具超时/报错时，
只跳过依赖它的模式并打印 `⚠️ xx 数据不可用，跳过 xx 模式`，不会让整个流程崩掉。
在 WorkBuddy / Cherry Studio / Cursor / Trae / VSCode 中配置 `mcp.mcd.cn` + 你的 Token，
即可让 Agent 调用真实菜单、券与积分（详见 [MCP_INTEGRATION.md](./MCP_INTEGRATION.md)）。

### 3. 作为 WorkBuddy Skill 使用
把本仓库放到 WorkBuddy 的 Skills 目录（`~/.workbuddy/skills/mcd-whiz` 或项目级 `skills/`），
SKILL.md 会被自动识别。

## 🧪 自测
```bash
python test_fixes.py      # 32 条断言，覆盖两轮外部代码审查提出的全部问题
```
把"审查意见"变成**可执行的断言**：积分不能当免费钱、会员解必须含主食、缺失字段不崩、
券解析失败返回 -1 而非 0、1 积分活动不按名义价值计价、券名自带到手价必须扣除、
套餐不模糊匹配营养、低钠贴线不宣告安全、单工具异常不拖垮全流程、随机种子可复现。

## 🧭 诚实性设计（本作品最在意的点）
- **积分不是免费的钱**：积分按 1 分≈¥x 折算成成本，只有「净省钱 > 0」才推荐兑换；
  估不出价值的商城商品（如 1 积分"应援资格"）**排除排名并如实计数**，不按名义价值凑数。
- **券的到手价必须扣除**：商城 `price` 常为 0，若券名自带"18.8元"，按 18.8 计为现金支出。
- **不虚报省钱**：省下的钱 = 原价 −（券后现金 + 积分折现成本）。
- **缺失数据如实标注**：解析失败返回 `-1 + 原因`，而不是静默变成 0。
- **低钠不贴线宣传**：795mg / 800mg 参考线时提示"贴线 99%"，不宣告"适合控钠人群"。
- **隐私分级**：个人账户/卡包券不随仓库公开。

## 🗂 目录结构
```
mcd-whiz/
├── SKILL.md              # Skill 定义（Agent 行为 + 安全合规）
├── mcd_whiz.py           # 离线演示 + 真实MCP接入入口（零依赖）
├── mcp_client.py         # 麦当劳官方 MCP 客户端（Streamable HTTP，零依赖）
├── capture_fixture.py    # 抓取真实数据 → 生成 public/private 两份快照
├── fixtures/
│   ├── real_snapshot_public.json    # 真实数据快照·公开段（随仓库，评委可复现）
│   └── real_snapshot_private.json   # 真实数据快照·私有段（本地，已 gitignore）
├── test_fixes.py         # 32 条回归断言（两轮外部审查的修复验证）
├── showcase.html         # 参赛展示页
├── share.html            # 拉星海报页（含二维码）
├── star_qr.png           # 仓库二维码
├── DEVELOPMENT_LOG.md    # 开发对话存档（赛事要求）
├── CONTEST_DECLARATION.md# 官方参赛声明
├── MCP_INTEGRATION.md    # 麦当劳 MCP 接入说明（端点/工具映射/单位坑）
├── CONTEST.md            # 参赛声明 / 报名信息
├── .env.example          # Token 配置样例（复制为 .env 使用）
├── .gitignore            # 忽略 .env 与私有快照，防泄露
└── README.md             # 本文件
```

## ⚠️ 合规说明
- 仅个人**非商业用途**，遵循《麦当劳 MCP 服务规则》与《使用条款》。
- 支付由用户在麦当劳链接/App 自行完成，Skill 不代付。
- Token 不落盘、不出现在任何输出中。

## 📜 License
MIT（示例代码与文档）；麦当劳 MCP 服务的使用受官方条款约束。
