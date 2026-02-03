from django.contrib.auth.models import User
from rest_framework import serializers
from .models import UserProfile
from robot_management.models import Robot

class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ["username", "email", "password"]

    def create(self, validated_data):
        user = User.objects.create_user(
            username=validated_data["username"],
            email=validated_data["email"],
            password=validated_data["password"],
            is_active=True
        )
        # Create profile automatically
        from .models import UserProfile
        UserProfile.objects.create(user=user)
        return user



class UserProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserProfile
        fields = ["is_verified"]

class AssignedRobotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Robot
        fields = ["id", "robo_id", "name"]  # adjust fields if needed


# class UserListSerializer(serializers.ModelSerializer):
#     profile = UserProfileSerializer()

#     class Meta:
#         model = User
#         fields = [
#             "id",
#             "username",
#             "email",
#             "is_active",
#             "profile",
#         ]

class UserListSerializer(serializers.ModelSerializer):
    assigned_robots = serializers.SerializerMethodField()
    profile = UserProfileSerializer()
    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "is_active",
            "assigned_robots",
            "profile",
        ]

    def get_assigned_robots(self, obj):
        robots = Robot.objects.filter(
            assigned_users__user=obj
        ).distinct()

        return AssignedRobotSerializer(robots, many=True).data


class RobotUserAssignSerializer(serializers.Serializer):
    robot_id = serializers.CharField()
    user_ids = serializers.ListField(
        child=serializers.IntegerField(),
        allow_empty=False
    )

class UserRobotAssignSerializer(serializers.Serializer):
    user_id = serializers.IntegerField()
    robot_ids = serializers.ListField(
        child=serializers.CharField(),
        allow_empty=False
    )
