from django import forms
from .models import Hospital, Specialist

class HospitalForm(forms.ModelForm):
    class Meta:
        model = Hospital
        fields = ['name', 'address', 'phone', 'email']

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Hospital name is required.")
        
        # Check case-insensitive uniqueness
        qs = Hospital.objects.filter(name__iexact=name)
        if self.instance and self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError("Hospital with this name already exists.")
        return name

class SpecialistForm(forms.ModelForm):
    class Meta:
        model = Specialist
        fields = ['name', 'icon', 'hospital']

    def clean_name(self):
        name = self.cleaned_data.get('name', '').strip()
        if not name:
            raise forms.ValidationError("Specialist name is required.")
        return name
