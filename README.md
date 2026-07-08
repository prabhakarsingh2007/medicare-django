# Medicare Django Healthcare Platform

A comprehensive, production-grade Django healthcare platform offering patient registration, doctor scheduling, consultation bookings, secure payment integration, Electronic Health Records (EHR), pharmacy management, pathology laboratory bookings, and multi-channel notifications.

The application is optimized for both local development and production environments, including direct integration with Render, Neon PostgreSQL, Cloudinary Media Storage, and Razorpay.

---

## 🚀 Key Features

- **User Authentication & Authorization (`accounts`)**:
  - Secure Patient and Hospital Administrator registrations.
  - Multi-factor OTP-based registration and login flows.
  - Fail-safe registration redirect handling.
- **Doctor Management (`doctors`)**:
  - Doctor profiles, specializations, and custom consultation fees.
  - Flexible shift schedules and appointment slots.
- **Appointment Scheduling (`appointments`)**:
  - Interactive appointment slot booking system.
  - State-tracked consultation flow (Scheduled, Completed, Cancelled).
- **Payment Integration (`payments`)**:
  - Complete integration with **Razorpay** checkout API for processing booking fees.
- **Dashboards (`dashboard`)**:
  - Personalized dashboards for Patients, Doctors, and Hospital Administrators to manage histories, slots, and bookings.
- **Notifications (`notifications`)**:
  - SMTP Email notifications for user registration and booking confirmations.
  - Blocked-SMTP fallback mechanism printing OTPs directly to application standard output (`stdout`/logs) for testing.
  - Optional SMS gateway support (Fast2SMS API).
- **Pharmacy & Prescriptions (`pharmacy`)**:
  - Medicine catalogs, prescription management, and ordering workflow.
- **Pathology Labs (`pathology`)**:
  - Lab test scheduling, diagnostic panel bookings, and lab report generation.
- **Electronic Health Records (`ehr`)**:
  - Secure patient medical records upload, view, and storage.

---

## 📁 Repository Structure

```
├── medicare/                  # Django project root
│   ├── accounts/              # User profiles & authentication
│   ├── appointments/          # Booking and scheduling logic
│   ├── core/                  # Landing pages & templates
│   ├── dashboard/             # Patient/Doctor/Admin interfaces
│   ├── doctors/               # Doctor shift & fee structures
│   ├── ehr/                   # Health record management
│   ├── notifications/         # Email & SMS notification dispatchers
│   ├── pathology/             # Laboratory tests & report models
│   ├── payments/              # Razorpay gateways & payment logs
│   ├── pharmacy/              # Medicine inventory & prescriptions
│   ├── medicare/              # Main settings and routing package
│   │   ├── settings.py        # Settings configuration
│   │   └── urls.py            # Root URL router
│   ├── wsgi/                  # WSGI package entry point (Gunicorn-compatible)
│   ├── manage.py              # Django management script
│   └── requirements.txt       # Subfolder python dependencies
├── build.sh                   # Render automated build script
├── Procfile                   # Production web server configuration
├── pyrefly.toml               # Formatter/linter config
├── pyrightconfig.json         # Pyright static analysis config
└── requirements.txt           # Main requirements pointing to medicare/requirements.txt
```

---

## ⚙️ Local Development Setup

Follow these steps to run the Medicare application locally:

### 1. Prerequisites
- Python 3.10+ installed
- PostgreSQL (optional, defaults to SQLite if environment variables are not set)

### 2. Set Up Virtual Environment
Clone the repository, open a terminal in the root directory, and run:
```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate
```

