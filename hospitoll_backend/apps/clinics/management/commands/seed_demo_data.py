from datetime import time, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import connection, transaction
from django.utils import timezone

from apps.clinics.models import Clinic, ClinicDepartment, ClinicService
from apps.child_safety.models import SafetyRegion
from apps.doctors.models import Doctor, DoctorAvailability, Specialization
from apps.patients.models import Patient
from apps.pharmacies.models import Medicine, Pharmacy, PharmacyMarchandise
from apps.users.models import CustomUser


CLINICS = [
    {
        'slug': 'demo-shifo-tibbiyot-markazi',
        'name': '[DEMO] Shifo Tibbiyot Markazi',
        'city': 'Toshkent',
        'address': 'DEMO manzil, Chilonzor tumani',
        'phone': '+998000000101',
        'department': 'Umumiy tibbiyot',
        'service': 'DEMO umumiy konsultatsiya',
    },
    {
        'slug': 'demo-samarqand-salomatlik-klinikasi',
        'name': '[DEMO] Samarqand Salomatlik Klinikasi',
        'city': 'Samarqand',
        'address': 'DEMO manzil, Samarqand shahri',
        'phone': '+998000000102',
        'department': 'Pediatriya',
        'service': 'DEMO pediatr konsultatsiyasi',
    },
    {
        'slug': 'demo-buxoro-oila-klinikasi',
        'name': '[DEMO] Buxoro Oila Klinikasi',
        'city': 'Buxoro',
        'address': 'DEMO manzil, Buxoro shahri',
        'phone': '+998000000103',
        'department': 'Kardiologiya',
        'service': 'DEMO kardiolog konsultatsiyasi',
    },
]

PHARMACIES = [
    {
        'slug': 'demo-gmed-dorixona-toshkent',
        'name': '[DEMO] G-MED Dorixona Toshkent',
        'city': 'Toshkent',
        'phone': '+998000000201',
    },
    {
        'slug': 'demo-gmed-dorixona-samarqand',
        'name': '[DEMO] G-MED Dorixona Samarqand',
        'city': 'Samarqand',
        'phone': '+998000000202',
    },
    {
        'slug': 'demo-gmed-dorixona-buxoro',
        'name': '[DEMO] G-MED Dorixona Buxoro',
        'city': 'Buxoro',
        'phone': '+998000000203',
    },
]

DOCTORS = [
    ('Shifokor', 'Demo 01', 0, 'DEMO_PED', 'Demo pediatriya'),
    ('Shifokor', 'Demo 02', 0, 'DEMO_FAM', 'Demo oilaviy shifokor'),
    ('Shifokor', 'Demo 03', 1, 'DEMO_PED', 'Demo pediatriya'),
    ('Shifokor', 'Demo 04', 1, 'DEMO_NEU', 'Demo nevrologiya'),
    ('Shifokor', 'Demo 05', 2, 'DEMO_CARD', 'Demo kardiologiya'),
    ('Shifokor', 'Demo 06', 2, 'DEMO_FAM', 'Demo oilaviy shifokor'),
]

MEDICINES = [
    ('DEMO-PAR-500', '[DEMO] Paratsetamol', '500 mg', 'Tabletka', 'Demo katalog mahsuloti'),
    ('DEMO-IBU-200', '[DEMO] Ibuprofen', '200 mg', 'Tabletka', 'Demo katalog mahsuloti'),
    ('DEMO-VIT-C', '[DEMO] Vitamin C', '500 mg', 'Tabletka', 'Demo katalog mahsuloti'),
    ('DEMO-ORS', '[DEMO] Oral rehidratatsiya tuzi', '20.5 g', 'Kukun', 'Demo katalog mahsuloti'),
    ('DEMO-SALINE', '[DEMO] Fiziologik eritma', '0.9%', 'Eritma', 'Demo katalog mahsuloti'),
    ('DEMO-BANDAGE', '[DEMO] Bint', '5 m', 'Tibbiy buyum', 'Demo katalog mahsuloti'),
    ('DEMO-THERMO', '[DEMO] Termometr', '', 'Tibbiy buyum', 'Demo katalog mahsuloti'),
    ('DEMO-MASK', '[DEMO] Tibbiy niqob', '', 'Tibbiy buyum', 'Demo katalog mahsuloti'),
]


