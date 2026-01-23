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
from .models import UserProfile
from rest_framework.decorators import api_view, permission_classes
from .serializers import UserListSerializer
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
                "role": role
            }
        }, status=200)

# ------------------- Current User Info -------------------
class MeAPIView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        return Response({
            "userid":user.id,
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




@api_view(["GET"])
@permission_classes([IsAuthenticated, IsAdminUser])
def list_users(request):
    users = User.objects.select_related("profile").all()
    serializer = UserListSerializer(users, many=True)

    return Response({
        "success": True,
        "message": "Users retrieved successfully",
        "data": serializer.data
    })



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

    # Only allow profile updates
    is_verified = request.data.get("is_verified")

    if is_verified is not None:
        profile.is_verified = is_verified
        profile.save()

    return Response({
        "success": True,
        "message": "User updated successfully",
        "data": {
            "user_id": user.id,
            "username": user.username,
            "is_verified": profile.is_verified
        }
    })
