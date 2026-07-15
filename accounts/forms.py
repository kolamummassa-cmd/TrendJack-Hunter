from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User


class SignupForm(UserCreationForm):
    email = forms.EmailField(required=True)

    class Meta:
        model = User
        fields = ["username", "email", "password1", "password2"]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({"class": "form-control"})

    def save(self, commit=True):
        user = super().save(commit=False)
        user.email = self.cleaned_data["email"]
        if commit:
            user.save()
        return user


class MpesaPhoneForm(forms.Form):
    phone_number = forms.CharField(
        max_length=15,
        label="M-Pesa phone number",
        help_text="Format: 2547XXXXXXXX",
        widget=forms.TextInput(attrs={"class": "form-control", "placeholder": "254712345678"}),
    )

    def clean_phone_number(self):
        value = self.cleaned_data["phone_number"].strip().replace(" ", "").replace("+", "")
        if value.startswith("0") and len(value) == 10:
            value = "254" + value[1:]
        if not (value.startswith("254") and len(value) == 12 and value.isdigit()):
            raise forms.ValidationError("Enter a valid Kenyan phone number, e.g. 254712345678.")
        return value
