# 🚀 Quick Start Guide - Hospitoll

## Development Setup (5 minutes)

### MacOS/Linux
```bash
# Clone and navigate
git clone <repo-url>
cd Hospitoll/hospitoll_backend

# Setup Python
python3.11 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# Setup database
python manage.py migrate
python manage.py createsuperuser

# Run server
python manage.py runserver

# In another terminal - start Celery
celery -A config worker -l info
```

### Windows (PowerShell)
```powershell
# Clone and navigate
git clone <repo-url>
cd Hospitoll/hospitoll_backend

# Setup Python
python -m venv venv
venv\Scripts\Activate.ps1
pip install -r requirements.txt

# Setup database
python manage.py migrate
python manage.py createsuperuser

# Run server
python manage.py runserver

# In another terminal - start Celery
celery -A config worker -l info
```

### Frontend
```bash
cd hospitoll_frontend
npm install
npm run dev
```

**🎉 Access at**: http://localhost:5173

---

## Docker Deployment (2 minutes)

```bash
# From root directory
docker-compose up -d

# Initialize
docker-compose exec backend python manage.py migrate
docker-compose exec backend python manage.py createsuperuser

# View logs
docker-compose logs -f
```

**🎉 Access at**: http://localhost:3000

---

## Common Commands

### Backend
```bash
# Apply migrations
python manage.py migrate

# Create superuser
python manage.py createsuperuser

# Run tests
python manage.py test

# Collect static files
python manage.py collectstatic --noinput

# Clear cache
python manage.py shell
>>> from django.core.cache import cache
>>> cache.clear()
```

### Frontend
```bash
# Build for production
npm run build

# Preview production build
npm run preview

# Format code
npm run format

# Lint code
npm run lint
```

### Docker
```bash
# View logs
docker-compose logs -f [service]

# Execute command
docker-compose exec [service] [command]

# Restart service
docker-compose restart [service]

# Stop all
docker-compose down

# Clean rebuild
docker-compose up --build --no-cache
```

---

## Default Credentials

| Service | User | Password | URL |
|---------|------|----------|-----|
| Admin | admin | (created) | http://localhost:8000/admin |
| API | - | JWT Token | http://localhost:8000/api |
| Frontend | - | - | http://localhost:5173 |

---

## Environment Variables

### Essential (.env)
```bash
# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# Database
DB_ENGINE=sqlite  # Use postgresql for production
DB_NAME=hospitoll_db

# Frontend
FRONTEND_URL=http://localhost:5173

# Email
EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend

# Redis/Celery
CELERY_BROKER_URL=redis://localhost:6379/0
```

---

## Project Structure

```
Hospitoll/
├── hospitoll_backend/          Django API
│   ├── config/                 Django config
│   ├── apps/                   Django apps (8)
│   ├── core/                   Core services
│   ├── tests/                  Test files
│   ├── manage.py              Django CLI
│   └── requirements.txt        Python deps
├── hospitoll_frontend/         React app
│   ├── src/
│   ├── public/
│   ├── package.json           NPM config
│   └── vite.config.js         Vite config
├── docker-compose.yml         Docker setup
├── nginx.conf                 Nginx config
└── Documentation/

```

---

## Troubleshooting

### Backend Won't Start
```bash
# Check migrations
python manage.py showmigrations

# Apply missing migrations
python manage.py migrate

# Verify setup
python manage.py check
```

### Frontend Won't Load
```bash
# Clear cache and reinstall
rm -rf node_modules package-lock.json
npm install
npm run dev
```

### Database Issues
```bash
# Reset database (WARNING: deletes data)
rm db.sqlite3
python manage.py migrate
python manage.py createsuperuser
```

### Port Already in Use
```bash
# Change port for dev server
python manage.py runserver 8001

# Change port for frontend
npm run dev -- --port 5174
```

---

## Performance Tips

- 🔄 Use Redis caching for production
- 📊 Enable database connection pooling
- 🚀 Use Gunicorn with multiple workers
- 📁 Serve static files with CDN
- 💾 Enable gzip compression in Nginx
- 🔍 Monitor with logging/monitoring tools

---

## Production Checklist

- [ ] Set `DEBUG=False`
- [ ] Generate strong `SECRET_KEY`
- [ ] Configure PostgreSQL
- [ ] Set up Redis
- [ ] Configure CORS origins
- [ ] Set up SSL certificate
- [ ] Configure email settings
- [ ] Set up backup strategy
- [ ] Enable monitoring
- [ ] Configure logging

---

## Support Resources

- 📚 [Full Documentation](SETUP_AND_DEPLOYMENT.md)
- 📖 [API Docs](http://localhost:8000/api/docs)
- 🏗️ [Architecture Guide](hospitoll_backend/ARCHITECTURE.md)
- 💾 [Database Schema](hospitoll_backend/DATABASE_SCHEMA.md)
- 🔐 [Security Guide](hospitoll_backend/SECURITY_AND_MONITORING.md)

---

**Happy Coding! 🎉**

Questions? Check the full documentation or submit an issue.
