from django.urls import path
from .views import RegisterAPIView, LoginAPIView, MeAPIView,ForgotPasswordAPIView,ResetPasswordAPIView,list_users,update_user
from rest_framework_simplejwt.views import TokenRefreshView


urlpatterns = [
    path("register/", RegisterAPIView.as_view()),
    path("login/", LoginAPIView.as_view()),
    path("me/", MeAPIView.as_view()),

    # JWT refresh
    path("token/refresh/", TokenRefreshView.as_view()),

    path("forgot-password/", ForgotPasswordAPIView.as_view()),
    path("reset-password/", ResetPasswordAPIView.as_view()),

    path("users/", list_users, name="users-list"),
    path("users/<int:user_id>/", update_user, name="user-update"),
    


    
]
