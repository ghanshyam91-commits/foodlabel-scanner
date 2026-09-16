#!/bin/sh
set -eu
python manage.py check
python manage.py collectstatic --noinput
exec gunicorn config.wsgi:application --bind "0.0.0.0:${PORT:-8000}" --workers 1 --threads 4 --timeout 100 --access-logfile - --error-logfile -
