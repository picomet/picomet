from django.contrib.auth.models import BaseUserManager


class UserManager(BaseUserManager):
    def create_user(self, username, password=None, *args, **kwargs):
        if not username:
            raise ValueError("Users must have an username")
        user = self.model(username=username)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_staffuser(self, username, password=None, *args, **kwargs):
        if not username:
            raise ValueError("Users must have an username")
        user = self.model(username=username)
        user.is_staff = True
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, username, password=None, *args, **kwargs):
        if not username:
            raise ValueError("Users must have an username")
        user = self.model(username=username)
        user.is_staff = True
        user.is_superuser = True
        user.set_password(password)
        user.save(using=self._db)
        return user
