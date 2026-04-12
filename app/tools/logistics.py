from typing import Any, Dict
from app.tools.base import BaseTool


class QueryLogisticsTool(BaseTool):
    name = "query_logistics"
    description = "Query logistics status and tracking number by order_id."

    input_schema = {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "Order ID, such as 1001"
            }
        },
        "required": ["order_id"]
    }

    output_schema = {
        "type": "object",
        "properties": {
            "order_id": {"type": "string"},
            "status": {"type": "string"},
            "tracking_no": {"type": "string"}
        }
    }

    examples = [
        {
            "input": {"order_id": "1001"},
            "description": "Query current logistics info of an order"
        }
    ]

    MOCK_LOGISTICS_DB = {
        "1001": {"order_id": "1001", "status": "运输中", "tracking_no": "SF123456"},
        "1002": {"order_id": "1002", "status": "已签收", "tracking_no": "YD888999"},
        "1003": {"order_id": "1003", "status": "已出库", "tracking_no": "ZT555666"},
    }

    def run(self, **kwargs) -> Dict[str, Any]:
        order_id = str(kwargs.get("order_id", "")).strip()
        if not order_id:
            return self.fail(
                error="Missing required parameter: order_id",
                suggestion="Please provide a valid order_id"
            )

        order = self.MOCK_LOGISTICS_DB.get(order_id)
        if not order:
            return self.fail(
                error=f"Order {order_id} not found in logistics system",
                suggestion="Check whether the order_id is correct"
            )

        return self.ok(data=order)