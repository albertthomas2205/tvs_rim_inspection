from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework.exceptions import AuthenticationFailed, NotAuthenticated
from rest_framework_simplejwt.exceptions import TokenError, InvalidToken

def custom_exception_handler(exc, context):
    """
    Custom DRF exception handler with:
    - success
    - message (simple)
    - status
    - error (machine-readable)
    """

    response = exception_handler(exc, context)

    if response is not None:
        # Default structure
        status_code = response.status_code
        message = ""
        error_code = "error"

        # Handle JWT / Authentication errors
        if isinstance(exc, (AuthenticationFailed, NotAuthenticated, InvalidToken, TokenError)):
            status_code = 401
            error_code = "invalid_token"

            # Simple message extraction
            try:
                # DRF often wraps detail in dict / list
                detail = exc.detail if hasattr(exc, "detail") else str(exc)
                if isinstance(detail, dict):
                    # Drill down to first message
                    first_key = next(iter(detail))
                    val = detail[first_key]
                    if isinstance(val, list):
                        message = str(val[0])
                    else:
                        message = str(val)
                elif isinstance(detail, list):
                    message = str(detail[0])
                else:
                    message = str(detail)
            except Exception:
                message = "Invalid token"

        # Handle other DRF errors
        else:
            message = getattr(exc, "detail", str(exc))
            error_code = "error"

        response.data = {
            "success": False,
            "message": message,
            "status": status_code,
            "error": error_code
        }

    else:
        # Fallback for unhandled exceptions
        response = Response({
            "success": False,
            "message": str(exc),
            "status": 500,
            "error": "server_error"
        }, status=500)

    return response
