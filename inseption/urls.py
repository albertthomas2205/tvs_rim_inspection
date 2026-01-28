
from django.urls import path
from . import views


urlpatterns = [
    
    path("schedule/", views.list_schedules),
    path("schedule/cancel-all/", views.cancel_all_schedules),
    path("robots/<int:robot_id>/schedules/", views.list_schedules_by_robot,name="list-schedules" ),
    path("robots/<int:robot_id>/schedule/create/", views.create_schedule,name="create-schedule" ),
    path("robots/<int:robot_id>/schedule/create-immediately/",views.create_schedule_immediately,name="create-schedule-immediately"),
    path("schedule/create/", views.create_schedule),
    path("schedule/create-immediately/", views.create_schedule_immediately),
    path("schedule/delete/<int:schedule_id>/", views.delete_schedule),
    path('schedule/update-immediately/<int:schedule_id>/', views.update_schedule, name='update_schedule'),
    path("schedule/<int:schedule_id>/inspections/", views.InspectionListCreateView.as_view()),
    path("schedule/filter-by-date-range/", views.ScheduleFilterByDateRangeView.as_view(), name="schedule-filter-by-date-range"),
    path("inspection/<int:pk>/", views.InspectionDetailView.as_view()),
    path("inspection/<int:pk>/verify/", views.InspectionHumanVerifyAPIView.as_view()),
    path('speak/start/', views.StartSpeakView.as_view(), name='start-speak'),
    path('speak/stop/', views.StopSpeakView.as_view(), name='stop-speak'),
    path("speak/status/", views.SpeakStatusView.as_view()),
    path("emergency-stop/", views.EmergencyStopAPIView.as_view()),
    path(
        "robots/<int:robot_id>/inspection-stats/",
        views.RobotInspectionStatsView.as_view(),
        name="robot-inspection-stats"
    ),
    path("rim-types/", views.rim_type_list_create, name="rim-type-list-create"),
    path("rim-types/<int:rim_type_id>/", views.rim_type_detail, name="rim-type-detail"),
]

