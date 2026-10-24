"""分析层：读取 data.json → 纯代码统计 + 人格判定 → 输出 analysis.json。

所有数字由代码计算，不由模型估算。
用法:
    python3 analyze.py [--input data/data.json] [--out data/analysis.json]
"""
import argparse
import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# 人格判定阈值（初版，实测后可调）
LATE_NIGHT_RATIO = 0.4      # 深夜食堂主理人：22:00 后订单占比
BREAKFAST_RATIO = 0.4       # 早餐信徒：10:30 前订单占比
COUPON_RATIO = 0.7          # 券神：有优惠的订单占比
LOYAL_RATIO = 0.5           # 本命专一派：同一单品出现在订单中的比例
DESSERT_RATIO = 0.3         # 甜品党：甜品类单品数量占比
DELIVERY_RATIO = 0.8        # 外送宅：外送订单占比
EXPLORER_STORES = 8         # 门店探险家：去过门店数

DESSERT_KEYWORDS = ("新地", "麦旋风", "圆筒", "冰淇淋", "派", "奶冻", "爆珠",
                    "拉明顿", "圣代", "雪冰", "阿芙佳朵")
RICE_BOWL_KCAL = 200        # 一碗米饭约 200 大卡（换算用）


def parse_time(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")


def is_late_night(dt: datetime) -> bool:
    return dt.hour >= 22 or dt.hour < 4


def is_breakfast(dt: datetime) -> bool:
    return dt.hour < 10 or (dt.hour == 10 and dt.minute < 30)


def is_dessert(name: str) -> bool:
    return any(k in name for k in DESSERT_KEYWORDS)


def is_delivery(take_way: str) -> bool:
    return bool(take_way) and any(k in take_way for k in ("外送", "送出", "麦乐送"))


PERSONAS = {
    "深夜食堂主理人": "城市睡了，你的麦乐送还醒着",
    "早餐信徒": "你的一天，从一份麦满分开始",
    "券神": "原价？没听说过",
    "本命专一派": "别人在探索菜单，你在守护唯一",
    "甜品党": "正餐是借口，甜品才是目的",
    "外送宅": "门店在哪？不重要",
    "门店探险家": "你的足迹比店长还广",
    "麦门路人": "偶尔来，但每次都很快乐",
}


def detect_persona(orders: list[dict]) -> dict:
    """按优先级判定主人格，最多两个副标签。"""
    n = max(len(orders), 1)
    hour_counts = Counter(parse_time(o["createTime"]).hour for o in orders)
    weekday_counts = Counter(parse_time(o["createTime"]).weekday() for o in orders)

    late = sum(c for h, c in hour_counts.items() if is_late_night(
        datetime(2026, 1, 1, h))) / n
    early = sum(c for h, c in hour_counts.items() if is_breakfast(
        datetime(2026, 1, 1, h))) / n

    # 单品 → 出现的订单数
    item_orders = Counter()
    item_qty = Counter()
    dessert_qty = 0
    total_qty = 0
    for o in orders:
        seen = set()
        for item in o["items"]:
            q = item.get("qty", 1)
            item_orders[item["name"]] += 1
            item_qty[item["name"]] += q
            total_qty += q
            if is_dessert(item["name"]):
                dessert_qty += q
            seen.add(item["name"])

    discount_orders = sum(1 for o in orders if o.get("discount", 0) > 0)
    delivery_orders = sum(1 for o in orders if is_delivery(o.get("takeWay", "")))
    unique_stores = {o["storeCode"] for o in orders if o.get("storeCode")}

    # (人格, 是否命中) 按优先级排列
    checks = [
        ("深夜食堂主理人", late >= LATE_NIGHT_RATIO),
        ("早餐信徒", early >= BREAKFAST_RATIO),
        ("券神", n and discount_orders / n >= COUPON_RATIO),
        ("本命专一派", item_orders and item_orders.most_common(1)[0][1] / n >= LOYAL_RATIO),
        ("甜品党", total_qty and dessert_qty / total_qty >= DESSERT_RATIO),
        ("外送宅", n and delivery_orders / n >= DELIVERY_RATIO),
        ("门店探险家", len(unique_stores) >= EXPLORER_STORES),
    ]
    hit = [name for name, ok in checks if ok]
    main = hit[0] if hit else "麦门路人"
    subs = hit[1:3]

    top_item_name, top_item_orders = (item_orders.most_common(1)[0]
                                      if item_orders else ("", 0))
    return {
        "persona": main,
        "personaLine": PERSONAS[main],
        "subPersonas": [{"name": s, "line": PERSONAS[s]} for s in subs],
        "stats": {
            "lateNightRatio": round(late, 3),
            "breakfastRatio": round(early, 3),
            "couponOrderRatio": round(discount_orders / n, 3) if n else 0,
            "deliveryRatio": round(delivery_orders / n, 3) if n else 0,
            "uniqueStoreCount": len(unique_stores),
            "topItemName": top_item_name,
            "topItemOrderCount": top_item_orders,
            "topItemRatio": round(top_item_orders / n, 3) if n else 0,
            "dessertRatio": round(dessert_qty / total_qty, 3) if total_qty else 0,
            "hourHistogram": [hour_counts.get(h, 0) for h in range(24)],
            "weekdayHistogram": [weekday_counts.get(d, 0) for d in range(7)],
        },
    }


def analyze(data: dict) -> dict:
    orders = data["orders"]
    n = len(orders)
    times = [parse_time(o["createTime"]) for o in orders]
    period = {
        "from": min(times).strftime("%Y-%m-%d"),
        "to": max(times).strftime("%Y-%m-%d"),
        "days": (max(times) - min(times)).days or 1,
    }

    total_spend = round(sum(o["total"] for o in orders), 1)
    total_discount = round(sum(o.get("discount", 0) for o in orders), 1)
    take_way = Counter(o.get("takeWay", "未知") for o in orders)
    kcal = sum(i["kcal"] for o in orders for i in o["items"]
               if i.get("kcal"))
    kcal_unmatched = [i["name"] for o in orders for i in o["items"]
                      if not i.get("kcal")]
    stores = Counter(o["storeName"] for o in orders if o.get("storeName"))
    coupon_savings = round(sum(c["amount"] for o in orders
                               for c in o.get("coupons", [])), 1)

    persona = detect_persona(orders)
    acc = data.get("account", {})

    # 活动日历：提取进行中活动的标题与摘要（清洗富文本）
    events = []
    raw_cal = data.get("calendar", {})
    cal_text = raw_cal.get("data") if isinstance(raw_cal.get("data"), str) \
        else json.dumps(raw_cal, ensure_ascii=False)
    for m in re.finditer(r"活动标题\*\*：(.+?)[\n#]", cal_text or ""):
        title = m.group(1).strip()
        title = re.sub(r"[🔥❤🆕✨🍗⏰🤔😎🫐💜💥😋🩶🍦🧀🍔🥪💳🛵🦉👛👶🎉👇🎊🎁]", "", title)
        if title and title not in [e["title"] for e in events]:
            events.append({"title": title})
    events = events[:4]

    return {
        "generatedAt": data.get("generatedAt"),
        "period": period,
        "orderCount": n,
        "totalSpend": total_spend,
        "avgSpend": round(total_spend / n, 1) if n else 0,
        "totalDiscount": total_discount,
        "couponSavings": coupon_savings,
        "takeWayBreakdown": dict(take_way),
        "totalKcal": kcal,
        "riceBowls": round(kcal / RICE_BOWL_KCAL),
        "kcalEstimated": any(i.get("estimated")
                             for o in orders for i in o["items"]),
        "kcalUnmatched": kcal_unmatched,
        "storeCount": len(stores),
        "topStore": {"name": stores.most_common(1)[0][0],
                     "count": stores.most_common(1)[0][1]} if stores else None,
        "storeBreakdown": dict(stores),
        "account": {
            "availablePoint": acc.get("availablePoint"),
            "expiringPoint": acc.get("expiringPoint"),
        },
        "events": events,
        **persona,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", default=str(ROOT / "data" / "data.json"))
    ap.add_argument("--out", default=str(ROOT / "data" / "analysis.json"))
    args = ap.parse_args()
    data = json.loads(Path(args.input).read_text())
    result = analyze(data)
    Path(args.out).write_text(json.dumps(result, ensure_ascii=False, indent=1))
    print(f"完成 → {args.out}")
    print(json.dumps({k: result[k] for k in
                      ("period", "orderCount", "totalSpend", "totalDiscount",
                       "totalKcal", "storeCount", "persona", "personaLine",
                       "subPersonas")}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
