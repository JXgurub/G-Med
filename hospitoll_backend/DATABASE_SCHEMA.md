"""
Database Schema Documentation
Hospitoll Health Management System
"""

DATABASE_SCHEMA = """
╔════════════════════════════════════════════════════════════════════════╗
║                    HOSPITOLL DATABASE SCHEMA v1.0                      ║
╚════════════════════════════════════════════════════════════════════════╝

┌─ USERS & AUTHENTICATION ─────────────────────────────────────────┐
│                                                                    │
│  CustomUser                                                        │
│  ├─ id: UUID (PK)                                               │
│  ├─ email: String (UNIQUE)                                      │
│  ├─ username: String                                            │
│  ├─ first_name: String                                          │
│  ├─ last_name: String                                           │
│  ├─ phone_number: String                                        │
│  ├─ role: Enum (admin, clinic, doctor, patient, pharmacy)      │
│  ├─ is_active: Boolean (default: True)                          │
│  ├─ is_verified: Boolean (email verification)                   │
│  ├─ created_at: DateTime (indexed)                              │
│  ├─ updated_at: DateTime                                        │
│  └─ password: String (hashed)                                   │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘

┌─ CLINICS & ORGANIZATIONS ───────────────────────────────────────┐
│                                                                    │
│  Clinic                                                            │
│  ├─ id: UUID (PK)                                               │
│  ├─ owner: FK → CustomUser (OneToOne, clinic role)             │
│  ├─ name: String (UNIQUE)                                       │
│  ├─ slug: String (UNIQUE, indexed)                              │
│  ├─ description: Text                                           │
│  ├─ address: String                                             │
│  ├─ phone_number: String                                        │
│  ├─ email: String                                               │
│  ├─ website: URL                                                │
│  ├─ registration_number: String (UNIQUE)                        │
│  ├─ license_document: File                                      │
│  ├─ status: Enum (active, inactive, suspended, trial)           │
│  ├─ is_verified: Boolean                                        │
│  ├─ is_blocked: Boolean (admin can block)                       │
│  ├─ logo: Image                                                 │
│  ├─ banner_image: Image                                         │
│  ├─ rating: Float (0-5)                                         │
│  ├─ total_ratings: Integer                                      │
│  ├─ created_at: DateTime (indexed)                              │
│  └─ updated_at: DateTime                                        │
│                                                                    │
│  ClinicDepartment                                               │
│  ├─ id: UUID (PK)                                               │
│  ├─ clinic: FK → Clinic                                         │
│  ├─ name: String (UNIQUE with clinic)                           │
│  ├─ description: Text                                           │
│  ├─ head_doctor: FK → Doctor (nullable)                         │
│  ├─ is_active: Boolean                                          │
│  └─ created_at: DateTime                                        │
│                                                                    │
│  ClinicService                                                   │
│  ├─ id: UUID (PK)                                               │
│  ├─ clinic: FK → Clinic                                         │
│  ├─ department: FK → ClinicDepartment (nullable)                │
│  ├─ name: String                                                │
│  ├─ description: Text                                           │
│  ├─ price: Decimal (So'm)                                       │
│  ├─ is_active: Boolean                                          │
│  └─ created_at: DateTime                                        │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘

┌─ DOCTORS ──────────────────────────────────────────────────────┐
│                                                                    │
│  Specialization                                                   │
│  ├─ id: UUID (PK)                                               │
│  ├─ name: String (UNIQUE)                                       │
│  ├─ code: String (UNIQUE, e.g., 'CARD')                         │
│  ├─ description: Text                                           │
│  ├─ is_active: Boolean                                          │
│  └─ created_at: DateTime                                        │
│                                                                    │
│  Doctor                                                            │
│  ├─ id: UUID (PK)                                               │
│  ├─ user: FK → CustomUser (OneToOne, doctor role)             │
│  ├─ clinic: FK → Clinic                                        │
│  ├─ specializations: M2M → Specialization                       │
│  ├─ license_number: String (UNIQUE)                             │
│  ├─ license_document: File                                      │
│  ├─ bio: Text                                                   │
│  ├─ profile_image: Image                                        │
│  ├─ years_of_experience: Integer                                │
│  ├─ consultation_fee: Decimal (So'm)                            │
│  ├─ available_from: Time                                        │
│  ├─ available_until: Time                                       │
│  ├─ working_days: String (indexed)                              │
│  ├─ is_active: Boolean                                          │
│  ├─ is_verified: Boolean (admin verified)                       │
│  ├─ rating: Float (0-5, indexed)                                │
│  ├─ total_ratings: Integer                                      │
│  ├─ total_patients: Integer                                     │
│  ├─ consultation_count: Integer                                 │
│  ├─ created_at: DateTime (indexed)                              │
│  └─ updated_at: DateTime                                        │
│                                                                    │
│  DoctorAvailability                                              │
│  ├─ id: UUID (PK)                                               │
│  ├─ doctor: FK → Doctor                                         │
│  ├─ date: Date                                                  │
│  ├─ start_time: Time                                            │
│  ├─ end_time: Time                                              │
│  ├─ status: Enum (available, booked, unavailable)               │
│  └─ created_at: DateTime                                        │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘

┌─ PATIENTS ──────────────────────────────────────────────────────┐
│                                                                    │
│  Patient                                                           │
│  ├─ id: UUID (PK)                                               │
│  ├─ user: FK → CustomUser (OneToOne, patient role)            │
│  ├─ clinics: M2M → Clinic                                       │
│  ├─ gender: Enum (male, female, other)                          │
│  ├─ date_of_birth: Date                                         │
│  ├─ blood_type: Enum (O+, O-, A+, A-, B+, B-, AB+, AB-)       │
│  ├─ national_id: String (UNIQUE)                                │
│  ├─ insurance_id: String                                        │
│  ├─ phone_number: String                                        │
│  ├─ address: String                                             │
│  ├─ city: String                                                │
│  ├─ country: String (default: Uzbekistan)                       │
│  ├─ emergency_contact_name: String                              │
│  ├─ emergency_contact_phone: String                             │
│  ├─ allergies: Text                                             │
│  ├─ chronic_diseases: Text                                      │
│  ├─ medications: Text                                           │
│  ├─ is_active: Boolean                                          │
│  ├─ created_at: DateTime (indexed)                              │
│  └─ updated_at: DateTime                                        │
│                                                                    │
│  PatientMedicalHistory                                           │
│  ├─ id: UUID (PK)                                               │
│  ├─ patient: FK → Patient                                       │
│  ├─ condition: String                                           │
│  ├─ description: Text                                           │
│  ├─ diagnosed_date: Date                                        │
│  ├─ status: Enum (ongoing, recovered, chronic)                  │
│  ├─ doctor: FK → Doctor (nullable)                              │
│  └─ created_at: DateTime (indexed)                              │
│                                                                    │
│  PatientDoctorRating                                             │
│  ├─ id: UUID (PK)                                               │
│  ├─ patient: FK → Patient                                       │
│  ├─ doctor: FK → Doctor (UNIQUE with patient)                   │
│  ├─ rating: Integer (1-5, indexed)                              │
│  ├─ comment: Text                                               │
│  ├─ is_anonymous: Boolean                                       │
│  └─ created_at: DateTime (indexed)                              │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘

┌─ PHARMACIES ──────────────────────────────────────────────────────┐
│                                                                    │
│  Pharmacy                                                          │
│  ├─ id: UUID (PK)                                               │
│  ├─ owner: FK → CustomUser (OneToOne, pharmacy role)          │
│  ├─ name: String (UNIQUE)                                       │
│  ├─ slug: String (UNIQUE, indexed)                              │
│  ├─ description: Text                                           │
│  ├─ registration_number: String (UNIQUE)                        │
│  ├─ license_document: File                                      │
│  ├─ address: String                                             │
│  ├─ phone_number: String                                        │
│  ├─ email: String                                               │
│  ├─ website: URL                                                │
│  ├─ logo: Image                                                 │
│  ├─ status: Enum (active, inactive, suspended, trial)           │
│  ├─ is_verified: Boolean                                        │
│  ├─ is_blocked: Boolean                                         │
│  ├─ rating: Float (0-5)                                         │
│  ├─ total_ratings: Integer                                      │
│  ├─ established_date: Date                                      │
│  ├─ created_at: DateTime (indexed)                              │
│  └─ updated_at: DateTime                                        │
│                                                                    │
│  Medicine                                                          │
│  ├─ id: UUID (PK)                                               │
│  ├─ name: String (indexed)                                      │
│  ├─ generic_name: String                                        │
│  ├─ atc_code: String (UNIQUE, indexed)                          │
│  ├─ description: Text                                           │
│  ├─ dosage_form: String                                         │
│  ├─ strength: String                                            │
│  ├─ manufacturer: String                                        │
│  ├─ is_prescription_required: Boolean                           │
│  ├─ is_active: Boolean                                          │
│  └─ created_at: DateTime                                        │
│                                                                    │
│  PharmacyMarchandise                                             │
│  ├─ id: UUID (PK)                                               │
│  ├─ pharmacy: FK → Pharmacy                                     │
│  ├─ medicine: FK → Medicine                                     │
│  ├─ batch_number: String (UNIQUE with pharmacy & medicine)      │
│  ├─ expiry_date: Date (indexed)                                 │
│  ├─ quantity_in_stock: Integer                                  │
│  ├─ unit_price: Decimal (So'm)                                  │
│  ├─ is_available: Boolean (indexed)                             │
│  ├─ created_at: DateTime                                        │
│  └─ updated_at: DateTime                                        │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘

┌─ MEDICAL RECORDS ──────────────────────────────────────────────┐
│                                                                    │
│  Appointment                                                       │
│  ├─ id: UUID (PK)                                               │
│  ├─ patient: FK → Patient                                       │
│  ├─ doctor: FK → Doctor                                         │
│  ├─ clinic: FK → Clinic                                         │
│  ├─ appointment_type: Enum (consultation, follow_up, ...)      │
│  ├─ status: Enum (scheduled, completed, cancelled, no_show)     │
│  ├─ scheduled_date: DateTime (indexed)                          │
│  ├─ duration_minutes: Integer (default: 30)                     │
│  ├─ reason: Text                                                │
│  ├─ notes: Text                                                 │
│  ├─ consultation_fee: Decimal                                   │
│  ├─ is_paid: Boolean                                            │
│  ├─ created_at: DateTime (indexed)                              │
│  └─ updated_at: DateTime                                        │
│                                                                    │
│  MedicalRecord                                                     │
│  ├─ id: UUID (PK)                                               │
│  ├─ patient: FK → Patient                                       │
│  ├─ doctor: FK → Doctor                                         │
│  ├─ clinic: FK → Clinic                                         │
│  ├─ appointment: FK → Appointment (OneToOne, nullable)          │
│  ├─ chief_complaint: Text                                       │
│  ├─ vital_signs: JSON                                           │
│  ├─ examination_findings: Text                                  │
│  ├─ assessment: Text                                            │
│  ├─ plan: Text                                                  │
│  ├─ is_locked: Boolean                                          │
│  ├─ created_at: DateTime (indexed)                              │
│  └─ updated_at: DateTime                                        │
│                                                                    │
│  Diagnosis                                                         │
│  ├─ id: UUID (PK)                                               │
│  ├─ medical_record: FK → MedicalRecord                          │
│  ├─ diagnosis_code: String (ICD-10)                             │
│  ├─ diagnosis_name: String                                      │
│  ├─ certainty: Enum (confirmed, probable, provisional)          │
│  ├─ notes: Text                                                 │
│  ├─ is_primary: Boolean (indexed)                               │
│  └─ created_at: DateTime                                        │
│                                                                    │
│  Prescription                                                      │
│  ├─ id: UUID (PK)                                               │
│  ├─ medical_record: FK → MedicalRecord                          │
│  ├─ patient: FK → Patient                                       │
│  ├─ doctor: FK → Doctor                                         │
│  ├─ medicine: FK → Medicine (nullable)                          │
│  ├─ dosage: String                                              │
│  ├─ frequency: String                                           │
│  ├─ duration_days: Integer (default: 7)                         │
│  ├─ instructions: Text                                          │
│  ├─ quantity: Integer                                           │
│  ├─ status: Enum (active, completed, expired, cancelled)        │
│  ├─ issued_date: DateTime (indexed)                             │
│  ├─ expiry_date: Date                                           │
│  ├─ filled_at_pharmacy: FK → Pharmacy (nullable)                │
│  ├─ is_filled: Boolean                                          │
│  ├─ created_at: DateTime (indexed)                              │
│  └─ updated_at: DateTime                                        │
│                                                                    │
│  LabTest                                                           │
│  ├─ id: UUID (PK)                                               │
│  ├─ medical_record: FK → MedicalRecord                          │
│  ├─ patient: FK → Patient                                       │
│  ├─ doctor: FK → Doctor                                         │
│  ├─ test_name: String                                           │
│  ├─ test_code: String                                           │
│  ├─ description: Text                                           │
│  ├─ status: Enum (ordered, in_progress, completed, cancelled)   │
│  ├─ ordered_date: DateTime (indexed)                            │
│  ├─ scheduled_date: Date                                        │
│  ├─ completed_date: DateTime                                    │
│  ├─ results: JSON                                               │
│  ├─ normal_range: String                                        │
│  └─ notes: Text                                                 │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘

┌─ SUBSCRIPTIONS & PAYMENTS ────────────────────────────────────────┐
│                                                                    │
│  SubscriptionPlan                                                │
│  ├─ id: UUID (PK)                                               │
│  ├─ name: String (UNIQUE)                                       │
│  ├─ description: Text                                           │
│  ├─ price: Decimal (monthly, So'm)                              │
│  ├─ duration_days: Integer (default: 30)                        │
│  ├─ max_doctors: Integer (nullable = unlimited)                 │
│  ├─ max_patients: Integer (nullable = unlimited)                │
│  ├─ features: JSON                                              │
│  ├─ is_active: Boolean                                          │
│  ├─ sort_order: Integer                                         │
│  ├─ created_at: DateTime                                        │
│  └─ updated_at: DateTime                                        │
│                                                                    │
│  Subscription                                                      │
│  ├─ id: UUID (PK)                                               │
│  ├─ subscriber_type: Enum (clinic, pharmacy)                    │
│  ├─ clinic: FK → Clinic (OneToOne, nullable)                    │
│  ├─ pharmacy: FK → Pharmacy (OneToOne, nullable)                │
│  ├─ plan: FK → SubscriptionPlan (PROTECT)                       │
│  ├─ status: Enum (trial, pending_payment, active, expired, ...) │
│  ├─ start_date: DateTime (indexed)                              │
│  ├─ end_date: DateTime (indexed)                                │
│  ├─ trial_period_days: Integer (default: 7)                    │
│  ├─ trial_end_date: DateTime                                    │
│  ├─ payment_confirmation_date: DateTime                         │
│  ├─ auto_renewal: Boolean (default: True)                       │
│  ├─ days_until_expiry: Integer                                  │
│  ├─ created_at: DateTime (indexed)                              │
│  └─ updated_at: DateTime                                        │
│                                                                    │
│  SubscriptionPayment                                             │
│  ├─ id: UUID (PK)                                               │
│  ├─ subscription: FK → Subscription                             │
│  ├─ amount: Decimal (So'm)                                      │
│  ├─ payment_method: Enum (card, bank_transfer, cash, check)     │
│  ├─ status: Enum (pending, confirmed, failed, cancelled, ...)   │
│  ├─ transaction_id: String                                      │
│  ├─ reference_number: String                                    │
│  ├─ notes: Text                                                 │
│  ├─ paid_date: DateTime                                         │
│  ├─ created_at: DateTime (indexed)                              │
│  └─ updated_at: DateTime                                        │
│                                                                    │
│  Payment                                                           │
│  ├─ id: UUID (PK)                                               │
│  ├─ payment_type: Enum (consultation, service, medicine, test) │
│  ├─ status: Enum (pending, confirmed, failed, cancelled, ...)   │
│  ├─ clinic: FK → Clinic (nullable)                              │
│  ├─ pharmacy: FK → Pharmacy (nullable)                          │
│  ├─ patient: FK → Patient (nullable)                            │
│  ├─ appointment: FK → Appointment (OneToOne, nullable)          │
│  ├─ description: String                                         │
│  ├─ amount: Decimal (So'm)                                      │
│  ├─ payment_method: Enum (card, bank_transfer, cash, wallet)    │
│  ├─ transaction_id: String                                      │
│  ├─ reference_number: String                                    │
│  ├─ notes: Text                                                 │
│  ├─ paid_date: DateTime                                         │
│  ├─ created_at: DateTime (indexed)                              │
│  └─ updated_at: DateTime                                        │
│                                                                    │
│  Invoice                                                           │
│  ├─ id: UUID (PK)                                               │
│  ├─ invoice_number: String (UNIQUE, indexed)                    │
│  ├─ clinic: FK → Clinic (nullable)                              │
│  ├─ pharmacy: FK → Pharmacy (nullable)                          │
│  ├─ patient: FK → Patient (nullable)                            │
│  ├─ status: Enum (draft, issued, paid, overdue, cancelled)      │
│  ├─ total_amount: Decimal                                       │
│  ├─ tax_amount: Decimal                                         │
│  ├─ discount_amount: Decimal                                    │
│  ├─ net_amount: Decimal                                         │
│  ├─ paid_amount: Decimal                                        │
│  ├─ payment_terms: String                                       │
│  ├─ due_date: Date                                              │
│  ├─ issued_date: Date (indexed)                                 │
│  ├─ paid_date: Date                                             │
│  ├─ notes: Text                                                 │
│  ├─ created_at: DateTime (indexed)                              │
│  └─ updated_at: DateTime                                        │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘

KEY INDEXES SUMMARY:
  - UserEmail, UserRole, UserCreatedAt
  - ClinicName, ClinicStatus, ClinicRegistration
  - DoctorClinic, DoctorRating, DoctorCreatedAt
  - PatientUser, PatientCreatedAt
  - AppointmentScheduledDate, AppointmentStatus
  - MedicalRecordPatient, MedicalRecordCreatedAt
  - PrescriptionPatient, PrescriptionStatus
  - SubscriptionStatus, SubscriptionEndDate
  - PaymentStatus
"""

print(DATABASE_SCHEMA)
