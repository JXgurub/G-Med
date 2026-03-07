"""
Comprehensive Architecture and Design Documentation for Hospitoll
"""

# Database Relationships and Model Hierarchy
RELATIONSHIPS = """
TASHKILIY MUNOSABATLAR (ORGANIZATIONAL RELATIONSHIPS)
=======================================================

1. USER - ROLE MAPPING
   CustomUser
   ├── admin (Administrator)
   ├── clinic → OneToOne → Clinic
   ├── doctor → OneToOne → Doctor
   ├── patient → OneToOne → Patient
   └── pharmacy → OneToOne → Pharmacy

2. CLINIC HIERARCHY
   Clinic (owner: CustomUser)
   ├── doctors (ForeignKey many)
   ├── patients (ManyToMany)
   ├── departments (ForeignKey many)
   ├── services (ForeignKey many)
   └── subscription (OneToOne)

3. DOCTOR MANAGEMENT
   Doctor (user: CustomUser, clinic: Clinic)
   ├── specializations (ManyToMany → Specialization)
   ├── patients (implicit through appointments)
   ├── availability_slots (ForeignKey many)
   ├── appointments (ForeignKey many)
   ├── medical_records (ForeignKey many)
   └── ratings (ForeignKey many)

4. PATIENT MEDICAL JOURNEY
   Patient (user: CustomUser)
   ├── clinics (ManyToMany)
   ├── appointments (ForeignKey many)
   │   └── medical_record (OneToOne)
   │       ├── diagnoses (ForeignKey many)
   │       ├── prescriptions (ForeignKey many)
   │       └── lab_tests (ForeignKey many)
   ├── medical_history (ForeignKey many)
   ├── prescriptions (ForeignKey many)
   ├── doctor_ratings (ForeignKey many)
   └── payments (ForeignKey many)

5. PHARMACY SYSTEM
   Pharmacy (owner: CustomUser)
   ├── medicines (ForeignKey many → PharmacyMarchandise)
   ├── prescriptions (ForeignKey many)
   └── subscription (OneToOne)

6. SUBSCRIPTION & PAYMENT FLOW
   SubscriptionPlan
   └── subscriptions (ForeignKey many)
       ├── status (trial/pending_payment/active/expired/cancelled)
       ├── payment (ForeignKey many → SubscriptionPayment)
       └── end_date (calculated based on 30-day activation)

7. MEDICAL WORKFLOW
   Appointment
   ├── patient → Patient
   ├── doctor → Doctor
   ├── clinic → Clinic
   └── medical_record → OneToOne → MedicalRecord
       ├── diagnoses (ICD-10 coded)
       ├── prescriptions (with medicine reference)
       └── lab_tests (with JSON results)
"""

# Subscription Logic
SUBSCRIPTION_LOGIC = """
OBUNA MANTIG'I (SUBSCRIPTION LOGIC)
===================================

STATUSES:
1. TRIAL (7-30 kun avtomatik)
   - Sinov davri o'tkazib berayotgan
   - Hech qanday to'lov talab qilinmaydi
   - Barcha xususiyatlar mavjud
   - Muddati tugagandan keyin → pending_payment

2. PENDING_PAYMENT
   - Sinov muddati tugadi
   - To'lov talab qilinadi
   - Status: pending_payment

3. ACTIVE (30 kun)
   - To'lov tasdiqlangandan keyin
   - 30 kunlik faol obuna
   - Ko'rsatilgan tarifga asosan xususiyatlar
   - Muddati tugagandan keyin → expired

4. EXPIRED
   - Muddati tugadi
   - Klinika/Dorixona avtomatik faolsiz bo'ladi
   - Doktorlar tizimga kira olmaydi
   - Bemorlar tibbiy ma'lumotlarni ko'ra oladi

5. CANCELLED
   - Administratorning to'saxali
   - Darhol faol bo'lmadi

AUTOMATIK OQIMLAR (AUTOMATED FLOWS):

Trial to Pending:
  - Celery task chaqiradi kuniga 1 marta
  - trial_end_date < now() → status = pending_payment

Pending to Active:
  - SubscriptionPayment.confirm_payment() qilinsa
  - Subscription.activate_by_payment() chaqiradi
  - end_date = now() + 30 days
  - Clinic/Pharmacy status = 'active'

Active to Expired:
  - Celery task chaqiradi kuniga 2 marta
  - end_date < now() → status = expired
  - Clinic/Pharmacy status = 'inactive'

Doctor Access Control:
  - Doctor.can_login → clinic.is_active_status va user.is_active
  - Oyna kliniquaning obunasi faolmi ko'radi
  - Agar obuna tugagan bo'lsa → kirish mumkin emas

Rating Update:
  - PatientDoctorRating uchun → calculate_doctor_rating()
  - Doctor.rating va total_ratings avtomatik yangilanadi
"""

