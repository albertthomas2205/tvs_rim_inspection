# views.py
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework import status
from rest_framework.pagination import PageNumberPagination
from django.utils import timezone
from datetime import datetime, timedelta
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from .models import Schedule, Inspection,SpeakConfig
from .serializers import ScheduleSerializer, InspectionSerializer,InspectionHumanVerifySerializer,ScheduleDateFilterSerializer
from .tasks import set_status_processing, set_status_completed
from .serializers import ScheduleDateRangeFilterSerializer
from drf_yasg.utils import swagger_auto_schema
from drf_yasg import openapi
from rest_framework.generics import ListCreateAPIView,UpdateAPIView
from .utilities import save_false_detection_image
from rest_framework.permissions import AllowAny,IsAuthenticated
from rest_framework.exceptions import ValidationError
# Import Channels
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import EmergencyStop
from .serializers import EmergencyStopSerializer
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from rest_framework.generics import RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from robot_management.models import Robot

# ----------- Custom Pagination Class -----------

class InspectionPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 50

    def get_paginated_response(self, data, *, total_defected=0, total_non_defected=0):
        return Response({
            "count": self.page.paginator.count,
            "total_defected": total_defected,
            "total_non_defected": total_non_defected,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data
        })
    

# class SchedulePagination(PageNumberPagination):
#     page_size = 10                  # max records per page
#     page_size_query_param = None    # prevent client override
#     page_query_param = "page"


class SchedulePagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = None
    page_query_param = "page"

    def get_paginated_response(self, data, status_totals):
        return Response({
            "count": self.page.paginator.count,
            **status_totals,  # 🔥 flattened here
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
        })


@swagger_auto_schema(
    method="post",
    request_body=ScheduleSerializer,
    responses={201: "Schedule created"}
)


# @api_view(["POST"])
# def create_schedule(request):
#     location = request.data.get("location")
#     date = request.data.get("scheduled_date")
#     time = request.data.get("scheduled_time")

#     # ---- REQUIRED FIELD VALIDATION ----
#     missing_fields = []
#     if not location:
#         missing_fields.append("location")
#     if not date:
#         missing_fields.append("scheduled_date")
#     if not time:
#         missing_fields.append("scheduled_time")

#     if missing_fields:
#         return Response(
#             {
#                 "status": 400,
#                 "message": f"Missing required fields: {', '.join(missing_fields)}",
#                 "success": False,
#             },
#             status=status.HTTP_400_BAD_REQUEST
#         )

#     # ---- TIME PARSING ----
#     def parse_time(t):
#         try:
#             return datetime.strptime(t, "%H:%M").time()
#         except ValueError:
#             return datetime.strptime(t, "%H:%M:%S").time()

#     scheduled_time = parse_time(time)
#     scheduled_date = datetime.strptime(date, "%Y-%m-%d").date()

#     # ---- COMPUTE 3-MINUTE END TIME ----
#     new_start_dt = datetime.combine(scheduled_date, scheduled_time)
#     new_end_dt = new_start_dt + timedelta(minutes=3)
#     new_end_time = new_end_dt.time()

#     # ---- OVERLAP CHECK ----
#     overlapping = Schedule.objects.filter(
#         location=location,
#         scheduled_date=scheduled_date,
#         scheduled_time__lt=new_end_time,
#         end_time__gt=scheduled_time
#     ).exists()

#     if overlapping:
#         return Response(
#             {
#                 "status": 400,
#                 "message": "Time slot already booked for this location",
#                 "success": False
#             },
#             status=status.HTTP_400_BAD_REQUEST,
#         )

#     # ---- SAVE SCHEDULE with UPDATED 3-MIN END TIME ----
#     data = request.data.copy()
#     data["end_time"] = new_end_time  # <<<<<< CRITICAL FIX

#     serializer = ScheduleSerializer(data=data)
#     serializer.is_valid(raise_exception=True)
#     schedule = serializer.save()

#     # ---- CELERY TASKS ----
#     start_datetime = timezone.make_aware(
#         datetime.combine(schedule.scheduled_date, schedule.scheduled_time)
#     )
#     end_datetime = timezone.make_aware(
#         datetime.combine(schedule.scheduled_date, schedule.end_time)
#     )

