"""彩蛋：领券 + 预算内最优下一单。

流程:
  1. (可选 --claim) auto-bind-coupons 一键领取麦麦省所有可用券
  2. query-nearby-stores 找到指定位置附近的门店
  3. query-meals 拉取该门店菜单
  4. query-my-coupons 查可用券
  5. 本地贪心组合出接近预算的点单方案，calculate-price 实时算价验证

⚠️ 本脚本绝不调用 create-order，只算价不下单。
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from mcd_client import McdClient

FOOD_HINTS = {  # 按券名猜适配单品（贪心用，失败则不用券）
    "麦辣鸡腿堡": "麦辣", "薯": "薯", "鸡": "鸡", "堡": "堡", "派": "派",
    "麦旋风": "旋风", "咖啡": "咖啡", "早餐": "满分",
}


def parse_price(v) -> float:
    """防御式解析价格：>1000 视为'分'，否则视为'元'。"""
    f = float(str(v).replace("¥", "").strip() or 0)
    return f / 100 if f > 1000 else f


def flatten_menu(meals_resp: dict) -> list[dict]:
    """把 query-meals 返回的（可能多层分类嵌套的）菜单拍平。"""
    out = []

    def walk(node):
        if isinstance(node, dict):
            if "productCode" in node and ("price" in node or "sellPrice" in node):
                price = node.get("price") or node.get("sellPrice") or node.get("productPrice")
                if price is not None:
                    out.append({
                        "code": node["productCode"],
                        "name": node.get("productName") or node.get("name", ""),
                        "price": parse_price(price),
                        "type": node.get("productType", ""),
                    })
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(meals_resp)
    return out


def guess_coupon_item(coupon_name: str, menu: list[dict]) -> dict | None:
    for hint in FOOD_HINTS.values():
        if hint in coupon_name:
            for item in menu:
                if hint in item["name"]:
                    return item
    return None


def greedy_combo(menu: list[dict], budget: float) -> list[dict]:
    """贪心：先拿一个主食，再往预算里凑小食/饮料。"""
    if not menu:
        return []
    picks = []
    remain = budget
    mains = sorted((m for m in menu if "堡" in m["name"] or "桶" in m["name"]
                    or "套" in m["name"] or "鸡" in m["name"]),
                   key=lambda x: x["price"])
    for m in mains:
        if m["price"] <= remain:
            picks.append(m)
            remain -= m["price"]
            break
    sides = sorted(menu, key=lambda x: x["price"])
    for s in sides:
        if s is picks[0] if picks else False:
            continue
        if s["price"] <= remain - 0.5:
            picks.append(s)
            remain -= s["price"]
        if len(picks) >= 4:
            break
    return picks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--token", required=True)
    ap.add_argument("--city", required=True, help="城市，如：广州")
    ap.add_argument("--keyword", required=True, help="位置关键词，如：嘉禾")
    ap.add_argument("--budget", type=float, default=30.0)
    ap.add_argument("--be-type", type=int, default=1, choices=[1, 5],
                    help="1 到店自取 / 5 得来速")
    ap.add_argument("--claim", action="store_true",
                    help="先一键领取麦麦省所有可用券（默认不领）")
    args = ap.parse_args()

    client = McdClient(args.token)

    if args.claim:
        print("[1/5] 一键领券 auto-bind-coupons ...")
        r = client.call_tool("auto-bind-coupons", {})
        print("      ", json.dumps(r, ensure_ascii=False)[:200])
        time.sleep(1)
    else:
        print("[1/5] 跳过领券（未加 --claim）")

    print("[2/5] 查询附近门店 query-nearby-stores ...")
    stores = client.call_tool("query-nearby-stores",
                              {"searchType": 2, "city": args.city,
                               "keyword": args.keyword, "beType": args.be_type})
    store_list = stores.get("data") or stores.get("_raw_text")
    if not isinstance(store_list, list) or not store_list:
        store_list = (stores.get("data") or {}).get("list", []) if isinstance(stores.get("data"), dict) else []
    if not store_list:
        print("      未找到门店，原始返回：", json.dumps(stores, ensure_ascii=False)[:300])
        sys.exit(1)
    store = store_list[0]
    store_code = store.get("storeCode") or store.get("code")
    be_code = store.get("beCode", "")
    print(f"      门店：{store.get('storeName') or store.get('name')} ({store_code})")

    print("[3/5] 拉取菜单 query-meals（自动跳过打烊门店）...")
    menu = []
    store = None
    store_code = be_code = None
    for s in store_list[:5]:
        sc = s.get("storeCode") or s.get("code")
        bc = s.get("beCode", "") or ""
        try:
            meals = client.call_tool(
                "query-meals",
                {"storeCode": sc, "orderType": 1, "beType": args.be_type,
                 **({"beCode": bc} if bc and args.be_type == 5 else {})})
        except RuntimeError as e:
            print(f"      {s.get('storeName') or s.get('name')} 跳过：{e}")
            continue
        if meals.get("success") is False:
            print(f"      {s.get('storeName') or s.get('name')} 跳过：{meals.get('message', '不可点餐')}")
            continue
        menu = flatten_menu(meals)
        if menu:
            store, store_code, be_code = s, sc, bc
            break
        print(f"      {s.get('storeName') or s.get('name')} 无可售商品，换下一家")
    if not menu:
        print("      附近门店均不可点餐（可能都打烊了）")
        sys.exit(1)
    menu.sort(key=lambda x: x["price"])
    print(f"      可售单品 {len(menu)} 个，价格区间 "
          f"¥{menu[0]['price'] if menu else '-'} ~ ¥{menu[-1]['price'] if menu else '-'}")

    print("[4/5] 查询可用券 query-my-coupons ...")
    coupons = client.call_tool("query-my-coupons", {"page": "1", "pageSize": "200"})
    coupon_text = json.dumps(coupons, ensure_ascii=False)

    print("[5/5] 组合方案 + calculate-price 实时算价 ...")
    picks = greedy_combo(menu, args.budget)
    if not picks:
        print("      预算内没有可行组合")
        sys.exit(1)
    items = [{"productCode": p["code"], "quantity": 1} for p in picks]
    price = client.call_tool("calculate-price",
                             {"storeCode": store_code, "orderType": 1,
                              "beType": args.be_type,
                              **({"beCode": be_code} if be_code and args.be_type == 5 else {}),
                              "items": items})
    pd = price.get("data", {})
    real = parse_price(pd.get("realTotalAmount") or 0)
    print()
    print("=" * 46)
    print(f"  门店：{store.get('storeName') or store.get('name')}")
    for p in picks:
        print(f"    - {p['name']}  ¥{p['price']}")
    print(f"  预算 ¥{args.budget} · 实时算价 ¥{real}")
    print("  （仅算价，不下单——想下单请去麦当劳 APP）")
    print("=" * 46)

    out = {"store": store, "picks": picks, "budget": args.budget,
           "realPrice": real, "priceDetail": pd}
    Path("data/next-order.json").write_text(
        json.dumps(out, ensure_ascii=False, indent=1))
    print("明细已存 → data/next-order.json")


if __name__ == "__main__":
    main()
