from __future__ import annotations

import asyncio
import os

from dotenv import load_dotenv
from livekit import api


async def main() -> None:
    load_dotenv()

    for name in (
        "LIVEKIT_URL",
        "LIVEKIT_API_KEY",
        "LIVEKIT_API_SECRET",
    ):
        if not os.getenv(name, "").strip():
            raise RuntimeError(f"Missing environment variable: {name}")

    room_name = os.getenv("ROOM_NAME", "scrubsync-demo").strip()
    if not room_name:
        raise RuntimeError("ROOM_NAME cannot be empty.")

    async with api.LiveKitAPI() as client:
        dispatch = await client.agent_dispatch.create_dispatch(
            api.CreateAgentDispatchRequest(
                agent_name="scrubsync",
                room=room_name,
            )
        )

    print("Agent dispatch created.")
    print(f"Room: {room_name}")
    print("Agent name: scrubsync")
    print(dispatch)


if __name__ == "__main__":
    asyncio.run(main())