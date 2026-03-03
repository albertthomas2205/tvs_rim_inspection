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
#         # Get robo_id from URL
#         self.robo_id = self.scope["url_route"]["kwargs"]["robo_id"]

#         # Validate robot exists and active
#         robot = await self.get_robot(self.robo_id)
#         if not robot:
#             await self.close(code=4001)
#             return

#         # Per-robot group
#         self.group_name = f"robot_message_{self.robo_id}"

#         await self.channel_layer.group_add(
#             self.group_name,
#             self.channel_name
#         )

#         await self.accept()

#         await self.send(text_data=json.dumps({
#             "event": "connected",
#             "robot": self.robo_id,
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

#         # 🔥 Send ONLY to this robot's group
#         await self.channel_layer.group_send(
#             self.group_name,
#             {
#                 "type": "robot_message",  # MUST match method below
#                 "event": event,
#                 "data": payload
#             }
#         )

#     # 🔹 Group → WebSocket
#     async def robot_message(self, event):
#         await self.send(text_data=json.dumps({
#             "event": event["event"],
#             "data": event["data"]
#         }))

#     @database_sync_to_async
#     def get_robot(self, robo_id):
#         from robot_management.models import Robot
#         return Robot.objects.filter(
#             robo_id=robo_id
#         ).first()


class RobotMessageConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        # ✅ Always initialize first
        self.group_name = None

        # Get robo_id from URL
        self.robo_id = self.scope["url_route"]["kwargs"]["robo_id"]

        # Validate robot exists
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
        # ✅ Prevent AttributeError
        if self.group_name:
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

        # Only send if group exists
        if self.group_name:
            await self.channel_layer.group_send(
                self.group_name,
                {
                    "type": "robot_message",
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
            robo_id=robo_id
        ).first()



class RobotProfileMessageConsumer(AsyncWebsocketConsumer):

    async def connect(self):
        # URL param
        self.robo_id = self.scope["url_route"]["kwargs"]["robo_id"]

        # Group name (profile_id removed)
        self.group_name = f"robot_profile_{self.robo_id}"

        # Join group
        await self.channel_layer.group_add(
            self.group_name,
            self.channel_name
        )

        await self.accept()

        # Optional: notify client on connect
        await self.send(text_data=json.dumps({
            "event": "CONNECTED",
            "data": {
                "robo_id": self.robo_id
            }
        }))

    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            self.group_name,
            self.channel_name
        )

    async def receive(self, text_data=None, bytes_data=None):
        """
        Handle messages coming FROM Robot / Postman
        """
        if not text_data:
            return

        payload = json.loads(text_data)

        event = payload.get("event")
        data = payload.get("data", {})

        # Broadcast message to group
        await self.channel_layer.group_send(
            self.group_name,
            {
                "type": "robot_message",
                "event": event,
                "data": data,
            }
        )

    async def robot_message(self, event):
        """
        Handle messages sent via group_send (backend → websocket)
        """
        await self.send(text_data=json.dumps({
            "event": event.get("event"),
            "data": event.get("data")
        }))


# class RobotsConsumer(AsyncWebsocketConsumer):

#     async def connect(self):
#         self.group_name = "robots_group"

#         await self.channel_layer.group_add(
#             self.group_name,
#             self.channel_name
#         )

#         await self.accept()

#         await self.send(text_data=json.dumps({
#             "event": "connected",
#             "message": "Connected to robots global channel"
#         }))

#     async def disconnect(self, close_code):
#         await self.channel_layer.group_discard(
#             self.group_name,
#             self.channel_name
#         )

#     async def robots_event(self, event):
#         await self.send(text_data=json.dumps({
#             "event": event["event"],
#             "data": event["data"]
#         }))



# class RobotsConsumer(AsyncWebsocketConsumer):

#     async def connect(self):

#         # Always join global group
#         self.global_group = "robots_group"
#         await self.channel_layer.group_add(
#             self.global_group,
#             self.channel_name
#         )

#         # Try to get authenticated user
#         self.user = self.scope.get("user", None)

#         self.user_group = None

#         # If user is authenticated → join user-specific group
#         if self.user and self.user.is_authenticated:
#             self.user_group = f"robots_user_{self.user.id}"
#             await self.channel_layer.group_add(
#                 self.user_group,
#                 self.channel_name
#             )

#         # Always accept connection (no 403)
#         await self.accept()

#         await self.send(text_data=json.dumps({
#             "event": "connected",
#             "global_group": self.global_group,
#             "user_group": self.user_group
#         }))

#     async def disconnect(self, close_code):

#         # Leave global group
#         if hasattr(self, "global_group"):
#             await self.channel_layer.group_discard(
#                 self.global_group,
#                 self.channel_name
#             )

#         # Leave user group if joined
#         if hasattr(self, "user_group") and self.user_group:
#             await self.channel_layer.group_discard(
#                 self.user_group,
#                 self.channel_name
#             )

#     # Handles both global and user events
#     async def robots_event(self, event):
#         await self.send(text_data=json.dumps({
#             "event": event.get("event"),
#             "data": event.get("data")
#         }))


class RobotsConsumer(AsyncWebsocketConsumer):

    async def connect(self):

        # Safely get user_id from URL
        self.user_id = self.scope.get("url_route", {}).get("kwargs", {}).get("user_id")

        # If no user_id → close safely (prevents 500 error)
        if not self.user_id:
            await self.close()
            return

        # Create group name
        self.user_group = f"robots_user_{self.user_id}"

        # Join group
        await self.channel_layer.group_add(
            self.user_group,
            self.channel_name
        )

        await self.accept()

        await self.send(text_data=json.dumps({
            "event": "connected",
            "user_group": self.user_group
        }))

    async def disconnect(self, close_code):

        if hasattr(self, "user_group"):
            await self.channel_layer.group_discard(
                self.user_group,
                self.channel_name
            )

    async def robots_event(self, event):

        await self.send(text_data=json.dumps({
            "event": event.get("event"),
            "data": event.get("data")
        }))