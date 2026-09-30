from django.urls import path

from .views import CommandView, SpeechView, VoiceView, WakeView

app_name = 'liza'

urlpatterns = [
    path('command/', CommandView.as_view(), name='command'),
    path('voice/', VoiceView.as_view(), name='voice'),
    path('wake/', WakeView.as_view(), name='wake'),
    path('speech/', SpeechView.as_view(), name='speech'),
]