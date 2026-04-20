from pathlib import Path
from typing import Any, Dict, List

import pandas as pd

from app.tools.base import BaseTool


class DetectBusinessAnomalyTool(BaseTool):
    name = "detect_business_anomaly"
    description = (
        "Detect business anomalies from sales data by comparing recent daily averages "
        "against historical daily-average baselines across regions, product lines, "
        "or region-product-line combinations."
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
                "description": "Grouping dimension, e.g. region, product_line, or region_product_line"
            },
            "time_range": {
                "type": "string",
                "description": "Time range to inspect, e.g. last_7_days or last_30_days"
            },
            "threshold": {
                "type": "number",
                "description": "Deviation threshold ratio, e.g. 0.2 means 20% deviation from baseline"
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
            "threshold": {"type": "number"},
            "anomaly_count": {"type": "integer"},
            "anomalies": {
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
                "time_range": "last_30_days",
                "threshold": 0.2
            },
            "description": "Detect regional sales amount anomalies over the last 30 days"
        },
        {
            "input": {
                "metric": "quantity",
                "group_by": "product_line",
                "time_range": "last_7_days",
                "threshold": 0.2
            },
            "description": "Detect product-line sales quantity anomalies over the last 7 days"
        },
        {
            "input": {
                "metric": "quantity",
                "group_by": "region_product_line",
                "time_range": "last_7_days",
                "threshold": 0.2
            },
            "description": "Detect anomalies on region-product-line combinations over the last 7 days"
        }
    ]

    ALLOWED_METRICS = {"sales_amount", "quantity"}
    ALLOWED_GROUPS = {"region", "product_line", "region_product_line"}
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
            df["quantity"] = pd.to_numeric(df["quantity"], errors="coerce").fillna(0.0)

        if "region" not in df.columns or "product_line" not in df.columns:
            raise ValueError("sales_data.csv must contain columns: region and product_line")

        df["region_product_line"] = (
            df["region"].astype(str).str.strip() + "-" + df["product_line"].astype(str).str.strip()
        )

        return df

    def _time_windows(self, df: pd.DataFrame, time_range: str) -> tuple[pd.Timestamp, pd.Timestamp, pd.Timestamp, int, int]:
        max_date = df["order_date"].max()

        if time_range == "last_7_days":
            recent_days = 7
            baseline_days = 21
        else:
            recent_days = 30
            baseline_days = 60

        recent_start = max_date - pd.Timedelta(days=recent_days - 1)
        baseline_start = recent_start - pd.Timedelta(days=baseline_days)

        return max_date, recent_start, baseline_start, recent_days, baseline_days

    def _severity(self, deviation_ratio: float) -> str:
        abs_ratio = abs(deviation_ratio)
        if abs_ratio >= 0.5:
            return "high"
        if abs_ratio >= 0.3:
            return "medium"
        return "low"

    def _build_suggested_action(self, group: str, direction: str, severity: str, group_by: str) -> str:
        if group_by == "region":
            target_label = "区域"
        elif group_by == "product_line":
            target_label = "产品线"
        else:
            target_label = "区域-产品线组合"

        if direction == "down":
            if severity == "high":
                return f"建议优先核查{target_label}{group}的促销变化、重点客户采购波动、库存状态和业务跟进节奏。"
            if severity == "medium":
                return f"建议关注{target_label}{group}近期订单变化，并结合库存与客户采购情况做进一步排查。"
            return f"建议持续观察{target_label}{group}的后续走势。"

        if severity == "high":
            return f"建议确认{target_label}{group}是否受活动拉动、短期集中采购或补货影响，避免误判为持续增长。"
        if severity == "medium":
            return f"建议复核{target_label}{group}增长原因，判断是否具有持续性。"
        return f"建议记录{target_label}{group}的增长变化并持续观察。"

    def _group_label(self, group_by: str) -> str:
        if group_by == "region":
            return "区域"
        if group_by == "product_line":
            return "产品线"
        return "区域-产品线组合"

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
        threshold = self.to_float(kwargs.get("threshold", 0.2), default=0.2)

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

        if threshold <= 0:
            return self.fail(
                error="threshold must be greater than 0",
                suggestion="Use a positive threshold such as 0.2 or 0.3"
            )

        try:
            df = self._load_data()
        except Exception as e:
            return self.fail(
                error=f"Failed to load sales data: {str(e)}",
                suggestion="Check whether app/data/sales_data.csv exists and has valid columns"
            )

        if df.empty:
            return self.fail(
                error="Sales dataset is empty",
                suggestion="Please provide a non-empty sales_data.csv file"
            )

        if group_by not in df.columns:
            return self.fail(
                error=f"Column not found for grouping: {group_by}",
                suggestion=f"Make sure sales_data.csv contains column: {group_by}"
            )

        max_date, recent_start, baseline_start, recent_days, baseline_days = self._time_windows(df, time_range)

        recent_df = df[df["order_date"] >= recent_start].copy()
        baseline_df = df[(df["order_date"] >= baseline_start) & (df["order_date"] < recent_start)].copy()

        if recent_df.empty:
            return self.fail(
                error="No recent data found for anomaly detection",
                suggestion="Try checking whether sales_data.csv contains recent records"
            )

        if baseline_df.empty:
            return self.fail(
                error="No historical baseline data found for anomaly detection",
                suggestion="Provide a longer history window in sales_data.csv"
            )

        recent_daily = (
            recent_df.groupby(["order_date", group_by], dropna=False)[metric]
            .sum()
            .reset_index()
        )

        baseline_daily = (
            baseline_df.groupby(["order_date", group_by], dropna=False)[metric]
            .sum()
            .reset_index()
        )

        recent_stats = (
            recent_daily.groupby(group_by, dropna=False)[metric]
            .mean()
            .reset_index()
            .rename(columns={metric: "recent_daily_avg"})
        )

        baseline_stats = (
            baseline_daily.groupby(group_by, dropna=False)[metric]
            .mean()
            .reset_index()
            .rename(columns={metric: "baseline_daily_avg"})
        )

        recent_total = (
            recent_df.groupby(group_by, dropna=False)[metric]
            .sum()
            .reset_index()
            .rename(columns={metric: "recent_total"})
        )

        merged = (
            recent_stats.merge(baseline_stats, on=group_by, how="left")
            .merge(recent_total, on=group_by, how="left")
            .fillna({"baseline_daily_avg": 0.0, "recent_total": 0.0})
        )

        anomalies: List[Dict[str, Any]] = []

        for _, row in merged.iterrows():
            group_value = row[group_by]
            recent_daily_avg = float(row["recent_daily_avg"])
            baseline_daily_avg = float(row["baseline_daily_avg"])
            recent_total_value = float(row["recent_total"])

            if baseline_daily_avg <= 0:
                continue

            deviation_ratio = (recent_daily_avg - baseline_daily_avg) / baseline_daily_avg

            if abs(deviation_ratio) >= threshold:
                direction = "up" if deviation_ratio > 0 else "down"
                severity = self._severity(deviation_ratio)

                anomalies.append(
                    {
                        "group": str(group_value),
                        "current_value": round(recent_total_value, 2),
                        "recent_daily_avg": round(recent_daily_avg, 2),
                        "baseline_daily_avg": round(baseline_daily_avg, 2),
                        "deviation_ratio": round(deviation_ratio, 4),
                        "direction": direction,
                        "severity": severity,
                        "metric": metric,
                        "suggested_action": self._build_suggested_action(
                            group=str(group_value),
                            direction=direction,
                            severity=severity,
                            group_by=group_by,
                        ),
                    }
                )

        severity_rank = {"high": 3, "medium": 2, "low": 1}
        anomalies = sorted(
            anomalies,
            key=lambda x: (severity_rank.get(x["severity"], 0), abs(x["deviation_ratio"])),
            reverse=True,
        )

        anomaly_count = len(anomalies)
        group_text = self._group_label(group_by)
        metric_text = "销售额" if metric == "sales_amount" else "销量"

        if anomaly_count == 0:
            summary = (
                f"已完成异常检测。在 {time_range} 范围内，按{group_text}统计的{metric_text}未发现超过 "
                f"{round(threshold * 100, 1)}% 阈值的明显异常。"
            )
        else:
            top_anomaly = anomalies[0]
            summary = (
                f"已完成异常检测，共识别出 {anomaly_count} 个异常对象。"
                f"当前最值得关注的是 {top_anomaly['group']}，其近端日均{metric_text}"
                f"相对历史基线{'上升' if top_anomaly['direction'] == 'up' else '下降'}了 "
                f"{round(abs(top_anomaly['deviation_ratio']) * 100, 1)}%，"
                f"严重程度为 {top_anomaly['severity']}。"
            )

        result = {
            "summary": summary,
            "metric": metric,
            "group_by": group_by,
            "time_range": time_range,
            "threshold": threshold,
            "reference_end_date": str(max_date.date()),
            "recent_window_days": recent_days,
            "baseline_window_days": baseline_days,
            "anomaly_count": anomaly_count,
            "anomalies": anomalies,
        }

        return self.ok(data=result, summary=summary)