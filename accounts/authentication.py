from rest_framework_simplejwt.authentication import JWTAuthentication
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.token_blacklist.models import OutstandingToken, BlacklistedToken
from django.utils import timezone


class BlockAwareJWTAuthentication(JWTAuthentication):

    def get_user(self, validated_token):
        user = super().get_user(validated_token)

        # Superuser bypasses all checks
        if user.is_superuser:
            return user

        try:
            profile = user.profile
        except Exception:
            raise AuthenticationFailed('User profile not found.')

        if not profile.is_verified:
            # Blacklist ALL active refresh + access tokens immediately
            tokens = OutstandingToken.objects.filter(
                user=user,
                expires_at__gt=timezone.now()
            )
            for token in tokens:
                BlacklistedToken.objects.get_or_create(token=token)

            raise AuthenticationFailed(
                'Your account is not verified. Please contact admin.'
            )

        return user


## What Happens Now

# Unverified user makes any request
#         ↓
# is_verified = False detected
#         ↓
# All active tokens (access + refresh) → blacklisted in DB instantly
#         ↓
# 401 returned → "Your account is not verified. Please contact admin."
#         ↓
# User tries to refresh → 401 Token is blacklisted
#         ↓
# Fully locked out 