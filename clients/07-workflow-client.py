"""Create a DAG, observe a failure, retry and inspect durable results.

Start example 08 with MCP_AUTH_TOKEN; use the same token for this client.
"""
import asyncio
import os
import uuid
from connection import session, json_result


async def main():
    async with session(os.getenv("MCP_URL", "http://localhost:8108/mcp")) as client:
        async def call(name, args):
            response = await client.call_tool(name, args)
            if response.isError:
                raise RuntimeError(response.content)
            return json_result(response)

        job = await call("create_workflow", {
            "request_key": uuid.uuid4().hex, "values": [-2, 1, 3, 3],
            "steps": [
                {"name": "positive", "operation": "positive"},
                {"name": "unique", "operation": "unique", "depends_on": ["positive"]},
                {"name": "retry", "operation": "fail_once", "depends_on": ["unique"]},
                {"name": "total", "operation": "sum", "depends_on": ["retry"]},
            ],
        })
        args = {"workflow_id": job["id"]}
        print("First run:", (await call("run_workflow", args))["state"])
        await call("retry_workflow", args)
        result = await call("run_workflow", args)
        print("After retry:", result["state"])
        for step in result["steps"]:
            print(step["name"], "attempts:", step["attempts"], "output:", step["output"])


if __name__ == "__main__":
    asyncio.run(main())
