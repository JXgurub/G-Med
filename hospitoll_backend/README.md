# Hospitoll - Hospital Management SaaS Platform

Hospitoll kasalxona boshqaruvi va SaaS platformasining Django-da yaratilgan to'liq orqa tomon arxitekturasi.

## Loyiha Tavsifi

Hospitoll - bu xususiyatli kasalxona, klinika va dorixonalar uchun qurilgan, quyidagi xususiyatlarga ega SaaS platformasi:

- **Multi-tenant arxitektura**: Bir nechta klinika va dorixonaları qo'llab-quvvatlash
- **Rol-asosiy kirish nazorati**: Administrator, Klinika, Doktor, Bemor, Dorixona
- **Obuna boshqaruvi**: 30 kunlik faollashtirish siklisi va to'lov tasdiqlandi
- **Tibbiy yozuvlar**: Maslahatlar, tashxislar, retseptlar, laboratoriya sinovlari
- **Bemor reytingi**: Bemorlar doktorlarni baholashi mumkin
- **Randevular**: Qo'ng'iroq va shunga o'xshash xizmatlar

## Texnologiya Staketi

- **Python 3.10+**
- **Django 4.2**
- **Django REST Framework 3.14**
- **PostgreSQL** (Ishlab chiqarishda tavsiya etiladi)
- **Celery** (Asinxron tasks)
- **Redis** (Cache va Celery broker)
- **JWT Authentication**

## Loyiha Strukturasi

```
hospitoll_backend/
├── config/                 # Django konfiguratsiyasi
│   ├── settings.py        # Asosiy sozlamalar
│   ├── urls.py            # URL yo'naltirish
│   └── wsgi.py
├── apps/                  # Django applications
│   ├── users/             # Foydalanuvchilar va autentifikatsiya
│   ├── clinics/           # Klinikalar boshqaruvi
│   ├── doctors/           # Doktorlar boshqaruvi
│   ├── patients/          # Bemorlar boshqaruvi
│   ├── pharmacies/        # Dorixonalar boshqaruvi
│   ├── medical/           # Tibbiy yozuvlar va randevular
│   ├── subscriptions/     # Obuna boshqaruvi
│   └── payments/          # To'lovlar va invoyslar
├── core/                  # Asosiy utilities va permissions
│   ├── permissions/       # Custom permission classes
│   └── utils/             # Helper functions
└── manage.py              # Django management command
```

## Asosiy Modellar

### CustomUser
Barcha foydalanuvchilar uchun tayyorlangan model. Roller:
- `admin`: Platform administratori
- `clinic`: Klinika egasi
- `doctor`: Doktor
- `patient`: Bemor
- `pharmacy`: Dorixona egasi

### Clinic
Klinika modeli. Xususiyatlari:
- Noyob identifikator (UUID)
- Obuna holati
- Doktor va bemor boshqaruvi
- Departamentlar va xizmatlar

### Subscription
Obuna lifecycle boshqaruvi:
- Sinov davri (7-30 kun)
- To'lovni kutish holati
- Aktiv (to'lov tasdiqlangandan so'ng 30 kun)
- Muddati tugagan / Bekor qilingan

### Medical Records
Tibbiy yozuvlar:
- Randevular va maslahatlar
- Tibbiy yozuvlar (chief complaint, examination, assessment)
- Tashxislar (ICD-10 kodi bilan)
- Retseptlar
- Laboratoriya sinovlari

## Ruxsat Qoidalari

### Administrator
- Klinika va dorixonaharni yaratish, o'zgartirish, o'chirish
- Foydalanuvchilarni manage qilish
- Obuna va to'lovlarni ko'rish
- Klinika va dorixonalarni bloc qilish

### Klinika
- O'z doktorlarini qo'shish, o'zgartirish, o'chirish
- O'z bemorlarini boshqarish
- Doktor statistikasini ko'rish
- Tibbiy xizmatlarni qo'shish

### Doktor
- Bemorlarni qo'shish va boshqarish
- Tibbiy yozuvlar yaratish
- Retseptlar va tashxislar belgilash
- Randevularni boshqarish
- Agar klinikanin obunasi tugagan bo'lsa, kira olmaydi

### Bemor
- O'z tibbiy tarixini ko'rish
- Retseptlar va tashxislarni ko'rish
- Doktorlarni baholash
- Faqat o'qish uchun ruxsat

### Dorixona
- O'z dorilarini boshqarish
- Retseptlarni ko'rish va to'ldirib berish
- Dorixona inventorini boshqarish

## Obuna Mantig'i

1. **Sinov davri** (7-30 kun)
   - Avtomatik 7 kunlik sinov davri
   - Barcha xususiyatlar mavjud

2. **To'lov kutish**
   - Sinov muddati tugagandan keyin to'lov talab qilinadi

