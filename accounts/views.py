from django.contrib.auth.models import User
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated,IsAdminUser
from rest_framework_simplejwt.tokens import RefreshToken
from django.utils.crypto import get_random_string
from .serializers import RegisterSerializer
from datetime import timedelta
from django.utils import timezone
from .models import UserProfile,RobotUser
from rest_framework.decorators import api_view, permission_classes
from .serializers import UserListSerializer,RobotUserAssignSerializer
from robot_management.models import Robot
from .serializers import *
from rest_framework.pagination import PageNumberPagination
from rest_framework_simplejwt.views import TokenVerifyView
from drf_yasg.utils import swagger_auto_schema
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

# ------------------- Registration -------------------
class RegisterAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response({
            "success": True,
            "message": "Registration successful. Wait for admin verification."
        }, status=status.HTTP_201_CREATED)




class LoginAPIView(APIView):
    permission_classes = [AllowAny]
    serializer_class = LoginSerializer

    @swagger_auto_schema(request_body=LoginSerializer)  
    def post(self, request):
        login_value = request.data.get("login")
        password = request.data.get("password")

        if not login_value or not password:
            return Response(
                {"success": False, "message": "Login and password are required"},
                status=400
            )

        # Find user by email or username
        user = User.objects.filter(email=login_value).first() \
               or User.objects.filter(username=login_value).first()

        if not user:
            return Response(
                {"success": False, "message": "Email or Username does not exist"},
                status=404
            )

        if not user.check_password(password):
            return Response(
                {"success": False, "message": "Incorrect password"},
                status=401
            )

        # Admin verification check (skip for superuser)
        if not user.is_superuser:
            if not hasattr(user, "profile") or not user.profile.is_verified:
                return Response(
                    {"success": False, "message": "User not verified by admin"},
                    status=403
                )

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        # Role determination
        if user.is_superuser:
            role = "ADMIN"
        else:
            role = "USER"

        return Response({
            "success": True,
            "message": "Login successful",
            "data": {
                "access": str(refresh.access_token),
                "refresh": str(refresh),
                "username": user.username,
                "email": user.email,
                "role": role,
                "user_id":user.id
            }
        }, status=200)

# ------------------- Current User Info -------------------
class MeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "user_id":user.id,
            "username": user.username,
            "email": user.email,
            "is_verified": hasattr(user, "profile") and user.profile.is_verified
        })



class ForgotPasswordAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        email = request.data.get("email")

        if not email:
            return Response(
                {"success": False, "message": "Email is required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.filter(email=email).first()
        if not user:
            return Response(
                {"success": False, "message": "Email not registered"},
                status=status.HTTP_404_NOT_FOUND
            )

        token = get_random_string(40)

        profile = user.profile
        profile.reset_token = token
        profile.reset_token_expiry = timezone.now() + timedelta(minutes=10)
        profile.save()

        return Response({
            "success": True,
            "message": "Reset token generated",
            "data": {
                "token": token
            }
        })
    



class ResetPasswordAPIView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        token = request.data.get("token")
        new_password = request.data.get("new_password")
        confirm_password = request.data.get("confirm_password")

        if not token or not new_password or not confirm_password:
            return Response(
                {"success": False, "message": "All fields are required"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if new_password != confirm_password:
            return Response(
                {"success": False, "message": "Passwords do not match"},
                status=status.HTTP_400_BAD_REQUEST
            )

        profile = UserProfile.objects.filter(reset_token=token).first()
        if not profile:
            return Response(
                {"success": False, "message": "Invalid token"},
                status=status.HTTP_400_BAD_REQUEST
            )

        if profile.reset_token_expiry < timezone.now():
            return Response(
                {"success": False, "message": "Token expired"},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = profile.user
        user.set_password(new_password)
        user.save()

        profile.reset_token = None
        profile.reset_token_expiry = None
        profile.save()

        return Response({
            "success": True,
            "message": "Password reset successful"
        })

class UserPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = "page_size"
    max_page_size = 10


@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminUser])
def list_users(request):
    users = (
        User.objects
        .select_related("profile")
        .prefetch_related("assigned_robots__robot")
        .order_by("id")
    )

    paginator = UserPagination()
    page = paginator.paginate_queryset(users, request)

    serializer = UserListSerializer(page, many=True)

    return paginator.get_paginated_response({
        "success": True,
        "message": "Users retrieved successfully",
        "data": serializer.data
    })



# @api_view(["PATCH"])
# @permission_classes([IsAuthenticated, IsAdminUser])
# def update_user(request, user_id):
#     try:
#         user = User.objects.select_related("profile").get(id=user_id)
#     except User.DoesNotExist:
#         return Response(
#             {"success": False, "message": "User not found"},
#             status=404
#         )

#     profile = user.profile

#     # Only allow profile updates
#     is_verified = request.data.get("is_verified")

#     if is_verified is not None:
#         profile.is_verified = is_verified
#         profile.save()

#     return Response({
#         "success": True,
#         "message": "User updated successfully",
#         "data": {
#             "user_id": user.id,
#             "username": user.username,
#             "is_verified": profile.is_verified
#         }
#     })

@api_view(["PATCH"])
@permission_classes([IsAuthenticated, IsAdminUser])
def update_user(request, user_id):
    try:
        user = User.objects.select_related("profile").get(id=user_id)
    except User.DoesNotExist:
        return Response(
            {"success": False, "message": "User not found"},
            status=404
        )

    profile = user.profile

    # User fields
    username = request.data.get("username")
    email = request.data.get("email")
    first_name = request.data.get("first_name")
    last_name = request.data.get("last_name")
    is_active = request.data.get("is_active")

    # Profile fields
    is_verified = request.data.get("is_verified")

    # Validate username uniqueness if being changed
    if username and username != user.username:
        if User.objects.filter(username=username).exists():
            return Response(
                {"success": False, "message": "Username already taken"},
                status=400
            )
        user.username = username

    if email and email != user.email:
        if User.objects.filter(email=email).exists():
            return Response(
                {"success": False, "message": "Email already in use"},
                status=400
            )
        user.email = email


    if is_active is not None:
        user.is_active = is_active

    user.save()

    if is_verified is not None:
        profile.is_verified = is_verified
        profile.save()

    return Response({
        "success": True,
        "message": "User updated successfully",
        "data": {
            "user_id": user.id,
            "username": user.username,
            "email": user.email,
            "is_active": user.is_active,
            "is_verified": profile.is_verified
        }
    })


class AssignUsersToRobotView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = RobotUserAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        robot_id = serializer.validated_data["robot_id"]
        user_ids = serializer.validated_data["user_ids"]

        robot = Robot.objects.get(robo_id=robot_id)

        assigned_users = []

        for user_id in user_ids:
            user = User.objects.get(id=user_id)

            obj, created = RobotUser.objects.get_or_create(
                robot=robot,
                user=user,
                defaults={"assigned_by": request.user}
            )
            assigned_users.append(user.username)

        return Response({
            "success": True,
            "message": "Users assigned successfully",
            "robot": robot.robo_id,
            "users": assigned_users
        }, status=status.HTTP_200_OK)
    

class RemoveUserFromRobot(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        robot_id = request.data.get("robot_id")
        user_id = request.data.get("user_id")

        RobotUser.objects.filter(
            robot__robo_id=robot_id,
            user_id=user_id
        ).delete()

        return Response({
            "success": True,
            "message": "User removed from robot"
        })

# class AssignRobotsToUserView(APIView):
#     permission_classes = [IsAdminUser]

#     def post(self, request):
#         serializer = UserRobotAssignSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         user_id = serializer.validated_data["user_id"]
#         robot_ids = serializer.validated_data["robot_ids"]

#         user = User.objects.get(id=user_id)
#         robots = Robot.objects.filter(robo_id__in=robot_ids)

#         assigned = []
#         already_assigned = []

#         for robot in robots:
#             obj, created = RobotUser.objects.get_or_create(
#                 user=user,
#                 robot=robot,
#                 defaults={"assigned_by": request.user}
#             )
#             if created:
#                 assigned.append(robot.robo_id)
#             else:
#                 already_assigned.append(robot.robo_id)

#         return Response(
#             {
#                 "success": True,
#                 "message": "Robots assignment processed",
#                 "user": user.username,
#                 "assigned_robots": assigned,
#                 "already_assigned": already_assigned
#             },
#             status=status.HTTP_200_OK
#         )





class AssignRobotsToUserView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):

        serializer = UserRobotAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data["user_id"]
        robot_ids = serializer.validated_data["robot_ids"]

        try:
            user = User.objects.get(id=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )

        robots = Robot.objects.filter(robo_id__in=robot_ids)
        channel_layer = get_channel_layer()

        assigned = []
        already_assigned = []

        for robot in robots:

            obj, created = RobotUser.objects.get_or_create(
                user=user,
                robot=robot,
                defaults={"assigned_by": request.user}
            )

            if created:
                assigned.append(robot.robo_id)

                event_data = {
                    "robo_id": robot.robo_id,
                    "action": "assigned",
                    "assigned_to": user.username,
                    "performed_by": request.user.username,
                    "message": f"Robot {robot.robo_id} assigned to {user.username}"
                }

                # 🔥 1️⃣ Send to robot device
                async_to_sync(channel_layer.group_send)(
                    f"robot_message_{robot.robo_id}",
                    {
                        "type": "robot_message",
                        "event": "robot_assigned",
                        "data": event_data
                    }
                )

                # 🔥 2️⃣ Send to global admin dashboard (if you use it)
                async_to_sync(channel_layer.group_send)(
                    "robots_group",
                    {
                        "type": "robots_event",
                        "event": "robot_status_updated",
                        "data": event_data
                    }
                )

                # 🔥 3️⃣ Send ONLY to that user's dashboard
                async_to_sync(channel_layer.group_send)(
                    f"robots_user_{user.id}",
                    {
                        "type": "robots_event",
                        "event": "robot_assigned",
                        "data": event_data
                    }
                )

            else:
                already_assigned.append(robot.robo_id)

        return Response(
            {
                "success": True,
                "message": "Robots assignment processed",
                "user": user.username,
                "assigned_robots": assigned,
                "already_assigned": already_assigned
            },
            status=status.HTTP_200_OK
        )
    
# class RemoveRobotsFromUserView(APIView):
#     permission_classes = [IsAdminUser]

#     def post(self, request):
#         serializer = UserRobotAssignSerializer(data=request.data)
#         serializer.is_valid(raise_exception=True)

#         user_id = serializer.validated_data["user_id"]
#         robot_ids = serializer.validated_data["robot_ids"]

#         deleted, _ = RobotUser.objects.filter(
#             user_id=user_id,
#             robot__robo_id__in=robot_ids
#         ).delete()

#         return Response(
#             {
#                 "success": True,
#                 "message": "Robots removed from user",
#                 "removed_count": deleted
#             },
#             status=status.HTTP_200_OK
#         )


class RemoveRobotsFromUserView(APIView):
    permission_classes = [IsAdminUser]

    def post(self, request):
        serializer = UserRobotAssignSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_id = serializer.validated_data["user_id"]
        robot_ids = serializer.validated_data["robot_ids"]

        user = User.objects.get(id=user_id)
        channel_layer = get_channel_layer()

        robot_users = RobotUser.objects.filter(
            user_id=user_id,
            robot__robo_id__in=robot_ids
        )

        robots = [ru.robot for ru in robot_users]

        robot_users.delete()

        for robot in robots:
            event_data = {
                "robo_id": robot.robo_id,
                "action": "unassigned",
                "removed_from": user.username,
                "performed_by": request.user.username,
                "message": f"Robot {robot.robo_id} removed from {user.username}"
            }

            # 🔥 Individual group
            async_to_sync(channel_layer.group_send)(
                f"robot_message_{robot.robo_id}",
                {
                    "type": "robot_message",
                    "event": "robot_unassigned",
                    "data": event_data
                }
            )

            # 🔥 Global group
            async_to_sync(channel_layer.group_send)(
                f"robots_user_{user_id}",
                {
                    "type": "robots_event",
                    "event": "robot_unassigned",
                    "data": event_data
                }
            )

        return Response(
            {
                "success": True,
                "message": "Robots removed from user",
                "removed_count": len(robots)
            },
            status=status.HTTP_200_OK
        )

class CustomTokenVerifyView(TokenVerifyView):

    def post(self, request, *args, **kwargs):
        response = super().post(request, *args, **kwargs)

        # If token is valid, super() returns 200
        return Response(
            {
                "status": True,
                "message": "Token is valid",
            },
            status=status.HTTP_200_OK
        )