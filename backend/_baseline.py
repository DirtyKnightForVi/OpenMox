import asyncio, os, sys, time
sys.path.insert(0, "agentscope/src")
os.environ["DEEPSEEK_API_KEY"] = "sk-6fae26aeffe643fdbe6a93f9edea1a58"
os.environ["DEEPSEEK_BASE_URL"] = "https://api.deepseek.com/v1"
os.environ["DEEPSEEK_MODEL"] = "deepseek-v4-flash"
os.environ["REDIS_HOST"] = "localhost"; os.environ["REDIS_PORT"] = "6480"

from contextlib import AsyncExitStack
from src.core.openmox_redis_storage import OpenMoxRedisStorage
from agentscope.app.message_bus import RedisMessageBus
from src.core.openmox_workspace_manager import OpenMoxWorkspaceManager
from agentscope.app._manager._background_task_manager import BackgroundTaskManager
from agentscope.app._manager._chat_run_registry import ChatRunRegistry
from agentscope.app._manager._scheduler._scheduler_manager import SchedulerManager
from agentscope.app._service._chat import ChatService
from agentscope.app.storage import SessionConfig, SessionSource, ChatModelConfig
from agentscope.message import Msg
from src.core.openmox_toolkit import make_middleware_factory

T0 = time.time()

async def main():
    stack = AsyncExitStack()
    st = OpenMoxRedisStorage(".", "localhost", 6480); await stack.enter_async_context(st)
    bus = RedisMessageBus("localhost", 6480); await stack.enter_async_context(bus)
    wm = await stack.enter_async_context(OpenMoxWorkspaceManager("."))
    bgm = await stack.enter_async_context(BackgroundTaskManager())
    reg = await stack.enter_async_context(ChatRunRegistry())
    sc = await stack.enter_async_context(SchedulerManager(st, bus))
    mwf = make_middleware_factory(message_bus=bus, project_root=".")
    chat = ChatService(st, wm, sc, bgm, bus, extra_agent_middlewares=mwf)

    mc = ChatModelConfig(type="deepseek_chat", credential_id="default", model="deepseek-v4-flash", parameters={})
    await st.upsert_session("openmox", "pm-secretary", SessionConfig(workspace_id="default", chat_model_config=mc), session_id="BASELINE", source=SessionSource.USER)

    msg = Msg(role="user", content=[{"type": "text", "text": "1+1=?"}], name="user")
    reply = []; sub_ready = asyncio.Event()

    async def col():
        async for p in bus.session_subscribe_events("BASELINE", on_ready=sub_ready.set):
            if p.get("type") == "TEXT_BLOCK_DELTA": reply.append(p.get("delta", ""))
            elif p.get("type") == "REPLY_END": break

    ct = asyncio.create_task(col())
    await asyncio.wait_for(sub_ready.wait(), timeout=3)
    await asyncio.sleep(0)
    await chat.run("openmox", "BASELINE", "pm-secretary", msg)
    print(f"BASELINE: +{time.time()-T0:.1f}s REPLY: \"{''.join(reply).strip()}\"")
    ct.cancel()
    await stack.aclose()

asyncio.run(main())
