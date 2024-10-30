from django import forms

from core.models import Blog, User


class UserAddForm(forms.ModelForm):
    password1 = forms.CharField()
    password2 = forms.CharField()

    def clean_password2(self):
        pass1 = self.cleaned_data["password1"]
        pass2 = self.cleaned_data["password2"]
        if pass1 and pass2 and pass1 != pass2:
            raise forms.ValidationError("password didn't match")
        return pass2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])

        if commit:
            user.save()
        return user

    class Meta:
        model = User
        fields = ("full_name", "username")


class UserProfileChangleForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ("full_name", "username")


class AuthenticationForm(forms.Form):
    username = forms.CharField(max_length=30)
    password = forms.CharField()


class BlogForm(forms.ModelForm):
    def __init__(self, user: User, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def save(self, commit=True):
        blog = super().save(commit=False)
        blog.user = self.user

        if commit:
            blog.save()
        return blog

    class Meta:
        model = Blog
        fields = ("title", "slug", "content")
