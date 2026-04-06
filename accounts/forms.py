from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser, Post

class RegisterForm(UserCreationForm):
    email = forms.EmailField(required=False)
    first_name = forms.CharField(max_length=30, required=True)
    last_name = forms.CharField(max_length=30, required=True)

    class Meta:
        model = CustomUser
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']

class ProfilePictureForm(forms.ModelForm):
    class Meta:
        model = CustomUser
        fields = ['profile_picture']

class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ['caption', 'image']
        widgets = {
            'caption': forms.Textarea(attrs={'placeholder': 'Напиши подпись...', 'rows': 3}),
        }