# Permission Rules
PERMISSION_RULES = """
RUXSAT QOIDALARI (PERMISSION RULES)
===================================

ADMINISTRATOR
  - View: Barcha foydalanuvchilar, klinikalar, dorixonalar
  - Create: Klinika, dorixona, superuser foydalanuvchilar
  - Edit: Hamma tizimni
  - Delete: Klinika, dorixona, foydalanuvchilar
  - Can: Klinikalarnibloklash/blokdan chiqarish
  - Can: To'lovlarni tasdiqlash
  - Can: Obunalarni yangilash

CLINIC (Klinika egasi)
  - View: O'z klinikasining ma'lumotlari, doktor, bemor
  - Create: Doktor, departament, xizmat
  - Edit: O'z klinikaning profili va xizmatlar
  - Delete: O'z doktor va xizmatlari
  - Can: Doktor statistikasini ko'rish
  - Can: Bemor ro'yxatini ko'rish
  - Cannot: Boshqa klinikalarnit'ushiring

DOCTOR
  - View: O'z bemorlarining tibbiy ma'lumotlari
  - Create: Tibbiy yozuv, tashxis, retsept, sinovlar
  - Edit: O'z yaratgan tibbiy ma'lumotlari
  - Delete: Yakuniy bo'lmagan yozuvlarini
  - Can: Randevu boshqarish (o'z klinikasida)
  - Cannot: Klinikai bosh ma'lumotlarni o'zgartirish
  - Precondition: Clinic.is_active_status == True

PATIENT
  - View: FAQAT O'z ma'lumotlari (READ-ONLY)
    - O'z tibbiy tarixi
    - O'z retseptlari
    - O'z tashxislari
    - Doktor ma'lumotlari
  - Create: Doktor reitingi
  - Cannot: Tibbiy ma'lumotlar o'zgartirish
  - Cannot: Doktor yaratish
  - Cannot: Admin funksiyalari

PHARMACY
  - View: O'z dorilar inventori
  - Create: Dorixona ma'lumotlari
  - Edit: O'z profili, dorilari
  - Can: Retseptlarni ko'rish
  - Can: Retseptlarni to'ldirib berish
  - Cannot: Dorixona bosh xizmatini o'zgartirish

MEDICAL RECORD ACCESS:
  - Administrator: Barchani ko'radi
  - Doctor: O'z bemorlarini va o'z yaratgan yozuvlarini
  - Patient: Faqat o'z ma'lumotlarini (READ-ONLY)
  - Clinic: O'z doktorlarining yozuvlarini
"""

# Database Constraints and Validations
CONSTRAINTS = """
BAZAVIY CHEKLOVLAR (DATABASE CONSTRAINTS)
==========================================

UNIQUE CONSTRAINTS:
  - CustomUser.email (platform bo'ylab unikal)
  - Clinic.registration_number (jismoniy manzil bo'ylab)
  - Clinic.slug (URL uchun)
  - Pharmacy.registration_number  
  - Doctor.license_number
  - SubscriptionPayment.transaction_id
  - Medicine.atc_code (tizim bo'ylab)
  - Patient.national_id (sanoat bo'ylab)
  - Appointment.id (har bir randevu unikal)

COMPOSITE UNIQUE:
  - (Clinic, Department.name)
  - (Clinic, Service.name)
  - (Doctor, Doctor.date, DoctorAvailability.start_time)
  - (Pharmacy, Medicine, Batch.number)
  - (Patient, Doctor, PatientDoctorRating)

FOREIGN KEY CASCADE:
  - Clinic deleted → doctors updated to null
  - Doctor deleted → appointments set null
  - Patient deleted → medical records deleted
  - Pharmacy deleted → medicines preserved

FOREIGN KEY PROTECT:
  - SubscriptionPlan 'protected' (rejalarni saqlab qolish)
"""

