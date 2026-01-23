from django.test import TestCase

# Create your tests here.

from django.db import models
from django.contrib.auth.models import User


class Robot(models.Model):

    # Identity
    name = models.CharField(max_length=150)
    robo_id = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique robot identifier"
    )
    model_number = models.CharField(null=True,blank=True,max_length=100)

    # Network
    local_ip = models.GenericIPAddressField(
        protocol="IPv4",
        null=True,
        blank=True,
        help_text="Local network IP of the robot"
    )

    # Lifecycle
    status = models.CharField(
        max_length=20,
        choices=[
            ("AVAILABLE", "Available"),
            ("SOLD", "Sold"),
            ("IN_TRANSIT", "In Transit"),
            ("MAINTENANCE", "Maintenance"),
        ],
        default="AVAILABLE"
    )

    # Emergency
    emergency = models.BooleanField(
        default=False,
        help_text="Indicates emergency stop or critical state"
    )

   

    # Inspection
    inspection_status = models.CharField(
        max_length=20,
        choices=[
            ("PENDING", "Pending"),
            ("PASSED", "Passed"),
            ("FAILED", "Failed"),
        ],
        default="PENDING"
    )
    last_inspected_at = models.DateTimeField(null=True, blank=True)

    # Meta
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="robots_created"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.robot_id})"
