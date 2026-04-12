from typing import Any, Dict
from app.tools.base import BaseTool


class ModifyOrderTool(BaseTool):
    name = "modify_order"
    description = "Modify the shipping address of an order by order_id and new_address."

    input_schema = {
        "type": "object",
        "properties": {
            "order_id": {
                "type": "string",
                "description": "Order ID, such as 1001"
            },
            "new_address": {
                "type": "string",
                "description": "The new shipping address to update to"
            }
        },
        "required": ["order_id", "new_address"]
    }

    output_schema = {
        "type": "object",
        "properties": {
            "order_id": {"type": "string"},
            "old_address": {"type": "string"},
            "new_address": {"type": "string"},
            "message": {"type": "string"}
        }
    }

    examples = [
        {
            "input": {"order_id": "1003", "new_address": "上海市闵行区XX路88号"},
            "description": "Modify address for an unshipped order"
        }
    ]

    MOCK_ORDER_DB = {
        "1001": {"order_id": "1001", "delivery_status": "运输中", "address": "北京市朝阳区A路1号"},
        "1002": {"order_id": "1002", "delivery_status": "已签收", "address": "上海市浦东新区B路2号"},
        "1003": {"order_id": "1003", "delivery_status": "未发货", "address": "广州市天河区C路3号"},
    }

    def run(self, **kwargs) -> Dict[str, Any]:
        order_id = str(kwargs.get("order_id", "")).strip()
        new_address = str(kwargs.get("new_address", "")).strip()

        if not order_id or not new_address:
            return self.fail(
                error="Missing required parameters: order_id or new_address",
                suggestion="Please provide both order_id and new_address"
            )

        order = self.MOCK_ORDER_DB.get(order_id)
        if not order:
            return self.fail(
                error=f"Order {order_id} not found",
                suggestion="Check whether the order_id is correct"
            )

        if order["delivery_status"] != "未发货":
            return self.fail(
                error=f"Order {order_id} cannot be modified because it is already {order['delivery_status']}",
                suggestion="You may query policy via knowledge base tool"
            )

        old_address = order["address"]
        order["address"] = new_address

        return self.ok(
            data={
                "order_id": order_id,
                "old_address": old_address,
                "new_address": new_address,
                "message": "Address updated successfully"
            }
        )