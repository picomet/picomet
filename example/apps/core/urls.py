from django.urls import path

from core import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("profile", views.profile, name="profile"),
    path("settings", views.settings, name="settings"),
    path("api/signup", views.signup_api, name="signup"),
    path("api/login", views.login_api, name="login"),
    path("new", views.new, name="new"),
    path("blog/<slug:slug>", views.blog, name="blog"),
    path("user/<str:username>", views.user, name="user"),
    path("bookmarks", views.bookmarks, name="bookmarks"),
]
