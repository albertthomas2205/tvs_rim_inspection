# serializers.py

from rest_framework import serializers
from .models import Schedule, Inspection,RimType

class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = "__all__"


class InspectionSerializer(serializers.ModelSerializer):
    class Meta:
        model = Inspection
        fields = "__all__"

class InspectionHumanVerifySerializer(serializers.ModelSerializer):
    class Meta:
        model = Inspection
        fields = [
            "false_detected",
            "is_approved",
            "correct_label",
            "user_description",
        ]

    def validate(self, attrs):
        false_detected = attrs.get(
            "false_detected",
            self.instance.false_detected if self.instance else False
        )

        is_approved = attrs.get(
            "is_approved",
            self.instance.is_approved if self.instance else None
        )

        correct_label = attrs.get(
            "correct_label",
            self.instance.correct_label if self.instance else None
        )

        user_description = attrs.get("user_description")

        # ---------------- AI CORRECT ----------------
        if false_detected is False:
            # Auto approve
            attrs["is_approved"] = True
            attrs["correct_label"] = None
            # description is OPTIONAL here
            return attrs

        # ---------------- AI WRONG ----------------
        if false_detected is True:
            # Description REQUIRED
            if not user_description:
                raise serializers.ValidationError({
                    "description": "Description is required when false_detected is true."
                })

            # Correct label REQUIRED
            if not correct_label:
                raise serializers.ValidationError({
                    "correct_label": "Correct label is required for false detections."
                })

            # Approval decision REQUIRED
            if is_approved is None:
                raise serializers.ValidationError({
                    "is_approved": "Approval decision is required for false detections."
                })

        return attrs


from .models import EmergencyStop

class EmergencyStopSerializer(serializers.ModelSerializer):
    class Meta:
        model = EmergencyStop
        fields = ["id", "is_emergency_stop", "updated_at"]



class ScheduleDateFilterSerializer(serializers.Serializer):
    scheduled_date = serializers.DateField()

class ScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = Schedule
        fields = "__all__"



class ScheduleDateRangeFilterSerializer(serializers.Serializer):
    start_date = serializers.DateField()
    end_date = serializers.DateField()

    def validate(self, data):
        if data["start_date"] > data["end_date"]:
            raise serializers.ValidationError(
                "start_date must be less than or equal to end_date"
            )
        return data
    


class RimTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = RimType
        fields = [
            "id",
            "name",
            "description",
            "is_active",
            "created_at",
        ]
        read_only_fields = ["id", "created_at"]