from __future__ import annotations

import random
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd


def main() -> None:
    random.seed(2026)

    output_path = Path("app/data/expense_data.csv")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    departments = ["销售", "财务", "运营", "人力", "采购", "市场"]
    expense_types = {
        "差旅住宿": (380, 650),
        "差旅交通": (120, 900),
        "业务招待": (150, 800),
        "办公采购": (80, 500),
        "培训费用": (200, 1200),
    }

    policy_limits = {
        "差旅住宿": 500,
        "差旅交通": 800,
        "业务招待": 600,
        "办公采购": 300,
        "培训费用": 1000,
    }

    employee_pool = [
        ("张三", "销售"),
        ("李四", "销售"),
        ("王敏", "财务"),
        ("赵磊", "运营"),
        ("陈洁", "人力"),
        ("孙涛", "采购"),
        ("周宁", "市场"),
        ("吴静", "销售"),
        ("郑凯", "运营"),
        ("刘芳", "财务"),
        ("谢婷", "人力"),
        ("彭飞", "采购"),
    ]

    rows = []
    expense_seq = 1
    invoice_seq = 800000

    start_date = datetime(2026, 1, 5)
    end_date = datetime(2026, 4, 20)

    # 先生成主体正常数据
    current_date = start_date
    while current_date <= end_date:
        daily_count = random.randint(2, 6)

        for _ in range(daily_count):
            employee_name, department = random.choice(employee_pool)
            expense_type = random.choice(list(expense_types.keys()))
            amount_low, amount_high = expense_types[expense_type]

            expense_date = current_date - timedelta(days=random.randint(0, 8))
            submit_date = expense_date + timedelta(days=random.randint(1, 20))

            amount = round(random.uniform(amount_low, amount_high), 2)

            invoice_no = f"INV-{invoice_seq}"
            invoice_seq += 1

            row = {
                "expense_id": f"EXP-{expense_seq:05d}",
                "employee_name": employee_name,
                "department": department,
                "expense_type": expense_type,
                "amount": amount,
                "invoice_no": invoice_no,
                "expense_date": expense_date.strftime("%Y-%m-%d"),
                "submit_date": submit_date.strftime("%Y-%m-%d"),
                "is_duplicate_candidate": 0,
                "policy_limit": policy_limits[expense_type],
            }
            rows.append(row)
            expense_seq += 1

        current_date += timedelta(days=1)

    # ---------- 注入异常数据 ----------
    anomaly_rows = []

    # 1. 超限报销
    for _ in range(10):
        employee_name, department = random.choice(employee_pool)
        expense_type = random.choice(["差旅住宿", "业务招待", "办公采购"])
        policy_limit = policy_limits[expense_type]
        amount = round(policy_limit * random.uniform(1.2, 1.8), 2)

        expense_date = end_date - timedelta(days=random.randint(5, 40))
        submit_date = expense_date + timedelta(days=random.randint(2, 12))

        anomaly_rows.append(
            {
                "expense_id": f"EXP-{expense_seq:05d}",
                "employee_name": employee_name,
                "department": department,
                "expense_type": expense_type,
                "amount": amount,
                "invoice_no": f"INV-{invoice_seq}",
                "expense_date": expense_date.strftime("%Y-%m-%d"),
                "submit_date": submit_date.strftime("%Y-%m-%d"),
                "is_duplicate_candidate": 0,
                "policy_limit": policy_limit,
            }
        )
        expense_seq += 1
        invoice_seq += 1

    # 2. 重复发票号
    for _ in range(6):
        employee_name, department = random.choice(employee_pool)
        expense_type = random.choice(list(expense_types.keys()))
        amount_low, amount_high = expense_types[expense_type]
        amount = round(random.uniform(amount_low, amount_high), 2)

        shared_invoice = f"INV-DUP-{random.randint(100, 102)}"

        expense_date = end_date - timedelta(days=random.randint(3, 25))
        submit_date = expense_date + timedelta(days=random.randint(1, 10))

        anomaly_rows.append(
            {
                "expense_id": f"EXP-{expense_seq:05d}",
                "employee_name": employee_name,
                "department": department,
                "expense_type": expense_type,
                "amount": amount,
                "invoice_no": shared_invoice,
                "expense_date": expense_date.strftime("%Y-%m-%d"),
                "submit_date": submit_date.strftime("%Y-%m-%d"),
                "is_duplicate_candidate": 0,
                "policy_limit": policy_limits[expense_type],
            }
        )
        expense_seq += 1

    # 3. 疑似重复报销
    for _ in range(8):
        employee_name, department = random.choice(employee_pool)
        expense_type = random.choice(list(expense_types.keys()))
        amount_low, amount_high = expense_types[expense_type]
        amount = round(random.uniform(amount_low, amount_high), 2)

        expense_date = end_date - timedelta(days=random.randint(5, 18))
        submit_date = expense_date + timedelta(days=random.randint(1, 6))

        anomaly_rows.append(
            {
                "expense_id": f"EXP-{expense_seq:05d}",
                "employee_name": employee_name,
                "department": department,
                "expense_type": expense_type,
                "amount": amount,
                "invoice_no": f"INV-{invoice_seq}",
                "expense_date": expense_date.strftime("%Y-%m-%d"),
                "submit_date": submit_date.strftime("%Y-%m-%d"),
                "is_duplicate_candidate": 1,
                "policy_limit": policy_limits[expense_type],
            }
        )
        expense_seq += 1
        invoice_seq += 1

    # 4. 超过 60 天才提交
    for _ in range(8):
        employee_name, department = random.choice(employee_pool)
        expense_type = random.choice(list(expense_types.keys()))
        amount_low, amount_high = expense_types[expense_type]
        amount = round(random.uniform(amount_low, amount_high), 2)

        expense_date = datetime(2026, 1, random.randint(1, 20))
        submit_date = expense_date + timedelta(days=random.randint(61, 90))

        anomaly_rows.append(
            {
                "expense_id": f"EXP-{expense_seq:05d}",
                "employee_name": employee_name,
                "department": department,
                "expense_type": expense_type,
                "amount": amount,
                "invoice_no": f"INV-{invoice_seq}",
                "expense_date": expense_date.strftime("%Y-%m-%d"),
                "submit_date": submit_date.strftime("%Y-%m-%d"),
                "is_duplicate_candidate": 0,
                "policy_limit": policy_limits[expense_type],
            }
        )
        expense_seq += 1
        invoice_seq += 1

    # 5. 费用日期晚于提交日期
    for _ in range(6):
        employee_name, department = random.choice(employee_pool)
        expense_type = random.choice(list(expense_types.keys()))
        amount_low, amount_high = expense_types[expense_type]
        amount = round(random.uniform(amount_low, amount_high), 2)

        submit_date = end_date - timedelta(days=random.randint(5, 20))
        expense_date = submit_date + timedelta(days=random.randint(1, 4))

        anomaly_rows.append(
            {
                "expense_id": f"EXP-{expense_seq:05d}",
                "employee_name": employee_name,
                "department": department,
                "expense_type": expense_type,
                "amount": amount,
                "invoice_no": f"INV-{invoice_seq}",
                "expense_date": expense_date.strftime("%Y-%m-%d"),
                "submit_date": submit_date.strftime("%Y-%m-%d"),
                "is_duplicate_candidate": 0,
                "policy_limit": policy_limits[expense_type],
            }
        )
        expense_seq += 1
        invoice_seq += 1

    # 6. 缺失字段
    for _ in range(6):
        employee_name, department = random.choice(employee_pool)
        expense_type = random.choice(list(expense_types.keys()))
        amount_low, amount_high = expense_types[expense_type]
        amount = round(random.uniform(amount_low, amount_high), 2)

        expense_date = end_date - timedelta(days=random.randint(4, 16))
        submit_date = expense_date + timedelta(days=random.randint(1, 10))

        bad_case_type = random.choice(["missing_invoice", "missing_department", "missing_expense_type"])

        row = {
            "expense_id": f"EXP-{expense_seq:05d}",
            "employee_name": employee_name,
            "department": department,
            "expense_type": expense_type,
            "amount": amount,
            "invoice_no": f"INV-{invoice_seq}",
            "expense_date": expense_date.strftime("%Y-%m-%d"),
            "submit_date": submit_date.strftime("%Y-%m-%d"),
            "is_duplicate_candidate": 0,
            "policy_limit": policy_limits[expense_type],
        }

        if bad_case_type == "missing_invoice":
            row["invoice_no"] = ""
        elif bad_case_type == "missing_department":
            row["department"] = ""
        elif bad_case_type == "missing_expense_type":
            row["expense_type"] = ""

        anomaly_rows.append(row)
        expense_seq += 1
        invoice_seq += 1

    rows.extend(anomaly_rows)

    df = pd.DataFrame(rows)

    # 打乱顺序，模拟真实导出数据
    df = df.sample(frac=1, random_state=2026).reset_index(drop=True)

    # 统一排序一个副本用于可读性观察
    df.to_csv(output_path, index=False, encoding="utf-8-sig")

    print(f"Generated {len(df)} rows.")
    print(f"Saved to: {output_path.resolve()}")
    print(df.head(12).to_string(index=False))


if __name__ == "__main__":
    main()