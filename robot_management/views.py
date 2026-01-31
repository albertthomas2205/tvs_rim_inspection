from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from rest_framework.permissions import AllowAny
# Create your views here.
from rest_framework import viewsets, status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.decorators import action
from .models import Robot
from .serializers import RobotSerializer
from .models import RobotMap
from .serializers import RobotMapSerializer
from rest_framework.parsers import MultiPartParser, FormParser
from django.db import transaction
from rest_framework.pagination import PageNumberPagination

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework import status
from django.db.models import Count, Q
from .models import RobotLocation,CalibrateHand,Profile
from robot_management.models import Robot
from .serializers import RobotLocationSerializer,EmergencySerializer,SpeakStartSerializer,CalibrateHandSerializer,ProfileSerializer

from django.shortcuts import get_object_or_404


from .models import RobotNavigation, Robot
from .serializers import RobotNavigationUpdateSerializer

class RobotPagination(PageNumberPagination):
    page_size = 4               # max 5 robots
    page_size_query_param = 'page_size'
    max_page_size = 4


class RobotViewSet(viewsets.ModelViewSet):
    serializer_class = RobotSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = RobotPagination
    
    def get_queryset(self):
        user = self.request.user

        qs = Robot.objects.all()

        # -------- Aggregations --------
        return qs.annotate(
            # Schedule summary
            total_schedules=Count(
                "schedules",
                filter=Q(schedules__is_canceled=False),
                distinct=True
            ),
            scheduled_count=Count(
                "schedules",
                filter=Q(
                    schedules__status="scheduled",
                    schedules__is_canceled=False
                ),
                distinct=True
            ),
            processing_count=Count(
                "schedules",
                filter=Q(
                    schedules__status="processing",
                    schedules__is_canceled=False
                ),
                distinct=True
            ),
            completed_count=Count(
                "schedules",
                filter=Q(
                    schedules__status="completed",
                    schedules__is_canceled=False
                ),
                distinct=True
            ),

            # Inspection summary
            total_inspections=Count(
                "schedules__inspections",
                distinct=True
            ),
            total_defected=Count(
                "schedules__inspections",
                filter=Q(schedules__inspections__is_defect=True),
                distinct=True
            ),
            total_non_defected=Count(
                "schedules__inspections",
                filter=Q(schedules__inspections__is_defect=False),
                distinct=True
            ),
            approved_count=Count(
                "schedules__inspections",
                filter=Q(schedules__inspections__is_approved=True),
                distinct=True
            ),
            human_verified_count=Count(
                "schedules__inspections",
                filter=Q(schedules__inspections__is_human_verified=True),
                distinct=True
            ),
            pending_verification_count=Count(
                "schedules__inspections",
                filter=Q(
                    schedules__inspections__is_human_verified=False,
                    schedules__inspections__is_approved=False
                ),
                distinct=True
            ),
        )

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()

        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response({
                "success": True,
                "message": "Robots fetched successfully",
                "data": serializer.data
            })

        serializer = self.get_serializer(queryset, many=True)
        return Response(
            {
                "success": True,
                "message": "Robots fetched successfully",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)

    def perform_update(self, serializer):
        serializer.save(updated_by=self.request.user)

    # Deactivate (DELETE)
    def destroy(self, request, *args, **kwargs):
        if not request.user.is_superuser:
            return Response(
                {"success": False, "message": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN
            )

        robot = self.get_object()
        robot.is_active = False
        robot.save(update_fields=["is_active"])

        return Response(
            {"success": True, "message": "Robot deactivated"},
            status=status.HTTP_200_OK
        )

    # ✅ Activate (PUT)
    @action(detail=True, methods=["put"])
    def activate(self, request, pk=None):
        if not request.user.is_superuser:
            return Response(
                {"success": False, "message": "Permission denied"},
                status=status.HTTP_403_FORBIDDEN
            )

        robot = self.get_object()
        robot.is_active = True
        robot.save(update_fields=["is_active"])

        return Response(
            {"success": True, "message": "Robot activated"},
            status=status.HTTP_200_OK
        )


class RobotEventBroadcastAPIView(APIView):
    """
    Receives robot events and broadcasts to WebSocket clients

    """

    authentication_classes = []   # 🔥 disable auth

    permission_classes = [AllowAny]   # ✅ allow anyone

    def post(self, request):
        event = request.data.get("event")
        data = request.data.get("data")

        if not event or not isinstance(data, dict):
            return Response(
                {"success": False, "message": "Invalid payload"},
                status=status.HTTP_400_BAD_REQUEST
            )

        channel_layer = get_channel_layer()

        async_to_sync(channel_layer.group_send)(
            "robot_message_group",
            {
                "type": "robot_message",
                "event": event,
                "data": data
            }
        )

        return Response({
            "success": True,
            "message": "Event broadcasted"
        })
    



class RobotMapCreateUpdateAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request, robot_id):
        # 1️⃣ Validate robot
        try:
            robot = Robot.objects.get(id=robot_id, is_active=True)
        except Robot.DoesNotExist:
            return Response(
                {"success": False, "message": "Robot not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        # 2️⃣ Validate map file
        new_file = request.FILES.get("map_file")
        if not new_file:
            return Response(
                {"success": False, "message": "map_file is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            with transaction.atomic():

                robot_map, created = RobotMap.objects.get_or_create(
                    robot=robot,
                    defaults={
                        "uploaded_by": request.user,
                        "is_active": True
                    }
                )

                # 3️⃣ If map exists → replace file only
                if robot_map.map_file:
                    robot_map.map_file.delete(save=False)

                # 4️⃣ Assign new file
                robot_map.map_file = new_file
                robot_map.uploaded_by = request.user
                robot_map.is_active = True
                robot_map.save()

                serializer = RobotMapSerializer(
                    robot_map,
                    context={"request": request}
                )

                return Response(
                    {
                        "success": True,
                        "message": "Robot map replaced successfully" if not created else "Robot map uploaded successfully",
                        "data": serializer.data
                    },
                    status=status.HTTP_200_OK if not created else status.HTTP_201_CREATED
                )

        except Exception as e:
            return Response(
                {
                    "success": False,
                    "message": "Failed to upload robot map",
                    "error": str(e)
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        

    # GET – fetch the current map for a robot
    def get(self, request, robot_id):
        try:
            robot_map = RobotMap.objects.get(robot_id=robot_id)
        except RobotMap.DoesNotExist:
            return Response(
                {"success": False, "message": "No map found for this robot"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = RobotMapSerializer(robot_map, context={"request": request})

        return Response(
            {
                "success": True,
                "message": "Robot map fetched successfully",
                "data": serializer.data
            },
            status=status.HTTP_200_OK
        )
        
    # DELETE – remove the map
    def delete(self, request, robot_id):
        try:
            robot_map = RobotMap.objects.get(robot_id=robot_id)
        except RobotMap.DoesNotExist:
            return Response(
                {"success": False, "message": "No map found for this robot"},
                status=status.HTTP_404_NOT_FOUND
            )

        # Delete file from storage
        if robot_map.map_file:
            robot_map.map_file.delete(save=False)

        # Delete DB record
        robot_map.delete()

        return Response(
            {"success": True, "message": "Robot map deleted successfully"},
            status=status.HTTP_200_OK
        )


class RobotMapDetailAPIView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def get_object(self, pk):
        try:
            return RobotMap.objects.get(pk=pk)
        except RobotMap.DoesNotExist:
            return None

    # GET by ID
    def get(self, request, pk):
        robot_map = self.get_object(pk)
        if not robot_map:
            return Response(
                {"success": False, "message": "Map not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = RobotMapSerializer(
            robot_map,
            context={"request": request}   # 🔥 REQUIRED
        )
        return Response(
            {"success": True, "data": serializer.data},
            status=status.HTTP_200_OK
        )
    
    # PUT – full update
    def put(self, request, pk):
        robot_map = self.get_object(pk)
        if not robot_map:
            return Response(
                {"success": False, "message": "Map not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = RobotMapSerializer(robot_map, data=request.data)
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"success": True, "data": serializer.data},
                status=status.HTTP_200_OK
            )
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    # PATCH – partial update
    def patch(self, request, pk):
        robot_map = self.get_object(pk)
        if not robot_map:
            return Response(
                {"success": False, "message": "Map not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = RobotMapSerializer(
            robot_map, data=request.data, partial=True
        )
        if serializer.is_valid():
            serializer.save()
            return Response(
                {"success": True, "data": serializer.data},
                status=status.HTTP_200_OK
            )
        return Response(
            {"success": False, "errors": serializer.errors},
            status=status.HTTP_400_BAD_REQUEST
        )

    # DELETE
    def delete(self, request, pk):
        robot_map = self.get_object(pk)
        if not robot_map:
            return Response(
                {"success": False, "message": "Map not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        robot_map.delete()
        return Response(
            {"success": True, "message": "Map deleted successfully"},
            status=status.HTTP_204_NO_CONTENT
        )



@api_view(["GET", "POST"])
@permission_classes([IsAuthenticated])
def robot_location(request, robot_id):
    # -------- Validate robot --------
    try:
        robot = Robot.objects.get(id=robot_id)
    except Robot.DoesNotExist:
        return Response(
            {"success": False, "message": "Robot not found"},
            status=status.HTTP_404_NOT_FOUND
        )

    # -------- GET LOCATION --------
    if request.method == "GET":
        try:
            location = RobotLocation.objects.get(robot=robot)
        except RobotLocation.DoesNotExist:
            return Response(
                {"success": False, "message": "Location not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = RobotLocationSerializer(location)
        return Response({
            "success": True,
            "message": "Robot location retrieved successfully",
            "data": serializer.data
        })

    # -------- CREATE / UPDATE LOCATION --------
    if request.method == "POST":
        location_obj, created = RobotLocation.objects.get_or_create(
            robot=robot,
            defaults={"location_data": request.data.get("location_data")}
        )

        if not created:
            location_obj.location_data = request.data.get("location_data")
            location_obj.save()

        serializer = RobotLocationSerializer(location_obj)
        return Response({
            "success": True,
            "message": "Robot location saved successfully",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    



class RobotNavigationAPIView(APIView):

    def get(self, request, robot_id):
        robot = get_object_or_404(Robot, id=robot_id)

        navigation, created = RobotNavigation.objects.get_or_create(
            robot=robot,
            defaults={
                "navigation_mode": "stationary",
                "navigation_style": None
            }
        )

        serializer = RobotNavigationUpdateSerializer(navigation)

        return Response({
            "status": "success",
            "created": created,
            "data": serializer.data
        })

    def patch(self, request, robot_id):
        robot = get_object_or_404(Robot, id=robot_id)

        navigation, created = RobotNavigation.objects.get_or_create(
            robot=robot,
            defaults={
                "navigation_mode": "stationary",
                "navigation_style": None
            }
        )

        serializer = RobotNavigationUpdateSerializer(
            navigation,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():
            serializer.save()
            return Response({
                "status": "success",
                "created": created,
                "data": serializer.data
            })

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
    




# Utility function to broadcast to robot WebSocket using robo_id
def broadcast_to_robot_by_robo_id(robo_id, event, data):
    channel_layer = get_channel_layer()
    group_name = f"robot_message_{robo_id}"
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            "type": "robot_message",
            "event": event,
            "data": data
        }
    )


# Emergency API
class EmergencyView(APIView):
    def get(self, request, robot_id):
        robot = Robot.objects.filter(pk=robot_id).first()
        if not robot:
            return Response({
                "success": False,
                "message": "Robot not found"
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = EmergencySerializer(robot)
        return Response({
            "success": True,
            "message": "Emergency status retrieved successfully",
            "data": serializer.data
        })

    def post(self, request, robot_id):
        robot = Robot.objects.filter(pk=robot_id).first()
        if not robot:
            return Response({
                "success": False,
                "message": "Robot not found"
            }, status=status.HTTP_404_NOT_FOUND)

        data = request.data

        # Default to False if no value is passed
        robot.emergency = data.get('emergency', False)
        robot.save()

        # 🔹 Broadcast to WebSocket using robo_id
        broadcast_to_robot_by_robo_id(
            robot.robo_id,  # <-- use robo_id from Robot model
            event="emergency_update",
            data={"emergency": robot.emergency}
        )

        serializer = EmergencySerializer(robot)
        return Response({
            "success": True,
            "message": f"Emergency status updated to {robot.emergency}",
            "data": serializer.data
        }, status=status.HTTP_200_OK)


# Speak Start API
class SpeakStartView(APIView):
    def get(self, request, robot_id):
        robot = Robot.objects.filter(pk=robot_id).first()
        if not robot:
            return Response({
                "success": False,
                "message": "Robot not found"
            }, status=status.HTTP_404_NOT_FOUND)

        serializer = SpeakStartSerializer(robot)
        return Response({
            "success": True,
            "message": "Speak start status retrieved successfully",
            "data": serializer.data
        })

    def post(self, request, robot_id):
        robot = Robot.objects.filter(pk=robot_id).first()
        if not robot:
            return Response({
                "success": False,
                "message": "Robot not found"
            }, status=status.HTTP_404_NOT_FOUND)

        data = request.data

        # Default to False if no value is passed
        robot.speak_start = data.get('speak_start', False)
        robot.save()

        # 🔹 Broadcast to WebSocket using robo_id
        broadcast_to_robot_by_robo_id(
            robot.robo_id,  # <-- use robo_id from Robot model
            event="speak_start_update",
            data={"speak_start": robot.speak_start}
        )

        serializer = SpeakStartSerializer(robot)
        return Response({
            "success": True,
            "message": f"Speak start status updated to {robot.speak_start}",
            "data": serializer.data
        }, status=status.HTTP_200_OK)
    


def get_profile_calibration(robot_id, profile_id):
    robot = get_object_or_404(Robot, id=robot_id)
    profile = get_object_or_404(Profile, id=profile_id, robot=robot)

    calibration, _ = CalibrateHand.objects.get_or_create(
        profile=profile,
        defaults={"robot": robot}
    )

    return robot, profile, calibration


def broadcast_to_profile(robot, profile, event, data):
    async_to_sync(get_channel_layer().group_send)(
        f"robot_profile_{robot.robo_id}_{profile.id}",
        {
            "type": "robot_message",
            "event": event,
            "data": data
        }
    )

class HandActivationAPI(APIView):

    def patch(self, request, robot_id, profile_id):
        robot, profile, calibration = get_profile_calibration(robot_id, profile_id)

        # 🔒 Calibration check
        if not calibration.calibration_status:
            return Response(
                {
                    "status": False,
                    "message": "Calibration is not active",
                    "data": None
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        hand = request.data.get("hand")
        active = request.data.get("active")

        if hand not in ["left", "right"] or not isinstance(active, bool):
            return Response(
                {
                    "status": False,
                    "message": "hand must be 'left' or 'right' and active must be boolean",
                    "data": None
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Update DB (UNCHANGED LOGIC)
        if hand == "left":
            calibration.left_hand_active = active
            if not active:
                calibration.left_point_one_active = False
                calibration.left_point_two_active = False
                calibration.left_point_three_active = False
        else:
            calibration.right_hand_active = active
            if not active:
                calibration.right_point_one_active = False
                calibration.right_point_two_active = False
                calibration.right_point_three_active = False

        calibration.save()

        
        # 🔥 WebSocket broadcast
        event_name = f"hand_{hand}_active"
        payload = {"value": active}

        broadcast_to_profile(robot, profile, event_name, payload)
        return Response(
            {
                "status": True,
                "message": f"{hand.capitalize()} hand {'activated' if active else 'deactivated'} successfully",
                "data": payload
            },
            status=status.HTTP_200_OK
        )


class HandPointAPI(APIView):

    def patch(self, request, robot_id, profile_id):
        robot, profile, calibration = get_profile_calibration(robot_id, profile_id)

        hand = request.data.get("hand")
        point = request.data.get("point")
        active = request.data.get("active")
        data = request.data.get("data")

        if hand not in ["left", "right"]:
            return Response({"success": False, "message": "hand must be 'left' or 'right'", "data": None}, status=400)

        if not calibration.calibration_status:
            return Response({"success": False, "message": "Calibration is not active.", "data": None}, status=400)

        if hand == "left" and not calibration.left_hand_active:
            return Response({"success": False, "message": "Left hand is inactive.", "data": None}, status=400)
        if hand == "right" and not calibration.right_hand_active:
            return Response({"success": False, "message": "Right hand is inactive.", "data": None}, status=400)

        field = f"{hand}_{point}"
        active_field = f"{field}_active"

        if not hasattr(calibration, active_field):
            return Response({"success": False, "message": "Invalid point", "data": None}, status=400)

        events = []

        # Activate point
        if active is True:
            setattr(calibration, active_field, True)
            calibration.save()

            event_name = f"{field}_active"
            broadcast_to_profile(robot, profile, event_name, {"value": True})
            events.append({"event": event_name, "value": True})

        if not getattr(calibration, active_field):
            event_name = f"{field}_active"
            broadcast_to_profile(robot, profile, event_name, {"value": False})
            return Response({"success": False, "message": f"Point '{point}' is inactive.", "data": {"event": event_name, "value": False}}, status=400)

        if data:
            setattr(calibration, field, data)
            calibration.save()

            event_name = f"{field}_data"
            broadcast_to_profile(robot, profile, event_name, {"value": True, "data": data})
            events.append({"event": event_name, "value": True, "data": data})

        return Response({"success": True, "message": f"Point '{point}' updated successfully", "data": events}, status=200)




class CalibrationDetailAPI(APIView):

    def get(self, request, robot_id, profile_id):
        robot, profile, calibration = get_profile_calibration(robot_id, profile_id)

        return Response(
            {
                "status": True,
                "profile": {
                    "id": profile.id,
                    "name": profile.name
                },
                "data": CalibrateHandSerializer(calibration).data
            },
            status=200
        )

    def patch(self, request, robot_id, profile_id):
        robot, profile, calibration = get_profile_calibration(robot_id, profile_id)

        calibration_status = request.data.get("calibration_status")
        if not isinstance(calibration_status, bool):
            return Response({"status": False, "message": "calibration_status must be true or false"}, status=400)

        calibration.calibration_status = calibration_status
        calibration.save(update_fields=["calibration_status"])

        event_name = "calibration_status"
        broadcast_to_profile(robot, profile, event_name, {"value": calibration_status})

        return Response({"status": True, "message": f"Calibration status set to {calibration_status}", 
                         "data": {"event": event_name, "value": calibration_status}}, status=200)


class ProfileListCreateAPI(APIView):

    def get(self, request, robot_id):
        robot = get_object_or_404(Robot, id=robot_id)
        profiles = robot.profiles.all()

        data = ProfileSerializer(profiles, many=True).data
        return Response({"success": True, "data": data})

    def post(self, request, robot_id):
        robot = get_object_or_404(Robot, id=robot_id)

        serializer = ProfileSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile = serializer.save(robot=robot)

        # 🔥 Auto-create calibration
        CalibrateHand.objects.create(profile=profile)

        return Response(
            {
                "success": True,
                "message": "Profile created successfully",
                "data": serializer.data
            },
            status=201
        )


class ProfileDetailAPI(APIView):

    def patch(self, request, robot_id, profile_id):
        profile = get_object_or_404(
            Profile,
            id=profile_id,
            robot_id=robot_id
        )

        serializer = ProfileSerializer(
            profile,
            data=request.data,
            partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(
            {
                "success": True,
                "message": "Profile updated successfully",
                "data": serializer.data
            }
        )
    
