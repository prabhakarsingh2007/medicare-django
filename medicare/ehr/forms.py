from django import forms
from .models import MedicalRecord

class MedicalRecordForm(forms.ModelForm):
    class Meta:
        model = MedicalRecord
        fields = ['title', 'record_type', 'description', 'attachment']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'w-full px-4 py-3 border border-slate-200 rounded-2xl focus:ring-2 focus:ring-blue-500 outline-none transition-all',
                'placeholder': 'e.g. Blood Test Report June 2026'
            }),
            'record_type': forms.Select(attrs={
                'class': 'w-full px-4 py-3 border border-slate-200 rounded-2xl focus:ring-2 focus:ring-blue-500 outline-none transition-all'
            }),
            'description': forms.Textarea(attrs={
                'class': 'w-full px-4 py-3 border border-slate-200 rounded-2xl focus:ring-2 focus:ring-blue-500 outline-none transition-all',
                'placeholder': 'Add details about the medical record or prescription...',
                'rows': 4
            }),
            'attachment': forms.ClearableFileInput(attrs={
                'class': 'w-full border border-slate-200 rounded-2xl px-4 py-3 text-sm'
            })
        }

    def clean_title(self):
        title = self.cleaned_data.get('title', '').strip()
        if not title:
            raise forms.ValidationError("Title cannot be empty.")
        if len(title) < 3:
            raise forms.ValidationError("Title must be at least 3 characters long.")
        return title

    def clean_attachment(self):
        attachment = self.cleaned_data.get('attachment')
        if attachment:
            # Validate file size (limit to 5MB)
            if attachment.size > 5 * 1024 * 1024:
                raise forms.ValidationError("File size cannot exceed 5MB.")
            # Validate file extensions (allow PDF, JPG, JPEG, PNG)
            allowed_extensions = ['.pdf', '.jpg', '.jpeg', '.png']
            import os
            ext = os.path.splitext(attachment.name)[1].lower()
            if ext not in allowed_extensions:
                raise forms.ValidationError("Only PDF, JPG, JPEG, or PNG files are allowed.")
        return attachment
