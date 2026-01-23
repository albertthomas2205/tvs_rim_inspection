import json
from channels.generic.websocket import AsyncWebsocketConsumer


import json
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

class InspectionConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.schedule_id = self.scope["url_route"]["kwargs"]["schedule_id"]
        self.group_name = f"schedule_{self.schedule_id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        # 🔔 Send connection confirmation message
        await self.send(text_data=json.dumps({
            "type": "connection",
            "message": f"Connected to schedule {self.schedule_id}"
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def inspection_created(self, event):
        await self.send(text_data=json.dumps({
        "event": "inspection_created",  # fallback to inspection_created
        "data": event["data"]  # full serialized inspection
    }))
        

class EmergencyStopConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        self.group_name = "emergency_stop"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        # ✅ Send initial connection message
        await self.send(text_data=json.dumps({
            "event": "connected",
            "message": "Connected to Emergency Stop channel"
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def emergency_updated(self, event):
        await self.send(text_data=json.dumps({
            "event": "emergency_updated",
            "data": event["data"]
        }))




# class RobotMessageConsumer(AsyncWebsocketConsumer):

#     async def connect(self):
#         self.group_name = "robot_message_group"

#         await self.channel_layer.group_add(
#             self.group_name,
#             self.channel_name
#         )

#         await self.accept()

#         await self.send(text_data=json.dumps({
#             "event": "connected",
#             "message": "WebSocket connected"
#         }))

#     async def disconnect(self, close_code):
#         await self.channel_layer.group_discard(
#             self.group_name,
#             self.channel_name
#         )

#     # 🔹 Client → Server
#     async def receive(self, text_data):
#         data = json.loads(text_data)

#         event = data.get("event")
#         payload = data.get("data", {})

#         # ping-pong
#         if event == "ping":
#             await self.send(text_data=json.dumps({
#                 "event": "pong"
#             }))
#             return

#         # 🔥 Send to group (includes same client)
#         await self.channel_layer.group_send(
#             self.group_name,
#             {
#                 "type": "robot_message",  # MUST match method below
#                 "event": event,
#                 "data": payload
#             }
#         )

#     # 🔹 Group → WebSocket (THIS IS REQUIRED)
#     async def robot_message(self, event):
#         await self.send(text_data=json.dumps({
#             "event": event["event"],
#             "data": event["data"]
#         }))





class RobotMessageConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        # Get robo_id from URL
        self.robo_id = self.scope["url_route"]["kwargs"]["robo_id"]

        # Validate robot exists and active
        robot = await self.get_robot(self.robo_id)
        if not robot:
            await self.close(code=4001)
            return

        # Per-robot group
        self.group_name = f"robot_message_{self.robo_id}"

        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        await self.send(text_data=json.dumps({
            "event": "connected",
            "robot": self.robo_id,
            "message": "WebSocket connected"
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    # 🔹 Client → Server
    async def receive(self, text_data):
        data = json.loads(text_data)

        event = data.get("event")
        payload = data.get("data", {})

        # ping-pong
        if event == "ping":
            await self.send(text_data=json.dumps({
                "event": "pong"
            }))
            return

        # 🔥 Send ONLY to this robot's group
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "robot_message",  # MUST match method below
                "event": event,
                "data": payload
            }
        )

    # 🔹 Group → WebSocket
    async def robot_message(self, event):
        await self.send(text_data=json.dumps({
            "event": event["event"],
            "data": event["data"]
        }))

    @database_sync_to_async
    def get_robot(self, robo_id):
        from robot_management.models import Robot
        return Robot.objects.filter(
            robo_id=robo_id,
            is_active=True
        ).first()