3. **Aktiv** (30 kun)
   - To'lov tasdiqlangandan keyin 30 kunlik faol obuna
   - Muddati tugaganda avtomatik faolsizlanadi

4. **Muddati tugagan/Bekor qilingan**
   - Klinika va dorixona avtomatik faolsiz bo'ladi
   - Doktorlar tizimga kira olmaydi

## Autentifikatsiya va Avtorizatsiya

JWT (JSON Web Token) asosidagi autentifikatsiyani ishlatamiz:
- Access token (1 soat)
- Refresh token (7 kun)
- Role-based access control (RBAC)

## API Hujjati

API hujjati Swagger va ReDoc orqali mavjud:
- Swagger: `/api/docs/`
- ReDoc: `/api/redoc/`
- OpenAPI schema: `/api/schema/`

## Setup va O'rnatish

### 1. Virtual Environment Yaratish

\`\`\`bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\\Scripts\\activate    # Windows
\`\`\`

### 2. Dependencies O'rnatish

\`\`\`bash
pip install -r requirements.txt
\`\`\`

### 3. .env File Yaratish

\`\`\`bash
cp .env.example .env
# .env faylda haqiqiy ma'lumotlarni to'ldiring
\`\`\`

### 4. Database Migratsiyasi

\`\`\`bash
python manage.py makemigrations
python manage.py migrate
\`\`\`

### 5. Superuser Yaratish

\`\`\`bash
python manage.py createsuperuser
\`\`\`

### 6. Server Ishga Tushirish

\`\`\`bash
python manage.py runserver
\`\`\`

## Production Best Practices

1. **Security**
   - `SECRET_KEY` haqiqiy va xavfsiz qildiring
   - `DEBUG=False` ishlab chiqarish uchun
   - HTTPS dan foydalaning
   - CORS sozlamalarini jiddiy qildiring

2. **Database**
   - PostgreSQL dan foydalaning
   - Tez-tez backup oling
   - Database connection pooling ishlating

3. **Performance**
   - Redis cache dan foydalaning
   - Celery bilan asinxron tasks ishlatid
   - Database queries optim qildiring
   - CDN dan foydalaning static fayllar uchun

4. **Monitoring**
   - Loglarni yozib boring
   - Error tracking (e.g., Sentry)
   - Performance monitoring

5. **Scaling**
   - Moduli arxitektura
   - Horizontal scaling tayyor
   - Load balancing

## API Endpoints (Asosiy)

```
# Authentication
POST   /api/v1/users/token/               - Token olish
POST   /api/v1/users/token/refresh/       - Token yangilash

# Clinics
GET    /api/v1/clinics/                   - Klinikalar ro'yxati
POST   /api/v1/clinics/                   - Klinika yaratish
GET    /api/v1/clinics/{id}/              - Klinika detallarni ko'rish
PUT    /api/v1/clinics/{id}/              - Klinika o'zgartirish

# Doctors
GET    /api/v1/doctors/                   - Doktorlar ro'yxati
POST   /api/v1/doctors/                   - Doktor qo'shish
GET    /api/v1/doctors/{id}/              - Doktor detallarni ko'rish

# Patients
GET    /api/v1/patients/                  - Bemorlar ro'yxati
POST   /api/v1/patients/                  - Bemor qo'shish
GET    /api/v1/patients/{id}/medical/     - Bemor tibbiy tarixi

# Medical Records
GET    /api/v1/medical/appointments/      - Randevular
POST   /api/v1/medical/appointments/      - Randevu yaratish
GET    /api/v1/medical/records/           - Tibbiy yozuvlar
POST   /api/v1/medical/records/           - Tibbiy yozuv yaratish

# Subscriptions
GET    /api/v1/subscriptions/             - Obunalar
POST   /api/v1/subscriptions/             - Obuna yaratish
GET    /api/v1/subscriptions/{id}/        - Obuna detallarni ko'rish

# Payments
POST   /api/v1/payments/                  - To'lov yaratish
GET    /api/v1/payments/{id}/             - To'lov detallarni ko'rish
```

## Katkalar

Katkalar qabul qilinadi! Iltimos:
1. Fork loyihasi
2. Feature branch yaratish (`git checkout -b feature/amazing-feature`)
3. O'zgarishlari commit qilish (`git commit -m 'Add amazing feature'`)
4. Branch ga push qilish (`git push origin feature/amazing-feature`)
5. Pull Request yaratish

## Litsenziya

MIT License - batafsil uchun LICENSE faylni ko'ring.

## Aloqa

Savol yoki taklif uchun:
- Email: support@hospitoll.uz
- GitHub Issues: issues sahifasi

---

Hospitoll - Sog'liqlikni raqamlashtirilgan 💚