#     set_status_processing.apply_async(args=[schedule.id], eta=start_datetime)
#     set_status_completed.apply_async(args=[schedule.id], eta=end_datetime)

#     # ---- SUCCESS RESPONSE ----
#     return Response(
#         {
#             "status": 201,
#             "message": "Schedule created successfully",
#             "success": True,
#             "data": serializer.data
#         },
#         status=status.HTTP_201_CREATED
#     )

@api_view(["POST"])
def create_schedule(request, robot_id):
    # ---- VALIDATE ROBOT ----
    try:
        robot = Robot.objects.get(id=robot_id, is_active=True)
    except Robot.DoesNotExist:
        return Response(
            {
                "status": 404,
                "message": "Robot not found",
                "success": False,
            },
            status=status.HTTP_404_NOT_FOUND
        )

    location = request.data.get("location")
    date = request.data.get("scheduled_date")
    time = request.data.get("scheduled_time")

    # ---- REQUIRED FIELD VALIDATION ----
    missing_fields = []
    if not location:
        missing_fields.append("location")
    if not date:
        missing_fields.append("scheduled_date")
    if not time:
        missing_fields.append("scheduled_time")

    if missing_fields:
        return Response(
            {
                "status": 400,
                "message": f"Missing required fields: {', '.join(missing_fields)}",
                "success": False,
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # ---- TIME PARSING ----
    def parse_time(t):
        try:
            return datetime.strptime(t, "%H:%M").time()
        except ValueError:
            return datetime.strptime(t, "%H:%M:%S").time()

    scheduled_time = parse_time(time)
    scheduled_date = datetime.strptime(date, "%Y-%m-%d").date()

    # ---- COMPUTE 3-MINUTE END TIME ----
    new_start_dt = datetime.combine(scheduled_date, scheduled_time)
    new_end_dt = new_start_dt + timedelta(minutes=3)
    new_end_time = new_end_dt.time()

    # ---- OVERLAP CHECK (per robot + location) ----
    overlapping = Schedule.objects.filter(
        robot=robot,
        location=location,
        scheduled_date=scheduled_date,
        scheduled_time__lt=new_end_time,
        end_time__gt=scheduled_time,
        is_canceled=False
    ).exists()

    if overlapping:
        return Response(
            {
                "status": 400,
                "message": "Time slot already booked for this robot and location",
                "success": False
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ---- SAVE SCHEDULE ----
    data = request.data.copy()
    data["end_time"] = new_end_time

    serializer = ScheduleSerializer(data=data)
    serializer.is_valid(raise_exception=True)

    schedule = serializer.save(
        robot=robot  # 🔥 ROBOT COMES FROM URL
    )

    # ---- CELERY TASKS ----
    start_datetime = timezone.make_aware(
        datetime.combine(schedule.scheduled_date, schedule.scheduled_time)
    )
    end_datetime = timezone.make_aware(
        datetime.combine(schedule.scheduled_date, schedule.end_time)
    )

    set_status_processing.apply_async(args=[schedule.id], eta=start_datetime)
    set_status_completed.apply_async(args=[schedule.id], eta=end_datetime)

    # ---- SUCCESS RESPONSE ----
    return Response(
        {
            "status": 201,
            "message": "Schedule created successfully",
            "success": True,
            "data": serializer.data
        },
        status=status.HTTP_201_CREATED
    )


@api_view(["POST"])
def create_schedule_immediately(request, robot_id):
    # ---- VALIDATE ROBOT ----
    try:
        robot = Robot.objects.get(id=robot_id, is_active=True)
    except Robot.DoesNotExist:
        return Response(
            {
                "status": 404,
                "message": "Robot not found",
                "success": False,
            },
            status=status.HTTP_404_NOT_FOUND
        )

    location = request.data.get("location")

    # ---- REQUIRED FIELD VALIDATION ----
    if not location:
        return Response(
            {
                "status": 400,
                "message": "Missing required field: location",
                "success": False,
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # ---- CURRENT IST TIME ----
    now = timezone.localtime()
    rounded_now = now.replace(second=0, microsecond=0)

    scheduled_date = rounded_now.date()
    scheduled_time = rounded_now.time()

    # ---- END TIME = +3 minutes ----
    new_end_dt = rounded_now + timedelta(minutes=3)
    end_time = new_end_dt.replace(second=0, microsecond=0).time()

    # ---- OVERLAP CHECK (PER ROBOT) ----
    overlapping = Schedule.objects.filter(
        robot=robot,
        location=location,
        scheduled_date=scheduled_date,
        scheduled_time__lt=end_time,
        end_time__gt=scheduled_time,
        is_canceled=False
    ).exists()

    if overlapping:
        return Response(
            {
                "status": 400,
                "message": "A schedule already exists for this robot at this time.",
                "success": False
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    # ---- SAVE SCHEDULE ----
    schedule = Schedule.objects.create(
        robot=robot,                 # 🔥 FROM URL
        location=location,
        scheduled_date=scheduled_date,
        scheduled_time=scheduled_time,
        end_time=end_time,
        status="processing"
    )

    # ---- CELERY TASKS ----
    start_datetime = rounded_now
    end_datetime = new_end_dt

    set_status_processing.apply_async(args=[schedule.id], eta=start_datetime)
    set_status_completed.apply_async(args=[schedule.id], eta=end_datetime)

    # ---- RESPONSE ----
    return Response(
        {
            "status": 201,
            "message": "Schedule created and started immediately",
            "success": True,
            "data": {
                "id": schedule.id,
                "robot_id": robot.id,
                "location": schedule.location,
                "scheduled_date": str(schedule.scheduled_date),
                "scheduled_time": str(schedule.scheduled_time),
                "end_time": str(schedule.end_time),
                "status": schedule.status
            }
        },
        status=status.HTTP_201_CREATED
    )



@api_view(["PUT"])
def update_schedule(request, schedule_id):

    # 1️⃣ GET SCHEDULE
    try:
        schedule = Schedule.objects.get(id=schedule_id, is_canceled=False)
    except Schedule.DoesNotExist:
        return Response(
            {"status": 404, "message": "Schedule not found", "success": False},
            status=status.HTTP_404_NOT_FOUND
        )

    # Optional: allow location update
    location = request.data.get("location", schedule.location)

    # 2️⃣ GET CURRENT IST TIME (Django already returns IST if TIME_ZONE is set)
    now = timezone.localtime()  # ensures IST even if system/DB is UTC
    rounded_now = now.replace(second=0, microsecond=0)
    new_scheduled_date = rounded_now.date()
    new_scheduled_time = rounded_now.time()

    # 3️⃣ END TIME = +1 hour
    # new_end_dt = now + timedelta(hours=1)
    new_end_dt = now + timedelta(minutes=3)
    new_end_time = new_end_dt.time()

    # 4️⃣ OVERLAP CHECK
    overlapping = Schedule.objects.filter(
        location=location,
        scheduled_date=new_scheduled_date,
        scheduled_time__lt=new_end_time,
        end_time__gt=new_scheduled_time
    ).exclude(id=schedule_id).exists()

    if overlapping:
        return Response(
            {
                "status": 400,
                "message": "Time slot already booked at this location",
                "success": False
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # 5️⃣ UPDATE THE SCHEDULE
    schedule.location = location
    schedule.scheduled_date = new_scheduled_date
    schedule.scheduled_time = new_scheduled_time
    schedule.end_time = new_end_time
    schedule.status = "processing"  # start immediately
    schedule.save()

    # 6️⃣ CELERY TASKS (Correct IST scheduling)
    start_datetime = timezone.localtime()          # IST now
    end_datetime = new_end_dt                      # IST + 1 hour

    set_status_processing.apply_async(args=[schedule.id], eta=start_datetime)
    set_status_completed.apply_async(args=[schedule.id], eta=end_datetime)

    # 7️⃣ RESPONSE
    return Response(
        {
            "status": 200,
            "message": "Schedule updated with current IST date/time and started",
            "success": True,
            "data": {
                "id": schedule.id,
                "location": schedule.location,
                "scheduled_date": str(schedule.scheduled_date),
                "scheduled_time": str(schedule.scheduled_time),
                "end_time": str(schedule.end_time),
                "status": schedule.status,
            }
        },
        status=status.HTTP_200_OK
    )




# -----------------------------------
# DELETE SCHEDULE
# -----------------------------------
@api_view(["DELETE"])
def delete_schedule(request, schedule_id):

    # Check if schedule exists
    try:
        schedule = Schedule.objects.get(id=schedule_id, is_canceled=False)
    except Schedule.DoesNotExist:
        return Response(
            {
                "success": False,
                "message": "Schedule not found",
            },
            status=status.HTTP_404_NOT_FOUND
        )

    # Prevent deleting completed schedules
    if schedule.status == "completed":
        return Response(
            {
                "success": False,
                "message": "Completed schedule cannot be deleted",
            },
            status=status.HTTP_400_BAD_REQUEST
        )

    # Soft delete
    schedule.is_canceled = True
    schedule.save()

    return Response(
        {
            "success": True,
            "message": "Schedule deleted successfully",
        },
        status=status.HTTP_200_OK
    )


@swagger_auto_schema(
    method="post",
    request_body=InspectionSerializer,
    responses={201: "Schedule created"}
)
# -----------------------------------
# CREATE INSPECTION (Simple)
# -----------------------------------
@api_view(["POST"])
def create_inspection(request):
    serializer = InspectionSerializer(data=request.data)
    if serializer.is_valid():
        serializer.save()
        return Response(
            {
                "success": True,
                "message": "Inspection created successfully",
                "inspections": serializer.data
            },
            status=status.HTTP_201_CREATED
        )

    return Response(
        {
            "success": False,
            "message": "Validation failed",
            "errors": serializer.errors,
        },
        status=status.HTTP_400_BAD_REQUEST
    )


# -----------------------------------
# LIST SCHEDULES
# -----------------------------------
# @api_view(["GET"])
# @permission_classes([IsAuthenticated])
# def list_schedules(request):

#     schedules = Schedule.objects.filter(is_canceled=False).order_by("-id")
#     serializer = ScheduleSerializer(schedules, many=True)

#     return Response(
#         {
#             "success": True,
#             "message": "Schedules fetched successfully",
#             "schedules": serializer.data,
#         },
#         status=status.HTTP_200_OK
#     )


# @api_view(["GET"])
# @permission_classes([IsAuthenticated])
# def list_schedules(request):

#     schedules = Schedule.objects.filter(is_canceled=False).order_by("-id")

#     paginator = SchedulePagination()
#     paginated_qs = paginator.paginate_queryset(schedules, request)

#     serializer = ScheduleSerializer(paginated_qs, many=True)

#     return paginator.get_paginated_response({
#         "success": True,
#         "message": "Schedules fetched successfully",
#         "schedules": serializer.data,
#     })



@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_schedules(request):

    base_qs = Schedule.objects.filter(is_canceled=False)

    # 🔥 dynamic status counts
    status_counts = (
        base_qs
        .values("status")
        .annotate(count=Count("id"))
    )

    # flatten counts
    status_totals = {
        item["status"]: item["count"]
        for item in status_counts
    }

    paginator = SchedulePagination()
    paginated_qs = paginator.paginate_queryset(
        base_qs.order_by("-id"), request
    )

    serializer = ScheduleSerializer(paginated_qs, many=True)

    return paginator.get_paginated_response({
        "success": True,
        "message": "Schedules fetched successfully",
        "schedules": serializer.data,
    }, status_totals=status_totals)


class InspectionListCreateView(ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = InspectionSerializer
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    pagination_class = InspectionPagination  # ← add pagination

    def get_queryset(self):
        return Inspection.objects.filter(schedule=self.kwargs["schedule_id"])

    def perform_create(self, serializer):
        schedule_id = self.kwargs["schedule_id"]
        # Save the inspection
        inspection = serializer.save(schedule_id=schedule_id)

        # ------------------ Broadcast full serialized data ------------------
        inspection_data = InspectionSerializer(inspection).data  # includes all fields

        channel_layer = get_channel_layer()
        group_name = f"schedule_{schedule_id}"

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "inspection_created",      # this tells the consumer which method to call
                "event": "inspection_created",    # optional extra info
                "data": inspection_data           # your full inspection data
            }
        )

        return inspection


    # ✅ Custom success response
    def create(self, request, *args, **kwargs):
        response = super().create(request, *args, **kwargs)
        return Response({
            "success": True,
            "message": "Inspection created successfully",
            "inspection": response.data
        }, status=status.HTTP_201_CREATED)

    # ---------- GET CUSTOM RESPONSE with pagination ----------

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        totals = queryset.aggregate(
            total_defected=Count("id", filter=Q(is_defect=True)),
            total_non_defected=Count("id", filter=Q(is_defect=False)),
        )

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.paginator.get_paginated_response(
                {
                    "success": True,
                    "message": "Inspections retrieved successfully",
                    "inspections": serializer.data
                },
                **totals
            )
        


class InspectionDetailView(RetrieveAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = InspectionSerializer
    queryset = Inspection.objects.all()  # REQUIRED for RetrieveAPIView

    def retrieve(self, request, *args, **kwargs):
        inspection = self.get_object()  # uses pk from URL
        serializer = self.get_serializer(inspection)

        return Response({
            "success": True,
            "message": "Inspection details retrieved successfully",
            "inspection": serializer.data
        })


# -----------------------------------
# CREATE INSPECTION (Standalone)
# -----------------------------------

class InspectionCreateView(APIView):

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def post(self, request):
        serializer = InspectionSerializer(data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(
                {
                    "success": True,
                    "message": "Inspection created successfully",
                    "inspections": serializer.data
                },
                status=status.HTTP_201_CREATED
            )

        return Response(
            {
                "success": False,
                "message": "Validation failed",
                "errors": serializer.errors
            },
            status=status.HTTP_400_BAD_REQUEST
        )


speak_status = {"speak": False}

class SpeakStatusView(APIView):
    def get(self, request):
        return Response({
            "success": True,
            "message": "Speak status fetched successfully",
            "data": speak_status
        })
        
        
class StartSpeakView(APIView):
    def post(self, request):
        speak_status["speak"] = True
        return Response({
            "success": True,
            "message": "Speak started successfully",
            "data": speak_status
        })

        
class StopSpeakView(APIView):
    def post(self, request):
        speak_status["speak"] = False
        return Response({
            "success": True,
            "message": "Speak stopped successfully",
            "data": speak_status
        })



class InspectionHumanVerifyAPIView(UpdateAPIView):
    permission_classes = [IsAuthenticated]
    queryset = Inspection.objects.all()
    serializer_class = InspectionHumanVerifySerializer

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(
            instance, data=request.data, partial=partial
        )
        serializer.is_valid(raise_exception=True)

        # ❌ Already verified check
        if instance.is_human_verified:
            return Response(
                {
                    "success": False,
                    "message": "Inspection has already been human verified.",
                    "status_code": status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # ✅ Save
        inspection = serializer.save(
            is_human_verified=True,
            verified_at=timezone.now(),
            verified_by=request.user
        )

        if inspection.false_detected:
            save_false_detection_image(inspection)

        return Response(
            {
                "success": True,
                "message": "Inspection human verification completed successfully.",
                "status_code": status.HTTP_200_OK,
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )




class EmergencyStopAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get_object(self):
        obj, _ = EmergencyStop.objects.get_or_create(
            id=1,
            defaults={"is_emergency_stop": False}
        )
        return obj

    def get(self, request):
        emergency = self.get_object()
        serializer = EmergencyStopSerializer(emergency)

        return Response({
            "success": True,
            "message": "Emergency stop status fetched",
            "data": serializer.data
        })

    def post(self, request):
        emergency = self.get_object()

        is_emergency_stop = request.data.get("is_emergency_stop")
        if is_emergency_stop is None:
            return Response(
                {"success": True,"message": "is_emergency_stop is required"},
                status=400
            )

        emergency.is_emergency_stop = bool(is_emergency_stop)
        emergency.save()

        serializer = EmergencyStopSerializer(emergency)

        # 🔔 BROADCAST TO WEBSOCKET
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            "emergency_stop",
            {
                "type": "emergency_updated",
                "data": serializer.data
            }
        )

        return Response({
            "success": True,
            "message": "Emergency stop status updated",
            "data": serializer.data
        })




class ScheduleFilterByDateRangeView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = ScheduleDateRangeFilterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        start_date = serializer.validated_data["start_date"]
        end_date = serializer.validated_data["end_date"]

        schedules = Schedule.objects.filter(
            scheduled_date__range=(start_date, end_date),
            is_canceled=False
        ).order_by("scheduled_date", "scheduled_time")

        return Response({
            "success": True,
            "message": "Schedules retrieved successfully",
            "count": schedules.count(),
            "schedules": ScheduleSerializer(schedules, many=True).data
        }, status=status.HTTP_200_OK)