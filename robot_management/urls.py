from django.urls import path
from .views import RobotEventBroadcastAPIView
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RobotViewSet, RobotEventBroadcastAPIView,RobotMapDetailAPIView,RobotMapCreateUpdateAPIView,robot_location,RobotNavigationAPIView,CalibrateHandAPI
from .views import EmergencyView, SpeakStartView, RobotViewSet

robot_list = RobotViewSet.as_view({
    'get': 'list',         # GET /robots/ → list all robots
    'post': 'create',      # POST /robots/ → create new robot
})

robot_detail = RobotViewSet.as_view({
    'get': 'retrieve',     # GET /robots/<pk>/ → get single robot
    'put': 'update',       # PUT /robots/<pk>/ → update robot
    'patch': 'partial_update',  # PATCH /robots/<pk>/ → partial update
    'delete': 'destroy',   # DELETE /robots/<pk>/ → soft delete
})

urlpatterns = [
 
    path("robots/event/", RobotEventBroadcastAPIView.as_view()),
    path('robots/', robot_list, name='robot-list'),
    path('robots/<int:pk>/', robot_detail, name='robot-detail'),

    path(
        "robots/<int:robot_id>/map/",
        RobotMapCreateUpdateAPIView.as_view(),
        name="robot-map"
    ),
    

    # path(
    #     "robot-maps/",
    #     RobotMapListCreateAPIView.as_view(),
    #     name="robot-map-list-create"
    # ),
    path(
        "robot-maps/<int:pk>/",
        RobotMapDetailAPIView.as_view(),
        name="robot-map-detail"
    ),

        path(
        "robots/<int:robot_id>/location/",
        robot_location,
        name="robot-location"
    ),

    path(
        "robots/<int:robot_id>/navigation/",
        RobotNavigationAPIView.as_view(),
        name="robot-navigation"
    ),

    path('robots/<int:robot_id>/emergency/', EmergencyView.as_view(), name='robot_emergency'),
    path('robots/<int:robot_id>/speak_start/', SpeakStartView.as_view(), name='robot_speak_start'),
    path(
        "robots/<int:robo_id>/calibrate-hand/",
        CalibrateHandAPI.as_view(),
        name="calibrate-hand"
    ),
]