#!/usr/bin/env bash
# exit on error
set -o errexit

pip install -r requirements.txt

python medicare/manage.py collectstatic --no-input
python medicare/manage.py migrate
