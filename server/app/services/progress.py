"""In-process pub/sub for real-time agent progress, delivered to browsers over WebSockets."""

import asyncio
from collections import defaultdict
from typing import Any

from app.core.db import utcnow


class ProgressHub:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)

    def subscribe(self, project_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=200)
        self._subscribers[project_id].add(queue)
        return queue

    def unsubscribe(self, project_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers[project_id].discard(queue)
        if not self._subscribers[project_id]:
            del self._subscribers[project_id]

    async def publish(self, project_id: str, event_type: str, **data: Any) -> None:
        event = {"type": event_type, "projectId": project_id, "at": utcnow().isoformat(), **data}
        for queue in list(self._subscribers.get(project_id, ())):
            if queue.full():
                # A slow client drops its oldest event rather than blocking the pipeline.
                queue.get_nowait()
            queue.put_nowait(event)


hub = ProgressHub()
