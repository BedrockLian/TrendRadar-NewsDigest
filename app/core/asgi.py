import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "app.core.settings")
from django.core.asgi import get_asgi_application

application = get_asgi_application()
