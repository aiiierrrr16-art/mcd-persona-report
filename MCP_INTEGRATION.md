# MCP Integration · 麦当劳 MCP 能力使用说明

## 接入信息

- **MCP Server**：`https://mcp.mcd.cn`（麦当劳中国官方，Streamable HTTP 协议）
- **鉴权**：请求头 `Authorization: Bearer <MCP_TOKEN>`，Token 在 [open.mcd.cn/mcp](https://open.mcd.cn/mcp) 控制台免费申请
- **实现方式**：本项目用 Python 标准库实现了一个约 100 行的极简 MCP 客户端（`src/mcd_client.py`），完成 `initialize` 握手与 `tools/call` 调用，自动兼容纯 JSON 与 SSE 分帧两种响应格式，内置重试与限速（官方限制 600 次/分钟）

## 工具使用清单

### 报告数据链路（核心）

| 工具 | 调用方式 | 业务价值 |
|---|---|---|
| `order-list` | 无参数，一次调用 | 拉取近期订单（含商品明细与套餐子项），是报告所有统计的数据源 |
| `query-order` | 传入每个 orderId | 获取 `totalDiscountAmount` 与用券明细，支撑「省钱成绩」屏 |
| `list-nutrition-foods` | 无参数 | 160 项餐品营养表，与订单单品模糊匹配后累加热量，支撑「热量换算」屏 |
| `query-my-account` | 无参数 | 可用积分 + 即将过期积分，支撑报告结尾的积分提醒 |
| `query-my-coupons` | 分页查询 | 用户卡包优惠券资产，展示与彩蛋算价用 |
| `campaign-calendar` | 无参数 | 当月营销活动，支撑「本月别错过」模块 |
| `now-time-info` | 无参数 | 报告生成时间与季节文案 |

### 彩蛋链路（只算价，不下单）

| 工具 | 调用方式 | 业务价值 |
|---|---|---|
| `auto-bind-coupons` | 可选开启 | 一键领取麦麦省全部可用券，让「下一单」拿到真实折扣 |
| `query-nearby-stores` | searchType=2 + 城市/关键词 + beType | 定位用户附近可点餐门店，自动跳过打烊门店 |
| `query-meals` | storeCode + orderType + beType | 拉取该门店实时可售菜单与价格，作为组合原料 |
| `calculate-price` | storeCode + items[] | 官方算价引擎（含优惠），实时验证预算内组合的最终价格 |

## 调用流程图

```
生成报告：
order-list ──┬──> 商品明细（套餐展开）──> list-nutrition-foods 匹配 ──> 热量统计
             ├──> query-order(逐单) ──> totalDiscountAmount ──> 省钱成绩
             └──> createTime/storeName ──> 时间画像 / 门店足迹 / 人格判定
query-my-account ──> 积分提醒        campaign-calendar ──> 本月活动

下一单彩蛋：
auto-bind-coupons(可选) ──> query-nearby-stores ──> query-meals
      ──> 本地贪心组合(预算内) ──> calculate-price 实时验证 ──> 输出方案
      （流程止步于算价，绝不调用 create-order）
```

## 业务价值

1. **把交易数据变成情感内容**：原始订单是一行行 JSON，报告把它变成可分享的人格卡片——同样的 MCP 数据，不同的产品形态
2. **只读安全**：全链路不涉及支付与下单接口，演示零风险
3. **真实价格闭环**：彩蛋从领券到算价全部走官方接口，给出的是"现在去 APP 下单就这个价"的可执行建议，而非纸面估算
4. **边界友好**：打烊门店自动跳过、限流内置重试、营养表缺失单品有估算映射并在报告中标注

## 错误处理

| 场景 | 处理 |
|---|---|
| 门店打烊（code 600057） | 自动尝试下一家营业中门店 |
| 429 限流 | 客户端内置指数退避重试 |
| 营养表无匹配单品 | 手动估算映射表 + 报告标注"约" |
| 已取消订单 | 清洗阶段自动过滤 |
