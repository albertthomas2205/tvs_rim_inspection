from django.urls import path
from .views import RobotEventBroadcastAPIView
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import RobotViewSet, RobotEventBroadcastAPIView,RobotMapDetailAPIView,RobotMapCreateUpdateAPIView,robot_location,RobotNavigationAPIView
from .views import EmergencyView, SpeakStartView, RobotViewSet
from .views import *
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

      # 1️⃣ Activate / Deactivate LEFT or RIGHT hand
    path(
        "robots/<int:robo_id>/calibration/hand/",
        HandActivationAPI.as_view(),
        name="hand-activation"
    ),

    # 2️⃣ Update calibration point (left/right, point_one/two/three)
    path(
        "robots/<int:robo_id>/calibration/point/",
        HandPointAPI.as_view(),
        name="hand-point-update"
    ),

    # 3️⃣ Get full calibration state (robot boot / UI refresh)
    path(
        "robots/<int:robo_id>/calibration/",
        CalibrationDetailAPI.as_view(),
        name="calibration-detail"
    ),


    # path(
    #     "robots/<int:robot_id>/profiles/",
    #     ProfileListCreateAPI.as_view()
    # ),
    # path(
    #     "robots/<int:robot_id>/profiles/<int:profile_id>/",
    #     ProfileDetailAPI.as_view()
    # ),

    # List all profiles / Create
    path('robots/<int:robot_id>/profiles/', ProfileListCreateAPI.as_view()),

    # Retrieve / Patch / Delete single profile
    path('robots/<int:robot_id>/profiles/<int:profile_id>/', ProfileListCreateAPI.as_view()),


    # Calibration
    path(
        "robots/<int:robot_id>/profiles/<int:profile_id>/calibration/",
        CalibrationDetailAPI.as_view()
    ),
    path(
        "robots/<int:robot_id>/profiles/<int:profile_id>/calibration/hand/",
        HandActivationAPI.as_view()
    ),
    path(
        "robots/<int:robot_id>/profiles/<int:profile_id>/calibration/point/",
        HandPointAPI.as_view()
    ),

    path(
        "robots/<int:robot_id>/profiles/<int:profile_id>/calibration/<str:action>/",
        HandActionAPI.as_view(),
        name="calibration-hand-action"
    ),

]