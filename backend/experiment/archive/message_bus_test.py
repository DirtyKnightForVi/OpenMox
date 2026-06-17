"""Experiment: OpenMoxMessageBus — inbox push/drain + wakeup queue + replay log.

Run: cd backend && .venv/bin/python experiment/message_bus_test.py
"""

import asyncio
import os
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR / "agentscope" / "src"))
sys.path.insert(0, str(BACKEND_DIR))
os.chdir(str(BACKEND_DIR))


async def main():
    results = []
    def ck(name, ok):
        results.append((name, "✅" if ok else "❌"))

    # ── Setup: in-memory DB ────────────────────────
    import src.core.store as store_mod
    store_mod._db = None
    await store_mod.get_db(":memory:")

    from src.core.openmox_message_bus import OpenMoxMessageBus

    async with OpenMoxMessageBus() as bus:
        # ── T1: inbox_push + inbox_drain ────────────
        try:
            sid = "test_session_1"
            eid = await bus.inbox_push(sid, {"msg": "hello from momo"})
            assert eid, "entry_id should not be empty"

            # Drain should return it
            drained = await bus.inbox_drain(sid, max_count=10)
            assert len(drained) == 1, f"expected 1, got {len(drained)}"
            assert drained[0][1]["msg"] == "hello from momo"
            print(f"  ✅ inbox_push → drain: 1 message round-tripped")

            # Second drain should be empty
            drained2 = await bus.inbox_drain(sid, max_count=10)
            assert len(drained2) == 0
            print(f"  ✅ second drain empty")
            ck("inbox", True)
        except Exception as e:
            print(f"  ❌ inbox: {e}")
            ck("inbox", False)

        # ── T2: enqueue_wakeup + dequeue_wakeups ─────
        try:
            await bus.enqueue_wakeup("user1", "session_a", "agent_pd")
            await bus.enqueue_wakeup("user1", "session_b", "agent_dev")

            entries = await bus.dequeue_wakeups(max_count=64)
            assert len(entries) >= 2, f"expected >=2 wakeups, got {len(entries)}"
            pd_entry = [e for e in entries if e["session_id"] == "session_a"]
            assert len(pd_entry) == 1
            assert pd_entry[0]["agent_id"] == "agent_pd"
            print(f"  ✅ enqueue_wakeup → dequeue: {len(entries)} entries")
            ck("wakeup", True)
        except Exception as e:
            print(f"  ❌ wakeup: {e}")
            ck("wakeup", False)

        # ── T3: session_publish_event + log_read ─────
        try:
            eid = await bus.session_publish_event("session_a", {"type": "TEXT_BLOCK_DELTA", "delta": "hello"})
            assert eid, "entry_id should not be empty"

            events = await bus.session_read_events("session_a")
            assert len(events) >= 1
            assert events[0][1]["type"] == "TEXT_BLOCK_DELTA"
            assert events[0][1]["delta"] == "hello"
            print(f"  ✅ session_publish_event → read: 1 event")
            ck("publish", True)
        except Exception as e:
            print(f"  ❌ publish: {e}")
            ck("publish", False)

        # ── T4: Inherits correctly ───────────────────
        try:
            from agentscope.app.message_bus._base import MessageBus
            assert isinstance(bus, MessageBus)
            print(f"  ✅ isinstance(OpenMoxMessageBus, MessageBus) = {isinstance(bus, MessageBus)}")
            ck("inherit", True)
        except Exception as e:
            print(f"  ❌ inherit: {e}")
            ck("inherit", False)

        # ── T5: subscribe + publish (in-process) ─────
        try:
            signal_key = "test_signal"
            received = []

            async def listener():
                async for payload in bus.subscribe(signal_key):
                    received.append(payload)
                    break  # one-shot

            task = asyncio.create_task(listener())
            await asyncio.sleep(0.1)  # give subscriber time to register
            await bus.publish(signal_key, {})
            await asyncio.sleep(0.1)
            task.cancel()
            assert len(received) >= 1, f"expected >=1 signal, got {len(received)}"
            print(f"  ✅ publish → subscribe: {len(received)} signal(s) delivered")
            ck("pubsub", True)
        except Exception as e:
            print(f"  ❌ pubsub: {e}")
            ck("pubsub", False)

    await store_mod.close_db()
    print("=" * 50)
    passed = sum(1 for _, r in results if r == "✅")
    print(f"Results: {passed}/{len(results)}")
    for name, status in results:
        print(f"  {status} {name}")
    if passed < len(results):
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
