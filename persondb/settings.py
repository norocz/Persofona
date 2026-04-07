import os
from pathlib import Path
from django.utils.translation import gettext_lazy as _

BASE_DIR = Path(__file__).resolve().parent.parent
SECRET_KEY = os.environ.get('DJANGO_SECRET_KEY', 'dev-CHANGE-ME-xk29!@#$%')
DEBUG = os.environ.get('DJANGO_DEBUG', 'True').lower() in ('true', '1')
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', '*').split(',')

INSTALLED_APPS = [
    'django.contrib.admin', 'django.contrib.auth',
    'django.contrib.contenttypes', 'django.contrib.sessions',
    'django.contrib.messages', 'django.contrib.staticfiles', 'core',
]
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.locale.LocaleMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.WorkspaceMiddleware',
]
ROOT_URLCONF = 'persondb.urls'
TEMPLATES = [{'BACKEND': 'django.template.backends.django.DjangoTemplates', 'DIRS': [],
    'APP_DIRS': True, 'OPTIONS': {'context_processors': [
        'django.template.context_processors.debug', 'django.template.context_processors.request',
        'django.contrib.auth.context_processors.auth', 'django.contrib.messages.context_processors.messages',
        'django.template.context_processors.i18n', 'core.context_processors.global_context',
]}}]
WSGI_APPLICATION = 'persondb.wsgi.application'

if os.environ.get('DB_ENGINE') == 'postgresql':
    DATABASES = {'default': {'ENGINE': 'django.db.backends.postgresql',
        'NAME': os.environ.get('DB_NAME', 'persondb'), 'USER': os.environ.get('DB_USER', 'persondb'),
        'PASSWORD': os.environ.get('DB_PASSWORD', 'persondb'),
        'HOST': os.environ.get('DB_HOST', 'db'), 'PORT': os.environ.get('DB_PORT', '5432')}}
else:
    DATABASES = {'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': BASE_DIR / 'db' / 'persondb.sqlite3'}}

LANGUAGE_CODE = os.environ.get('LANGUAGE_CODE', 'cs')
LANGUAGES = [('cs', _('Čeština')), ('en', _('English')), ('de', _('Deutsch')), ('sk', _('Slovenčina'))]
LOCALE_PATHS = [BASE_DIR / 'locale']
TIME_ZONE = os.environ.get('TIME_ZONE', 'Europe/Prague')
USE_I18N = True; USE_L10N = True; USE_TZ = True

STATIC_URL = '/static/'; STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [BASE_DIR / 'static']
MEDIA_URL = '/media/'; MEDIA_ROOT = BASE_DIR / 'media'
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

PERSONDB_THEME = os.environ.get('PERSONDB_THEME', 'matrix')
PERSONDB_PER_PAGE = int(os.environ.get('ITEMS_PER_PAGE', '24'))
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'
