import asyncio
from typing import Dict, Set
from fastapi import WebSocket
from datetime import datetime

class ColonyNotifier:
    """
    Location-Based Real-Time WebSocket Broadcaster.
    
    Routes emergency notifications, live community reports, and ML verification 
    alerts to all residents connected within a specific colony/area room.
    """
    def __init__(self):
        self.active_rooms: Dict[str, Set[WebSocket]] = {}
        self.lock = asyncio.Lock()

    async def connect(self, colony_name: str, websocket: WebSocket):
        await websocket.accept()
        colony_key = colony_name.strip().lower()
        async with self.lock:
            if colony_key not in self.active_rooms:
                self.active_rooms[colony_key] = set()
            self.active_rooms[colony_key].add(websocket)
        print(f"[COLONY WS] Client joined room '{colony_name}'. Active clients in room: {len(self.active_rooms[colony_key])}")

    async def disconnect(self, colony_name: str, websocket: WebSocket):
        colony_key = colony_name.strip().lower()
        async with self.lock:
            if colony_key in self.active_rooms:
                self.active_rooms[colony_key].discard(websocket)
                if len(self.active_rooms[colony_key]) == 0:
                    del self.active_rooms[colony_key]
        print(f"[COLONY WS] Client left room '{colony_name}'.")

    async def broadcast_to_colony(self, colony_name: str, event_type: str, payload: dict):
        """Broadcast alert or new report event to all residents in that colony."""
        colony_key = colony_name.strip().lower()
        message = {
            "type": event_type,
            "colony": colony_name,
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "data": payload
        }
        
        async with self.lock:
            targets = list(self.active_rooms.get(colony_key, []))

        if not targets:
            print(f"[COLONY BROADCAST] No active clients currently connected in room '{colony_name}'.")
            return

        print(f"[COLONY BROADCAST] Broadcasting {event_type} to {len(targets)} client(s) in '{colony_name}'...")
        for ws in targets:
            try:
                await ws.send_json(message)
            except Exception as e:
                print(f"[COLONY BROADCAST] Error sending to client: {e}")

colony_notifier = ColonyNotifier()
