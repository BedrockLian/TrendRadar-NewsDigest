from django.contrib.auth import views as auth
from django.urls import path

from . import views
from .auth import PrivateLoginView

urlpatterns = [
    path("login/", PrivateLoginView.as_view(), name="login"),
    path("logout/", auth.LogoutView.as_view(), name="logout"),
    path("health/", views.health),
    path("", views.home, name="home"),
    path("news/", views.news, name="news"),
    path("news/<int:pk>/", views.article, name="article"),
    path("briefs/", views.briefs, name="briefs"),
    path("briefs/<int:pk>/", views.briefs, name="brief"),
    path("events/", views.events, name="events"),
    path("events/new/", views.edit_event, name="event-new"),
    path("events/<int:pk>/", views.events, name="event"),
    path("events/<int:pk>/edit/", views.edit_event, name="event-edit"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("settings/", views.preferences, name="settings"),
    path("settings/feed/new/", views.edit_feed, name="feed-new"),
    path("settings/feed/<int:pk>/", views.edit_feed, name="feed-edit"),
    path("action/", views.action, name="action"),
    path("api/v1/news/", views.api_news),
    path("api/v1/stats/", views.api_stats),
    path("api/v1/briefs/", views.api_briefs),
    path("api/v1/events/", views.api_events),
    path("api/v1/jobs/<uuid:pk>/", views.api_job),
    path("api/v1/jobs/<uuid:pk>/stream/", views.job_stream),
    path("api/v1/answer/", views.api_answer),
    path("api/v1/actions/", views.action),
    path("fragments/queue/", views.queue_fragment),
]
