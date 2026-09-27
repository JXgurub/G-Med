from django.urls import path
from .views import AnalysisUploadView, AnalysisListView, AnalysisDetailView

urlpatterns = [
    path('upload/', AnalysisUploadView.as_view(), name='ai-doctor-upload'),
    path('analyses/', AnalysisListView.as_view(), name='ai-doctor-list'),
    path('analyses/<uuid:pk>/', AnalysisDetailView.as_view(), name='ai-doctor-detail'),
]
