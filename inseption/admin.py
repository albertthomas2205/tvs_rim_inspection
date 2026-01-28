from django.contrib import admin
from .models import Inspection, RimType,Schedule

# Register your models here.

@admin.register(RimType)
class RimTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)



@admin.register(Schedule)
class ScheduleAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "robot",
        "location",
        "scheduled_date",
        "scheduled_time",
        "end_time",
        "status",
        "is_canceled",
        "created_at",
    )

    list_filter = (
        "status",
        "is_canceled",
        "scheduled_date",
        "robot",
    )

    ordering = ("-id",)

    readonly_fields = (
        "created_at",
        "end_time",
    )