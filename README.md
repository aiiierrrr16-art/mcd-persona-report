# 🍔 麦门人格报告 · MCD Persona Report

> 一句话：连上你的麦当劳账号，生成一份 **Spotify Wrapped 式的「近期麦门报告」**——你吃了什么、什么时候吃、省了多少、是哪种麦门人格，最后送你一份「下一单最优方案」。

**[👉 在线演示（模拟数据）](https://mcd-persona-report.app.workbuddy.host/?sharecode=KKSMOUGDST)**

---

## 你能得到什么

九屏竖滑式报告（移动端优先，动效拉满）：

| # | 屏幕 | 内容 |
|---|---|---|
| 1 | 开场 | 「2026，你和麦当劳的 N 次相遇」 |
| 2 | 总览 | 总花费 / 堂食 vs 外送占比 / 平均客单 |
| 3 | 本命单品 | 点得最多的单品与次数 |
| 4 | 时间画像 | 24 小时下单热力图 |
| 5 | 热量换算 | 「累计 X 大卡 ≈ Y 碗米饭」（轻松换算，不评价身材） |
| 6 | 门店足迹 | 去过几家店，最常去哪家 |
| 7 | 省钱成绩 | 「优惠帮你省了 ¥X」 |
| 8 | 人格卡 | 竖版可截图：人格名 + 文案 + 三个关键数据 |
| 9 | 下一单彩蛋 | 积分即将过期提醒 + 本月活动 + 预算内最优组合 |

## 8 种麦门人格

按优先级判定，命中即定，最多两个副标签：

| 人格 | 判定条件 | 文案 |
|---|---|---|
| 深夜食堂主理人 | 22:00 后订单占比 ≥ 40% | 城市睡了，你的麦乐送还醒着 |
| 早餐信徒 | 10:30 前订单占比 ≥ 40% | 你的一天，从一份麦满分开始 |
| 券神 | 有优惠订单占比 ≥ 70% | 原价？没听说过 |
| 本命专一派 | 同一单品出现在 ≥ 50% 订单 | 别人在探索菜单，你在守护唯一 |
| 甜品党 | 甜品类单品占比 ≥ 30% | 正餐是借口，甜品才是目的 |
| 外送宅 | 外送订单占比 ≥ 80% | 门店在哪？不重要 |
| 门店探险家 | 去过 ≥ 8 家不同门店 | 你的足迹比店长还广 |
| 麦门路人 | 兜底 | 偶尔来，但每次都很快乐 |

## 快速开始（3 步）

```bash
# 1. 获取麦当劳 MCP Token（免费）
#    打开 https://open.mcd.cn/mcp → 手机号登录 → 控制台 → 激活 → 复制 Token

# 2. 生成你的报告（拉取数据 + 分析 + 渲染一条龙）
python3 src/fetch_data.py --token YOUR_MCP_TOKEN
python3 src/analyze.py
python3 src/build_report.py
open report.html   # 浏览器打开，建议用手机模式

# 3. 下一单彩蛋（可选，营业时间运行；只算价，不下单）
python3 src/best_next.py --token YOUR_MCP_TOKEN --city 广州 --keyword 嘉禾 --budget 30
#    加 --claim 可先一键领取麦麦省所有可用券
```

无第三方依赖，仅 Python 3.10+ 标准库。

## 没有订单数据？用模拟数据体验

```bash
python3 src/analyze.py --input data/mock-data.json --out data/analysis-mock.json
python3 src/build_report.py --input data/analysis-mock.json --out report-demo.html
```

## 技术架构

```
src/mcd_client.py   零依赖 MCP 客户端（Streamable HTTP / JSON-RPC，
                    自动处理 SSE 分帧、initialize 握手、重试与限速）
src/fetch_data.py   数据层：拉取订单/营养/积分/券 → 清洗 → data.json
src/analyze.py      分析层：纯代码统计 + 8 人格优先级判定 → analysis.json
src/build_report.py 展示层：单文件 HTML 报告生成器（数据内联、零外部资源）
src/best_next.py    彩蛋：领券 + 门店 + 菜单 + 实时算价（绝不调用 create-order）
```

设计原则：**数字全部由代码计算，不让模型估算**；报告数据仅本地处理。

## 用到的麦当劳 MCP 工具

详见 [MCP_INTEGRATION.md](MCP_INTEGRATION.md)。核心链路：
`order-list` → `query-order` → `list-nutrition-foods` → `query-my-account` → `query-my-coupons` → `campaign-calendar` → `query-nearby-stores` → `query-meals` → `calculate-price`

## 隐私说明

- 所有数据仅在你的电脑本地处理，不上传到任何服务器
- 报告页只含聚合统计（单数、金额、门店名），不含地址、手机号、订单号
- 请妥善保管你的 MCP Token，它等同于你麦当劳账号的操作权限
- `.gitignore` 已排除全部真实个人数据文件

## License

[MIT](LICENSE)
