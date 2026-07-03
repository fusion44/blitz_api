"""
Regression test: the channel listener must release its Redis resources.

listen() only called pubsub.unsubscribe() in its finally block; it never
closed the pubsub connection or the listener's own Redis client, leaking one
connection per install/uninstall and per app-status listener recreation.
"""

from app.api.channel import BaseChannelListener


class _FakePubSub:
    def __init__(self, on_poll):
        self._on_poll = on_poll
        self.aclosed = False

    async def subscribe(self, channel):
        pass

    async def get_message(self, **kwargs):
        self._on_poll()
        return None

    async def unsubscribe(self):
        pass

    async def aclose(self):
        self.aclosed = True


class _FakeRedis:
    def __init__(self, pubsub):
        self._pubsub = pubsub
        self.aclosed = False

    def pubsub(self):
        return self._pubsub

    async def aclose(self):
        self.aclosed = True


async def test_listen_closes_pubsub_and_redis():
    listener = BaseChannelListener("test-channel")

    # stop the listen loop after the first poll
    pubsub = _FakePubSub(on_poll=lambda: setattr(listener, "running", False))
    redis = _FakeRedis(pubsub)
    listener.redis = redis

    await listener.listen()

    assert pubsub.aclosed is True, "pubsub connection must be closed"
    assert redis.aclosed is True, "listener's redis client must be closed"
