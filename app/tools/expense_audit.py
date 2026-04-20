from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from app.tools.base import BaseTool


class ExpenseAuditTool(BaseTool):
    name = "audit_expense"
    description = (
        "Audit expense records and flag suspicious items such as amount limit violations, "
        "duplicate invoices, missing fields, and abnormal dates."
    )

    input_schema = {
        "type": "object",
        "properties": {
            "top_k": {
                "type": "integer",
                "description": "Maximum number of flagged records to return"
            }
        },
        "required": []
    }

    output_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "total_records": {"type": "integer"},
            "flagged_count": {"type": "integer"},
            "flagged_items": {
                "type": "array",
                "items": {"type": "object"}
            }
        }
    }

    examples = [
        {
            "input": {"top_k": 10},
            "description": "Audit the latest batch of expense records and return top suspicious items"
        }
    ]

    REQUIRED_COLUMNS = {
        "expense_id",
        "employee_name",
        "department",
        "expense_type",
        "amount",
        "invoice_no",
        "expense_date",
        "submit_date",
        "is_duplicate_candidate",
        "policy_limit",
    }

    def __init__(self) -> None:
        self.data_path = Path("app/data/expense_data.csv")

    def _load_data(self) -> pd.DataFrame:
        if not self.data_path.exists():
            raise FileNotFoundError(f"expense data file not found: {self.data_path}")

        df = pd.read_csv(self.data_path)

        missing_cols = self.REQUIRED_COLUMNS - set(df.columns)
        if missing_cols:
            raise ValueError(
                f"expense_data.csv is missing required columns: {', '.join(sorted(missing_cols))}"
            )

        df["amount"] = pd.to_numeric(df["amount"], errors="coerce").fillna(0.0)
        df["policy_limit"] = pd.to_numeric(df["policy_limit"], errors="coerce").fillna(0.0)
        df["expense_date"] = pd.to_datetime(df["expense_date"], errors="coerce")
        df["submit_date"] = pd.to_datetime(df["submit_date"], errors="coerce")

        df["invoice_no"] = df["invoice_no"].astype(str).fillna("")
        df["employee_name"] = df["employee_name"].astype(str).fillna("")
        df["department"] = df["department"].astype(str).fillna("")
        df["expense_type"] = df["expense_type"].astype(str).fillna("")
        df["expense_id"] = df["expense_id"].astype(str).fillna("")
        df["is_duplicate_candidate"] = (
            df["is_duplicate_candidate"]
            .astype(str)
            .str.lower()
            .isin(["1", "true", "yes", "y"])
        )

        return df

    def _build_issue_list(self, row: pd.Series, duplicate_invoice_set: set) -> List[str]:
        issues: List[str] = []

        if not str(row.get("employee_name", "")).strip():
            issues.append("missing_employee_name")

        if not str(row.get("department", "")).strip():
            issues.append("missing_department")

        if not str(row.get("expense_type", "")).strip():
            issues.append("missing_expense_type")

        if not str(row.get("invoice_no", "")).strip() or str(row.get("invoice_no", "")).strip().lower() == "nan":
            issues.append("missing_invoice_no")

        amount = float(row.get("amount", 0.0))
        policy_limit = float(row.get("policy_limit", 0.0))

        if amount > policy_limit and policy_limit > 0:
            issues.append("amount_exceeds_policy_limit")

        invoice_no = str(row.get("invoice_no", "")).strip()
        if invoice_no and invoice_no in duplicate_invoice_set:
            issues.append("duplicate_invoice_no")

        if bool(row.get("is_duplicate_candidate", False)):
            issues.append("duplicate_claim_candidate")

        expense_date = row.get("expense_date")
        submit_date = row.get("submit_date")

        if pd.isna(expense_date):
            issues.append("invalid_expense_date")

        if pd.isna(submit_date):
            issues.append("invalid_submit_date")

        if not pd.isna(expense_date) and not pd.isna(submit_date):
            if expense_date > submit_date:
                issues.append("expense_date_after_submit_date")

            days_gap = (submit_date - expense_date).days
            if days_gap > 60:
                issues.append("late_submission_over_60_days")

        return issues

    def _risk_level(self, issues: List[str]) -> str:
        if len(issues) >= 3:
            return "high"
        if len(issues) == 2:
            return "medium"
        if len(issues) == 1:
            return "low"
        return "none"

    def run(self, **kwargs) -> Dict[str, Any]:
        top_k = self.to_int(kwargs.get("top_k"), default=10)
        if top_k <= 0:
            top_k = 10

        try:
            df = self._load_data()
        except Exception as e:
            return self.fail(
                error=f"Failed to load expense data: {str(e)}",
                suggestion="Check whether app/data/expense_data.csv exists and contains valid columns"
            )

        if df.empty:
            return self.fail(
                error="Expense dataset is empty",
                suggestion="Please provide a non-empty expense_data.csv file"
            )

        invoice_counts = (
            df["invoice_no"]
            .astype(str)
            .str.strip()
            .value_counts()
            .to_dict()
        )
        duplicate_invoice_set = {
            invoice_no
            for invoice_no, count in invoice_counts.items()
            if invoice_no and invoice_no.lower() != "nan" and count > 1
        }

        flagged_items: List[Dict[str, Any]] = []

        for _, row in df.iterrows():
            issues = self._build_issue_list(row, duplicate_invoice_set)
            if not issues:
                continue

            item = {
                "expense_id": str(row.get("expense_id", "")).strip(),
                "employee_name": str(row.get("employee_name", "")).strip(),
                "department": str(row.get("department", "")).strip(),
                "expense_type": str(row.get("expense_type", "")).strip(),
                "amount": float(row.get("amount", 0.0)),
                "invoice_no": str(row.get("invoice_no", "")).strip(),
                "issue_list": issues,
                "risk_level": self._risk_level(issues),
            }
            flagged_items.append(item)

        risk_rank = {"high": 3, "medium": 2, "low": 1, "none": 0}
        flagged_items = sorted(
            flagged_items,
            key=lambda x: (risk_rank.get(x["risk_level"], 0), len(x["issue_list"])),
            reverse=True,
        )

        limited_items = flagged_items[:top_k]

        total_records = int(len(df))
        flagged_count = int(len(flagged_items))
        high_risk_count = sum(1 for item in flagged_items if item["risk_level"] == "high")

        if flagged_count == 0:
            summary = (
                f"已完成报销审核，共检查 {total_records} 条记录，未发现明显异常。"
            )
        else:
            summary = (
                f"已完成报销审核，共检查 {total_records} 条记录，识别出 {flagged_count} 条疑似异常记录，"
                f"其中高风险 {high_risk_count} 条。当前返回前 {len(limited_items)} 条供人工复核。"
            )

        result = {
            "summary": summary,
            "total_records": total_records,
            "flagged_count": flagged_count,
            "flagged_items": limited_items,
        }

        return self.ok(data=result, summary=summary)