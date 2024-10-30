from django.contrib.auth import authenticate, login
from django.http import HttpRequest, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse

from core.decorators import normaluser_required
from core.forms import AuthenticationForm, BlogForm, UserAddForm, UserProfileChangleForm
from core.models import Blog, Bookmark, User
from picomet.decorators import template
from picomet.http import PicometResponseRedirect
from picomet.views import render


@template("Home")
def home(request: HttpRequest):
    context = {"blogs": Blog.objects.all().order_by("-created_at")}
    return render(request, context)


@normaluser_required
@template("User")
def profile(request: HttpRequest):
    context = {"u": request.user}
    return render(request, context)


@normaluser_required
@template("ProfileSettings")
def profile_settings(request: HttpRequest):
    context = {}
    form = UserProfileChangleForm(instance=request.user)
    if request.method == "POST" and not request.action:
        form = UserProfileChangleForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
    context["form"] = form
    return render(request, context)


@normaluser_required
@template("AccountSettings")
def account_settings(request: HttpRequest):
    context = {}
    return render(request, context)


def signup_api(request: HttpRequest):
    form = UserAddForm(request.POST)
    if form.is_valid():
        form.save()
        username = form.cleaned_data.get("username")
        password = form.cleaned_data.get("password1")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return JsonResponse(
                {"success": "Your account has been succesfully created"}
            )
        form.add_error(None, "username number or password is incorrect")
        return JsonResponse({"errors": form.errors})
    return JsonResponse({"errors": form.errors})


def login_api(request: HttpRequest):
    form = AuthenticationForm(request.POST)
    if form.is_valid():
        username = form.cleaned_data.get("username")
        password = form.cleaned_data.get("password")
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return JsonResponse({"success": "You have been succesfully loged in"})
        form.add_error(None, "username number or password is incorrect")
        return JsonResponse({"errors": form.errors})
    return JsonResponse({"errors": form.errors})


@normaluser_required
@template("New")
def new(request: HttpRequest):
    context = {}
    form = BlogForm(request.user)
    if request.method == "POST" and not request.action:
        form = BlogForm(request.user, request.POST)
        if form.is_valid():
            blog = form.save()
            return PicometResponseRedirect(
                request, reverse("core:blog", kwargs={"slug": blog.slug})
            )
    context["form"] = form
    return render(request, context)


@template("Blog")
def blog(request: HttpRequest, slug):
    context = {"blog": get_object_or_404(Blog, slug=slug)}
    return render(request, context)


@template("User")
def user(request: HttpRequest, username):
    context = {"u": get_object_or_404(User, username=username)}
    return render(request, context)


@normaluser_required
@template("Bookmarks")
def bookmarks(request: HttpRequest):
    context = {
        "bookmarks": Bookmark.objects.filter(user=request.user).prefetch_related(
            "blog__like_set", "blog__comment_set"
        )
    }
    return render(request, context)
