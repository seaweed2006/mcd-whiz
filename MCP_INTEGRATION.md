# 麦当劳 MCP 接入说明 (MCP Integration)

本 Skill 调用 **麦当劳中国官方 MCP Server**（`M-China/mcd-mcp-server`）。下面是从零接入的步骤。

## 1. 申请 MCP Token
1. 打开 👉 https://open.mcd.cn/mcp ，点击右上角【登录】
2. 手机号验证登录，登录后右上角变为【控制台】
3. 点【控制台】→ 弹窗里点【激活】→ 同意服务协议 → 申请成功，一键复制 Token
4. ⚠️ Token 私密，切勿提交到代码仓库或在回答中展示

## 2. 接入地址与协议
- 接入地址：`https://mcp.mcd.cn`
- 传输协议：**Streamable HTTP**
- 鉴权：请求头 `Authorization: Bearer YOUR_MCP_TOKEN`
- 限流：每 Token 每分钟最多 600 次（超限返回 429），合理控制频率
- 仅支持 MCP 规范 2025-06-18 及之前版本

## 3. MCP Client 配置 JSON
复制以下配置，替换 `YOUR_MCP_TOKEN` 后粘贴到客户端 MCP Server 配置：
```json
{
  "mcpServers": {
    "mcd-mcp": {
      "type": "streamablehttp",
      "url": "https://mcp.mcd.cn",
      "headers": {
        "Authorization": "Bearer YOUR_MCP_TOKEN"
      }
    }
  }
}
```
支持客户端：WorkBuddy、Cherry Studio、Cursor、Trae、Kiro、VSCode（Copilot）。

## 4. 本 Skill 用到的工具映射
| 模式 | 调用工具 |
|------|----------|
| 通用 | query-nearby-stores, query-meals, query-meal-detail, calculate-price, now-time-info |
| 省钱 | query-store-coupons, available-coupons, auto-bind-coupons, query-my-coupons |
| 控卡 | list-nutrition-foods |
| 积分 | query-my-account, mall-points-products, mall-product-detail |
| 下单 | create-order（返回支付链接，用户自付）, query-order, cancel-order |

## 5. 价格单位坑（重要）
- 仅 `calculate-price` 返回的价格字段是**「分」**（整数），展示前 **÷100**
- `query-meals` / `query-meal-detail` / `create-order` / `query-order` 及商城订单金额已是**「元」**字符串，直接展示
- 所有积分字段（points / totalPoints 等）**不按金额换算**

## 6. 调用流程示例（省钱模式）
```
用户: "50 块怎么点最划算"
→ query-nearby-stores(地址)         # 选门店
→ query-meals(storeId)              # 拿菜单
→ query-store-coupons / available-coupons / query-my-coupons   # 拉可用券
→ calculate-price(items, coupons)   # 算应付（结果÷100）
→ 输出最优组合 + 省钱率
→ 用户确认 → auto-bind-coupons 领券 → create-order 生成支付链接（用户自付）
```

## 7. 调试
- 401：Token 无效/过期 → 检查 Authorization 头
- 429：触发限流 → 降低频率
- 客户端需支持 Streamable HTTP；详见官方仓库 https://github.com/M-China/mcd-mcp-server
