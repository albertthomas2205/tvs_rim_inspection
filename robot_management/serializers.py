from rest_framework import serializers
from .models import Robot,RobotMap,RobotLocation,RobotNavigation,CalibrateHand
class RobotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Robot
        fields = "__all__"
        read_only_fields = (
            "id", "created_at", "updated_at",
            "is_deleted", "created_by", "updated_by"
        )


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
        exclude = ("robot",)

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