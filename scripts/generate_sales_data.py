from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


def main() -> None:
    random.seed(42)

    output_path = Path("app/data/sales_data.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    start_date = datetime(2026, 1, 1)
    end_date = datetime(2026, 4, 20)

    regions = ["华东", "华中", "西南", "华北"]
    product_lines = {
        "骨科": ["ORTHO-001", "ORTHO-002", "ORTHO-003"],
        "儿科": ["PED-001", "PED-002", "PED-003"],
        "皮肤科": ["DERM-001", "DERM-002", "DERM-003"],
        "肿瘤科": ["ONCO-001", "ONCO-002", "ONCO-003"],
    }
    customer_types = ["连锁药房", "单体药店", "诊所", "医院终端"]

    # 各区域基础强度
    region_multiplier = {
        "华东": 1.20,
        "华中": 1.00,
        "西南": 0.95,
        "华北": 1.10,
    }

    # 各产品线基础强度
    product_multiplier = {
        "骨科": 1.30,
        "儿科": 1.05,
        "皮肤科": 0.90,
        "肿瘤科": 1.15,
    }

    # 各产品线基础客单价区间
    unit_price_range = {
        "骨科": (55, 95),
        "儿科": (30, 65),
        "皮肤科": (25, 70),
        "肿瘤科": (80, 150),
    }

    rows = []
    current_date = start_date
    order_seq = 1

    while current_date <= end_date:
        weekday = current_date.weekday()  # Monday=0, Sunday=6

        # 周内波动：工作日更强，周末稍弱
        weekday_factor = 1.0
        if weekday in [0, 1, 2, 3]:
            weekday_factor = 1.08
        elif weekday == 4:
            weekday_factor = 1.03
        else:
            weekday_factor = 0.88

        # 月度轻微趋势
        month_factor = {
            1: 0.96,
            2: 1.00,
            3: 1.04,
            4: 1.08,
        }.get(current_date.month, 1.0)

        for region in regions:
            for product_line, sku_list in product_lines.items():
                base_orders = 3

                # 根据区域、产品线、日期因子决定当天订单量
                strength = region_multiplier[region] * product_multiplier[product_line] * weekday_factor * month_factor
                order_count = max(1, int(round(base_orders * strength + random.uniform(0, 2.2))))

                # ----- 人工注入异常，用于后面 anomaly.py 检测 -----
                # 1. 西南区骨科在 4 月上半月明显下滑
                if (
                    region == "西南"
                    and product_line == "骨科"
                    and datetime(2026, 4, 1) <= current_date <= datetime(2026, 4, 15)
                ):
                    order_count = max(1, int(order_count * 0.45))

                # 2. 华东区肿瘤科在 3 月中下旬明显上升
                if (
                    region == "华东"
                    and product_line == "肿瘤科"
                    and datetime(2026, 3, 12) <= current_date <= datetime(2026, 3, 28)
                ):
                    order_count = max(2, int(order_count * 1.75))

                # 3. 华北区皮肤科在 4 月初有一段波动
                if (
                    region == "华北"
                    and product_line == "皮肤科"
                    and datetime(2026, 4, 5) <= current_date <= datetime(2026, 4, 12)
                ):
                    order_count = max(1, int(order_count * 0.60))

                for _ in range(order_count):
                    sku = random.choice(sku_list)
                    customer_type = random.choices(
                        population=customer_types,
                        weights=[0.35, 0.28, 0.20, 0.17],
                        k=1,
                    )[0]

                    customer_id = f"CUST-{region[:2]}-{random.randint(1000, 1099)}"

                    unit_price_low, unit_price_high = unit_price_range[product_line]
                    unit_price = round(random.uniform(unit_price_low, unit_price_high), 2)

                    quantity = random.randint(5, 60)

                    # 某些产品线/客户类型更容易拿到折扣
                    discount = 0.0
                    if customer_type in {"连锁药房", "医院终端"}:
                        discount = round(random.choice([0, 0.02, 0.03, 0.05, 0.08]), 2)
                    else:
                        discount = round(random.choice([0, 0.01, 0.02, 0.03, 0.05]), 2)

                    gross_amount = unit_price * quantity
                    sales_amount = round(gross_amount * (1 - discount), 2)

                    # 退货标记：小概率发生，某些异常期间略高
                    return_probability = 0.04
                    if region == "西南" and product_line == "骨科" and datetime(2026, 4, 1) <= current_date <= datetime(2026, 4, 15):
                        return_probability = 0.08
                    if region == "华北" and product_line == "皮肤科" and datetime(2026, 4, 5) <= current_date <= datetime(2026, 4, 12):
                        return_probability = 0.07

                    return_flag = 1 if random.random() < return_probability else 0

                    # 库存水平：不同产品线库存差异
                    inventory_base = {
                        "骨科": 900,
                        "儿科": 1200,
                        "皮肤科": 800,
                        "肿瘤科": 600,
                    }[product_line]

                    inventory_noise = random.randint(-180, 180)
                    inventory_level = max(50, inventory_base + inventory_noise)

                    # 异常期间库存也做一点联动
                    if (
                        region == "西南"
                        and product_line == "骨科"
                        and datetime(2026, 4, 1) <= current_date <= datetime(2026, 4, 15)
                    ):
                        inventory_level = max(80, inventory_level + random.randint(80, 220))

                    if (
                        region == "华东"
                        and product_line == "肿瘤科"
                        and datetime(2026, 3, 12) <= current_date <= datetime(2026, 3, 28)
                    ):
                        inventory_level = max(50, inventory_level - random.randint(50, 160))

                    row = {
                        "order_id": f"ORD-{current_date.strftime('%Y%m%d')}-{order_seq:05d}",
                        "order_date": current_date.strftime("%Y-%m-%d"),
                        "region": region,
                        "product_line": product_line,
                        "sku": sku,
                        "customer_id": customer_id,
                        "customer_type": customer_type,
                        "sales_amount": sales_amount,
                        "quantity": quantity,
                        "discount": discount,
                        "return_flag": return_flag,
                        "inventory_level": inventory_level,
                    }
                    rows.append(row)
                    order_seq += 1

        current_date += timedelta(days=1)

    df = pd.DataFrame(rows)

    # 让数据顺序更接近真实订单流
    df = df.sort_values(by=["order_date", "region", "product_line", "order_id"]).reset_index(drop=True)

    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"Generated {len(df)} rows.")
    print(f"Saved to: {output_path.resolve()}")
    print(df.head(10).to_string(index=False))


if __name__ == "__main__":
    main()