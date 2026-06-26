from django.test import TestCase, Client
from django.contrib.auth.models import User
from django.urls import reverse
from core.models import Hospital
from accounts.models import Patient, HospitalAdminProfile
from accounts.forms import HospitalAdminProfileForm, PatientProfileForm, PatientProfileCompleteForm

class FormsValidationTestCase(TestCase):
    def setUp(self):
        self.hospital = Hospital.objects.create(name="Test Hospital", slug="test-hospital", is_active=True)
        # Create a user to test duplicate username/email
        self.existing_user = User.objects.create_user(
            username="existinguser",
            email="existing@example.com",
            password="StrongPassword123!"
        )

    def test_hospital_admin_profile_form_valid(self):
        form_data = {
            'hospital': self.hospital.id,
            'full_name': 'New Admin',
            'username': 'newadmin',
            'email': 'newadmin@example.com',
            'password': 'StrongPassword123!'
        }
        form = HospitalAdminProfileForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

    def test_hospital_admin_profile_form_duplicate_username(self):
        form_data = {
            'hospital': self.hospital.id,
            'full_name': 'New Admin',
            'username': 'existinguser',
            'email': 'newadmin@example.com',
            'password': 'StrongPassword123!'
        }
        form = HospitalAdminProfileForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('username', form.errors)

    def test_hospital_admin_profile_form_weak_password(self):
        form_data = {
            'hospital': self.hospital.id,
            'full_name': 'New Admin',
            'username': 'newadmin',
            'email': 'newadmin@example.com',
            'password': 'weak'
        }
        form = HospitalAdminProfileForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('password', form.errors)

    def test_patient_profile_form_validation(self):
        # Invalid phone format
        form_data = {
            'full_name': 'John Doe',
            'phone': '123',
            'age': 25,
            'gender': 'Male'
        }
        form = PatientProfileForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('phone', form.errors)

        # Invalid age
        form_data = {
            'full_name': 'John Doe',
            'phone': '1234567890',
            'age': 150,
            'gender': 'Male'
        }
        form = PatientProfileForm(data=form_data)
        self.assertFalse(form.is_valid())
        self.assertIn('age', form.errors)

        # Valid input
        form_data = {
            'full_name': 'John Doe',
            'phone': '1234567890',
            'age': 30,
            'gender': 'Male',
            'address': 'Test Address',
            'date_of_birth': '1996-01-01'
        }
        form = PatientProfileForm(data=form_data)
        self.assertTrue(form.is_valid(), form.errors)

class ProfilesWorkflowTestCase(TestCase):
    def setUp(self):
        self.client = Client()
        self.hospital = Hospital.objects.create(name="Test Hospital", slug="test-hospital", is_active=True)
        self.user = User.objects.create_user(
            username="patientuser",
            email="patient@example.com",
            password="StrongPassword123!"
        )
        self.patient = Patient.objects.create(
            user=self.user,
            name="Patient User",
            email="patient@example.com",
            hospital=self.hospital
        )
        self.client.force_login(self.user)

    def test_patient_profile_update_view(self):
        response = self.client.post(reverse('patient_profile'), {
            'full_name': 'Patient Two',
            'email': 'patient_two@example.com',
            'phone': '9876543210',
            'age': 40,
            'gender': 'Male',
            'address': 'Updated Street'
        })
        self.assertEqual(response.status_code, 302) # Redirects back to patient_profile
        self.patient.refresh_from_db()
        self.user.refresh_from_db()
        self.assertEqual(self.patient.name, 'Patient Two')
        self.assertEqual(self.user.first_name, 'Patient')
        self.assertEqual(self.user.last_name, 'Two')
        self.assertEqual(self.user.email, 'patient_two@example.com')

    def test_complete_profile_view(self):
        response = self.client.post(reverse('complete_profile'), {
            'phone': '9988776655',
            'age': 35,
            'gender': 'Female',
            'address': 'New Home'
        })
        self.assertEqual(response.status_code, 302) # Redirects to patient_dashboard
        self.patient.refresh_from_db()
        self.assertEqual(self.patient.phone, '9988776655')
        self.assertEqual(self.patient.age, 35)
        self.assertEqual(self.patient.gender, 'Female')
        self.assertEqual(self.patient.address, 'New Home')

    def test_add_hospital_admin_view(self):
        superuser = User.objects.create_superuser(
            username="superadmin",
            email="super@example.com",
            password="SuperPassword123!"
        )
        self.client.force_login(superuser)
        
        response = self.client.post(reverse('add_hospital_admin'), {
            'hospital': self.hospital.id,
            'full_name': 'Hospital Admin User',
            'username': 'hospadmin',
            'email': 'hospadmin@example.com',
            'password': 'StrongPassword123!'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(User.objects.filter(username='hospadmin').exists())
        self.assertTrue(HospitalAdminProfile.objects.filter(user__username='hospadmin').exists())
