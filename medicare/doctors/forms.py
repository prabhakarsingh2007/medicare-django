from django import forms
from django.contrib.auth.models import User
from .models import Doctor
from core.security_utils import is_strong_password, PASSWORD_RULE_TEXT

class DoctorForm(forms.ModelForm):
    username = forms.CharField(max_length=150, required=True)
    password = forms.CharField(widget=forms.PasswordInput(), required=True)

    class Meta:
        model = Doctor
        fields = ['name', 'hospital', 'specialist', 'experience', 'qualification', 'fees', 'image']

    def clean_username(self):
        username = self.cleaned_data.get('username', '').strip()
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError("Username already exists.")
        return username

    def clean_password(self):
        password = self.cleaned_data.get('password')
        if password and not is_strong_password(password):
            raise forms.ValidationError(PASSWORD_RULE_TEXT)
        return password

    def clean_experience(self):
        experience = self.cleaned_data.get('experience')
        if experience is not None and experience < 0:
            raise forms.ValidationError("Experience must be a valid non-negative number.")
        return experience

    def clean_fees(self):
        fees = self.cleaned_data.get('fees')
        if fees is not None and fees < 0:
            raise forms.ValidationError("Consultation fee must be a valid non-negative number.")
        return fees

    def clean(self):
        cleaned_data = super().clean()
        specialist = cleaned_data.get('specialist')
        hospital = cleaned_data.get('hospital')

        if specialist and hospital:
            if specialist.hospital_id and specialist.hospital_id != hospital.id:
                raise forms.ValidationError("Selected specialist belongs to another hospital.")
        return cleaned_data
