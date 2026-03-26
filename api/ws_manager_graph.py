class ConnectionManager:
    def __init__(self):
        self.connections = {}  # session_id -> websocket

    async def connect(self, session_id: str, websocket):
        await websocket.accept()
        self.connections[session_id] = websocket

    def disconnect(self, session_id: str):
        if session_id in self.connections:
            del self.connections[session_id]

    async def send(self, session_id: str, data):
        ws = self.connections.get(session_id)
        if ws:
            await ws.send_json(data)


manager = ConnectionManager()