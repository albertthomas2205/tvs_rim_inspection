from django.urls import re_path
from .consumers import InspectionConsumer,EmergencyStopConsumer,RobotMessageConsumer,RobotProfileMessageConsumer

websocket_urlpatterns = [
    
    re_path(r"ws/inspection/(?P<schedule_id>[^/]+)/$",InspectionConsumer.as_asgi()),
    re_path(r"ws/emergency-stop/$", EmergencyStopConsumer.as_asgi()),
    # re_path(r"ws/robot_message/?$", RobotMessageConsumer.as_asgi()),

    re_path(
        r"ws/robot_message/(?P<robo_id>[\w-]+)/$",
        RobotMessageConsumer.as_asgi()
    ),

    re_path(
    r"ws/robot_message/(?P<robo_id>[\w-]+)/profile/(?P<profile_id>\d+)/$",
    RobotProfileMessageConsumer.as_asgi()
),

]
