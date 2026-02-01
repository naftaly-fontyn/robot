# messagebus.py
import uasyncio as asyncio

from utils.t_logger import get_logger
log = get_logger()



class QueueEmpty(Exception):
    pass

class QueueFull(Exception):
    pass


class Queue:
    def __init__(self, maxsize=0):
        self.maxsize = maxsize
        self._items = []
        self._get_waiters = []
        self._put_waiters = []

    def full(self):
        return self.maxsize > 0 and len(self._items) >= self.maxsize

    def empty(self):
        return len(self._items) == 0

    async def put(self, item):
        while self.full():
            event = asyncio.Event()
            self._put_waiters.append(event)
            await event.wait()

        self._items.append(item)

        # notify get waiters
        self._notify_get_waiters()

    async def get(self, timeout=None):
        if timeout is not None and timeout != 0:
            try:
                await asyncio.wait_for(self._wait_for_item(), timeout)
            except asyncio.TimeoutError:
                raise QueueEmpty("Queue get timed out")
        elif timeout is None:
            await self._wait_for_item()
        try:
            item = self._items.pop(0)
            # Notify put waiters if an item was successfully retrieved
            # This was moved from the previous diff, ensuring it's called after item retrieval.
            self._notify_put_waiters()
        except IndexError:
            raise QueueEmpty
        return item

    def get_nowait(self):
        """Return next item if available, else raise exception."""
        if self.empty():
            raise asyncio.QueueEmpty  # compatible with CPython asyncio
        return self._items.pop(0)

    def put_nowait(self, item):
        if self.full():
            raise QueueFull
        self._items.append(item)
        self._notify_get_waiters()

    async def _wait_for_item(self):
        """Internal helper to wait for an item to be available."""
        while self.empty():
            event = asyncio.Event()
            self._get_waiters.append(event)
            await event.wait()

    def _notify_get_waiters(self):
        """Internal helper to notify waiting getters."""
        if self._get_waiters:
            self._get_waiters.pop(0).set()

    def _notify_put_waiters(self):
        """Internal helper to notify waiting putters."""
        if self._put_waiters:
            self._put_waiters.pop(0).set()
# -------------------------------
# Subscriber
# -------------------------------
class Subscriber:
    """
    Each subscriber has ONE queue and can subscribe to multiple topics.
    Messages arrive as: (topic: str, sender_id: str, message: any)
    """
    def __init__(self, subscriber_id=None, topics=None, queue=None):
        self.id = f'' if subscriber_id is None else subscriber_id
#         self.queue = asyncio.Queue() if queue is None else queue
        self.queue = Queue() if queue is None else queue
        self.bus = MessageBus.instance()
        if topics and isinstance(topics, str):
            topics = [topics]
        if topics:
            for t in topics:
                self.bus.subscribe(self, t)

    def _push(self, topic, sender_id, message):
        """Internal: message injection."""
        self.queue.put_nowait((topic, sender_id, message))

    async def get(self, timeout=None):
        """Wait for next message from ANY subscribed topic."""
        ret = await self.queue.get(timeout=timeout)
        log.info('Subsider %s get: %s', self.id ,ret)
        return ret

    def get_nowait(self):
        """Get message if available, else return None."""
        if not self.queue.empty():
            return self.queue.get_nowait()
        return None

    def subscribe(self, topic: str):
        """Subscribe this subscriber to a topic."""
        self.bus.subscribe(self, topic)

    def unsubscribe(self, topic: str):
        """Unsubscribe from a single topic."""
        self.bus.unsubscribe(self, topic)

    def unsubscribe_all(self):
        """Unsubscribe from ALL topics."""
        self.bus.unsubscribe_all(self)

    def close(self):
        self.unsubscribe_all()
        del self.queue
        self.queue = None

    def __del__(self):
        self.close()



# -------------------------------
# Topic
# -------------------------------
class Topic:
    """
    Represents one named topic. Keeps a list of subscribers.
    """
    def __init__(self, name):
        self.name = name
        self.subscribers = []

    def add_subscriber(self, sub: Subscriber):
        if sub not in self.subscribers:
            self.subscribers.append(sub)

    def remove_subscriber(self, sub: Subscriber):
        """Unsubscribe a subscriber safely."""
        try:
            self.subscribers.remove(sub)
        except ValueError:
            pass

    def publish(self, sender_id, message):
        """Send a message to all subscribers."""
        for sub in self.subscribers:
            sub._push(self.name, sender_id, message)


# -------------------------------
# MessageBus (singleton)
# -------------------------------
class MessageBus:
    _instance = None

    def __init__(self):
        self.topics = {}

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_topic(self, name):
        """Return existing topic or create a new one."""
        return self.topics.setdefault(name, Topic(name))

    def subscribe(self, subscriber: Subscriber, topic: str):
        self.get_topic(topic).add_subscriber(subscriber)

    def unsubscribe(self, subscriber: Subscriber, topic: str):
        """Remove subscriber from a topic."""
        if topic in self.topics:
            self.topics[topic].remove_subscriber(subscriber)

    def unsubscribe_all(self, subscriber: Subscriber):
        for t in self.topics.values():
            t.remove_subscriber(subscriber)

    def publish(self, topic: str, sender_id=None, message=None):
        """Low-level publish (used by Publisher)."""

        t = self.get_topic(topic)
        t.publish(sender_id, message)


# -------------------------------
# Publisher
# -------------------------------
class Publisher:
    """
    A publisher has a fixed sender_id string.
    Publishes messages or events to topics.
    """
    def __init__(self, publisher_id: str):
        self.id = publisher_id
        self.bus = MessageBus.instance()

    def publish(self, topic: str, message=None):
        log.info('Publish topic:%s sender_id:%s message:%s', topic, self.id, message)
        self.bus.publish(topic, sender_id=self.id, message=message)

    def event(self, topic: str):
        """Publish an event (message=None)."""
        self.publish(topic, None)

    def close(self):
        self.bus = None

    def __del__(self):
        self.close()
