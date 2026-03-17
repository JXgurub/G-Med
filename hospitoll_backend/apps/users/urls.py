from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from .views import (
    EmailTokenObtainPairView,
    PatientTokenObtainView,
    ProfileView,
    ChangePasswordView,
    PasswordResetRequestView,
    PasswordResetVerifyView,
    PasswordResetConfirmView,
    DoctorPasswordResetRequestView,
    DoctorPasswordResetVerifyView,
    DoctorPasswordResetConfirmView,
    ClinicPasswordResetRequestView,
    ClinicPasswordResetVerifyView,
    ClinicPasswordResetConfirmView,
    PharmacyPasswordResetRequestView,
    PharmacyPasswordResetVerifyView,
    PharmacyPasswordResetConfirmView,
)

urlpatterns = [
    path('token/', EmailTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('patient-token/', PatientTokenObtainView.as_view(), name='patient_token_obtain'),
    path('profile/', ProfileView.as_view(), name='user_profile'),
    path('change-password/', ChangePasswordView.as_view(), name='change_password'),
    path('password-reset/request/', PasswordResetRequestView.as_view(), name='password_reset_request'),
    path('password-reset/verify/', PasswordResetVerifyView.as_view(), name='password_reset_verify'),
    path('password-reset/confirm/', PasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('doctor-password-reset/request/', DoctorPasswordResetRequestView.as_view(), name='doctor_password_reset_request'),
    path('doctor-password-reset/verify/', DoctorPasswordResetVerifyView.as_view(), name='doctor_password_reset_verify'),
    path('doctor-password-reset/confirm/', DoctorPasswordResetConfirmView.as_view(), name='doctor_password_reset_confirm'),
    path('clinic-password-reset/request/', ClinicPasswordResetRequestView.as_view(), name='clinic_password_reset_request'),
    path('clinic-password-reset/verify/', ClinicPasswordResetVerifyView.as_view(), name='clinic_password_reset_verify'),
    path('clinic-password-reset/confirm/', ClinicPasswordResetConfirmView.as_view(), name='clinic_password_reset_confirm'),
    path('pharmacy-password-reset/request/', PharmacyPasswordResetRequestView.as_view(), name='pharmacy_password_reset_request'),
    path('pharmacy-password-reset/verify/', PharmacyPasswordResetVerifyView.as_view(), name='pharmacy_password_reset_verify'),
    path('pharmacy-password-reset/confirm/', PharmacyPasswordResetConfirmView.as_view(), name='pharmacy_password_reset_confirm'),
]
