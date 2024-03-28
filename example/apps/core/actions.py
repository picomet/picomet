import functools

from django.contrib.auth import logout as _logout
from django.http import HttpRequest
from django.urls import reverse
from furl import furl
from picomet.shortcuts import ActionRedirect

from core.models import Blog, Bookmark, Comment, Like


def normaluser_required(function):
    @functools.wraps(function)
    def wrapper(request: HttpRequest, *args, **kwargs):
        user = request.user
        REFERER = request.META.get("HTTP_REFERER", "/")
        if user.is_authenticated and not user.is_staff:
            return function(request, *args, **kwargs)
        raise ActionRedirect(furl(REFERER).set({"v": "login"}).url, False)

    return wrapper


@normaluser_required
def logout(request: HttpRequest):
    _logout(request)
    return ["&auth"]


@normaluser_required
def like(request: HttpRequest):
    blog = Blog.objects.get(id=request.POST["blog"])
    Like.objects.get_or_create(blog=blog, user=request.user)
    return ["&like"]


@normaluser_required
def dislike(request: HttpRequest):
    blog = Blog.objects.get(id=request.POST["blog"])
    Like.objects.filter(blog=blog, user=request.user).delete()
    return ["&like"]


@normaluser_required
def bookmark(request: HttpRequest):
    blog = Blog.objects.get(id=request.POST["blog"])
    Bookmark.objects.get_or_create(blog=blog, user=request.user)
    return ["&bookmark"]


@normaluser_required
def unbookmark(request: HttpRequest):
    blog = Blog.objects.get(id=request.POST["blog"])
    Bookmark.objects.filter(blog=blog, user=request.user).delete()
    return ["&bookmark"]


@normaluser_required
def comment(request: HttpRequest):
    blog = Blog.objects.get(id=request.POST["blog"])
    Comment.objects.create(text=request.POST["text"], blog=blog, user=request.user)
    return ["&comment"]


@normaluser_required
def delete_comment(request: HttpRequest):
    Comment.objects.filter(id=request.POST["comment"], user=request.user).delete()
    return ["&comment"]


@normaluser_required
def delete_blog(request: HttpRequest):
    Blog.objects.filter(slug=request.POST["blog"], user=request.user).delete()
    raise ActionRedirect(reverse("core:profile"), True)
