import json

from app.manager import ConnectionManager

ORDER_EVENT = {"type": "order", "order_id": "abc-123", "status": "CONFIRMED"}
OTHER_ORDER_EVENT = {"type": "order", "order_id": "zzz-999", "status": "PENDING"}
STOCK_EVENT = {"type": "stock", "warehouse": "LDN", "changes": []}


def drain(client) -> list[dict]:
    messages = []
    while not client.queue.empty():
        messages.append(json.loads(client.queue.get_nowait()))
    return messages


def test_register_and_unregister():
    manager = ConnectionManager()
    client = manager.register()
    assert manager.client_count == 1
    manager.unregister(client)
    assert manager.client_count == 0
    manager.unregister(client)  # idempotent


def test_firehose_client_receives_everything():
    manager = ConnectionManager()
    client = manager.register()
    manager.broadcast(ORDER_EVENT)
    manager.broadcast(STOCK_EVENT)
    assert drain(client) == [ORDER_EVENT, STOCK_EVENT]


def test_filtered_client_receives_only_its_order():
    manager = ConnectionManager()
    client = manager.register(order_filter="abc-123")
    manager.broadcast(ORDER_EVENT)
    manager.broadcast(OTHER_ORDER_EVENT)
    manager.broadcast(STOCK_EVENT)
    assert drain(client) == [ORDER_EVENT]


def test_slow_consumer_sheds_oldest_not_newest():
    manager = ConnectionManager(queue_size=3)
    client = manager.register()
    for index in range(5):
        manager.broadcast({"type": "stock", "seq": index})

    received = drain(client)
    assert [message["seq"] for message in received] == [2, 3, 4]
    assert client.dropped == 2
    assert manager.total_dropped == 2


def test_one_slow_client_does_not_affect_others():
    manager = ConnectionManager(queue_size=2)
    slow = manager.register()
    fast = manager.register()
    for index in range(4):
        manager.broadcast({"type": "stock", "seq": index})
    drain(fast)  # fast client drains everything...
    manager.broadcast({"type": "stock", "seq": 99})

    assert [m["seq"] for m in drain(fast)] == [99]
    assert [m["seq"] for m in drain(slow)] == [3, 99]  # oldest shed, newest kept
