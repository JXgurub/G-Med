"""
LOCAL SETUP & DEVELOPMENT GUIDE
Hospitoll Hospital Management System
"""

SETUP_GUIDE = """
╔════════════════════════════════════════════════════════════════════════╗
║        HOSPITOLL BACKEND - LOCAL DEVELOPMENT SETUP                    ║
╚════════════════════════════════════════════════════════════════════════╝

PREREQUISITES
═════════════

Before starting, ensure you have installed:
  • Python 3.10 or higher
  • Git
  • PostgreSQL 13+ (or SQLite for development)
  • Redis 6+ (for caching and Celery)
  • Virtual Environment tools (venv)

┌─ OPTION 1: Ubuntu/Debian Installation ──────────────────────────────┐
$ sudo apt-get install python3.10 python3.10-venv python3-pip
$ sudo apt-get install postgresql postgresql-contrib
$ sudo apt-get install redis-server
└────────────────────────────────────────────────────────────────────────┘

┌─ OPTION 2: macOS Installation ──────────────────────────────┐
$ brew install python@3.10 postgresql redis
└────────────────────────────────────────────────────────────┘

┌─ OPTION 3: Windows Installation ────────────────────────────┐
1. Download Python 3.10+: https://www.python.org/downloads/
2. Download PostgreSQL: https://www.postgresql.org/download/
3. Download Redis for Windows: https://github.com/microsoftarchive/redis/releases
4. Or use WSL2 with Ubuntu
└────────────────────────────────────────────────────────────┘

STEP 1: Clone Repository
═════════════════════════

$ cd c:\\Hospitoll
$ git clone <repository-url> hospitoll_backend
$ cd hospitoll_backend

Or if you've already downloaded:
$ cd hospitoll_backend

STEP 2: Create Virtual Environment
═══════════════════════════════════

Windows:
$ python -m venv venv
$ venv\\Scripts\\activate

Linux/macOS:
$ python3 -m venv venv
$ source venv/bin/activate

STEP 3: Install Dependencies
════════════════════════════

$ pip install --upgrade pip
$ pip install -r requirements.txt

STEP 4: Configure Environment Variables
═════════════════════════════════════════

$ cp .env.example .env

Edit .env file:
━━━━━━━━━━━━━

DEBUG=True
SECRET_KEY=your-super-secret-key-change-in-production
DJANGO_SETTINGS_MODULE=config.settings
ALLOWED_HOSTS=localhost,127.0.0.1

# SQLite (Development)
DB_ENGINE=sqlite

# OR PostgreSQL (Recommended)
# DB_ENGINE=postgresql
# DB_NAME=hospitoll_db
# DB_USER=postgres
# DB_PASSWORD=your_password
# DB_HOST=localhost
# DB_PORT=5432

CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

CORS_ALLOWED_ORIGINS=http://localhost:3000,http://127.0.0.1:3000

┌─ SETUP POSTGRESQL (if using) ───────────────────────────────┐

Windows (using pgAdmin):
1. Open pgAdmin (installed with PostgreSQL)
2. Right-click Servers → Register → Server
3. Name: localhost
4. Connection tab:
   - Host: localhost
   - Port: 5432
   - Username: postgres
   - Password: (password set during install)
5. Create database: hospitoll_db

OR via Command Line:
$ psql -U postgres
postgres=# CREATE DATABASE hospitoll_db;
postgres=# CREATE USER hospitoll_user WITH PASSWORD 'password';
postgres=# ALTER ROLE hospitoll_user SET client_encoding TO 'utf8';
postgres=# GRANT ALL PRIVILEGES ON DATABASE hospitoll_db TO hospitoll_user;

Linux/macOS:
$ sudo -u postgres psql
postgres=# CREATE DATABASE hospitoll_db;
postgres=# CREATE USER hospitoll_user WITH PASSWORD 'password';
postgres=# GRANT ALL PRIVILEGES ON DATABASE hospitoll_db TO hospitoll_user;

└────────────────────────────────────────────────────────────┘

STEP 5: Run Database Migrations
════════════════════════════════

$ python manage.py makemigrations

Output:
  Migrations for 'users':
  apps/users/migrations/0001_initial.py
    - Create model CustomUser
  Migrations for 'clinics':
  apps/clinics/migrations/0001_initial.py
    - Create model Clinic
    ... (more migrations)

$ python manage.py migrate

Output:
  Operations to perform:
    Apply all migrations: admin, auth, clinics, ...
  Running migrations:
    Applying users.0001_initial... OK
    Applying clinics.0001_initial... OK
    ... (more migrations)

STEP 6: Create Superuser (Admin)
════════════════════════════════

$ python manage.py createsuperuser

Prompt:
  Email: admin@hospitoll.uz
  First name: Admin
  Last name: User
  Password: 
  Password (again):
  Superuser created successfully.

STEP 7: Create Test Data (Optional)
    ═════════════════════════════════

$ python manage.py shell

In the Python shell:
>>> from django.contrib.auth import get_user_model
>>> from apps.clinics.models import Clinic
>>> from apps.doctors.models import Specialization, Doctor
>>> 
>>> User = get_user_model()
>>> 
>>> # Create clinic user
>>> clinic_user = User.objects.create_user(
...     email='clinic@test.uz',
...     password='testpass123',
...     first_name='Test',
...     last_name='Clinic',
...     role='clinic'
... )
>>> 
>>> # Create clinic
>>> clinic = Clinic.objects.create(
...     owner=clinic_user,
...     name='Test Clinic',
...     slug='test-clinic',
...     registration_number='REG001',
...     address='123 Main St',
...     phone_number='+998900000000',
...     email='clinic@test.uz'
... )
>>> 
>>> # Create doctor user
>>> doctor_user = User.objects.create_user(
...     email='doctor@test.uz',
...     password='testpass123',
...     first_name='John',
...     last_name='Doe',
...     role='doctor'
... )
>>> 
>>> # Create specialization
>>> cardiology = Specialization.objects.create(
...     name='Cardiology',
...     code='CARD'
... )
>>> 
>>> # Create doctor
>>> doctor = Doctor.objects.create(
...     user=doctor_user,
...     clinic=clinic,
...     license_number='LIC001',
...     years_of_experience=10
... )
>>> doctor.specializations.add(cardiology)
>>> 
>>> # Create patient user
>>> patient_user = User.objects.create_user(
...     email='patient@test.uz',
...     password='testpass123',
...     first_name='Jane',
...     last_name='Patient',
...     role='patient'
... )
>>> 
>>> from apps.patients.models import Patient
>>> patient = Patient.objects.create(user=patient_user)
>>> patient.clinics.add(clinic)
>>> 
>>> # Create subscription for clinic
>>> from apps.subscriptions.models import SubscriptionPlan, Subscription
>>> plan = SubscriptionPlan.objects.create(
...     name='Basic',
...     price=500000,
...     duration_days=30
... )
>>> subscription = Subscription.objects.create(
...     subscriber_type='clinic',
...     clinic=clinic,
...     plan=plan,
...     status='active'
... )
>>> 
>>> print("Test data created successfully!")
>>> exit()

STEP 8: Start Development Server
════════════════════════════════

Terminal 1 - Django Development Server:
$ python manage.py runserver

Output:
  Watching for file changes with StatReloader
  Quit the server with CONTROL-C.
  Starting development server at http://127.0.0.1:8000/
  Django version 4.2.10, using settings 'config.settings'

Terminal 2 - Redis (if not running as service):
$ redis-server

Terminal 3 - Celery Worker:
$ celery -A config worker --loglevel=info

Output:
  celery@hostname ready.
  ....
  [Tasks]
   . apps.subscriptions.tasks.check_and_deactivate_expired_subscriptions
   . apps.subscriptions.tasks.send_subscription_expiry_reminders
   ... (more tasks)

Terminal 4 - Celery Beat (for scheduled tasks):
$ celery -A config beat --loglevel=info

Output:
  celerybeat: Starting SchedulingCluster v5.3.4: beat_scheduler.
  celerybeat: [Scheduler] Ticking queue ...

STEP 9: Access the Application
════════════════════════════════

Browser → Web Interface:
  Admin Panel:        http://localhost:8000/admin/
  API Documentation:  http://localhost:8000/api/docs/
  API Schema:         http://localhost:8000/api/schema/

Credentials:
  Email: admin@hospitoll.uz
  Password: (superuser password)

TESTING ENDPOINTS
═════════════════

Get Access Token:
$ curl -X POST http://localhost:8000/api/v1/users/token/ \\
  -H "Content-Type: application/json" \\
  -d '{"email":"admin@hospitoll.uz","password":"yourpassword"}'

Response:
{
  "access":"eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh":"eyJ0eXAiOiJKV1QiLCJhbGc..."
}

List Clinics:
$ curl http://localhost:8000/api/v1/clinics/ \\
  -H "Authorization: Bearer <access_token>"

COMMON COMMANDS
═════════════

Database:
$ python manage.py makemigrations           # Create migration files
$ python manage.py migrate                   # Apply migrations
$ python manage.py migrate --fake-initial    # Fake initial migration (if needed)
$ python manage.py sqlmigrate [app] [num]   # See SQL for a migration

Admin:
$ python manage.py createsuperuser          # Create admin user
$ python manage.py changepassword [user]    # Change user password
$ python manage.py shell                     # Interactive Python shell
$ python manage.py shell_plus                # Enhanced shell (with ipython)

Testing:
$ python manage.py test                      # Run all tests
$ python manage.py test apps.users           # Run specific app tests
$ python manage.py test --keepdb             # Keep test database

Django:
$ python manage.py check                     # Check project configuration
$ python manage.py collectstatic             # Collect static files
$ python manage.py flush                     # Clear database

TROUBLESHOOTING
═══════════════

Issue: "ModuleNotFoundError: No module named 'django'"
Solution: Activate virtual environment and install requirements
  $ source venv/bin/activate  (Linux/macOS)
  $ pip install -r requirements.txt

Issue: "django.db.utils.OperationalError: FATAL: role 'hospitoll_user' does not exist"
Solution: Create PostgreSQL user
  $ sudo -u postgres createuser hospitoll_user

Issue: "ConnectionRefusedError: [Errno 111] Connection refused" (Redis)
Solution: Start Redis server
  $ redis-server (separate terminal)
  Or on Windows: redis-server.exe

Issue: "CORS error in browser"
Solution: Update CORS_ALLOWED_ORIGINS in .env
  CORS_ALLOWED_ORIGINS=http://localhost:3000,http://localhost:5173

Issue: "Static files not found"
Solution: Collect static files
  $ python manage.py collectstatic --noinput

PERFORMANCE NOTES
═════════════════

For development:
  • Debug logging is enabled
  • Dev server uses single-threaded server
  • No query optimization needed
  • SQLite works fine

For production:
  • See DEPLOYMENT.md
  • Use PostgreSQL
  • Enable caching
  • Use Gunicorn + Nginx
  • Enable query optimization
  • Set up monitoring

NEXT STEPS
══════════

1. Read ARCHITECTURE.md for data model relationships
2. Read API_DOCUMENTATION.md for API endpoints
3. Create frontend consuming the API
4. Implement authentication in frontend
5. Create views for each role (Admin, Clinic, Doctor, Patient)
6. Test complete workflows

═══════════════════════════════════════════════════════════════════════════
"""

print(SETUP_GUIDE)
