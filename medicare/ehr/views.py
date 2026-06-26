from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from accounts.models import Patient
from doctors.models import Doctor
from .models import MedicalRecord
from .forms import MedicalRecordForm
from core.activity import log_activity
from core.views import get_current_hospital

@login_required(login_url='login')
def patient_ehr_list(request):
    patient = Patient.objects.filter(user=request.user).first()
    if not patient:
        messages.error(request, "Patient profile not found.")
        return redirect('home')

    records = MedicalRecord.objects.filter(patient=patient)
    
    # Filtering by record type
    record_type = request.GET.get('record_type', '').strip()
    if record_type:
        records = records.filter(record_type=record_type)

    return render(request, 'ehr/patient_ehr_list.html', {
        'patient': patient,
        'records': records,
        'selected_type': record_type,
        'record_types': [choice[0] for choice in MedicalRecord.RECORD_TYPES]
    })

@login_required(login_url='login')
def patient_ehr_upload(request):
    patient = Patient.objects.filter(user=request.user).first()
    if not patient:
        messages.error(request, "Patient profile not found.")
        return redirect('home')

    current_hospital = get_current_hospital(request) or patient.hospital

    if request.method == 'POST':
        form = MedicalRecordForm(request.POST, request.FILES)
        if form.is_valid():
            record = form.save(commit=False)
            record.patient = patient
            record.hospital = current_hospital
            record.save()

            log_activity(
                actor=request.user,
                action="ehr_uploaded",
                target_type="medical_record",
                target_id=str(record.id),
                description=f"Patient {patient.name} uploaded medical record: {record.title}",
                extra_data={"record_type": record.record_type}
            )

            messages.success(request, "Medical record uploaded successfully!")
            return redirect('patient_ehr_list')
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = MedicalRecordForm()

    return render(request, 'ehr/patient_ehr_upload.html', {
        'form': form,
        'patient': patient
    })

@login_required(login_url='login')
def doctor_ehr_list(request, patient_id):
    doctor = Doctor.objects.filter(user=request.user).first()
    if not doctor:
        messages.error(request, "Doctor profile not found.")
        return redirect('home')

    patient = get_object_or_404(Patient, id=patient_id)
    records = MedicalRecord.objects.filter(patient=patient)

    # If the doctor is restricted to their own hospital's patients
    if doctor.hospital and patient.hospital != doctor.hospital:
        messages.error(request, "You can only view electronic health records of patients registered at your hospital.")
        return redirect('doctor_dashboard')

    return render(request, 'ehr/doctor_ehr_list.html', {
        'doctor': doctor,
        'patient': patient,
        'records': records
    })

@login_required(login_url='login')
def doctor_ehr_add(request, patient_id):
    doctor = Doctor.objects.filter(user=request.user).first()
    if not doctor:
        messages.error(request, "Doctor profile not found.")
        return redirect('home')

    patient = get_object_or_404(Patient, id=patient_id)
    if doctor.hospital and patient.hospital != doctor.hospital:
        messages.error(request, "You can only add health records for patients at your hospital.")
        return redirect('doctor_dashboard')

    if request.method == 'POST':
        form = MedicalRecordForm(request.POST, request.FILES)
        if form.is_valid():
            record = form.save(commit=False)
            record.patient = patient
            record.doctor = doctor
            record.hospital = doctor.hospital
            record.save()

            log_activity(
                actor=request.user,
                action="ehr_created",
                target_type="medical_record",
                target_id=str(record.id),
                description=f"Doctor {doctor.name} created medical record/prescription: {record.title} for patient {patient.name}",
                extra_data={"record_type": record.record_type, "patient_id": patient.id}
            )

            messages.success(request, f"Medical record added for patient {patient.name}!")
            return redirect('doctor_ehr_list', patient_id=patient.id)
        else:
            for field, errors in form.errors.items():
                for error in errors:
                    messages.error(request, f"{field.capitalize()}: {error}")
    else:
        form = MedicalRecordForm()

    return render(request, 'ehr/doctor_ehr_add.html', {
        'form': form,
        'doctor': doctor,
        'patient': patient
    })
