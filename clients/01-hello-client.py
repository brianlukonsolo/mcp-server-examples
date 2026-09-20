"""Start 01-hello-world/server.py separately, then run this remote client."""
import asyncio
import os
from connection import session


async def main():
    async with session(os.getenv("MCP_URL", "http://localhost:8101/mcp")) as client:
        print("Tools:", ", ".join(t.name for t in (await client.list_tools()).tools))
        for name, args in [("say_hello", {"name": "Brian"}), ("add", {"a": 2.5, "b": 4})]:
            result = await client.call_tool(name, args)
            if result.isError:
                raise RuntimeError(result.content)
            print(name, "->", result.content)


if __name__ == "__main__":
    asyncio.run(main())
