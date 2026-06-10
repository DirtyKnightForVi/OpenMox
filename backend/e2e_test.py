"""E2E test: WebSocket + ChatService full chain."""
import asyncio, json, websockets, sys, time

WS = "ws://localhost:8000/ws"
PROJ = "/home/yangjy/桌面/Data Agents/Project/OpenMox/OpenMox-Plan-C/TestProject"


async def main():
    T0 = time.time()
    async with websockets.connect(WS) as ws:
        for _ in range(2):
            await ws.recv()
        print(f"+{time.time()-T0:.1f}s CONNECTED")

        cmd = {
            "type": "pilotdeck-command",
            "command": "@pm-secretary 1+1等于几？只回答数字。",
            "options": {
                "sessionKey": "e2e-final", "sessionId": "e2e-final",
                "projectPath": PROJ, "cwd": PROJ,
            },
        }
        await ws.send(json.dumps(cmd))
        print(f"+{time.time()-T0:.1f}s SENT")

        reply = []
        for _ in range(300):
            try:
                m = json.loads(
                    await asyncio.wait_for(ws.recv(), timeout=60),
                )
                t = m.get("type", "?")
                a = m.get("_agent_id", "")
                d = m.get("delta", "") or m.get("text", "") or m.get("hint", "") or ""

                if t == "TEXT_BLOCK_DELTA" and d:
                    reply.append(d)
                    sys.stdout.write(d)
                    sys.stdout.flush()
                elif t == "REPLY_END":
                    elapsed = f"+{time.time()-T0:.1f}s"
                    print(f"\n{elapsed} ✅ REPLY_END — text: \"{''.join(reply).strip()}\"")
                    break
                elif t not in ("TEXT_BLOCK_DELTA",) and d:
                    print(f"\n+{time.time()-T0:.1f}s [{t}] {d[:80]}")

            except asyncio.TimeoutError:
                elapsed = f"+{time.time()-T0:.1f}s"
                print(f"\n{elapsed} ⏰ TIMEOUT — partial: \"{''.join(reply).strip()[:100]}\"")
                break


asyncio.run(main())
