import re
from django import forms
from django.contrib.auth.models import User
from core.security_utils import is_strong_password, PASSWORD_RULE_TEXT
from .models import Patient, HospitalAdminProfile

class HospitalAdminProfileForm(forms.ModelForm):
    full_name = forms.CharField(max_length=150, required=True)
    username = forms.CharField(max_length=150, required=True)
    password = forms.CharField(widget=forms.PasswordInput(), required=True)
    email = forms.EmailField(required=False)

    class Meta:
        model = HospitalAdminProfile
        fields = ['hospital']

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Username already exists.")
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if email and User.objects.filter(email=email).exists():
            raise forms.ValidationError("Email already exists.")
        return email

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password and not is_strong_password(password):
            raise forms.ValidationError(PASSWORD_RULE_TEXT)
        return password

class BasePatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = ['phone', 'address', 'age', 'gender']

    def clean_phone(self):
        phone = self.cleaned_data.get('phone', '').strip()
        if phone and not re.fullmatch(r"\d{10,15}", phone):
            raise forms.ValidationError("Phone number should be 10 to 15 digits.")
        return phone

    def clean_age(self):
        age = self.cleaned_data.get('age')
        if age is not None:
            if age <= 0 or age > 130:
                raise forms.ValidationError("Please enter a valid age between 1 and 130.")
        return age

class PatientProfileForm(BasePatientForm):
    full_name = forms.CharField(max_length=150, required=True)
    email = forms.EmailField(required=False)

    class Meta(BasePatientForm.Meta):
        fields = ['phone', 'address', 'age', 'date_of_birth', 'gender', 'profile_pic']

    def clean_full_name(self):
        full_name = self.cleaned_data.get('full_name', '').strip()
        if not full_name:
            raise forms.ValidationError("Full name is required.")
        return full_name

class PatientProfileCompleteForm(BasePatientForm):
    class Meta(BasePatientForm.Meta):
        fields = ['phone', 'address', 'age', 'gender']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].required = True
