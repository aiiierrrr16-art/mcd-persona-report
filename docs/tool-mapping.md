# 实测结论 · 工具映射表 v2（2026-10-25 00:47）

## 四个「待确认」的答案

1. **作品形态**：形式不限，脚本 + HTML 报告合规。仓库需含 README.md / CONTEST_DECLARATION.md / MCP_INTEGRATION.md / 源码。
2. **提交渠道**：GitHub 公开仓库 → 官方仓库提 Issue（标题+正文格式固定，字段间不换行，地址不用 Markdown 链接）。截止 10-25 23:59，排名看 Star。
3. **order-list 数据范围**：仅返回近期 **10 条**订单（实测区间 2026-03-09 ~ 2026-05-24），**无分页参数**。→ 报告改名「近期麦门报告」，时间范围动态取 min~max createTime。
4. **优惠字段**：`query-order` 返回 `totalDiscountAmount`（总优惠）+ `couponList[].couponName/discountAmount`。→ 省钱屏：对每单调一次 query-order（10 次，加缓存），累加 totalDiscountAmount。

## 关键实测发现（影响架构）

- **order-list 已含完整商品明细**：`orderProductList[].productName/quantity/comboItemList[].name`，**不需要逐单查详情拿单品**。仅「省钱屏」需要 query-order。
- `orderStatus` 含「订单已取消」的订单 → 分析时过滤。
- **营养表**：`list-nutrition-foods` 返回纯文本 160 项，格式 `productName,desc,energyKj,energyKcal,protein,fat,carb,sodium,calcium`。需清洗成 JSON + 模糊匹配（如「麦辣鸡翅2块」↔「麦辣鸡翅-2块」、「那么大鸡排（椒盐风味）」↔「那么大鸡排」）。「高达吉士双牛堡」等不在表中 → 标注未计入。
- `query-my-coupons`：返回券名/用券价格/有效期/标签，分页 page/pageSize（字符串类型）。
- `campaign-calendar`：返回富文本活动列表（含 HTML 图片标签），展示时需提取标题+摘要。
- `available-coupons`：返回可领/已领状态。

## 报告模块 → 工具映射（最终版）

| 模块 | 工具 | 实测说明 |
|---|---|---|
| 订单总览/本命单品/时间画像/门店足迹 | `order-list` | 一次调用拿全，含单品明细，无需逐单查 |
| 热量统计 | `order-list` + `list-nutrition-foods` | 模糊匹配，匹配不上标注未计入 |
| 省钱成绩 | `order-list` → `query-order`(×N, 带缓存) | 累加 totalDiscountAmount；订单列表本身无优惠字段 |
| 积分提醒 | `query-my-account` | availablePoint / currentMouthExpirePoint |
| 优惠券展示 | `query-my-coupons` / `available-coupons` | 已实测 |
| 时间/季节 | `now-time-info` | 已实测 |
| 当月活动 | `campaign-calendar` | 富文本需清洗 |
| 下一单彩蛋 | `auto-bind-coupons` → `query-nearby-stores`(需城市+beType) → `query-meals`(需 storeId) → `calculate-price` | 领券+算价，绝不调 create-order |

## 待办（数据层实现时注意）

- [ ] 取消订单过滤（orderStatus === "订单已取消"）
- [ ] 门店足迹：去重 storeCode（本账号 10 单中 8 单在嘉禾鹤龙店）
- [ ] 人格初判数据预览：本账号 100% 堂食(beType=1)、随心配 3 次、Hold不住鸡排堡 3 次、圆筒冰淇淋 2 次 → 大概率「本命专一派」或兜底
- [ ] calculate-price 的入参格式未实测（需要门店+就餐方式+商品编码），明天实现彩蛋时先查 schema
