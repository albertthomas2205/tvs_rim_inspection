# tasks.py

from celery import shared_task
from django.utils import timezone
from .models import Schedule
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer


@shared_task
def set_status_processing(schedule_id):
    try:
        schedule = Schedule.objects.select_related("robot").get(id=schedule_id)
        schedule.status = "processing"
        schedule.save()

        channel_layer = get_channel_layer()
        group_name = f"robot_message_{schedule.robot.robo_id}"
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "robot_message",  # must match consumer method
                "event": "schedule_updated",
                "data": {
                    "status": schedule.status,
                },
            }
        )

    except Schedule.DoesNotExist:
        pass


@shared_task
def set_status_completed(schedule_id):
    try:
        schedule = Schedule.objects.select_related("robot").get(id=schedule_id)
        schedule.status = "completed"
        schedule.save()

        channel_layer = get_channel_layer()
        group_name = f"robot_message_{schedule.robot.robo_id}"
        print(group_name)

        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                "type": "robot_message",
                "event": "schedule_updated",
                "data": {
                    "status": schedule.status,
                },
            }
        )

    except Schedule.DoesNotExist:
        pass
