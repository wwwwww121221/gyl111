from typing import Any


def calculate_bargain_feedback(
    target_price: float,
    market_min_price: float,
    current_price: float,
    current_round: int,
    max_rounds: int,
) -> tuple[float, float, str]:
    target_price = float(target_price)
    market_min_price = float(market_min_price)
    current_price = float(current_price)

    if current_price <= target_price:
        return 0.0, current_price, ""

    ideal_price = min(target_price, market_min_price)
    if current_price <= ideal_price:
        return 0.0, current_price, ""

    required_drop_ratio = (current_price - ideal_price) / current_price
    if max_rounds <= 1:
        adjust_factor = 1.0
    else:
        adjust_factor = float(current_round) / float(max_rounds - 1)
    actual_drop_ratio = required_drop_ratio * adjust_factor

    if actual_drop_ratio > 0.15:
        actual_drop_ratio = 0.15
    if actual_drop_ratio < 0.01:
        return 0.0, current_price, ""

    new_price = current_price * (1 - actual_drop_ratio)
    message = (
        f"您当前报价{current_price:.4f}元，高于目标价和市场最低价，"
        f"请降价{actual_drop_ratio * 100:.2f}%至{new_price:.4f}元。"
    )
    return actual_drop_ratio, new_price, message


def calculate_supplier_scores(suppliers_data: list[dict], score_weights: dict | None = None) -> list[dict]:
    if not suppliers_data:
        return []

    weights = score_weights or {"price": 0.7, "delivery": 0.3}
    price_weight = float(weights.get("price", 0.7))
    delivery_weight = float(weights.get("delivery", 0.3))

    item_prices: dict[Any, list[float]] = {}
    item_deliveries: dict[Any, list[float]] = {}
    for supplier in suppliers_data:
        for item in supplier.get("items") or []:
            iid = item.get("item_id")
            price = float(item.get("price", 0))
            dd = float(item.get("delivery_days", 0))
            if iid is None:
                continue
            if price > 0:
                item_prices.setdefault(iid, []).append(price)
            if dd > 0:
                item_deliveries.setdefault(iid, []).append(dd)

    item_min_price = {iid: min(prices) for iid, prices in item_prices.items()}
    item_min_delivery = {iid: min(dds) for iid, dds in item_deliveries.items()}

    enriched: list[dict[str, Any]] = []
    for supplier in suppliers_data:
        items = supplier.get("items") or []
        record = dict(supplier)

        total_price = sum(float(it.get("price", 0)) * float(it.get("qty", 0)) for it in items)
        item_count = len(items)
        avg_delivery_days = (
            sum(float(it.get("delivery_days", 0)) for it in items) / item_count if item_count > 0 else 0.0
        )
        record["total_price"] = total_price
        record["avg_delivery_days"] = avg_delivery_days

        per_item_price_scores = []
        per_item_delivery_scores = []
        per_item_weights = []

        for it in items:
            iid = it.get("item_id")
            price = float(it.get("price", 0))
            qty = float(it.get("qty", 0))
            dd = float(it.get("delivery_days", 0))

            if iid is None or price <= 0:
                continue

            min_p = item_min_price.get(iid, 0)
            if min_p > 0:
                per_item_price_scores.append(min_p / price * 100)
            else:
                per_item_price_scores.append(0.0)

            min_d = item_min_delivery.get(iid, 0)
            if min_d > 0 and dd > 0:
                per_item_delivery_scores.append(min_d / dd * 100)
            else:
                per_item_delivery_scores.append(0.0)

            per_item_weights.append(qty if qty > 0 else 1.0)

        if per_item_weights:
            total_weight = sum(per_item_weights)
            price_score = sum(s * w for s, w in zip(per_item_price_scores, per_item_weights)) / total_weight
            delivery_score = sum(s * w for s, w in zip(per_item_delivery_scores, per_item_weights)) / total_weight
        else:
            price_score = 0.0
            delivery_score = 0.0

        total_score = price_score * price_weight + delivery_score * delivery_weight
        record["price_score"] = price_score
        record["delivery_score"] = delivery_score
        record["total_score"] = total_score
        enriched.append(record)

    return enriched
