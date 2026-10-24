# workbuddy.md · WorkBuddy 开发记录

> 本项目全程使用 WorkBuddy（https://www.workbuddy.cn ）协作开发。
> 本文件为开发对话的过程记录，用于参与麦当劳程序员节创意开发大赛的 WorkBuddy 联动活动奖励核验。
> 开发时间线：2026-10-24 14:04 ~ 2026-10-25 02:07（北京时间，跨一晚完成）。

## 开发过程

### 1. 赛题研究与报名确认（10-24 下午）
- 用户发起：帮忙看怎么参加麦当劳程序员创意开发大赛
- WorkBuddy 抓取官方仓库规则：基于麦当劳 MCP 开发 Skill，GitHub 公开仓库 + Issue 报名，按 Star 排名
- 明确参赛要求：README.md / CONTEST_DECLARATION.md / MCP_INTEGRATION.md / 源码，创建时间限制等

### 2. 环境接入（10-24 下午）
- 指导用户在麦当劳 MCP 开放平台（open.mcd.cn/mcp）注册并激活 MCP Token
- 在 WorkBuddy 配置 mcd-mcp 连接器（Streamable HTTP，Bearer 鉴权）
- 实测连接：调用 now-time-info、query-my-account 验证 Token 有效（顺带发现 22.9 积分即将过期）

### 3. 创意方案（10-24 晚）
- WorkBuddy 分析全部 30+ 个 MCP 工具，提出 4 个方向（省钱助手/营养管家/薅羊毛日历/组合拳）
- 用户提出「麦门人格报告」策划案：Spotify Wrapped 式九屏报告 + 8 种麦门人格 + 下一单彩蛋
- WorkBuddy 制定执行时间表与砍需求优先级

### 4. 工具实测（10-25 00:47）
- 实测关键工具并记录返回字段：order-list（发现一次返回全部商品明细，砍掉逐单查询）、query-order（确认 totalDiscountAmount 优惠字段）、list-nutrition-foods（160 项纯文本营养表）
- 确认报告定名「近期麦门报告」；产出 docs/tool-mapping.md

### 5. 数据层（10-25 01:05）
- WorkBuddy 编写零依赖 MCP 客户端 src/mcd_client.py（Python 标准库实现 Streamable HTTP / JSON-RPC，兼容 SSE 分帧，重试限速）
- src/fetch_data.py：拉取订单/逐单优惠/营养表/积分/券/活动日历，营养表模糊匹配 + 手动估算映射（报告标注"约"）
- 拉取真实数据：9 单有效订单，全部营养匹配成功

### 6. 分析层（10-25 01:18）
- src/analyze.py：纯代码统计（订单聚合/时间分布/热量换算/门店足迹）+ 8 种人格优先级判定
- 验证：真实数据判为「麦门路人」；40 单模拟数据判为「深夜食堂主理人」+ 副标签「券神」「本命专一派」
- 原则：所有数字由代码计算，不让模型估算

### 7. 展示层（10-25 01:18 ~ 01:26）
- src/build_report.py：单文件 HTML 报告生成器，九屏竖滑、移动端优先、数据内联零外部资源
- 用户反馈"更有动效感"→ 增加数字滚动、柱状图生长、巨型描边背景字、漂浮麦门元素、人格卡流光、顶部进度条，并适配 prefers-reduced-motion
- 通过 WorkBuddy 应用发布能力上线在线演示：https://mcd-persona-report.app.workbuddy.host/?sharecode=KKSMOUGDST （仅含报告页，个人数据不上传）

### 8. 仓库与提交（10-25 01:55 ~ 02:07）
- src/best_next.py 彩蛋：一键领券（可选）→ 附近门店 → 实时菜单 → 预算内贪心组合 → calculate-price 实时算价，绝不调用 create-order；实测处理"凌晨门店打烊自动换店"边界情况
- 生成 README.md / MCP_INTEGRATION.md / LICENSE / .gitignore（排除全部个人真实数据）；CONTEST_DECLARATION.md 使用官方原文（远端与本地字节级一致）
- git push 遇代理 502，改用 GitHub Contents API 完成 14 个文件上传
- 通过 gh 提交报名 Issue：M-China/mcd-developer-innovation-challenge#1327

## WorkBuddy 在本项目中的价值

- **全链路单人协作**：从赛题解读、方案策划、编码、测试、发布到提交，一个人 + WorkBuddy 一晚完成
- **直连真实业务**：WorkBuddy 的 MCP 连接器让 AI 直接操作麦当劳官方接口（下单链路除外），数据与功能全部真实
- **工程习惯内建**：隐私文件隔离、错误边界处理、动效无障碍适配、报告数字可复现，均由对话中即时落实
