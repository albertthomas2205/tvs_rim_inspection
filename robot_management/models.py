
# Create your models here.
from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError


class RobotQuerySet(models.QuerySet):
    def active(self):
        return self.filter(is_active=True)


class RobotManager(models.Manager):
    def get_queryset(self):
        return RobotQuerySet(self.model, using=self._db).active()


class Robot(models.Model):

       # Robot Type / Purpose
    ROBOT_TYPE_CHOICES = [
        ("INSPECTION", "Inspection"),
        ("PICK_DROP", "Pick and Drop"),
    ]

    robot_type = models.CharField(
        max_length=20,
        choices=ROBOT_TYPE_CHOICES,
        default="INSPECTION",
        help_text="Type of robot (inspection or pick & drop)"
    )
    

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

    speak_start = models.BooleanField(default=False)


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
    updated_by  = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="robots_updated"
    )


    def soft_delete(self):
        self.is_deleted = True
        self.is_active = False
        self.save(update_fields=["is_deleted", "is_active"])

    def __str__(self):
        return f"{self.name} ({self.robo_id})"
    





class RobotLog(models.Model):

    robot = models.ForeignKey(
        Robot,
        on_delete=models.CASCADE,
        related_name="logs"
    )

    log_data = models.JSONField(
        help_text="Raw robot logs stored as JSON"
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "robot_logs"
        indexes = [
            models.Index(fields=["created_at"]),
        ]

    def __str__(self):
        return f"Log for {self.robot.robo_id} at {self.created_at}"
    



def validate_stcm_file(value):
    if not value.name.endswith(".stcm"):
        raise ValidationError("Only .stcm map files are allowed")


class RobotMap(models.Model):

    robot = models.ForeignKey(
        Robot,
        on_delete=models.CASCADE,
        related_name="maps"
    )

    map_file = models.FileField(
        upload_to="robot_maps/",
        validators=[validate_stcm_file],
        help_text="STCM map file for robot"
    )


    is_active = models.BooleanField(
        default=True,
        help_text="Currently active map"
    )

    uploaded_at = models.DateTimeField(auto_now_add=True)

    uploaded_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name="uploaded_maps"
    )

    class Meta:
        db_table = "robot_maps"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"Map {self.version} for {self.robot.robo_id}"
    

class RobotLocation(models.Model):
    robot = models.OneToOneField(
        Robot,
        on_delete=models.CASCADE,
        related_name="location"
    )
    location_data = models.JSONField()
    updated_at = models.DateTimeField(auto_now=True)



class RobotNavigation(models.Model):

    NAVIGATION_MODE_CHOICES = [
        ('autonomous', 'Autonomous'),
        ('stationary', 'Stationary'),
    ]

    NAVIGATION_STYLE_CHOICES = [
        ('free', 'Free'),
        ('strict', 'Strict'),
        ('strict_with_autonomous', 'Strict With Autonomous'),
    ]

    # ✅ One-to-One relation (each robot has only one navigation config)
    robot = models.OneToOneField(
        'Robot',               # or Robot if already imported
        on_delete=models.CASCADE,
        related_name='navigation'
    )

    navigation_mode = models.CharField(
        max_length=20,
        choices=NAVIGATION_MODE_CHOICES
    )

    navigation_style = models.CharField(
        max_length=30,
        choices=NAVIGATION_STYLE_CHOICES,
        null=True,
        blank=True
    )

    updated_at = models.DateTimeField(auto_now=True)

    def clean(self):
        """
        Enforce navigation rules
        """
        if self.navigation_mode == 'stationary' and self.navigation_style is not None:
            raise ValidationError({
                "navigation_style": "Navigation style must be null when mode is stationary."
            })

        if self.navigation_mode == 'autonomous' and self.navigation_style is None:
            raise ValidationError({
                "navigation_style": "Navigation style is required when mode is autonomous."
            })

    def save(self, *args, **kwargs):
        self.full_clean()   # 🔒 Always enforce validation
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.robot} - {self.navigation_mode}"
