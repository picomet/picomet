from django.conf import settings
from django.urls import path

from picomet import consumers

urlpatterns = []

if settings.DEBUG:
    urlpatterns += [
        path("ws/hmr", consumers.HmrConsumer.as_asgi()),
    ]