class Command(BaseCommand):
    help = 'Add clearly marked demo records to the local SQLite database.'

    def handle(self, *args, **options):
        expected_database = (Path(settings.BASE_DIR) / 'db.sqlite3').resolve()
        configured_database = Path(connection.settings_dict['NAME']).resolve()
        if connection.vendor != 'sqlite' or configured_database != expected_database:
            raise CommandError(
                'Demo seeding faqat hospitoll_backend/db.sqlite3 lokal SQLite bazasida ishlaydi.'
            )

        self.created = {}
        with transaction.atomic():
            clinics = self._seed_clinics()
            doctors = self._seed_doctors(clinics)
            pharmacies = self._seed_pharmacies()
            medicines = self._seed_medicines(pharmacies)
            patients = self._seed_patients(clinics)
            self._seed_availability(doctors)
            self._seed_child_safety_regions()

        self.stdout.write(self.style.SUCCESS('Demo ma’lumotlar qo‘shildi (mavjud yozuvlar o‘zgartirilmadi):'))
        for label, count in self.created.items():
            self.stdout.write(f'  {label}: {count} ta yangi')

    def _record_created(self, label, was_created):
        self.created[label] = self.created.get(label, 0) + int(was_created)

    def _get_demo_user(self, username, role, first_name, last_name):
        email = f'{username}@example.test'
        user = CustomUser.objects.filter(email=email).first()
        if user:
            if user.role != role:
                raise CommandError(f'Demo email boshqa rol bilan band: {email}')
            return user

        return CustomUser.objects.create_user(
            username=username,
            email=email,
            password=None,
            role=role,
            first_name=first_name,
            last_name=last_name,
            is_active=True,
            is_verified=False,
        )

    def _seed_clinics(self):
        clinics = []
        for index, data in enumerate(CLINICS, start=1):
            owner = self._get_demo_user(
                f'demo_clinic_{index:02}', 'clinic', 'DEMO', f'Klinika {index:02}'
            )
            clinic, created = Clinic.objects.get_or_create(
                slug=data['slug'],
                defaults={
                    'owner': owner,
                    'name': data['name'],
                    'description': 'Faqat lokal sinov uchun yaratilgan DEMO klinika.',
                    'address': data['address'],
                    'phone_number': data['phone'],
                    'email': f'demo.clinic.{index:02}@example.test',
                    'registration_number': f'DEMO-CLINIC-{index:03}',
                    'status': 'active',
                    'is_verified': False,
                    'rating': 4.5,
                    'total_ratings': 8,
                    'working_hours': '09:00 - 18:00',
                },
            )
            if clinic.owner_id != owner.id:
                raise CommandError(f'Demo klinika slugi boshqa egaga tegishli: {data["slug"]}')
            self._record_created('Klinikalar', created)

            department, created = ClinicDepartment.objects.get_or_create(
                clinic=clinic,
                name=f'[DEMO] {data["department"]}',
                defaults={'description': 'Faqat demo ko‘rsatish uchun.'},
            )
            self._record_created('Klinika bo‘limlari', created)
            _, created = ClinicService.objects.get_or_create(
                clinic=clinic,
                name=data['service'],
                defaults={
                    'department': department,
                    'description': 'Faqat demo ko‘rsatish uchun. Tibbiy xizmat taklifi emas.',
                    'price': '50000.00',
                    'is_active': True,
                },
            )
            self._record_created('Klinika xizmatlari', created)
            clinics.append(clinic)
        return clinics

    def _seed_doctors(self, clinics):
        doctors = []
        for index, (first_name, last_name, clinic_index, code, specialization_name) in enumerate(DOCTORS, start=1):
            username = f'demo_doctor_{index:02}'
            user = self._get_demo_user(username, 'doctor', first_name, last_name)
            specialization, created = Specialization.objects.get_or_create(
                code=code,
                defaults={
                    'name': specialization_name,
                    'description': 'Faqat demo profil uchun.',
                    'is_active': True,
                },
            )
            self._record_created('Demo ixtisosliklar', created)
            doctor, created = Doctor.objects.get_or_create(
                user=user,
                defaults={
                    'clinic': clinics[clinic_index],
                    'license_number': f'DEMO-DOCTOR-LICENSE-{index:03}',
                    'bio': 'Bu lokal sinov uchun yaratilgan demo profil. Haqiqiy shifokor emas.',
                    'years_of_experience': 5 + index,
                    'consultation_fee': '50000.00',
                    'is_active': True,
                    'is_verified': False,
                    'rating': 4.5,
                    'total_ratings': 6,
                },
            )
            self._record_created('Shifokorlar', created)
            doctor.specializations.add(specialization)
            doctors.append(doctor)
        return doctors

    def _seed_pharmacies(self):
        pharmacies = []
        for index, data in enumerate(PHARMACIES, start=1):
            owner = self._get_demo_user(
                f'demo_pharmacy_{index:02}', 'pharmacy', 'DEMO', f'Dorixona {index:02}'
            )
            pharmacy, created = Pharmacy.objects.get_or_create(
                slug=data['slug'],
                defaults={
                    'owner': owner,
                    'name': data['name'],
                    'description': 'Faqat lokal sinov uchun yaratilgan DEMO dorixona.',
                    'registration_number': f'DEMO-PHARMACY-{index:03}',
                    'address': f'DEMO manzil, {data["city"]} shahri',
                    'phone_number': data['phone'],
                    'email': f'demo.pharmacy.{index:02}@example.test',
                    'status': 'active',
                    'is_verified': False,
                    'rating': 4.4,
                    'total_ratings': 5,
                    'working_hours': '09:00 - 20:00',
                },
            )
            if pharmacy.owner_id != owner.id:
                raise CommandError(f'Demo dorixona slugi boshqa egaga tegishli: {data["slug"]}')
            self._record_created('Dorixonalar', created)
            pharmacies.append(pharmacy)
        return pharmacies

    def _seed_medicines(self, pharmacies):
        medicines = []
        for code, name, strength, dosage_form, description in MEDICINES:
            medicine, created = Medicine.objects.get_or_create(
                atc_code=code,
                defaults={
                    'name': name,
                    'generic_name': name.replace('[DEMO] ', ''),
                    'description': description,
                    'category': 'DEMO',
                    'dosage_form': dosage_form,
                    'strength': strength,
                    'manufacturer': 'DEMO',
                    'country_of_origin': 'DEMO',
                    'is_prescription_required': False,
                    'is_active': True,
                },
            )
            self._record_created('Dori katalogi', created)
            medicines.append(medicine)

        expiry_date = timezone.localdate() + timedelta(days=730)
        for pharmacy_index, pharmacy in enumerate(pharmacies, start=1):
            for medicine_index, medicine in enumerate(medicines, start=1):
                _, created = PharmacyMarchandise.objects.get_or_create(
                    pharmacy=pharmacy,
                    medicine=medicine,
                    batch_number=f'DEMO-{pharmacy_index:02}-{medicine_index:02}',
                    defaults={
                        'expiry_date': expiry_date,
                        'quantity_in_stock': 25 + medicine_index,
                        'unit_price': str(5000 + medicine_index * 2500),
                        'is_available': True,
                    },
                )
                self._record_created('Dorixona zaxiralari', created)
        return medicines

    def _seed_patients(self, clinics):
        patients = []
        for index in range(1, 7):
            username = f'demo_patient_{index:02}'
            user = self._get_demo_user(username, 'patient', 'DEMO', f'Bemor {index:02}')
            patient, created = Patient.objects.get_or_create(
                user=user,
                defaults={
                    'gender': 'other',
                    'birth_year': 1990 + index,
                    'city': CLINICS[(index - 1) % len(CLINICS)]['city'],
                    'country': 'Uzbekistan',
                    'address': 'DEMO manzil',
                    'is_active': True,
                },
            )
            self._record_created('Bemor profillari', created)
            patient.clinics.add(clinics[(index - 1) % len(clinics)])
            patients.append(patient)
        return patients

    def _seed_availability(self, doctors):
        appointment_day = timezone.localdate() + timedelta(days=2)
        for index, doctor in enumerate(doctors, start=1):
            start_time = time(9 + ((index - 1) % 6), 0)
            _, created = DoctorAvailability.objects.get_or_create(
                doctor=doctor,
                date=appointment_day,
                start_time=start_time,
                defaults={
                    'end_time': time(start_time.hour, 30),
                    'status': 'available',
                },
            )
            self._record_created('Shifokor qabul vaqtlari', created)

    def _seed_child_safety_regions(self):
        city, created = SafetyRegion.objects.get_or_create(
            name='[DEMO] Toshkent shahri',
            level=SafetyRegion.Level.REGION,
            defaults={'is_active': True},
        )
        self._record_created('Demo xavfsizlik hududlari', created)
        district, created = SafetyRegion.objects.get_or_create(
            name='[DEMO] Chilonzor tumani',
            level=SafetyRegion.Level.DISTRICT,
            parent=city,
            defaults={'is_active': True},
        )
        self._record_created('Demo xavfsizlik hududlari', created)
        _, created = SafetyRegion.objects.get_or_create(
            name='[DEMO] Namuna mahallasi',
            level=SafetyRegion.Level.MAHALLA,
            parent=district,
            defaults={'is_active': True},
        )
        self._record_created('Demo xavfsizlik hududlari', created)
