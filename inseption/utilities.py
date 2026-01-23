import os
import shutil
from django.conf import settings
from django.utils.text import slugify


def get_unique_path(base_dir, filename):
    name, ext = os.path.splitext(filename)
    counter = 1
    unique_filename = filename

    while os.path.exists(os.path.join(base_dir, unique_filename)):
        unique_filename = f"{name}_{counter}{ext}"
        counter += 1

    return os.path.join(base_dir, unique_filename)


def save_false_detection_image(inspection):
    # Only for false detected cases
    if not inspection.image or not inspection.correct_label or not inspection.false_detected:
        return

    # Decide folder based on approval
    approval_dir = "approved" if inspection.is_approved else "not_approved"

    base_dir = os.path.join(
        settings.MEDIA_ROOT,
        "human_feedback_data",
        approval_dir
    )
    os.makedirs(base_dir, exist_ok=True)

    src_path = inspection.image.path

    # Keep original extension
    _, ext = os.path.splitext(src_path)

    # Safe label-based filename
    safe_label = slugify(inspection.correct_label)
    filename = f"{safe_label}{ext}"

    # Unique path
    dst_path = get_unique_path(base_dir, filename)

    shutil.copy(src_path, dst_path)
