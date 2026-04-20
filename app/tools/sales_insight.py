from pathlib import Path
from typing import Any, Dict

import pandas as pd

from app.tools.base import BaseTool


class SalesInsightTool(BaseTool):
    name = "query_sales_insight"
    description = (
        "Analyze sales data by metric, group dimension, and time range. "
        "Supports regional and product-line level aggregation."
    )

    input_schema = {
        "type": "object",
        "properties": {
            "metric": {
                "type": "string",
                "description": "Metric to analyze, e.g. sales_amount or quantity"
            },
            "group_by": {
                "type": "string",
                "description": "Grouping dimension, e.g. region or product_line"
            },
            "time_range": {
                "type": "string",
                "description": "Time range, e.g. last_7_days or last_30_days"
            },
            "dimension_filter": {
                "type": "object",
                "description": "Optional filters, e.g. {'product_line': '骨科'}"
            }
        },
        "required": ["metric", "group_by", "time_range"]
    }

    output_schema = {
        "type": "object",
        "properties": {
            "summary": {"type": "string"},
            "metric": {"type": "string"},
            "group_by": {"type": "string"},
            "time_range": {"type": "string"},
            "row_count": {"type": "integer"},
            "top_groups": {
                "type": "array",
                "items": {"type": "object"}
            }
        }
    }

    examples = [
        {
            "input": {
                "metric": "sales_amount",
                "group_by": "region",
                "time_range": "last_30_days"
            },
            "description": "Analyze regional sales amount in the last 30 days"
        },
        {
            "input": {
                "metric": "quantity",
                "group_by": "product_line",
                "time_range": "last_7_days",
                "dimension_filter": {"region": "西南"}
            },
            "description": "Analyze product-line sales quantity in the last 7 days for Southwest region"
        }
    ]

    ALLOWED_METRICS = {"sales_amount", "quantity"}
    ALLOWED_GROUPS = {"region", "product_line"}
    ALLOWED_TIME_RANGES = {"last_7_days", "last_30_days"}

    def __init__(self) -> None:
        self.data_path = Path("app/data/sales_data.csv")

    def _load_data(self) -> pd.DataFrame:
        if not self.data_path.exists():
            raise FileNotFoundError(f"sales data file not found: {self.data_path}")

        df = pd.read_csv(self.data_path)
        if "order_date" not in df.columns:
            raise ValueError("sales_data.csv must contain column: order_date")

        df["order_date"] = pd.to_datetime(df["order_date"], errors="coerce")
        df = df.dropna(subset=["order_date"]).copy()

        if "sales_amount" in df.columns:
            df["sales_amount"] = pd.to_numeric(df["sales_amount"], errors="coerce").fillna(0.0)

        if "quantity" in df.columns:
            df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0)

        return df

    def _apply_time_range(self, df: pd.DataFrame, time_range: str) -> pd.DataFrame:
        if df.empty:
            return df

        max_date = df["order_date"].max()
        if pd.isna(max_date):
            return df.iloc[0:0].copy()

        if time_range == "last_7_days":
            start_date = max_date - pd.Timedelta(days=6)
        else:
            start_date = max_date - pd.Timedelta(days=29)

        return df[df["order_date"] >= start_date].copy()

    def _apply_dimension_filter(self, df: pd.DataFrame, dimension_filter: Dict[str, Any]) -> pd.DataFrame:
        filtered = df.copy()
        for key, value in dimension_filter.items():
            if key in filtered.columns and value not in (None, "", []):
                filtered = filtered[filtered[key].astype(str) == str(value)]
        return filtered

    def run(self, **kwargs) -> Dict[str, Any]:
        payload = {
            "metric": kwargs.get("metric"),
            "group_by": kwargs.get("group_by"),
            "time_range": kwargs.get("time_range"),
        }
        missing = self.require_fields(payload, ["metric", "group_by", "time_range"])
        if missing:
            return missing

        metric = str(kwargs.get("metric", "")).strip()
        group_by = str(kwargs.get("group_by", "")).strip()
        time_range = str(kwargs.get("time_range", "")).strip()
        dimension_filter = kwargs.get("dimension_filter") or {}

        if metric not in self.ALLOWED_METRICS:
            return self.fail(
                error=f"Unsupported metric: {metric}",
                suggestion=f"Use one of: {', '.join(sorted(self.ALLOWED_METRICS))}"
            )

        if group_by not in self.ALLOWED_GROUPS:
            return self.fail(
                error=f"Unsupported group_by: {group_by}",
                suggestion=f"Use one of: {', '.join(sorted(self.ALLOWED_GROUPS))}"
            )

        if time_range not in self.ALLOWED_TIME_RANGES:
            return self.fail(
                error=f"Unsupported time_range: {time_range}",
                suggestion=f"Use one of: {', '.join(sorted(self.ALLOWED_TIME_RANGES))}"
            )

        if not isinstance(dimension_filter, dict):
            return self.fail(
                error="dimension_filter must be an object",
                suggestion="Pass dimension_filter as a JSON object, e.g. {'region': '西南'}"
            )

        try:
            df = self._load_data()
        except Exception as e:
            return self.fail(
                error=f"Failed to load sales data: {str(e)}",
                suggestion="Check whether app/data/sales_data.csv exists and has valid columns"
            )

        df = self._apply_time_range(df, time_range)
        df = self._apply_dimension_filter(df, dimension_filter)

        if df.empty:
            return self.fail(
                error="No sales data matched the given conditions",
                suggestion="Try a wider time range or remove some filters"
            )

        if group_by not in df.columns:
            return self.fail(
                error=f"Column not found for grouping: {group_by}",
                suggestion=f"Make sure sales_data.csv contains column: {group_by}"
            )

        grouped = (
            df.groupby(group_by, dropna=False)[metric]
            .sum()
            .reset_index()
            .sort_values(metric, ascending=False)
        )

        row_count = int(len(df))
        top_groups = grouped.head(5).to_dict(orient="records")

        top_group_name = str(top_groups[0][group_by]) if top_groups else "N/A"
        top_group_value = top_groups[0][metric] if top_groups else 0

        if metric == "sales_amount":
            metric_text = "销售额"
        else:
            metric_text = "销量"

        if group_by == "region":
            group_text = "区域"
        else:
            group_text = "产品线"

        summary = (
            f"已完成销售分析。在 {time_range} 范围内，按{group_text}统计的{metric_text}中，"
            f"表现最高的是 {top_group_name}，数值为 {top_group_value}。"
            f"当前共有 {row_count} 条记录参与分析。"
        )

        result = {
            "summary": summary,
            "metric": metric,
            "group_by": group_by,
            "time_range": time_range,
            "row_count": row_count,
            "top_groups": top_groups,
            "applied_filter": dimension_filter,
        }

        return self.ok(data=result, summary=summary)