### 3. Install Dependencies
Install all required python modules:
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Create a `.env` file inside the `medicare/` subdirectory:
```ini
DEBUG=True
SECRET_KEY=dev-secret-key-change-in-production
# DATABASE_URL=postgresql://user:password@localhost:5432/medicare  # Optional, falls back to SQLite if empty

# Razorpay Integration
RAZORPAY_KEY_ID=your_razorpay_key_id
RAZORPAY_KEY_SECRET=your_razorpay_key_secret

# Email / Notifications Settings
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=465
EMAIL_USE_SSL=True
EMAIL_HOST_USER=your_email@gmail.com
EMAIL_HOST_PASSWORD=your_app_password

# Fast2SMS Settings (Optional)
FAST2SMS_API_KEY=your_fast2sms_key
```

### 5. Apply Migrations & Collect Static Files
```bash
# Navigate to Django project root
cd medicare

# Apply database schema migrations
python manage.py migrate

# Collect static assets
python manage.py collectstatic --no-input

# Run server
python manage.py runserver
```
Visit the application at `http://127.0.0.1:8000/`.

---

## ☁️ Render Deployment Guide

The Medicare project is fully pre-configured to build and run on Render.

### 1. Build and Start Parameters
Set the following options in your Render Web Service settings:
- **Build Command**: `./build.sh`
- **Start Command**: `gunicorn --chdir medicare medicare.wsgi`

### 2. Environment Variables Checklist
Configure these variables in the **Environment** tab of the Render Service Dashboard:

| Variable | Description | Recommended Production Value |
| :--- | :--- | :--- |
| `DEBUG` | Disables debug information and stack traces | `False` |
| `SECRET_KEY` | High-entropy random key for cryptographic signing | *A long, secure random string* |
| `DATABASE_URL` | Neon or PostgreSQL connection string | `postgresql://<user>:<password>@<host>/<db>?sslmode=require` |
| `RAZORPAY_KEY_ID` | Razorpay API Key ID | *Your production or test key* |
| `RAZORPAY_KEY_SECRET` | Razorpay API Key Secret | *Your production or test secret* |
| `CLOUDINARY_CLOUD_NAME` | Cloudinary Storage Cloud Name | *For persistent image uploads* |
| `CLOUDINARY_API_KEY` | Cloudinary API Key | *For persistent image uploads* |
| `CLOUDINARY_API_SECRET` | Cloudinary API Secret | *For persistent image uploads* |
| `EMAIL_HOST_USER` | Sending Gmail/SMTP Username | *Your SMTP username* |
| `EMAIL_HOST_PASSWORD` | App-specific SMTP Password | *Your SMTP password* |

---

## 🛠️ Diagnostics & Production Troubleshooting

### 1. Gunicorn Concurrency-Safe Logging
Django is configured with standard output stream handling rather than traditional file log writing:
- Prevents file write-locks when executing under multi-worker Gunicorn server configurations.
- Directs python error tracebacks directly into the Render central logs panel.

### 2. SMTP Setup & The OTP Console Fallback
In restricted cloud environments (such as Render's free tier), outbound SMTP port 587 is blocked by default. To resolve this:
- **Port 465 SSL configuration**: The application is configured to send emails using SSL on Port 465 by default, which is not blocked by Render and delivers OTP emails successfully.
- **Fast Timeout (`EMAIL_TIMEOUT = 5`)**: The SMTP connection attempt is limited to 5 seconds to prevent Gunicorn workers from hanging.
- **Log Fallback**: If email transmission still fails (e.g., due to incorrect or missing credentials), the system prints the OTP code directly to stdout (the Render logs stream) and reports success.
- **How to log in during tests**: If SMTP credentials are not configured, check the service log stream on the Render Dashboard or local terminal console to retrieve the OTP.

### 3. Media Uploads & Cloudinary
Since Render utilizes ephemeral filesystems where locally saved images are lost on server restarts:
- The project integrates `django-cloudinary-storage`.
- Providing `CLOUDINARY_CLOUD_NAME`, `CLOUDINARY_API_KEY`, and `CLOUDINARY_API_SECRET` will automatically configure persistent storage for EHRs, pharmacy medicine uploads, and user profile pictures. If these keys are omitted, the application falls back safely to local folder uploads for evaluation.
