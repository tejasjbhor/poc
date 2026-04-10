import asyncio
import json


class ConnectionManager:
    def __init__(self):
        self.connections = {}  # session_id -> websocket
        self.loops = {}  # session_id -> event loop

    async def connect(self, session_id: str, websocket):
        await websocket.accept()
        self.connections[session_id] = websocket
        self.loops[session_id] = asyncio.get_running_loop()

    def disconnect(self, session_id: str):
        if session_id in self.connections:
            del self.connections[session_id]
        if session_id in self.loops:
            del self.loops[session_id]

    async def send(self, session_id: str, data):
        ws = self.connections.get(session_id)

        if not ws:
            print("NO WS FOUND")
            return
        try:
            await ws.send_json(data)
        except Exception as e:
            print("SEND FAILED:", e)
            self.disconnect(session_id)

    def send_nowait(self, session_id: str, data):
        loop = self.loops.get(session_id)

        if not loop or loop.is_closed():
            return None

        future = asyncio.run_coroutine_threadsafe(self.send(session_id, data), loop)
        future.add_done_callback(self._consume_future_result)
        return future

    @staticmethod
    def _consume_future_result(future):
        try:
            future.result()
        except Exception as e:
            print("SEND FAILED:", e)

    async def broadcast(self, message: str):
        for session_id, ws in list(self.connections.items()):
            try:
                await ws.send_text(message)
            except Exception:
                self.disconnect(session_id)

    async def broadcast_json(self, data: dict):
        """Main helper you will use from LLM / LangGraph"""
        message = json.dumps(data, ensure_ascii=False)
        await self.broadcast(message)


ws_manager_graph = ConnectionManager()
