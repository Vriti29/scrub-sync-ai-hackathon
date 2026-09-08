from __future__ import annotations

import hmac
import logging
import os
import time
import uuid
from collections import defaultdict, deque
from datetime import timedelta

from aiohttp import web
from dotenv import load_dotenv
from livekit import api

load_dotenv()
log = logging.getLogger("scrubsync.tokens")


def required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"Missing environment variable: {name}")
    return value


def create_app() -> web.Application:
    api_key = required("LIVEKIT_API_KEY")
    api_secret = required("LIVEKIT_API_SECRET")
    livekit_url = required("LIVEKIT_URL")
    access_secret = required("TERMINAL_ACCESS_SECRET")
    origin = os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")
    room = os.getenv("ROOM_NAME", "scrubsync-demo")
    if len(access_secret) < 24:
        raise RuntimeError("TERMINAL_ACCESS_SECRET must contain at least 24 characters.")

    attempts: dict[str, deque[float]] = defaultdict(deque)

    @web.middleware
    async def cors_and_errors(request: web.Request, handler):
        request_origin = request.headers.get("Origin")
        if request_origin is not None and request_origin != origin:
            return web.json_response({"error": "Origin not allowed"}, status=403)
        try:
            response = await handler(request)
        except web.HTTPException as exc:
            response = web.json_response({"error": exc.reason}, status=exc.status)
        except Exception:
            log.exception("Token endpoint failure")
            response = web.json_response({"error": "Internal server error"}, status=500)

        response.headers["Cache-Control"] = "no-store"
        if request_origin == origin:
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"
            response.headers["Access-Control-Allow-Headers"] = "Authorization, Content-Type"
            response.headers["Access-Control-Allow-Methods"] = "POST, OPTIONS"
        return response

    async def preflight(request: web.Request) -> web.Response:
        return web.Response(status=204)

    async def ensure_agent_dispatch() -> None:
        """
        Explicit agent_name workers do not auto-join rooms.
        Each arm must dispatch a fresh job; clear the prior room so a stale
        agent from a previous session cannot stack with the new one.
        """
        async with api.LiveKitAPI(
            url=livekit_url,
            api_key=api_key,
            api_secret=api_secret,
        ) as client:
            try:
                await client.room.delete_room(api.DeleteRoomRequest(room=room))
            except Exception:
                log.info("Room %s was not present before arming", room)
            dispatch = await client.agent_dispatch.create_dispatch(
                api.CreateAgentDispatchRequest(
                    agent_name="scrubsync",
                    room=room,
                )
            )
            log.info(
                "Dispatched scrubsync to %s (%s)",
                room,
                getattr(dispatch, "id", dispatch),
            )

    async def token(request: web.Request) -> web.Response:
        remote = request.remote or "unknown"
        now = time.monotonic()
        # Bound the in-memory limiter. Use a shared gateway limiter in deployment.
        if len(attempts) > 4096:
            for key in list(attempts):
                if not attempts[key] or now - attempts[key][-1] > 60:
                    del attempts[key]
        bucket = attempts[remote]
        while bucket and now - bucket[0] > 60:
            bucket.popleft()
        if len(bucket) >= 10:
            raise web.HTTPTooManyRequests(reason="Too many provisioning requests")
        bucket.append(now)

        supplied = request.headers.get("Authorization", "")
        expected = f"Bearer {access_secret}"
        if not hmac.compare_digest(supplied, expected):
            raise web.HTTPUnauthorized(reason="Invalid terminal access secret")

        await ensure_agent_dispatch()

        identity = f"terminal-{uuid.uuid4().hex}"
        jwt = (
            api.AccessToken(api_key, api_secret)
            .with_identity(identity)
            .with_name("Sterile-field demonstration terminal")
            .with_ttl(timedelta(minutes=15))
            .with_grants(
                api.VideoGrants(
                    room_join=True,
                    room=room,
                    can_publish=True,
                    can_subscribe=True,
                    can_publish_data=True,
                )
            )
            .to_jwt()
        )
        return web.json_response(
            {"token": jwt, "url": livekit_url, "room": room, "identity": identity}
        )

    app = web.Application(
        middlewares=[cors_and_errors],
        client_max_size=4096,
    )
    app.router.add_route("OPTIONS", "/token", preflight)
    app.router.add_post("/token", token)
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    web.run_app(
        create_app(),
        host=os.getenv("TOKEN_HOST", "127.0.0.1"),
        port=int(os.getenv("TOKEN_PORT", "8080")),
    )