# Special Business Rules
BUSINESS_RULES = """
BIZNES QOIDALARI (BUSINESS RULES)
=================================

1. SUBSCRIPTION ACTIVATION
   - Payment confirmed → 30 days activity
   - Trial expiry → pending_payment
   - Pending non-payment → expired (auto)
   - Clinic inactive → doctors can't login

2. DOCTOR RATING CALCULATION
   - Patient rates doctor (1-5 stars)
   - Doctor.rating = average of all ratings
   - Doctor.total_ratings = count
   - Clinic.rating = average of doctors' ratings

3. APPOINTMENT MANAGEMENT
   - Only available time slots allowed
   - Doctor availability must be set first
   - Appointment status: scheduled/completed/cancelled/no_show
   - Payment optional (depends on consultation fee)

4. MEDICAL RECORD LOCKING
   - Records can be edited before locking
   - Once locked, read-only
   - Doctor controls locking
   - Helps with data integrity

5. PRESCRIPTION WORKFLOW
   - Doctor creates prescription
   - Patient can check in patient portal
   - Pharmacy receives prescription
   - Is_filled flag when dispensed
   - Expiry date for prescription validity

6. INVENTORY MANAGEMENT
   - Expiry date tracking
   - Stock quantity monitoring
   - Batch number tracking
   - Is_available flag filtering

7. BILLING & INVOICES
   - Multiple invoice states
   - Tax and discount calculations
   - Payment tracking per invoice
   - Overdue automatic flagging
"""

# API Response Patterns
RESPONSE_PATTERNS = """
API JAVOB SHABLONLARI (API RESPONSE PATTERNS)
==============================================

SUCCESS RESPONSE:
{
    "status": "success",
    "data": {
        "id": "uuid",
        "name": "value",
        ...
    },
    "message": "Operation successful"
}

LIST RESPONSE (PAGINATED):
{
    "status": "success",
    "data": [
        { "id": "uuid", ... },
        { "id": "uuid", ... }
    ],
    "pagination": {
        "count": 100,
        "next": "?page=2",
        "previous": null,
        "page_size": 20
    }
}

ERROR RESPONSE:
{
    "status": "error",
    "error": {
        "code": "INVALID_REQUEST",
        "message": "Descriptive error message",
        "details": {
            "field_name": ["Error detail"]
        }
    }
}

AUTHENTICATION ERROR:
{
    "status": "error",
    "error": {
        "code": "UNAUTHORIZED",
        "message": "Authentication credentials were not provided."
    }
}

PERMISSION ERROR:
{
    "status": "error",
    "error": {
        "code": "FORBIDDEN", 
        "message": "Siz bu amalni bajarolmaysiz."
    }
}
"""

# Deployment Considerations
DEPLOYMENT = """
DEPLOYMENT TEZLIK (DEPLOYMENT CONSIDERATIONS)
==============================================

SCALABILITY:
  - Microservices ready: Har bir app alohida deploy qilish mumkin
  - Load balancing: Multiple gunicorn workers
  - Database: PostgreSQL with replication
  - Cache: Redis for session and query caching
  - Static files: CloudFront/CDN

SECURITY:
  - JWT tokens with refresh rotation
  - CORS whitelist configured
  - HTTPS enforced
  - Secret key from environment
  - SQL injection prevention (ORM)
  - CSRF protection enabled

MONITORING:
  - Celery task monitoring
  - Database query logging
  - Error tracking (Sentry)
  - Performance monitoring (Datadog)
  - Log aggregation (ELK stack)

BACKUP & DISASTER RECOVERY:
  - Daily database backups
  - Point-in-time recovery
  - Media file backups to S3
  - Database replication to standby

PERFORMANCE:
  - Database indexing on frequent queries
  - Query optimization (select_related, prefetch_related)
  - Caching strategy for medical data
  - Pagination for large datasets
  - API rate limiting
"""

if __name__ == '__main__':
    print(__doc__)
    print(RELATIONSHIPS)
    print(SUBSCRIPTION_LOGIC)
    print(PERMISSION_RULES)
    print(CONSTRAINTS)
    print(BUSINESS_RULES)
    print(RESPONSE_PATTERNS)
    print(DEPLOYMENT)
