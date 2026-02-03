from rest_framework import serializers
from .models import Robot,RobotMap,RobotLocation,RobotNavigation,CalibrateHand,Profile
from django.contrib.auth.models import User


class AssignedUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ["id", "username", "email"]

class RobotSerializer(serializers.ModelSerializer):
    schedule_summary = serializers.SerializerMethodField()
    inspection_summary = serializers.SerializerMethodField()
    assigned_users = serializers.SerializerMethodField()

    class Meta:
        model = Robot
        fields = [
            "id",

            # grouped summaries
            "schedule_summary",
            "inspection_summary",

            # robot fields
            "robot_type",
            "name",
            "robo_id",
            "model_number",
            "local_ip",
            "status",
            "emergency",
            "speak_start",
            "inspection_status",
            "last_inspected_at",
            "is_active",
            "created_at",
            "updated_at",
            "created_by",
            "updated_by",
            "assigned_users"
        ]

    def get_schedule_summary(self, obj):
        return {
            "total": obj.total_schedules,
            "scheduled": obj.scheduled_count,
            "processing": obj.processing_count,
            "completed": obj.completed_count,
        }

    def get_inspection_summary(self, obj):
        return {
            "total": obj.total_inspections,
            "defected": obj.total_defected,
            "non_defected": obj.total_non_defected,
            "approved": obj.approved_count,
            "human_verified": obj.human_verified_count,
            "pending_verification": obj.pending_verification_count,
        }
    
    def get_assigned_users(self, obj):
        request = self.context.get("request")

        # 🔐 Only superuser can see assigned users
        if not request or not request.user.is_superuser:
            return None

        users = User.objects.filter(
            assigned_robots__robot=obj
        ).distinct()

        return AssignedUserSerializer(users, many=True).data

class RobotMapSerializer(serializers.ModelSerializer):
    uploaded_by = serializers.ReadOnlyField(source="uploaded_by.username")
    robot_id = serializers.ReadOnlyField(source="robot.id")

    # ✅ WRITEABLE field (for upload)
    map_file = serializers.FileField(write_only=True)

    # ✅ READ-ONLY URL for frontend
    map_file_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = RobotMap
        fields = [
            "id",
            "robot",
            "robot_id",
            "map_file",        # upload only
            "map_file_url",    # response only
            "is_active",
            "uploaded_at",
            "uploaded_by",
        ]
        read_only_fields = ["uploaded_at", "uploaded_by"]

    def get_map_file_url(self, obj):
        request = self.context.get("request")
        if obj.map_file and request:
            return request.build_absolute_uri(obj.map_file.url)
        return None



class RobotLocationSerializer(serializers.ModelSerializer):
    class Meta:
        model = RobotLocation
        fields = ["robot", "location_data", "updated_at"]
        read_only_fields = ["updated_at", "robot"]




class RobotNavigationUpdateSerializer(serializers.ModelSerializer):
    navigation_style = serializers.ChoiceField(
        choices=RobotNavigation.NAVIGATION_STYLE_CHOICES,
        allow_null=True,
        required=False
    )

    class Meta:
        model = RobotNavigation
        fields = ["navigation_mode", "navigation_style"]

    def validate(self, attrs):
        mode = attrs.get(
            "navigation_mode",
            self.instance.navigation_mode
        )
        style = attrs.get(
            "navigation_style",
            self.instance.navigation_style
        )

        if mode == "stationary":
            if style is not None:
                raise serializers.ValidationError({
                    "navigation_style": "Must be null when navigation_mode is stationary."
                })

        elif mode == "autonomous":
            if style is None:
                raise serializers.ValidationError({
                    "navigation_style": "Navigation style is required when navigation_mode is autonomous."
                })

        return attrs


class EmergencySerializer(serializers.ModelSerializer):
    class Meta:
        model = Robot
        fields = ['emergency']

class SpeakStartSerializer(serializers.ModelSerializer):
    class Meta:
        model = Robot
        fields = ['speak_start']


class CalibrateHandSerializer(serializers.ModelSerializer):

    class Meta:
        model = CalibrateHand
        fields = "__all__"

    def validate(self, data):
        """
        Rules:
        - Hand activation does NOT require points
        - Points are optional
        - If a point is provided, it must be a JSON object
        """

        point_fields = {
            "left_point_one": data.get("left_point_one"),
            "left_point_two": data.get("left_point_two"),
            "left_point_three": data.get("left_point_three"),
            "right_point_one": data.get("right_point_one"),
            "right_point_two": data.get("right_point_two"),
            "right_point_three": data.get("right_point_three"),
        }

        for field_name, value in point_fields.items():
            # validate only if point is being sent
            if value is not None:
                if not isinstance(value, dict):
                    raise serializers.ValidationError({
                        field_name: "Must be a valid JSON object"
                    })

        return data
    


class ProfileSerializer(serializers.ModelSerializer):

    class Meta:
        model = Profile
        fields = [
            "id",
            "name",
            "is_active",
            "created_at",
            "updated_at"
        ]
        read_only_fields = ["id", "created_at", "updated_at"]