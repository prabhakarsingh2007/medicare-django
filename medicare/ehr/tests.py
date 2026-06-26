from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from core.models import Hospital
from accounts.models import Patient
from doctors.models import Doctor
from ehr.models import MedicalRecord
from ehr.forms import MedicalRecordForm

class EHRAccessTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.hospital_x = Hospital.objects.create(name="Hospital X", slug="hospital-x", is_active=True)
        self.hospital_y = Hospital.objects.create(name="Hospital Y", slug="hospital-y", is_active=True)

        # Create Patient A (Hospital X)
        self.user_a = User.objects.create_user(username="patienta", email="a@example.com", password="Password123!")
        self.patient_a = Patient.objects.create(user=self.user_a, name="Patient A", email="a@example.com", hospital=self.hospital_x)

        # Create Patient B (Hospital Y)
        self.user_b = User.objects.create_user(username="patientb", email="b@example.com", password="Password123!")
        self.patient_b = Patient.objects.create(user=self.user_b, name="Patient B", email="b@example.com", hospital=self.hospital_y)

        from core.models import Specialist
        self.specialist_x = Specialist.objects.create(name="Cardiology", hospital=self.hospital_x)
        self.specialist_y = Specialist.objects.create(name="Dermatology", hospital=self.hospital_y)

        # Create Doctor X (Hospital X)
        self.user_doc_x = User.objects.create_user(username="doctorx", email="doc_x@example.com", password="Password123!")
        self.doctor_x = Doctor.objects.create(
            user=self.user_doc_x,
            name="Doctor X",
            hospital=self.hospital_x,
            fees=500,
            qualification="MBBS",
            slug="doctor-x",
            specialist=self.specialist_x,
            experience=5
        )

        # Create Doctor Y (Hospital Y)
        self.user_doc_y = User.objects.create_user(username="doctory", email="doc_y@example.com", password="Password123!")
        self.doctor_y = Doctor.objects.create(
            user=self.user_doc_y,
            name="Doctor Y",
            hospital=self.hospital_y,
            fees=600,
            qualification="MD",
            slug="doctor-y",
            specialist=self.specialist_y,
            experience=10
        )

        # Create a medical record for Patient A
        self.record_a = MedicalRecord.objects.create(
            patient=self.patient_a,
            hospital=self.hospital_x,
            title="Blood Report Patient A",
            record_type="Lab Report",
            description="Normal counts"
        )

    def test_patient_can_view_own_ehr_records(self):
        self.client.force_login(self.user_a)
        response = self.client.get(reverse('patient_ehr_list'))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Blood Report Patient A")

    def test_patient_cannot_view_others_ehr_records(self):
        # Patient B logs in, should not see Patient A's record
        self.client.force_login(self.user_b)
        response = self.client.get(reverse('patient_ehr_list'))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Blood Report Patient A")

    def test_doctor_view_patient_ehr_same_hospital(self):
        # Doctor X views Patient A (both Hospital X)
        self.client.force_login(self.user_doc_x)
        response = self.client.get(reverse('doctor_ehr_list', kwargs={'patient_id': self.patient_a.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Blood Report Patient A")

    def test_doctor_view_patient_ehr_different_hospital(self):
        # Doctor X tries to view Patient B (Hospital Y)
        self.client.force_login(self.user_doc_x)
        response = self.client.get(reverse('doctor_ehr_list', kwargs={'patient_id': self.patient_b.id}))
        self.assertEqual(response.status_code, 302) # Redirect to doctor dashboard
        # Follow the redirect
        response = self.client.get(response.url)
        self.assertContains(response, "You can only view electronic health records of patients registered at your hospital.")

    def test_doctor_add_ehr_patient_same_hospital(self):
        # Doctor X adds EHR for Patient A (both Hospital X)
        self.client.force_login(self.user_doc_x)
        response = self.client.post(reverse('doctor_ehr_add', kwargs={'patient_id': self.patient_a.id}), {
            'title': 'New Prescription',
            'record_type': 'Prescription',
            'description': 'Take 2 pills daily'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(MedicalRecord.objects.filter(title='New Prescription', patient=self.patient_a).exists())

    def test_doctor_add_ehr_patient_different_hospital(self):
        # Doctor X tries to add EHR for Patient B (Hospital Y)
        self.client.force_login(self.user_doc_x)
        response = self.client.post(reverse('doctor_ehr_add', kwargs={'patient_id': self.patient_b.id}), {
            'title': 'Invalid Prescription',
            'record_type': 'Prescription',
            'description': 'Take 2 pills daily'
        })
        self.assertEqual(response.status_code, 302)
        self.assertFalse(MedicalRecord.objects.filter(title='Invalid Prescription').exists())

class EHRFormValidationTestCase(TestCase):
    def test_valid_pdf_upload(self):
        pdf_file = SimpleUploadedFile("test_report.pdf", b"pdf content", content_type="application/pdf")
        form_data = {
            'title': 'Blood Test Report',
            'record_type': 'Lab Report',
            'description': 'Normal counts'
        }
        form = MedicalRecordForm(data=form_data, files={'attachment': pdf_file})
        self.assertTrue(form.is_valid(), form.errors)

    def test_invalid_file_extension(self):
        text_file = SimpleUploadedFile("danger.exe", b"executable content", content_type="application/octet-stream")
        form_data = {
            'title': 'Hack Attempt',
            'record_type': 'Other',
            'description': 'Description'
        }
        form = MedicalRecordForm(data=form_data, files={'attachment': text_file})
        self.assertFalse(form.is_valid())
        self.assertIn('attachment', form.errors)
        self.assertEqual(form.errors['attachment'][0], "Only PDF, JPG, JPEG, or PNG files are allowed.")

    def test_file_size_exceeds_limit(self):
        pdf_file = SimpleUploadedFile("huge.pdf", b"pdf content", content_type="application/pdf")
        pdf_file.size = 6 * 1024 * 1024 # 6MB
        form_data = {
            'title': 'Large File',
            'record_type': 'Lab Report',
            'description': 'Description'
        }
        form = MedicalRecordForm(data=form_data, files={'attachment': pdf_file})
        self.assertFalse(form.is_valid())
        self.assertIn('attachment', form.errors)
        self.assertEqual(form.errors['attachment'][0], "File size cannot exceed 5MB.")
