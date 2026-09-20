"""Demonstrate retry-safe stock receipt, reservation and release on example 09.

This writes demo inventory and an audit trail. Use a test instance.
"""
import asyncio
import os
import uuid
from connection import session, json_result


async def main():
    async with session(os.getenv("MCP_URL", "http://localhost:8109/mcp")) as client:
        async def call(name, args):
            result = await client.call_tool(name, args)
            if result.isError:
                raise RuntimeError(result.content)
            return json_result(result)

        key = uuid.uuid4().hex
        sku = "DEMO-" + key[:12].upper()
        await call("receive_stock", {"request_key": key + "-receive", "sku": sku, "quantity": 10})
        args = {"request_key": key + "-reserve", "items": [{"sku": sku, "quantity": 3}]}
        first = await call("reserve_stock", args)
        retry = await call("reserve_stock", args)
        assert first["id"] == retry["id"]
        print("Retried request returned the same reservation:", retry["id"])
        print(await call("settle_reservation", {"request_key": key + "-release", "reservation_id": first["id"], "action": "release"}))


if __name__ == "__main__":
    asyncio.run(main())
