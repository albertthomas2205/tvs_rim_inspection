# views.py
from rest_framework.views import APIView
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from rest_framework.generics import ListAPIView
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
from rest_framework.permissions import AllowAny,IsAuthenticated,IsAdminUser
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

from .models import RimType
from .serializers import RimTypeSerializer


# ----------- Custom Pagination Class -----------

class InspectionPagination(PageNumberPagination):
    page_size = 5
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
    



class SchedulePagination(PageNumberPagination):
    page_size = 8
    page_size_query_param = None
    page_query_param = "page"

    def get_paginated_response(self, data, **extra):
        return Response({
            "count": self.page.paginator.count,
            "next": self.get_next_link(),
            "previous": self.get_previous_link(),
            "results": data,
            **extra,  # 🔥 status_totals injected here
        })


@swagger_auto_schema(
    method="post",
    request_body=ScheduleSerializer,
    responses={201: "Schedule created"}
)


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



@api_view(["POST"])
@permission_classes([IsAdminUser])
def cancel_all_schedules(request):
    updated_count = Schedule.objects.filter(is_canceled=False).update(
        is_canceled=True
    )

    return Response({
        "success": True,
        "message": "All schedules canceled successfully",
        "affected_rows": updated_count
    })



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




@api_view(["GET"])
@permission_classes([IsAuthenticated])
def list_schedules_by_robot(request, robot_id=None):
    """
    List schedules for a specific robot (robot_id) or all robots if None.
    Returns paginated schedules + status totals.
    """

    base_qs = Schedule.objects.filter(is_canceled=False)

    if robot_id:
        try:
            robot_id = int(robot_id)
        except ValueError:
            return Response(
                {"success": False, "message": "Invalid robot_id"},
                status=400
            )

        get_object_or_404(Robot, id=robot_id)
        base_qs = base_qs.filter(robot__id=robot_id)

    # 🔹 status totals
    status_counts = base_qs.values("status").annotate(count=Count("id"))

    status_mapping = {
        "scheduled": "pending",
        "processing": "processing",
        "completed": "completed",
    }

    status_totals = {v: 0 for v in status_mapping.values()}

    for item in status_counts:
        api_status = status_mapping.get(item["status"])
        status_totals[api_status] = item["count"]

    status_totals["total"] = sum(status_totals.values())

    # 🔹 pagination
    paginator = SchedulePagination()
    page = paginator.paginate_queryset(base_qs.order_by("-id"), request)
    serializer = ScheduleSerializer(page, many=True)

    paginated_response = paginator.get_paginated_response(serializer.data)

    # 🔹 final wrapped response
    paginated_response.data = {
        "success": True,
        "message": "Schedules fetched successfully",
        "data": {
            "result": paginated_response.data,
            "status_totals": status_totals,
        },
    }

    return paginated_response



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

    def post(self, request, robot_id):
        serializer = ScheduleDateRangeFilterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        start_date = serializer.validated_data["start_date"]
        end_date = serializer.validated_data["end_date"]

        schedules = Schedule.objects.filter(
            robot_id=robot_id,              # ✅ robot filter
            scheduled_date__range=(start_date, end_date),
            is_canceled=False
        ).order_by("scheduled_date", "scheduled_time")

        return Response({
            "success": True,
            "message": "Schedules retrieved successfully",
            "robot_id": robot_id,
            "count": schedules.count(),
            "schedules": ScheduleSerializer(schedules, many=True).data
        }, status=status.HTTP_200_OK)


class RobotInspectionStatsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, robot_id):
        inspections = Inspection.objects.filter(
            schedule__robot_id=robot_id
        )

        stats = inspections.aggregate(
            total_inspections=Count("id"),
            total_defected=Count("id", filter=Q(is_defect=True)),
            total_passed=Count("id", filter=Q(is_defect=False)),
            total_approved=Count("id", filter=Q(is_approved=True)),
            total_verified=Count("id", filter=Q(is_human_verified=True)),
            total_false_detected=Count("id", filter=Q(false_detected=True)),
        )

        return Response({
            "success": True,
            "message": "Robot inspections retrieved successfully",
            "data": {
                "robot_id": robot_id,
                **stats
            }
        })
    

# ---------------- LIST & CREATE ----------------
@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated, IsAdminUser])
def rim_type_list_create(request):
    if request.method == "GET":
        rim_types = RimType.objects.all().order_by("-created_at")
        serializer = RimTypeSerializer(rim_types, many=True)
        return Response({
            "success": True,
            "message": "Rim types retrieved successfully",
            "data": serializer.data
        })

    if request.method == "POST":
        serializer = RimTypeSerializer(data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response({
                "success": True,
                "message": "Rim type created successfully",
                "data": serializer.data
            }, status=status.HTTP_201_CREATED)

        return Response({
            "success": False,
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)


# ---------------- RETRIEVE / UPDATE / DELETE ----------------
@api_view(["GET", "PATCH", "DELETE"])
@permission_classes([IsAuthenticated, IsAdminUser])
def rim_type_detail(request, rim_type_id):
    try:
        rim_type = RimType.objects.get(id=rim_type_id)
    except RimType.DoesNotExist:
        return Response(
            {"success": False, "message": "Rim type not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    if request.method == "GET":
        serializer = RimTypeSerializer(rim_type)
        return Response({
            "success": True,
            "message": "Rim type retrieved successfully",
            "data": serializer.data
        })

    if request.method == "PATCH":
        serializer = RimTypeSerializer(
            rim_type,
            data=request.data,
            partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response({
                "success": True,
                "message": "Rim type updated successfully",
                "data": serializer.data
            })

        return Response({
            "success": False,
            "errors": serializer.errors
        }, status=status.HTTP_400_BAD_REQUEST)

    # -------- SOFT DELETE --------
    if request.method == "DELETE":
        rim_type.is_active = False
        rim_type.save()

        return Response({
            "success": True,
            "message": "Rim type deactivated successfully"
        }, status=status.HTTP_200_OK)