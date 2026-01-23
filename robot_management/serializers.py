from rest_framework import serializers
from .models import Robot,RobotMap,RobotLocation
class RobotSerializer(serializers.ModelSerializer):
    class Meta:
        model = Robot
        fields = "__all__"
        read_only_fields = (
            "id", "created_at", "updated_at",
            "is_deleted", "created_by", "updated_by"
        )



# class RobotMapSerializer(serializers.ModelSerializer):
#     uploaded_by = serializers.ReadOnlyField(source="uploaded_by.username")
#     robot_id = serializers.ReadOnlyField(source="robot.id")
#     map_file = serializers.SerializerMethodField()

#     class Meta:
#         model = RobotMap
#         fields = [
#             "id",
#             "robot",
#             "robot_id",
#             "map_file",
#             "is_active",
#             "uploaded_at",
#             "uploaded_by",
#         ]
#         read_only_fields = ["uploaded_at", "uploaded_by"]
    
#     def get_map_file(self, obj):
#         request = self.context.get("request")
#         if obj.map_file and request:
#             return request.build_absolute_uri(obj.map_file.url)
#         return None


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