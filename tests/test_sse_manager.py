"""
Regression test: SSEManager must not touch the event loop at import time.

setup() ran at module import via asyncio.get_event_loop(), which is
deprecated without a running loop and breaks when the module is imported
outside a running loop (e.g. in a Celery worker). The broadcast consumer
must instead start lazily, the first time it's needed from within a loop.
"""


async def test_broadcast_task_starts_lazily_within_a_loop():
    from app.api.sse_manager import SSEManager

    mgr = SSEManager()
    assert mgr._broadcast_task is None, "must not start a task before it's needed"

    mgr._ensure_broadcast_task()
    assert mgr._broadcast_task is not None, "task should start within a running loop"

    # a second call must not spawn another task
    first = mgr._broadcast_task
    mgr._ensure_broadcast_task()
    assert mgr._broadcast_task is first

    mgr._broadcast_task.cancel()
