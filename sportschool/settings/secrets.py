"""
secrets.py

Add passwords, API keys and other secrets in this file.
"""

# Make this unique, and don't share it with anybody.
SECRET_KEY = 'IRV+kBYsfdgsfdfjk8KJB(*fkjhsd**86534djk'


# Database authentication
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': 'sportschool',
        'USER': 'gannetson',
        'PASSWORD': 'l3tm31n'
    }
}

