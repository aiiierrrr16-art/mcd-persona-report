"""数据层：拉取麦当劳 MCP 数据 → 清洗 → 输出 data.json（真实数据）。

用法:
    python3 fetch_data.py --token YOUR_MCP_TOKEN [--out data/data.json]

隐私说明: 数据仅保存在本地，脚本不会上传任何数据。
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mcd_client import McdClient

ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = ROOT / "data" / "raw"


def parse_nutrition(raw_text: str) -> list[dict]:
    """把 list-nutrition-foods 的纯文本表清洗成结构化列表。

    行格式: "  名称,描述,能量kJ,能量kcal,蛋白质,脂肪,碳水,钠,钙"
    """
    items = []
    for line in raw_text.splitlines():
        line = line.strip()
        if not line or line.startswith("[") or line.startswith(":"):
            continue
        parts = [p.strip() for p in line.split(",")]
        if len(parts) < 9:
            continue
        name, desc = parts[0], parts[1]
        nums = parts[2:9]
        try:
            vals = [float(v) if v not in ("null", "") else 0.0 for v in nums]
        except ValueError:
            continue
        items.append({
            "name": name,
            "desc": desc if desc != "null" else "",
            "energyKcal": vals[1],
            "protein": vals[2],
            "fat": vals[3],
            "carbohydrate": vals[4],
            "sodium": vals[5],
            "calcium": vals[6],
        })
    return items


def normalize(name: str) -> str:
    """名称归一化，用于营养表模糊匹配。"""
    s = name.lower()
    s = re.sub(r"[（(].*?[)）]", "", s)        # 去括号注解: 那么大鸡排（椒盐风味）
    s = re.sub(r"[\s\-—·]+", "", s)
    s = s.replace("块", "")                    # 麦辣鸡翅2块 / 麦辣鸡翅-2块
    return s


def match_nutrition(product_name: str, nutrition: list[dict],
                    index: dict) -> dict | None:
    key = normalize(product_name)
    if key in index:
        return index[key]
    # 包含式匹配：营养表名包含单品名，或反之
    for item in nutrition:
        n = normalize(item["name"])
        if n and (n in key or key in n):
            return item
    return None


# 营养表缺失单品的手动映射（基于相似单品的估算，报告中标注"约"）
MANUAL_MATCH = {
    "10块麦乐鸡": ("麦乐鸡5块", 2.0),          # 精确换算
    "10块星愿薯饼": ("脆薯饼", 2.0),            # 估算
    "高达吉士双牛堡": ("双层吉士汉堡", 1.0),     # 估算
    "Hold不住鸡排堡（椒盐风味）": ("麦辣鸡腿汉堡", 1.0),  # 估算
}


def extract_items(order: dict) -> list[dict]:
    """从订单提取扁平单品列表（套餐展开为子项，取子项名）。"""
    items = []
    for prod in order.get("orderProductList", []):
        subs = prod.get("comboItemList") or []
        if subs:
            for sub in subs:
                items.append({"name": sub.get("name") or sub.get("itemName", ""),
                              "qty": sub.get("quantity", sub.get("itemQuantity", 1)),
                              "parent": prod.get("productName", "")})
        else:
            items.append({"name": prod.get("productName", ""),
                          "qty": prod.get("quantity", 1),
                          "parent": ""})
    return [i for i in items if i["name"]]


def clean_orders(raw_list: list[dict]) -> list[dict]:
    """过滤取消订单，保留有效字段。"""
    orders = []
    for o in raw_list:
        if "取消" in (o.get("orderStatus") or ""):
            continue
        orders.append({
            "orderId": o.get("orderId"),
            "createTime": o.get("createTime"),
            "storeCode": o.get("storeCode"),
            "storeName": o.get("storeName"),
            "takeWayHint": o.get("beType"),
            "total": float(o.get("realTotalAmount") or 0),
            "items": extract_items(o),
        })
    return orders


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", required=True)
    ap.add_argument("--out", default=str(ROOT / "data" / "data.json"))
    args = ap.parse_args()

    client = McdClient(args.token)
    RAW_DIR.mkdir(parents=True, exist_ok=True)

    def fetch(tool, arguments=None, cache_name=None):
        """带本地缓存的拉取：raw 目录有缓存就不再请求。"""
        cache = RAW_DIR / f"{cache_name or tool}.json"
        if cache.exists():
            return json.loads(cache.read_text())
        data = client.call_tool(tool, arguments)
        cache.write_text(json.dumps(data, ensure_ascii=False, indent=1))
        time.sleep(0.3)  # 温和限速
        return data

    print("[1/5] 拉取历史订单 order-list ...")
    raw_orders = fetch("order-list")["data"]["list"]
    orders = clean_orders(raw_orders)
    print(f"      有效订单 {len(orders)} 单（已过滤取消订单）")

    print("[2/5] 逐单查询优惠明细 query-order（带缓存）...")
    for o in orders:
        detail = fetch("query-order", {"orderId": o["orderId"]},
                       cache_name=f"order-{o['orderId'][-8:]}")
        d = detail.get("data", {})
        o["discount"] = float(d.get("totalDiscountAmount") or 0)
        o["takeWay"] = d.get("takeWay", "")
        o["coupons"] = [
            {"name": c.get("couponName"), "amount": float(c.get("discountAmount") or 0)}
            for c in (d.get("couponList") or [])
        ]
        o["productPrice"] = float(d.get("productPrice") or 0)

    print("[3/5] 拉取营养表 list-nutrition-foods ...")
    nut_raw = fetch("list-nutrition-foods")
    nutrition = parse_nutrition(nut_raw.get("data") or nut_raw.get("_raw_text", ""))
    print(f"      清洗后 {len(nutrition)} 项")

    print("[4/5] 拉取积分 / 优惠券 / 活动日历 ...")
    account = fetch("query-my-account").get("data", {})
    coupons = fetch("query-my-coupons", {"page": "1", "pageSize": "200"})
    calendar = fetch("campaign-calendar")

    print("[5/5] 营养匹配 + 汇总输出 ...")
    index = {normalize(i["name"]): i for i in nutrition}
    unmatched = []
    for o in orders:
        for item in o["items"]:
            m = match_nutrition(item["name"], nutrition, index)
            est = False
            if not m and item["name"] in MANUAL_MATCH:
                ref, mult = MANUAL_MATCH[item["name"]]
                ref_item = index.get(normalize(ref))
                if ref_item:
                    m = ref_item
                    est = True
                    item["qty_factor"] = mult
            if m:
                factor = item.get("qty_factor", 1.0)
                item["kcal"] = round(m["energyKcal"] * item["qty"] * factor)
                item["matched"] = m["name"]
                item["estimated"] = est
            else:
                item["kcal"] = None
                item["matched"] = None
                if item["name"] not in unmatched and item["name"] != "鸡薯双全四拼酱":
                    unmatched.append(item["name"])

    out = {
        "generatedAt": time.strftime("%Y-%m-%d %H:%M:%S"),
        "orders": orders,
        "nutritionCount": len(nutrition),
        "unmatchedItems": unmatched,
        "account": {
            "availablePoint": account.get("availablePoint"),
            "expiringPoint": account.get("currentMouthExpirePoint"),
            "accumulativePoint": account.get("accumulativePoint"),
        },
        "coupons": coupons,
        "calendar": calendar,
    }
    Path(args.out).write_text(json.dumps(out, ensure_ascii=False, indent=1))
    print(f"完成 → {args.out}")
    if unmatched:
        print(f"未匹配营养数据单品: {unmatched}")


if __name__ == "__main__":
    main()
