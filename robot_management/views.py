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


class RobotPagination(PageNumberPagination):
    page_size = 2                # max 5 robots
    page_size_query_param = 'page_size'
    max_page_size = 2


class RobotViewSet(viewsets.ModelViewSet):
    serializer_class = RobotSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = RobotPagination
    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            return Robot.objects.all()
        return Robot.objects.filter(is_active=True)
    
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
