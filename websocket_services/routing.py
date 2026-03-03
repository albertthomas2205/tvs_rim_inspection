from django.urls import re_path
from .consumers import InspectionConsumer,EmergencyStopConsumer,RobotMessageConsumer,RobotProfileMessageConsumer,RobotsConsumer

websocket_urlpatterns = [
    
    re_path(r"ws/inspection/(?P<schedule_id>[^/]+)/$",InspectionConsumer.as_asgi()),
    re_path(r"ws/emergency-stop/$", EmergencyStopConsumer.as_asgi()),


    re_path(
        r"ws/robot_message/(?P<robo_id>[\w-]+)/$",
        RobotMessageConsumer.as_asgi()
    ),

     re_path(
        r"ws/robot_message/(?P<robo_id>[\w-]+)/profile/$",
        RobotProfileMessageConsumer.as_asgi()
    ),

    re_path(
        r"ws/robots/(?P<user_id>\d+)/$",
        RobotsConsumer.as_asgi()
    ),
     

]
