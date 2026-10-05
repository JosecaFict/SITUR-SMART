from django.urls import path

from .views import (
    AssistantChatView,
    AssistantStatusView,
    AssistantVoiceView,
    RecommendationListView,
)

urlpatterns = [
    path("asistente/estado/", AssistantStatusView.as_view(), name="assistant-status"),
    path("asistente/chat/", AssistantChatView.as_view(), name="assistant-chat"),
    path("asistente/voz/", AssistantVoiceView.as_view(), name="assistant-voice"),
    path("asistente/recomendaciones/", RecommendationListView.as_view(), name="assistant-recommendations"),
]
