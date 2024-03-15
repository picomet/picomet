import uuid

from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from core.managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    """Model definition for User."""

    username = models.CharField(unique=True, max_length=30)
    uid = models.UUIDField(default=uuid.uuid4, editable=False)
    full_name = models.CharField(max_length=40)
    nick_name = models.CharField(max_length=20, default="", blank=True)
    profile = models.ImageField(upload_to="user/profiles", null=True, blank=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "username"
    REQUIRED_FIELDS = []
    objects = UserManager()

    class Meta:
        db_table = "auth_user"
        ordering = ["-date_joined"]

    def __str__(self):
        return self.username


class Blog(models.Model):
    """Model definition for Blog."""

    title = models.CharField(max_length=50)
    slug = models.SlugField(unique=True)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE)

    class Meta:
        """Meta definition for Blog."""

        verbose_name = "Blog"
        verbose_name_plural = "Blogs"

    def __str__(self):
        self.title


class Bookmark(models.Model):
    """Model definition for Bookmark."""

    blog = models.ForeignKey(Blog, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Meta definition for Bookmark."""

        verbose_name = "Bookmark"
        verbose_name_plural = "Bookmarks"

    def __str__(self):
        self.blog.title


class Like(models.Model):
    """Model definition for Like."""

    blog = models.ForeignKey(Blog, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Meta definition for Like."""

        verbose_name = "Like"
        verbose_name_plural = "Likes"

    def __str__(self):
        self.blog.title


class Comment(models.Model):
    """Model definition for Comment."""

    text = models.TextField()
    blog = models.ForeignKey(Blog, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Meta definition for Comment."""

        verbose_name = "Comment"
        verbose_name_plural = "Comments"
        ordering = ["-created_at"]

    def __str__(self):
        self.text
