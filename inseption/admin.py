from django.contrib import admin
from .models import Inspection, RimType

# Register your models here.

@admin.register(RimType)
class RimTypeAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
