from django.contrib.auth.models import User
from django.db import models
from django.conf import settings

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    is_verified = models.BooleanField(default=False)  # Admin verifies user in Django admin

    reset_token = models.CharField(max_length=255, null=True, blank=True)
    reset_token_expiry = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return f"{self.user.username} | Verified={self.is_verified}"




class RobotUser(models.Model):
    robot = models.ForeignKey(
        "robot_management.Robot",   # ✅ string reference
        on_delete=models.CASCADE,
        related_name="assigned_users"
    )

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,   # ✅ safe user reference
        on_delete=models.CASCADE,
        related_name="assigned_robots"
    )

    assigned_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,   # ✅ admin / superuser
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="robot_assignments_done"
    )

    assigned_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("robot", "user")
        verbose_name = "Robot User Assignment"
        verbose_name_plural = "Robot User Assignments"

    def __str__(self):
        return f"{self.user} → {self.robot}"