import os
from pathlib import Path
from urllib.parse import urlparse, unquote

BASE_DIR = Path(__file__).resolve().parents[2]
DEBUG = os.getenv("RADAR_DEBUG", "0") == "1"
SECRET_KEY = os.getenv("RADAR_SECRET_KEY", "")
if not SECRET_KEY:
    if not DEBUG:
        raise RuntimeError("RADAR_SECRET_KEY must be set")
    SECRET_KEY = "local-development-only-not-for-production"
ALLOWED_HOSTS = os.getenv("RADAR_HOSTS", "localhost,127.0.0.1,testserver").split(",")
CSRF_TRUSTED_ORIGINS = [x for x in os.getenv("RADAR_ORIGINS", "").split(",") if x]
INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "app.core",
    "app.news",
    "app.briefs",
    "app.events",
    "app.ai",
]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "app.core.middleware.ApiAuthenticationMiddleware",
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "app.core.urls"
ASGI_APPLICATION = "app.core.asgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "app/ui/templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ]
        },
    }
]
db = urlparse(os.getenv("DATABASE_URL", "postgresql://radar:radar@127.0.0.1:55432/radar"))
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": db.path.lstrip("/"),
        "USER": unquote(db.username or ""),
        "PASSWORD": unquote(db.password or ""),
        "HOST": db.hostname or "127.0.0.1",
        "PORT": db.port or 5432,
        "OPTIONS": {
            "pool": {"min_size": 0, "max_size": int(os.getenv("RADAR_DB_POOL", "3"))},
            "options": "-c statement_timeout=30000 -c lock_timeout=5000",
        },
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
TIME_ZONE = "Asia/Shanghai"
USE_TZ = True
LANGUAGE_CODE = "zh-hans"
FORMS_URLFIELD_ASSUME_HTTPS = True
STATIC_URL = "/static/"
STATIC_ROOT = Path(os.getenv("RADAR_STATIC_ROOT", str(BASE_DIR / ".local/static")))
STATICFILES_DIRS = [BASE_DIR / "app/ui/static"]
LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/login/"
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SESSION_COOKIE_AGE = 86400 * 7
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000 if not DEBUG else 0
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_MEMORY_SIZE = 1024 * 1024
AI_KEY = os.getenv("DEEPSEEK_API_KEY", "")
AI_BASE_URL = os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
DATA_PATH = Path(os.getenv("RADAR_DATA_PATH", str(BASE_DIR / ".local")))
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": "INFO"},
}
