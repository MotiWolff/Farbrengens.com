from os import environ

# עדכן את הגדרות בסיס הנתונים
SQLALCHEMY_DATABASE_URI = environ.get('DATABASE_URL', 'sqlite:///your.db')
if SQLALCHEMY_DATABASE_URI.startswith('postgres://'):
    SQLALCHEMY_DATABASE_URI = SQLALCHEMY_DATABASE_URI.replace('postgres://', 'postgresql://', 1) 