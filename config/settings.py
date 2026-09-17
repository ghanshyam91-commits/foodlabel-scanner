import os
from pathlib import Path
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / '.env')
DEBUG = os.environ.get('DJANGO_DEBUG', '0') == '1'
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', '')
if not SECRET_KEY:
    if not DEBUG:
        raise ImproperlyConfigured('Set DJANGO_SECRET_KEY or DJANGO_DEBUG=1 for local development.')
    SECRET_KEY = 'local-development-only-never-use-in-production-foodlabel-scanner'
if not DEBUG and (len(SECRET_KEY) < 50 or SECRET_KEY.startswith('replace-')):
    raise ImproperlyConfigured('Production DJANGO_SECRET_KEY must be a unique random secret, at least 50 characters.')
ALLOWED_HOSTS = [v.strip() for v in os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1,[::1]').split(',') if v.strip()]
CSRF_TRUSTED_ORIGINS = [v.strip() for v in os.environ.get('DJANGO_CSRF_TRUSTED_ORIGINS', '').split(',') if v.strip()]
INSTALLED_APPS = ['django.contrib.contenttypes', 'django.contrib.sessions', 'django.contrib.staticfiles', 'scanner']
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'scanner.views.PrivacyHeadersMiddleware',
]
ROOT_URLCONF = 'config.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates',
    'DIRS': [], 'APP_DIRS': True, 'OPTIONS': {'context_processors': [
        'django.template.context_processors.request', 'django.template.context_processors.csrf']}}]
WSGI_APPLICATION = 'config.wsgi.application'
import dj_database_url
DATABASES = {'default': dj_database_url.config(default=f'sqlite:///{BASE_DIR / "db.sqlite3"}', conn_max_age=600, conn_health_checks=True)}
SESSION_ENGINE = 'django.contrib.sessions.backends.signed_cookies'
SESSION_COOKIE_AGE = 12 * 60 * 60
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG
SECURE_SSL_REDIRECT = not DEBUG
SECURE_REDIRECT_EXEMPT = [r'^health/$']
SECURE_HSTS_SECONDS = 3600 if not DEBUG else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = False
SECURE_HSTS_PRELOAD = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
if os.environ.get('TRUST_PROXY_SSL') == '1':
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
LANGUAGE_CODE = 'en'
TIME_ZONE = 'UTC'
USE_TZ = True
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STORAGES = {'default': {'BACKEND': 'django.core.files.storage.FileSystemStorage'},
    'staticfiles': {'BACKEND': 'whitenoise.storage.CompressedStaticFilesStorage'}}
# Keep uploads in memory; never write photos to MEDIA_ROOT or a database.
FILE_UPLOAD_HANDLERS = ['django.core.files.uploadhandler.MemoryFileUploadHandler']
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024
DATA_UPLOAD_MAX_NUMBER_FILES = 1
DATA_UPLOAD_MAX_NUMBER_FIELDS = 8
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')
GEMINI_MODEL = os.environ.get('GEMINI_MODEL', 'gemini-2.5-flash-lite')
# Display-only conversion for the usage estimate. Keep configurable because the
# provider bills in USD and exchange rates change independently of scan usage.
USD_TO_INR_RATE = max(0.0, float(os.environ.get('USD_TO_INR_RATE', '90')))
GOOGLE_OAUTH_CLIENT_ID = os.environ.get('GOOGLE_OAUTH_CLIENT_ID', '')
GOOGLE_OAUTH_CLIENT_SECRET = os.environ.get('GOOGLE_OAUTH_CLIENT_SECRET', '')
GOOGLE_AUTH_CONFIGURED = bool(GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET)
TEMPORARY_LOGIN_PIN = os.environ.get('TEMPORARY_LOGIN_PIN', '')
AUTH_REQUIRED = os.environ.get('AUTH_REQUIRED', '0' if DEBUG else '1') == '1'
SCANNER_ACCESS_CODE = os.environ.get('SCANNER_ACCESS_CODE', '')
REDIS_URL = os.environ.get('REDIS_URL', '')
if not DEBUG and not REDIS_URL:
    raise ImproperlyConfigured('Set REDIS_URL for shared, fail-closed production quotas.')
CACHES = {'default': {'BACKEND': 'django.core.cache.backends.redis.RedisCache', 'LOCATION': REDIS_URL}
    if REDIS_URL else {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache', 'LOCATION': 'foodlabel-local'}}
SCANS_PER_MINUTE = max(1, int(os.environ.get('SCANS_PER_MINUTE', '5')))
SCANS_PER_DAY = max(1, int(os.environ.get('SCANS_PER_DAY', '100')))
