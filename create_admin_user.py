import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.users.models import CustomUser

username = 'jxgroup'
email = 'jxgroup@gmail.com'
password = '20030320'

if CustomUser.objects.filter(username=username).exists():
    user = CustomUser.objects.get(username=username)
    user.email = email
    user.set_password(password)
    user.role = 'admin'
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    user.save()
    print('Updated existing user', username)
else:
    user = CustomUser.objects.create_user(username=username, email=email, password=password)
    user.role = 'admin'
    user.is_staff = True
    user.is_superuser = True
    user.is_active = True
    user.save()
    print('Created new admin user', username)
