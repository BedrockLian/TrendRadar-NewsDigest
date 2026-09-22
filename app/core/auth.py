from datetime import timedelta

from django.contrib.auth.views import LoginView
from django.db import transaction
from django.http import HttpResponse
from django.utils import timezone

from app.news.services import digest

from .models import LoginAttempt


class PrivateLoginView(LoginView):
    template_name = "login.html"

    def post(self, request, *args, **kwargs):
        identity = request.META.get("HTTP_X_REAL_IP", request.META.get("REMOTE_ADDR", "unknown"))
        key = digest(identity)
        with transaction.atomic():
            attempt, _ = LoginAttempt.objects.get_or_create(key=key)
            attempt = LoginAttempt.objects.select_for_update().get(pk=key)
            if attempt.since < timezone.now() - timedelta(minutes=15):
                attempt.since, attempt.count = timezone.now(), 0
            if attempt.count >= 10:
                response = HttpResponse("登录尝试过多，请15分钟后再试。", status=429)
                response["Retry-After"] = "900"
                return response
            attempt.count += 1
            attempt.save()
        response = super().post(request, *args, **kwargs)
        if request.user.is_authenticated:
            LoginAttempt.objects.filter(pk=key).delete()
        return response
