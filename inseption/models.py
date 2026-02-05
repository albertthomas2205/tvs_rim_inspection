from django.db import models
from datetime import timedelta, datetime
from robot_management.models import Robot

# Create your models here.


class Schedule(models.Model):
    STATUS_CHOICES = [
        ('scheduled', 'Scheduled'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
    ]


    robot = models.ForeignKey(
        Robot,
        on_delete=models.CASCADE,
        related_name="schedules",
        default=1
    )

    location = models.CharField(max_length=150)
    scheduled_date = models.DateField()
    scheduled_time = models.TimeField()
    end_time = models.TimeField(null=True, blank=True)
    is_canceled = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="scheduled")
    created_at = models.DateTimeField(auto_now_add=True)

    # def save(self, *args, **kwargs):
    #     # Auto set end_time = scheduled_time + 1 hour
    #     if self.scheduled_time and not self.end_time:
    #         dt = datetime.combine(self.scheduled_date, self.scheduled_time)
    #         self.end_time = (dt + timedelta(hours=1)).time()

    #     super().save(*args, **kwargs)

    def __str__(self):
        return f"Schedule {self.id} at {self.location}"
    

class RimType(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Inspection(models.Model):
    schedule = models.ForeignKey(Schedule, on_delete=models.CASCADE, related_name="inspections")



    rim_type = models.ForeignKey(
        RimType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="inspections"
    )

    rim_id = models.CharField(max_length=50,unique=True)

    image = models.ImageField(upload_to="rim_photos/", null=True, blank=True)
    is_defect = models.BooleanField(default=False)

    inspected_at = models.DateTimeField(auto_now_add=True)

     # ---------------- HUMAN VERIFICATION ----------------
    is_human_verified = models.BooleanField(default=False)

    # If AI was wrong
    false_detected = models.BooleanField(default=False)

    description = models.TextField(null=True, blank=True)

    user_description = models.TextField(null=True, blank=True)

    is_approved = models.BooleanField(default=False)

    # Required ONLY when false_detected = True
    correct_label = models.CharField(
        max_length=100,
        null=True,
        blank=True
    )

    class Meta:
        unique_together = ("schedule", "rim_id")
    def __str__(self):
        return f"Inspection {self.rim_id} -> Schedule {self.schedule.id}"
    
    

class SpeakConfig(models.Model):
    value = models.JSONField(default=dict) 




class EmergencyStop(models.Model):
    is_emergency_stop = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    robot = models.OneToOneField(
        Robot,
        on_delete=models.CASCADE,
        related_name="emergency_stop"
    )

    def save(self, *args, **kwargs):
        self.pk = 1  # FORCE single row
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Emergency Stop: {'ON' if self.is_emergency_stop else 'OFF'}"


