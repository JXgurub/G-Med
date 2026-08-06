from datetime import datetime, timedelta
from decimal import Decimal
from types import SimpleNamespace
from typing import Any, cast
from unittest.mock import patch
from uuid import uuid4

from django.urls import reverse
from django.test import override_settings
from django.utils import timezone
from django.core.cache import cache
from rest_framework.test import APITestCase

from apps.users.models import CustomUser
from apps.clinics.models import Clinic
from apps.doctors.models import Doctor, DoctorAvailability, DoctorWorkRecord, Specialization, DoctorSpecialization, DoctorEmployment
from apps.patients.models import Patient, PatientDoctorRating
from apps.medical.models import Appointment, MedicalRecord
from apps.medical.telegram_bot_service import TelegramBotService
from apps.medical.tasks import (
    run_auto_queue_cycle,
    send_today_first_queue_reminders,
    send_telegram_appointment_15min_prompt,
)


class MedicalApiTestCase(APITestCase):
    def auth_as(self, user: CustomUser) -> None:
        cast(Any, self.client).force_authenticate(user=user)

    @staticmethod
    def body(response):
        return response.json()


def safe_queue_base_now():
    return timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)


def queue_reference_now():
    now = timezone.localtime().replace(second=0, microsecond=0)
    if now.hour >= 23:
        return now - timedelta(hours=1)
    return now


class NotifyReadyDoctorRatingTests(MedicalApiTestCase):
    def setUp(self):
        self.owner_user = CustomUser.objects.create_user(
            username='clinic_owner_rating',
            email='clinic.rating@example.com',
            password='Pass12345!',
            role='clinic',
            first_name='Clinic',
            last_name='Owner',
        )
        self.clinic = Clinic.objects.create(
            owner=self.owner_user,
            name='Rating Clinic',
            slug='rating-clinic',
            address='Rating address',
            phone_number='+998901111111',
            email='rating@test.uz',
            registration_number='REG-RATING-001',
            status='active',
        )

        self.doctor_user = CustomUser.objects.create_user(
            username='doctor_rating_user',
            email='doctor.rating@example.com',
            password='Pass12345!',
            role='doctor',
            first_name='Rate',
            last_name='Doctor',
        )
        self.doctor = Doctor.objects.create(
            user=self.doctor_user,
            clinic=self.clinic,
            license_number='LIC-RATING-001',
            working_days='Mon,Tue,Wed,Thu,Fri,Sat,Sun',
        )

        self.patient_user = CustomUser.objects.create_user(
            username='patient_rating_user',
            email='patient.rating@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Rate',
            last_name='Patient',
        )
        self.patient = Patient.objects.create(user=self.patient_user)
        self.appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            clinic=self.clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=1,
            scheduled_date=timezone.now() + timedelta(minutes=15),
            duration_minutes=30,
            telegram_user_id=991001,
            telegram_chat_id=991001,
        )

    def test_notify_ready_sends_rating_buttons(self):
        sent_messages = []
        fake_client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        self.auth_as(self.doctor_user)
        url = reverse('appointment-notify-ready', args=[self.appointment.id])
        with patch('apps.medical.telegram_bot_service.TelegramBotService._require_client', return_value=fake_client):
            response = self.client.post(url, {}, format='json')

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(sent_messages), 1)
        self.assertIn('xizmatini baholang', sent_messages[0]['text'])
        keyboard = sent_messages[0]['reply_markup']['inline_keyboard']
        self.assertEqual(len(keyboard[0]), 5)
        self.assertEqual(keyboard[0][4]['callback_data'], f'rate:{self.appointment.id}:5')

    def test_rating_callback_updates_doctor_rating(self):
        sent_messages = []
        service = TelegramBotService()
        cast(Any, service).client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: sent_messages.append({'callback': kwargs.get('text') or (args[1] if len(args) > 1 else '')}),
        )

        service._handle_callback_query({
            'id': 'cb-rate-1',
            'data': f'rate:{self.appointment.id}:5',
            'from': {'id': 991001},
            'message': {'chat': {'id': 991001}},
        })

        rating = PatientDoctorRating.objects.get(doctor=self.doctor, patient=self.patient)
        self.assertEqual(rating.rating, 5)
        self.doctor.refresh_from_db()
        self.assertEqual(float(self.doctor.rating), 5.0)
        self.assertEqual(int(self.doctor.total_ratings), 1)
        self.assertTrue(any('5' in item.get('text', '') or '⭐⭐⭐⭐⭐' in item.get('text', '') for item in sent_messages if 'text' in item))

    def test_rating_callback_allows_followup_comment(self):
        sent_messages = []
        service = TelegramBotService()
        cast(Any, service).client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        service._handle_callback_query({
            'id': 'cb-rate-2',
            'data': f'rate:{self.appointment.id}:4',
            'from': {'id': 991001},
            'message': {'chat': {'id': 991001}},
        })

        state = self.appointment.telegram_states.get(action='rating_awaiting_comment')
        self.assertFalse(state.is_expired)
        self.assertTrue(any('Izohsiz yakunlash' in str(item.get('reply_markup', {})) for item in sent_messages))

        service.handle_update({
            'message': {
                'from': {'id': 991001},
                'chat': {'id': 991001},
                'text': 'Juda yaxshi xizmat',
            }
        })

        rating = PatientDoctorRating.objects.get(doctor=self.doctor, patient=self.patient)
        self.assertEqual(rating.rating, 4)
        self.assertEqual(rating.comment, 'Juda yaxshi xizmat')
        self.assertFalse(self.appointment.telegram_states.filter(action='rating_awaiting_comment').exists())

    def test_rating_comment_can_be_skipped(self):
        sent_messages = []
        service = TelegramBotService()
        cast(Any, service).client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        service._handle_callback_query({
            'id': 'cb-rate-3',
            'data': f'rate:{self.appointment.id}:3',
            'from': {'id': 991001},
            'message': {'chat': {'id': 991001}},
        })
        self.assertTrue(self.appointment.telegram_states.filter(action='rating_awaiting_comment').exists())

        service._handle_callback_query({
            'id': 'cb-rate-skip',
            'data': f'skipratecomment:{self.appointment.id}',
            'from': {'id': 991001},
            'message': {'chat': {'id': 991001}},
        })

        rating = PatientDoctorRating.objects.get(doctor=self.doctor, patient=self.patient)
        self.assertEqual(rating.rating, 3)
        self.assertEqual(rating.comment, '')
        self.assertFalse(self.appointment.telegram_states.filter(action='rating_awaiting_comment').exists())

    def test_today_endpoint_excludes_in_progress_appointments(self):
        self.appointment.status = Appointment.Status.IN_PROGRESS
        self.appointment.save(update_fields=['status', 'updated_at'])

        waiting_appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            clinic=self.clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=2,
            scheduled_date=timezone.now() + timedelta(minutes=45),
            duration_minutes=30,
        )

        self.auth_as(self.doctor_user)
        response = self.client.get(reverse('appointment-today'))

        self.assertEqual(response.status_code, 200)
        returned_ids = [item['id'] for item in self.body(response)]
        self.assertNotIn(str(self.appointment.id), returned_ids)
        self.assertIn(str(waiting_appointment.id), returned_ids)


class DoctorDashboardStatsTests(MedicalApiTestCase):
    def setUp(self):
        self.owner_user = CustomUser.objects.create_user(
            username='clinic_owner',
            email='clinic@example.com',
            password='Pass12345!',
            role='clinic',
            first_name='Clinic',
            last_name='Owner',
        )
        self.clinic = Clinic.objects.create(
            owner=self.owner_user,
            name='Test Clinic',
            slug='test-clinic',
            address='Test address',
            phone_number='+998901234567',
            email='clinic@test.uz',
            registration_number='REG-TEST-001',
            status='active',
        )

        self.doctor_user = CustomUser.objects.create_user(
            username='doctor_user',
            email='doctor@example.com',
            password='Pass12345!',
            role='doctor',
            first_name='Test',
            last_name='Doctor',
        )
        self.doctor = Doctor.objects.create(
            user=self.doctor_user,
            clinic=self.clinic,
            license_number='LIC-001',
            working_days='Mon,Tue,Wed,Thu,Fri,Sat,Sun',
        )

        self.patient_user = CustomUser.objects.create_user(
            username='patient_user',
            email='patient@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Test',
            last_name='Patient',
        )
        self.patient = Patient.objects.create(
            user=self.patient_user,
        )

        self.auth_as(self.doctor_user)
        self.url = reverse('appointment-doctor-dashboard-stats')

    def _create_record(self, created_at):
        record = MedicalRecord.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            clinic=self.clinic,
            chief_complaint='test',
        )
        MedicalRecord.objects.filter(id=record.id).update(created_at=created_at)
        return MedicalRecord.objects.get(id=record.id)

    def _create_appointment(self, status, scheduled_date, updated_at=None):
        appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            clinic=self.clinic,
            status=status,
            scheduled_date=scheduled_date,
            duration_minutes=30,
        )
        if updated_at is not None:
            Appointment.objects.filter(id=appointment.id).update(updated_at=updated_at)
            appointment.refresh_from_db()
        return appointment

    def test_dashboard_stats_counts_from_checkin_checkout_window(self):
        now = timezone.localtime().replace(hour=12, minute=0, second=0, microsecond=0)
        in_session = now - timedelta(minutes=2, seconds=30)
        before_checkin = now - timedelta(minutes=4)
        after_checkout = now - timedelta(minutes=1)
        prev_month = now - timedelta(days=35)

        DoctorWorkRecord.objects.create(
            doctor=self.doctor,
            date=timezone.localdate(),
            checked_in_at=(now - timedelta(minutes=3)).time(),
            checked_out_at=(now - timedelta(minutes=2)).time(),
        )

        self._create_record(created_at=in_session)
        self._create_record(created_at=before_checkin)
        self._create_record(created_at=after_checkout)
        self._create_record(created_at=prev_month)

        self._create_appointment(status=Appointment.Status.CANCELLED, scheduled_date=now - timedelta(hours=1))
        self._create_appointment(status=Appointment.Status.NO_SHOW, scheduled_date=now - timedelta(hours=2))
        self._create_appointment(
            status=Appointment.Status.CANCELLED,
            scheduled_date=prev_month,
            updated_at=prev_month,
        )

        with patch('apps.medical.views.timezone.localtime', return_value=now):
            response = self.client.get(self.url)
        response_json = self.body(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_json['today_24h_patients'], 1)
        self.assertEqual(response_json['monthly_arrived_patients'], 3)
        self.assertEqual(response_json['monthly_cancelled_appointments'], 2)
        self.assertIn('no-store', response.headers.get('Cache-Control', ''))

    def test_today_24h_counts_without_checkin_record_using_day_window(self):
        now = timezone.localtime()
        self._create_record(created_at=now - timedelta(hours=2))

        response = self.client.get(self.url)
        response_json = self.body(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_json['today_24h_patients'], 1)

    def test_bot_cancelled_future_appointment_counts_in_monthly_cancelled(self):
        future_dt = timezone.localtime() + timedelta(days=2)
        appt = self._create_appointment(status=Appointment.Status.SCHEDULED, scheduled_date=future_dt)
        appt.telegram_user_id = 777001
        appt.telegram_chat_id = 777001
        appt.save(update_fields=['telegram_user_id', 'telegram_chat_id', 'updated_at'])

        service = TelegramBotService()
        cast(Any, service).client = SimpleNamespace(
            send_message=lambda *args, **kwargs: None,
            answer_callback_query=lambda *args, **kwargs: None,
        )

        service._cancel_appointment_from_bot(
            telegram_user_id=777001,
            chat_id=777001,
            appointment_id=str(appt.id),
        )

        response = self.client.get(self.url)
        response_json = self.body(response)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response_json['monthly_cancelled_appointments'], 1)

    def test_dashboard_stats_salary_balance_uses_fixed_monthly_value(self):
        self.doctor.compensation_type = 'salary'
        self.doctor.compensation_value = Decimal('1500000')
        self.doctor.save(update_fields=['compensation_type', 'compensation_value'])

        now = timezone.localtime()
        self._create_record(created_at=now - timedelta(hours=1))

        response = self.client.get(self.url)
        payload = self.body(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['compensation_type'], 'salary')
        self.assertEqual(float(payload['compensation_value']), 1500000.0)
        self.assertEqual(float(payload['monthly_estimated_balance']), 1500000.0)

    def test_dashboard_stats_percent_balance_uses_monthly_revenue(self):
        self.doctor.compensation_type = 'percent'
        self.doctor.compensation_value = Decimal('25')
        self.doctor.consultation_fee = 80000
        self.doctor.save(update_fields=['compensation_type', 'compensation_value', 'consultation_fee'])

        now = timezone.localtime()
        appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            clinic=self.clinic,
            status=Appointment.Status.COMPLETED,
            scheduled_date=now - timedelta(hours=2),
            consultation_fee=100000,
        )
        MedicalRecord.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            clinic=self.clinic,
            appointment=appointment,
            chief_complaint='record-with-appointment',
        )
        MedicalRecord.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            clinic=self.clinic,
            chief_complaint='record-with-default-fee',
        )

        response = self.client.get(self.url)
        payload = self.body(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['compensation_type'], 'percent')
        self.assertEqual(float(payload['compensation_value']), 25.0)
        self.assertEqual(float(payload['monthly_effective_revenue']), 180000.0)
        self.assertEqual(float(payload['monthly_estimated_balance']), 45000.0)

    def test_dashboard_stats_are_zero_when_doctor_is_unassigned_or_inactive(self):
        now = timezone.localtime()
        self._create_record(created_at=now - timedelta(hours=1))
        self._create_appointment(status=Appointment.Status.CANCELLED, scheduled_date=now - timedelta(minutes=30))

        self.doctor.is_active = False
        self.doctor.clinic = None
        self.doctor.save(update_fields=['is_active', 'clinic', 'updated_at'])

        response = self.client.get(self.url)
        payload = self.body(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['today_24h_patients'], 0)
        self.assertEqual(payload['monthly_cancelled_appointments'], 0)
        self.assertEqual(payload['monthly_arrived_patients'], 0)
        self.assertEqual(float(payload['monthly_effective_revenue']), 0.0)
        self.assertEqual(float(payload['monthly_estimated_balance']), 0.0)

    def test_dashboard_stats_scope_monthly_values_to_active_employment_window(self):
        now = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)
        active_started_at = now - timedelta(days=2)

        self.doctor.compensation_type = 'salary'
        self.doctor.compensation_value = Decimal('0')
        self.doctor.consultation_fee = 100000
        self.doctor.save(update_fields=['compensation_type', 'compensation_value', 'consultation_fee'])

        DoctorEmployment.objects.create(
            doctor=self.doctor,
            clinic=self.clinic,
            started_at=now - timedelta(days=10),
            ended_at=active_started_at - timedelta(minutes=1),
            compensation_type='salary',
            compensation_value=Decimal('0'),
        )
        DoctorEmployment.objects.create(
            doctor=self.doctor,
            clinic=self.clinic,
            started_at=active_started_at,
            compensation_type='percent',
            compensation_value=Decimal('50'),
        )

        self._create_record(created_at=active_started_at - timedelta(hours=1))
        self._create_record(created_at=active_started_at + timedelta(hours=1))

        self._create_appointment(
            status=Appointment.Status.CANCELLED,
            scheduled_date=active_started_at - timedelta(minutes=30),
        )
        self._create_appointment(
            status=Appointment.Status.CANCELLED,
            scheduled_date=active_started_at + timedelta(minutes=30),
        )

        response = self.client.get(self.url)
        payload = self.body(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['monthly_arrived_patients'], 1)
        self.assertEqual(payload['monthly_cancelled_appointments'], 1)
        self.assertEqual(payload['compensation_type'], 'percent')
        self.assertEqual(float(payload['compensation_value']), 50.0)
        self.assertEqual(float(payload['monthly_effective_revenue']), 100000.0)
        self.assertEqual(float(payload['monthly_estimated_balance']), 50000.0)

class MonthlyStatsHistoryTests(MedicalApiTestCase):
    def setUp(self):
        self.owner_user = CustomUser.objects.create_user(
            username='clinic_owner_monthly_stats',
            email='clinic.monthly.stats@example.com',
            password='Pass12345!',
            role='clinic',
            first_name='Clinic',
            last_name='Owner',
        )
        self.clinic = Clinic.objects.create(
            owner=self.owner_user,
            name='Monthly Stats Clinic',
            slug='monthly-stats-clinic',
            address='Test address',
            phone_number='+998901234569',
            email='clinic.monthly.stats@test.uz',
            registration_number='REG-MONTHLY-STATS-001',
            status='active',
        )

        self.doctor_user = CustomUser.objects.create_user(
            username='doctor_monthly_stats',
            email='doctor.monthly.stats@example.com',
            password='Pass12345!',
            role='doctor',
            first_name='Monthly',
            last_name='Doctor',
        )
        self.doctor = Doctor.objects.create(
            user=self.doctor_user,
            clinic=self.clinic,
            license_number='LIC-MONTHLY-STATS-001',
            working_days='Mon,Tue,Wed,Thu,Fri,Sat,Sun',
        )

        self.patient_user = CustomUser.objects.create_user(
            username='patient_monthly_stats',
            email='patient.monthly.stats@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Monthly',
            last_name='Patient',
        )
        self.patient = Patient.objects.create(
            user=self.patient_user,
        )

        self.auth_as(self.owner_user)
        self.url = reverse('appointment-monthly-stats')

    def _month_shift(self, year: int, month: int, offset: int) -> tuple[int, int]:
        absolute = (year * 12 + (month - 1)) + offset
        return absolute // 12, (absolute % 12) + 1

    def _create_appointment(self, year: int, month: int, day: int, status: str, is_paid: bool, fee: int):
        local_dt = timezone.make_aware(datetime(year, month, day, 10, 0, 0))
        return Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            clinic=self.clinic,
            status=status,
            scheduled_date=local_dt,
            duration_minutes=30,
            is_paid=is_paid,
            consultation_fee=fee,
        )

    def _create_record_for_appointment(self, appointment: Appointment, year: int, month: int, day: int):
        created_at = timezone.make_aware(datetime(year, month, day, 11, 0, 0))
        record = MedicalRecord.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            clinic=self.clinic,
            appointment=appointment,
            chief_complaint='monthly-stats-record',
        )
        MedicalRecord.objects.filter(id=record.id).update(created_at=created_at)
        return MedicalRecord.objects.get(id=record.id)

    def test_monthly_stats_returns_consistent_history_and_cumulative_totals(self):
        today = timezone.localdate()
        current_year, current_month = today.year, today.month
        prev_year, prev_month = self._month_shift(current_year, current_month, -1)
        old_year, old_month = self._month_shift(current_year, current_month, -2)

        old_appt = self._create_appointment(old_year, old_month, 10, Appointment.Status.COMPLETED, True, 90000)
        prev_appt = self._create_appointment(prev_year, prev_month, 10, Appointment.Status.CONFIRMED, True, 120000)
        cur_paid_appt = self._create_appointment(current_year, current_month, 10, Appointment.Status.SCHEDULED, True, 150000)
        cur_unpaid_appt = self._create_appointment(current_year, current_month, 11, Appointment.Status.WAITING, False, 170000)
        self._create_appointment(current_year, current_month, 12, Appointment.Status.CANCELLED, True, 300000)

        self._create_record_for_appointment(old_appt, old_year, old_month, 10)
        self._create_record_for_appointment(prev_appt, prev_year, prev_month, 10)
        self._create_record_for_appointment(cur_paid_appt, current_year, current_month, 10)
        self._create_record_for_appointment(cur_unpaid_appt, current_year, current_month, 11)

        response = self.client.get(self.url, {'clinic': self.clinic.id})
        payload = self.body(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['current']['appointments'], 2)
        self.assertEqual(payload['previous']['appointments'], 1)
        self.assertEqual(payload['comparison']['appointments_diff'], 1)
        self.assertEqual(float(payload['current']['revenue_total']), 320000.0)
        self.assertEqual(float(payload['current']['revenue_paid']), 150000.0)
        self.assertEqual(float(payload['previous']['revenue_total']), 120000.0)
        self.assertEqual(float(payload['comparison']['revenue_total_diff']), 200000.0)
        self.assertEqual(float(payload['comparison']['revenue_paid_diff']), 30000.0)

        history = payload.get('history') or []
        self.assertGreaterEqual(len(history), 3)

        last = history[-1]
        self.assertEqual(last['year'], current_year)
        self.assertEqual(last['month'], current_month)
        self.assertEqual(last['appointments'], payload['current']['appointments'])
        self.assertEqual(last['cumulative_appointments'], sum(item['appointments'] for item in history))
        self.assertEqual(last['cumulative_revenue_total'], sum(float(item['revenue_total']) for item in history))

        prev_entry = None
        for item in history:
            if not isinstance(item, dict):
                continue
            if item.get('year') == prev_year and item.get('month') == prev_month:
                prev_entry = item
                break
        self.assertIsNotNone(prev_entry)
        if prev_entry is not None:
            self.assertEqual(prev_entry['appointments'], payload['previous']['appointments'])

    def test_monthly_stats_forbidden_for_non_clinic_user(self):
        self.auth_as(self.doctor_user)
        response = self.client.get(self.url, {'clinic': self.clinic.id})
        self.assertEqual(response.status_code, 403)


class ClinicDoctorStatsAuditTests(MedicalApiTestCase):
    def setUp(self):
        self.owner_user = CustomUser.objects.create_user(
            username='clinic_owner_audit',
            email='clinic.audit@example.com',
            password='Pass12345!',
            role='clinic',
            first_name='Clinic',
            last_name='Owner',
        )
        self.clinic = Clinic.objects.create(
            owner=self.owner_user,
            name='Audit Clinic',
            slug='audit-clinic',
            address='Audit address',
            phone_number='+998901234580',
            email='clinic.audit@test.uz',
            registration_number='REG-AUDIT-001',
            status='active',
        )

        self.doctor_user = CustomUser.objects.create_user(
            username='doctor_audit_user',
            email='doctor.audit@example.com',
            password='Pass12345!',
            role='doctor',
            first_name='Audit',
            last_name='Doctor',
        )
        self.doctor = Doctor.objects.create(
            user=self.doctor_user,
            clinic=self.clinic,
            license_number='LIC-AUDIT-001',
            working_days='Mon,Tue,Wed,Thu,Fri,Sat,Sun',
        )

        self.patient_user = CustomUser.objects.create_user(
            username='patient_audit_user',
            email='patient.audit@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Audit',
            last_name='Patient',
        )
        self.patient = Patient.objects.create(
            user=self.patient_user,
        )

        now = timezone.localtime().replace(hour=10, minute=0, second=0, microsecond=0)

        MedicalRecord.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            clinic=self.clinic,
            chief_complaint='audit-1',
        )
        MedicalRecord.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            clinic=self.clinic,
            chief_complaint='audit-2',
        )

        Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            clinic=self.clinic,
            status=Appointment.Status.CANCELLED,
            scheduled_date=now - timedelta(hours=2),
            duration_minutes=30,
        )

        self.url = reverse('appointment-clinic-doctor-stats-audit')

    def test_clinic_owner_gets_audit_rows_and_metrics(self):
        self.auth_as(self.owner_user)

        response = self.client.get(self.url)
        payload = self.body(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['doctor_count'], 1)
        self.assertEqual(payload['mismatch_count'], 0)

        doctor_row = payload['doctors'][0]
        self.assertEqual(doctor_row['doctor_id'], str(self.doctor.id))
        self.assertEqual(doctor_row['api_monthly_arrived_patients'], 2)
        self.assertEqual(doctor_row['legacy_monthly_patients'], 2)
        self.assertEqual(doctor_row['monthly_cancelled_appointments'], 1)
        self.assertTrue(doctor_row['is_monthly_match'])

    def test_non_clinic_user_is_forbidden(self):
        self.auth_as(self.doctor_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)


class ClinicDashboardStatsTests(MedicalApiTestCase):
    def setUp(self):
        self.owner_user = CustomUser.objects.create_user(
            username='clinic_owner_dashboard_stats',
            email='clinic.dashboard.stats@example.com',
            password='Pass12345!',
            role='clinic',
            first_name='Clinic',
            last_name='Owner',
        )
        self.clinic = Clinic.objects.create(
            owner=self.owner_user,
            name='Dashboard Stats Clinic',
            slug='dashboard-stats-clinic',
            address='Test address',
            phone_number='+998901234581',
            email='clinic.dashboard.stats@test.uz',
            registration_number='REG-DASH-STATS-001',
            status='active',
        )

        self.doctor1_user = CustomUser.objects.create_user(
            username='doctor_dashboard_stats_1',
            email='doctor.dashboard.stats.1@example.com',
            password='Pass12345!',
            role='doctor',
            first_name='Doctor',
            last_name='One',
        )
        self.doctor1 = Doctor.objects.create(
            user=self.doctor1_user,
            clinic=self.clinic,
            license_number='LIC-DASH-STATS-001',
            working_days='Mon,Tue,Wed,Thu,Fri,Sat,Sun',
            is_active=True,
        )

        self.doctor2_user = CustomUser.objects.create_user(
            username='doctor_dashboard_stats_2',
            email='doctor.dashboard.stats.2@example.com',
            password='Pass12345!',
            role='doctor',
            first_name='Doctor',
            last_name='Two',
        )
        self.doctor2 = Doctor.objects.create(
            user=self.doctor2_user,
            clinic=self.clinic,
            license_number='LIC-DASH-STATS-002',
            working_days='Mon,Tue,Wed,Thu,Fri,Sat,Sun',
            is_active=False,
        )

        self.patient_user = CustomUser.objects.create_user(
            username='patient_dashboard_stats',
            email='patient.dashboard.stats@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Patient',
            last_name='Stats',
        )
        self.patient = Patient.objects.create(
            user=self.patient_user,
        )

        now = timezone.localtime()
        appointment1 = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor1,
            clinic=self.clinic,
            status=Appointment.Status.COMPLETED,
            scheduled_date=now - timedelta(hours=2),
            consultation_fee=120000,
        )
        appointment2 = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor1,
            clinic=self.clinic,
            status=Appointment.Status.COMPLETED,
            scheduled_date=now - timedelta(hours=1),
            consultation_fee=120000,
        )

        MedicalRecord.objects.create(
            patient=self.patient,
            doctor=self.doctor1,
            clinic=self.clinic,
            appointment=appointment1,
            chief_complaint='stats-1',
        )
        MedicalRecord.objects.create(
            patient=self.patient,
            doctor=self.doctor1,
            clinic=self.clinic,
            appointment=appointment2,
            chief_complaint='stats-2',
        )

        specialization = Specialization.objects.create(name='Terapevt', code='THER')
        DoctorSpecialization.objects.create(
            doctor=self.doctor1,
            specialization=specialization,
            consultation_fee=120000,
            is_active=True,
        )
        DoctorSpecialization.objects.filter(doctor=self.doctor1, specialization=specialization).update(consultation_fee=150000)

        DoctorWorkRecord.objects.create(
            doctor=self.doctor1,
            date=timezone.localdate(),
            checked_in_at=(timezone.localtime() - timedelta(hours=3)).time(),
            checked_out_at=(timezone.localtime() - timedelta(hours=1)).time(),
        )

        self.url = reverse('appointment-clinic-dashboard-stats')

    def test_clinic_dashboard_stats_returns_db_values(self):
        self.auth_as(self.owner_user)
        response = self.client.get(self.url)
        payload = self.body(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['active_doctors'], 1)
        self.assertEqual(payload['total_doctors'], 2)
        self.assertEqual(payload['monthly_arrived_patients'], 2)
        self.assertGreaterEqual(float(payload['monthly_total_hours']), 2.0)
        self.assertEqual(float(payload['monthly_estimated_revenue']), 240000.0)
        self.assertTrue(isinstance(payload['monthly_estimated_revenue_by_doctor'], list))
        self.assertEqual(len(payload['monthly_estimated_revenue_by_doctor']), 1)
        doctor_row = payload['monthly_estimated_revenue_by_doctor'][0]
        self.assertEqual(doctor_row['seen_patients'], 2)
        self.assertEqual(float(doctor_row['consultation_fee']), 120000.0)
        self.assertEqual(float(doctor_row['estimated_revenue']), 240000.0)

    def test_clinic_dashboard_stats_forbidden_for_non_clinic(self):
        self.auth_as(self.doctor1_user)
        response = self.client.get(self.url)
        self.assertEqual(response.status_code, 403)

    def test_clinic_dashboard_stats_uses_monthly_medical_records_for_count_and_revenue(self):
        now = timezone.localtime()
        Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor1,
            clinic=self.clinic,
            status=Appointment.Status.COMPLETED,
            scheduled_date=now - timedelta(minutes=30),
            consultation_fee=120000,
        )

        MedicalRecord.objects.create(
            patient=self.patient,
            doctor=self.doctor1,
            clinic=self.clinic,
            chief_complaint='stats-3',
        )

        self.auth_as(self.owner_user)
        response = self.client.get(self.url)
        payload = self.body(response)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload['monthly_arrived_patients'], 3)
        self.assertEqual(float(payload['monthly_estimated_revenue']), 390000.0)
        doctor_row = payload['monthly_estimated_revenue_by_doctor'][0]
        self.assertEqual(doctor_row['seen_patients'], 3)
        self.assertEqual(float(doctor_row['estimated_revenue']), 390000.0)


class MedicalRecordAutoAppointmentTests(MedicalApiTestCase):
    def setUp(self):
        self.owner_user = CustomUser.objects.create_user(
            username='clinic_owner_record_auto',
            email='clinic.record.auto@example.com',
            password='Pass12345!',
            role='clinic',
            first_name='Clinic',
            last_name='Owner',
        )
        self.clinic = Clinic.objects.create(
            owner=self.owner_user,
            name='Record Auto Clinic',
            slug='record-auto-clinic',
            address='Test address',
            phone_number='+998901234582',
            email='clinic.record.auto@test.uz',
            registration_number='REG-RECORD-AUTO-001',
            status='active',
        )

        self.doctor_user = CustomUser.objects.create_user(
            username='doctor_record_auto',
            email='doctor.record.auto@example.com',
            password='Pass12345!',
            role='doctor',
            first_name='Doctor',
            last_name='Auto',
        )
        self.doctor = Doctor.objects.create(
            user=self.doctor_user,
            clinic=self.clinic,
            license_number='LIC-RECORD-AUTO-001',
            consultation_fee=70000,
            working_days='Mon,Tue,Wed,Thu,Fri,Sat,Sun',
            is_active=True,
        )

        self.patient_user = CustomUser.objects.create_user(
            username='patient_record_auto',
            email='patient.record.auto@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Patient',
            last_name='Auto',
        )
        self.patient = Patient.objects.create(
            user=self.patient_user,
        )

        self.url = reverse('medical-record-list')
        self.auth_as(self.doctor_user)

    def test_create_record_auto_creates_completed_appointment_with_doctor_fee(self):
        response = self.client.post(self.url, {
            'patient': str(self.patient.id),
            'doctor': str(self.doctor.id),
            'clinic': str(self.clinic.id),
            'chief_complaint': 'Bosh og\'rig\'i',
            'assessment': 'Migren',
            'plan': 'Davolash rejasi',
        }, format='json')

        self.assertEqual(response.status_code, 201)
        record_id = response.json().get('id')
        self.assertTrue(record_id)

        record = MedicalRecord.objects.select_related('appointment').get(id=record_id)
        appointment = record.appointment
        self.assertIsNotNone(appointment)
        appointment = cast(Appointment, appointment)
        self.assertEqual(appointment.status, Appointment.Status.COMPLETED)
        self.assertEqual(float(appointment.consultation_fee), 70000.0)

    def test_create_record_with_existing_appointment_marks_completed_and_sets_fee(self):
        appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            clinic=self.clinic,
            status=Appointment.Status.WAITING,
            scheduled_date=timezone.now(),
            consultation_fee=0,
        )

        response = self.client.post(self.url, {
            'patient': str(self.patient.id),
            'doctor': str(self.doctor.id),
            'clinic': str(self.clinic.id),
            'appointment': str(appointment.id),
            'chief_complaint': 'Qorin og\'rig\'i',
            'assessment': 'Gastrit',
            'plan': 'Parhez',
        }, format='json')

        self.assertEqual(response.status_code, 201)
        appointment.refresh_from_db()
        self.assertEqual(appointment.status, Appointment.Status.COMPLETED)
        self.assertEqual(float(appointment.consultation_fee), 70000.0)

    def test_create_record_sets_fee_from_unique_specialty_when_doctor_fee_zero(self):
        self.doctor.consultation_fee = 0
        self.doctor.save(update_fields=['consultation_fee'])

        specialization = Specialization.objects.create(name='Nevrolog-auto', code='NEU-AUTO')
        DoctorSpecialization.objects.create(
            doctor=self.doctor,
            specialization=specialization,
            consultation_fee=25000,
            is_active=True,
        )

        response = self.client.post(self.url, {
            'patient': str(self.patient.id),
            'doctor': str(self.doctor.id),
            'clinic': str(self.clinic.id),
            'chief_complaint': 'Bel og\'rig\'i',
            'assessment': 'Nevralgiya',
            'plan': 'Davolash',
        }, format='json')

        self.assertEqual(response.status_code, 201)
        record = MedicalRecord.objects.select_related('appointment').get(id=response.json().get('id'))
        appointment = cast(Appointment, record.appointment)
        self.assertIsNotNone(appointment)
        self.assertEqual(appointment.status, Appointment.Status.COMPLETED)
        self.assertEqual(float(appointment.consultation_fee), 25000.0)

class BookingWindowLunchTests(MedicalApiTestCase):
    def setUp(self):
        self.owner_user = CustomUser.objects.create_user(
            username='clinic_owner_lunch',
            email='clinic.lunch@example.com',
            password='Pass12345!',
            role='clinic',
            first_name='Clinic',
            last_name='Owner',
        )
        self.clinic = Clinic.objects.create(
            owner=self.owner_user,
            name='Lunch Clinic',
            slug='lunch-clinic',
            address='Test address',
            phone_number='+998901234568',
            email='clinic.lunch@test.uz',
            registration_number='REG-LUNCH-001',
            status='active',
        )

        self.doctor_user = CustomUser.objects.create_user(
            username='doctor_lunch_user',
            email='doctor.lunch@example.com',
            password='Pass12345!',
            role='doctor',
            first_name='Lunch',
            last_name='Doctor',
        )
        self.doctor = Doctor.objects.create(
            user=self.doctor_user,
            clinic=self.clinic,
            license_number='LIC-LUNCH-001',
            working_days='Mon,Tue,Wed,Thu,Fri,Sat,Sun',
            available_from='09:00',
            available_until='18:00',
            lunch_break_start='12:00',
            lunch_break_end='13:00',
            is_checked_in=True,
        )

    def test_online_booking_allows_when_doctor_not_checked_in(self):
        self.doctor.is_checked_in = False
        self.doctor.save(update_fields=['is_checked_in'])

        target_date = timezone.localdate() + timedelta(days=1)
        slot = DoctorAvailability.objects.create(
            doctor=self.doctor,
            date=target_date,
            start_time='10:00',
            end_time='10:30',
            status='available',
        )

        url = reverse('appointment-online-booking')
        response = self.client.post(url, {
            'clinic': str(self.clinic.id),
            'doctor': str(self.doctor.id),
            'slot_id': str(slot.id),
            'first_name': 'Ali',
            'last_name': 'Valiyev',
            'phone_number': '+998901111000',
        }, format='json')

        self.assertEqual(response.status_code, 201)

    def test_online_booking_rejects_date_after_tomorrow(self):
        target_date = timezone.localdate() + timedelta(days=2)
        slot = DoctorAvailability.objects.create(
            doctor=self.doctor,
            date=target_date,
            start_time='10:00',
            end_time='10:30',
            status='available',
        )

        url = reverse('appointment-online-booking')
        response = self.client.post(url, {
            'clinic': str(self.clinic.id),
            'doctor': str(self.doctor.id),
            'slot_id': str(slot.id),
            'first_name': 'Ali',
            'last_name': 'Valiyev',
            'phone_number': '+998901111333',
        }, format='json')

        self.assertEqual(response.status_code, 400)
        response_json = self.body(response)
        self.assertIn('bugun va ertaga', str(response_json.get('detail', '')).lower())

    def test_online_booking_rejects_lunch_time_slot(self):
        target_date = timezone.localdate() + timedelta(days=1)
        slot = DoctorAvailability.objects.create(
            doctor=self.doctor,
            date=target_date,
            start_time='12:00',
            end_time='12:30',
            status='available',
        )

        url = reverse('appointment-online-booking')
        response = self.client.post(url, {
            'clinic': str(self.clinic.id),
            'doctor': str(self.doctor.id),
            'slot_id': str(slot.id),
            'first_name': 'Ali',
            'last_name': 'Valiyev',
            'phone_number': '+998901111111',
        }, format='json')

        self.assertEqual(response.status_code, 400)
        response_json = self.body(response)
        self.assertIn('abet', str(response_json.get('detail', '')).lower())

    def test_online_booking_uses_selected_specialty_price(self):
        target_date = timezone.localdate() + timedelta(days=1)
        slot = DoctorAvailability.objects.create(
            doctor=self.doctor,
            date=target_date,
            start_time='10:00',
            end_time='10:30',
            status='available',
        )

        specialization = Specialization.objects.create(name='Dermatolog', code='DERM')
        specialty_price = DoctorSpecialization.objects.create(
            doctor=self.doctor,
            specialization=specialization,
            consultation_fee=25000,
            is_active=True,
        )

        url = reverse('appointment-online-booking')
        response = self.client.post(url, {
            'clinic': str(self.clinic.id),
            'doctor': str(self.doctor.id),
            'specialty_price_id': str(specialty_price.id),
            'slot_id': str(slot.id),
            'first_name': 'Ali',
            'last_name': 'Valiyev',
            'phone_number': '+998901111112',
        }, format='json')

        self.assertEqual(response.status_code, 201)
        appointment_id = response.json().get('appointment', {}).get('id')
        self.assertTrue(appointment_id)
        appointment = Appointment.objects.get(id=appointment_id)
        self.assertEqual(float(appointment.consultation_fee), 25000.0)

    def test_online_booking_without_specialty_id_uses_uniform_active_specialty_fee(self):
        self.doctor.consultation_fee = 35000
        self.doctor.save(update_fields=['consultation_fee'])

        target_date = timezone.localdate() + timedelta(days=1)
        slot = DoctorAvailability.objects.create(
            doctor=self.doctor,
            date=target_date,
            start_time='10:40',
            end_time='11:10',
            status='available',
        )

        specialization = Specialization.objects.create(name='Lor', code='LOR')
        DoctorSpecialization.objects.create(
            doctor=self.doctor,
            specialization=specialization,
            consultation_fee=25000,
            is_active=True,
        )

        url = reverse('appointment-online-booking')
        response = self.client.post(url, {
            'clinic': str(self.clinic.id),
            'doctor': str(self.doctor.id),
            'slot_id': str(slot.id),
            'first_name': 'Ali',
            'last_name': 'Valiyev',
            'phone_number': '+998901111119',
        }, format='json')

        self.assertEqual(response.status_code, 201)
        appointment_id = response.json().get('appointment', {}).get('id')
        self.assertTrue(appointment_id)
        appointment = Appointment.objects.get(id=appointment_id)
        self.assertEqual(float(appointment.consultation_fee), 25000.0)

    def test_online_booking_with_invalid_specialty_id_returns_400(self):
        target_date = timezone.localdate() + timedelta(days=1)
        slot = DoctorAvailability.objects.create(
            doctor=self.doctor,
            date=target_date,
            start_time='11:20',
            end_time='11:50',
            status='available',
        )

        url = reverse('appointment-online-booking')
        response = self.client.post(url, {
            'clinic': str(self.clinic.id),
            'doctor': str(self.doctor.id),
            'specialty_price_id': '11111111-1111-1111-1111-111111111111',
            'slot_id': str(slot.id),
            'first_name': 'Ali',
            'last_name': 'Valiyev',
            'phone_number': '+998901111101',
        }, format='json')

        self.assertEqual(response.status_code, 400)
        response_json = self.body(response)
        self.assertIn('ixtisoslik', str(response_json.get('detail', '')).lower())

    def test_online_booking_requires_specialty_when_multiple_fees_exist(self):
        self.doctor.consultation_fee = 0
        self.doctor.save(update_fields=['consultation_fee'])

        target_date = timezone.localdate() + timedelta(days=1)
        slot = DoctorAvailability.objects.create(
            doctor=self.doctor,
            date=target_date,
            start_time='14:20',
            end_time='14:50',
            status='available',
        )

        spec_a = Specialization.objects.create(name='Kardio', code='KRD')
        spec_b = Specialization.objects.create(name='Nevro', code='NVR')
        DoctorSpecialization.objects.create(
            doctor=self.doctor,
            specialization=spec_a,
            consultation_fee=20000,
            is_active=True,
        )
        DoctorSpecialization.objects.create(
            doctor=self.doctor,
            specialization=spec_b,
            consultation_fee=25000,
            is_active=True,
        )

        url = reverse('appointment-online-booking')
        response = self.client.post(url, {
            'clinic': str(self.clinic.id),
            'doctor': str(self.doctor.id),
            'slot_id': str(slot.id),
            'first_name': 'Ali',
            'last_name': 'Valiyev',
            'phone_number': '+998901111102',
        }, format='json')

        self.assertEqual(response.status_code, 400)
        response_json = self.body(response)
        self.assertIn('ixtisoslikni tanlang', str(response_json.get('detail', '')).lower())

    def test_online_booking_selected_zero_specialty_fee_falls_back_to_doctor_fee(self):
        self.doctor.consultation_fee = 50000
        self.doctor.save(update_fields=['consultation_fee'])

        target_date = timezone.localdate() + timedelta(days=1)
        slot = DoctorAvailability.objects.create(
            doctor=self.doctor,
            date=target_date,
            start_time='15:20',
            end_time='15:50',
            status='available',
        )

        specialization = Specialization.objects.create(name='Allergolog', code='ALRG')
        specialty_price = DoctorSpecialization.objects.create(
            doctor=self.doctor,
            specialization=specialization,
            consultation_fee=0,
            is_active=True,
        )

        url = reverse('appointment-online-booking')
        response = self.client.post(url, {
            'clinic': str(self.clinic.id),
            'doctor': str(self.doctor.id),
            'specialty_price_id': str(specialty_price.id),
            'slot_id': str(slot.id),
            'first_name': 'Ali',
            'last_name': 'Valiyev',
            'phone_number': '+998901111103',
        }, format='json')

        self.assertEqual(response.status_code, 201)
        appointment_id = response.json().get('appointment', {}).get('id')
        self.assertTrue(appointment_id)
        appointment = Appointment.objects.get(id=appointment_id)
        self.assertEqual(float(appointment.consultation_fee), 50000.0)

    def test_public_booking_rejects_lunch_time(self):
        target_date = timezone.localdate() + timedelta(days=1)

        url = reverse('appointment-public-booking')
        response = self.client.post(url, {
            'clinic': str(self.clinic.id),
            'doctor': str(self.doctor.id),
            'full_name': 'Ali Valiyev',
            'phone_number': '+998901111111',
            'date': target_date.isoformat(),
            'time': '12:00',
        }, format='json')

        self.assertEqual(response.status_code, 400)
        response_json = self.body(response)
        self.assertIn('abet', str(response_json.get('detail', '')).lower())

    def test_public_booking_rejects_date_after_tomorrow(self):
        target_date = timezone.localdate() + timedelta(days=2)

        url = reverse('appointment-public-booking')
        response = self.client.post(url, {
            'clinic': str(self.clinic.id),
            'doctor': str(self.doctor.id),
            'full_name': 'Ali Valiyev',
            'phone_number': '+998901111444',
            'date': target_date.isoformat(),
            'time': '10:00',
        }, format='json')

        self.assertEqual(response.status_code, 400)
        response_json = self.body(response)
        self.assertIn('bugun va ertaga', str(response_json.get('detail', '')).lower())

    def test_availability_endpoint_excludes_lunch_slots(self):
        target_date = timezone.localdate() + timedelta(days=1)
        url = reverse('doctor-availability-available')

        response = self.client.get(url, {
            'doctor': str(self.doctor.id),
            'date': target_date.isoformat(),
        })

        self.assertEqual(response.status_code, 200)
        slots = self.body(response) or []
        self.assertTrue(all(slot.get('start_time')[:5] != '12:00' for slot in slots))
        self.assertTrue(all(slot.get('start_time')[:5] != '12:30' for slot in slots))


class QueueDecisionTests(MedicalApiTestCase):
    def setUp(self):
        self.owner_user = CustomUser.objects.create_user(
            username='clinic_owner_queue',
            email='clinic.queue@example.com',
            password='Pass12345!',
            role='clinic',
            first_name='Clinic',
            last_name='Owner',
        )
        self.clinic = Clinic.objects.create(
            owner=self.owner_user,
            name='Queue Clinic',
            slug='queue-clinic',
            address='Test address',
            phone_number='+998901234570',
            email='clinic.queue@test.uz',
            registration_number='REG-QUEUE-001',
            status='active',
        )

        self.doctor_user = CustomUser.objects.create_user(
            username='doctor_queue_user',
            email='doctor.queue@example.com',
            password='Pass12345!',
            role='doctor',
            first_name='Queue',
            last_name='Doctor',
        )
        self.doctor = Doctor.objects.create(
            user=self.doctor_user,
            clinic=self.clinic,
            license_number='LIC-QUEUE-001',
            working_days='Mon,Tue,Wed,Thu,Fri,Sat,Sun',
            slot_minutes=30,
        )

        self.patient1_user = CustomUser.objects.create_user(
            username='patient_queue_1',
            email='patient.queue.1@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Queue',
            last_name='One',
        )
        self.patient1 = Patient.objects.create(user=self.patient1_user)

        self.patient2_user = CustomUser.objects.create_user(
            username='patient_queue_2',
            email='patient.queue.2@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Queue',
            last_name='Two',
        )
        self.patient2 = Patient.objects.create(user=self.patient2_user)

        now = safe_queue_base_now()
        self.appt1 = Appointment.objects.create(
            patient=self.patient1,
            doctor=self.doctor,
            clinic=self.clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=1,
            scheduled_date=now + timedelta(minutes=1),
            duration_minutes=30,
            telegram_chat_id=100001,
        )
        self.appt2 = Appointment.objects.create(
            patient=self.patient2,
            doctor=self.doctor,
            clinic=self.clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=2,
            scheduled_date=now + timedelta(minutes=20),
            duration_minutes=30,
            telegram_chat_id=100002,
        )

        self.auth_as(self.doctor_user)

    def test_wait_decision_recalculates_queue_and_notifies_when_shift_over_15_minutes(self):
        now_local = queue_reference_now()
        self.appt1.scheduled_date = now_local + timedelta(minutes=1)
        self.appt1.save(update_fields=['scheduled_date', 'updated_at'])
        self.appt2.scheduled_date = now_local + timedelta(minutes=10)
        self.appt2.save(update_fields=['scheduled_date', 'updated_at'])

        old_appt1_dt = self.appt1.scheduled_date
        old_appt2_dt = self.appt2.scheduled_date

        sent_messages = []

        class _Client:
            def send_message(self, chat_id, text, reply_markup=None):
                sent_messages.append({'chat_id': chat_id, 'text': text})

        with patch('apps.medical.telegram_bot_service.TelegramBotService') as mocked_service:
            mocked_service.return_value._require_client.return_value = _Client()

            url = reverse('appointment-queue-decision', args=[self.appt1.id])
            response = self.client.post(url, {'decision': 'wait'}, format='json')

        self.assertEqual(response.status_code, 200)
        response_json = self.body(response)
        self.assertGreaterEqual(response_json.get('queue_updated', 0), 2)

        self.appt1.refresh_from_db()
        self.appt2.refresh_from_db()

        self.assertGreater(self.appt1.scheduled_date, old_appt1_dt)
        self.assertGreater(self.appt2.scheduled_date, old_appt2_dt)
        self.assertEqual(int((self.appt1.scheduled_date - old_appt1_dt).total_seconds() // 60), 15)
        self.assertEqual(int((self.appt2.scheduled_date - old_appt2_dt).total_seconds() // 60), 15)
        self.assertEqual(self.appt1.queue_position, 1)
        self.assertEqual(self.appt2.queue_position, 2)

        chat_ids = [entry['chat_id'] for entry in sent_messages]
        self.assertIn(100001, chat_ids)
        self.assertNotIn(100002, chat_ids)

    def test_enter_decision_uses_realtime_for_selected_and_message(self):
        # Put selected appointment further in future to ensure it is pulled to now.
        future_dt = timezone.localtime().replace(second=0, microsecond=0) + timedelta(minutes=18)
        self.appt1.scheduled_date = future_dt
        self.appt1.save(update_fields=['scheduled_date', 'updated_at'])
        self.appt2.scheduled_date = future_dt + timedelta(minutes=10)
        self.appt2.save(update_fields=['scheduled_date', 'updated_at'])

        sent_messages = []

        class _Client:
            def send_message(self, chat_id, text, reply_markup=None):
                sent_messages.append({'chat_id': chat_id, 'text': text})

        with patch('apps.medical.telegram_bot_service.TelegramBotService') as mocked_service:
            mocked_service.return_value._require_client.return_value = _Client()

            now_before = timezone.localtime().replace(second=0, microsecond=0)
            url = reverse('appointment-queue-decision', args=[self.appt1.id])
            response = self.client.post(url, {'decision': 'enter'}, format='json')
            now_after = timezone.localtime().replace(second=0, microsecond=0)

        self.assertEqual(response.status_code, 200)

        self.appt1.refresh_from_db()
        self.assertGreaterEqual(self.appt1.scheduled_date, now_before)
        self.assertLessEqual(self.appt1.scheduled_date, now_after)

        leader_msgs = [m for m in sent_messages if m['chat_id'] == 100001]
        self.assertTrue(leader_msgs)
        expected_time = timezone.localtime(self.appt1.scheduled_date).strftime('%d.%m.%Y %H:%M')
        self.assertIn(expected_time, leader_msgs[-1]['text'])

    def test_enter_decision_notifies_next_patients_when_notify_all_shifted_enabled(self):
        now_local = queue_reference_now()
        self.appt1.scheduled_date = now_local + timedelta(minutes=1)
        self.appt1.save(update_fields=['scheduled_date', 'updated_at'])
        self.appt2.scheduled_date = now_local + timedelta(minutes=10)
        self.appt2.save(update_fields=['scheduled_date', 'updated_at'])

        sent_messages = []

        class _Client:
            def send_message(self, chat_id, text, reply_markup=None):
                sent_messages.append({'chat_id': chat_id, 'text': text})

        with patch('apps.medical.telegram_bot_service.TelegramBotService') as mocked_service:
            mocked_service.return_value._require_client.return_value = _Client()
            url = reverse('appointment-queue-decision', args=[self.appt1.id])
            response = self.client.post(
                url,
                {
                    'decision': 'enter',
                    'notify_current': False,
                    'notify_all_shifted': True,
                },
                format='json',
            )

        self.assertEqual(response.status_code, 200)
        chat_ids = [entry['chat_id'] for entry in sent_messages]
        self.assertIn(100002, chat_ids)

    def test_enter_decision_skips_shift_message_for_recently_arrived_patient(self):
        now_local = safe_queue_base_now()
        self.appt1.scheduled_date = now_local + timedelta(minutes=20)
        self.appt1.patient_arrival_confirmed_at = timezone.now() - timedelta(minutes=5)
        self.appt1.save(update_fields=['scheduled_date', 'patient_arrival_confirmed_at', 'updated_at'])

        self.appt2.scheduled_date = now_local + timedelta(minutes=50)
        self.appt2.save(update_fields=['scheduled_date', 'updated_at'])

        sent_messages = []

        class _Client:
            def send_message(self, chat_id, text, reply_markup=None):
                sent_messages.append({'chat_id': chat_id, 'text': text})

        with patch('apps.medical.telegram_bot_service.TelegramBotService') as mocked_service:
            mocked_service.return_value._require_client.return_value = _Client()
            url = reverse('appointment-queue-decision', args=[self.appt1.id])
            response = self.client.post(
                url,
                {
                    'decision': 'enter',
                    'notify_current': True,
                    'notify_all_shifted': True,
                },
                format='json',
            )

        self.assertEqual(response.status_code, 200)

        first_patient_messages = [m['text'] for m in sent_messages if m['chat_id'] == 100001]
        self.assertTrue(any('Navbat sizga keldi' in text for text in first_patient_messages))
        self.assertFalse(any('Navbat vaqtingiz yangilandi' in text for text in first_patient_messages))

    def test_enter_decision_rejects_non_leader_appointment(self):
        # Queue leader is appt1, so enter on appt2 must be rejected.
        url = reverse('appointment-queue-decision', args=[self.appt2.id])
        response = self.client.post(url, {'decision': 'enter'}, format='json')

        self.assertEqual(response.status_code, 400)
        response_json = self.body(response)
        self.assertIn('1-bemor', str(response_json.get('detail', '')))

        self.appt1.refresh_from_db()
        self.appt2.refresh_from_db()
        self.assertEqual(self.appt1.queue_position, 1)
        self.assertEqual(self.appt2.queue_position, 2)

    def test_wait_decision_rejects_non_leader_appointment(self):
        # Queue leader is appt1, so wait on appt2 must be rejected.
        url = reverse('appointment-queue-decision', args=[self.appt2.id])
        response = self.client.post(url, {'decision': 'wait'}, format='json')

        self.assertEqual(response.status_code, 400)
        response_json = self.body(response)
        self.assertIn('1-bemor', str(response_json.get('detail', '')))

        self.appt1.refresh_from_db()
        self.appt2.refresh_from_db()
        self.assertEqual(self.appt1.queue_position, 1)
        self.assertEqual(self.appt2.queue_position, 2)

    def test_cancel_decision_cancels_target_and_compresses_queue(self):
        self.patient3_user = CustomUser.objects.create_user(
            username='patient_queue_3',
            email='patient.queue.3@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Queue',
            last_name='Three',
        )
        self.patient3 = Patient.objects.create(user=self.patient3_user)

        old_appt2_dt = self.appt2.scheduled_date
        self.appt3 = Appointment.objects.create(
            patient=self.patient3,
            doctor=self.doctor,
            clinic=self.clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=3,
            scheduled_date=old_appt2_dt + timedelta(minutes=30),
            duration_minutes=30,
            telegram_chat_id=100003,
        )
        old_appt3_dt = self.appt3.scheduled_date
        call_time = timezone.localtime().replace(second=0, microsecond=0)

        sent_messages = []

        class _Client:
            def send_message(self, chat_id, text, reply_markup=None):
                sent_messages.append({'chat_id': chat_id, 'text': text})

        with patch('apps.medical.telegram_bot_service.TelegramBotService') as mocked_service:
            mocked_service.return_value._require_client.return_value = _Client()

            url = reverse('appointment-queue-decision', args=[self.appt1.id])
            response = self.client.post(url, {'decision': 'cancel'}, format='json')

        self.assertEqual(response.status_code, 200)

        self.appt1.refresh_from_db()
        self.appt2.refresh_from_db()
        self.appt3.refresh_from_db()

        self.assertEqual(self.appt1.status, Appointment.Status.CANCELLED)
        self.assertEqual(self.appt2.queue_position, 1)
        self.assertEqual(self.appt3.queue_position, 2)
        self.assertNotEqual(self.appt2.scheduled_date, old_appt2_dt)
        self.assertNotEqual(self.appt3.scheduled_date, old_appt3_dt)
        self.assertGreaterEqual(self.appt2.scheduled_date, call_time)
        self.assertEqual(
            int((self.appt3.scheduled_date - self.appt2.scheduled_date).total_seconds() // 60),
            30,
        )

        chat_ids = [entry['chat_id'] for entry in sent_messages]
        self.assertIn(100001, chat_ids)
        self.assertIn(100003, chat_ids)
        self.assertNotIn(100002, chat_ids)
        self.assertTrue(any(entry['chat_id'] == 100003 and 'Oldingizda faqat 1 ta bemor bor' in entry['text'] for entry in sent_messages))


class TelegramRescheduleDayButtonsTests(MedicalApiTestCase):
    def setUp(self):
        owner_user = CustomUser.objects.create_user(
            username='clinic_owner_tg',
            email='clinic.tg@example.com',
            password='Pass12345!',
            role='clinic',
            first_name='Clinic',
            last_name='Owner',
        )
        clinic = Clinic.objects.create(
            owner=owner_user,
            name='Telegram Clinic',
            slug='telegram-clinic',
            address='Test address',
            phone_number='+998901234569',
            email='clinic.tg@test.uz',
            registration_number='REG-TG-001',
            status='active',
        )

        doctor_user = CustomUser.objects.create_user(
            username='doctor_tg_user',
            email='doctor.tg@example.com',
            password='Pass12345!',
            role='doctor',
            first_name='Telegram',
            last_name='Doctor',
        )
        self.doctor = Doctor.objects.create(
            user=doctor_user,
            clinic=clinic,
            license_number='LIC-TG-001',
            working_days='Mon,Tue,Wed,Thu,Fri,Sat,Sun',
            available_from='09:00',
            available_until='14:00',
            lunch_break_start='12:00',
            lunch_break_end='13:00',
            slot_minutes=30,
        )

        patient_user = CustomUser.objects.create_user(
            username='patient_tg_user',
            email='patient.tg@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Telegram',
            last_name='Patient',
        )
        patient = Patient.objects.create(
            user=patient_user,
        )

        self.telegram_user_id = 900001
        tomorrow = timezone.localdate() + timedelta(days=1)
        self.appointment = Appointment.objects.create(
            patient=patient,
            doctor=self.doctor,
            clinic=clinic,
            status=Appointment.Status.SCHEDULED,
            scheduled_date=timezone.make_aware(
                timezone.datetime.combine(tomorrow, timezone.datetime.strptime('10:00', '%H:%M').time())
            ),
            duration_minutes=30,
            telegram_user_id=self.telegram_user_id,
            telegram_chat_id=self.telegram_user_id,
        )

    def test_resday_tomorrow_returns_inline_reslot_buttons_without_lunch_slots(self):
        sent_messages = []
        answered_callbacks = []

        service = TelegramBotService()
        cast(Any, service).client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda callback_query_id, text=None: answered_callbacks.append(
                {'callback_query_id': callback_query_id, 'text': text}
            ),
        )

        update = {
            'callback_query': {
                'id': 'cb-1',
                'data': f'resday:{self.appointment.id}:tomorrow',
                'from': {'id': self.telegram_user_id},
                'message': {'chat': {'id': self.telegram_user_id}},
            }
        }

        service.handle_update(update)

        self.assertTrue(sent_messages)
        payload = sent_messages[-1]
        self.assertIn('Ertangi bo‘sh vaqtlar', payload['text'])

        keyboard = (payload.get('reply_markup') or {}).get('inline_keyboard') or []
        callback_data_items = [
            btn.get('callback_data', '')
            for row in keyboard
            for btn in row
        ]
        self.assertTrue(callback_data_items)
        self.assertTrue(all(item.startswith(f'reslot:{self.appointment.id}:') for item in callback_data_items))
        self.assertTrue(all(not item.endswith('1200') and not item.endswith('1230') for item in callback_data_items))

        self.assertTrue(answered_callbacks)
        self.assertEqual(answered_callbacks[-1]['text'], 'Bo‘sh vaqtlar')

class TelegramStartTokenNormalizationTests(MedicalApiTestCase):
    def setUp(self):
        owner_user = CustomUser.objects.create_user(
            username='clinic_owner_tg_start',
            email='clinic.tg.start@example.com',
            password='Pass12345!',
            role='clinic',
            first_name='Clinic',
            last_name='Owner',
        )
        clinic = Clinic.objects.create(
            owner=owner_user,
            name='Telegram Start Clinic',
            slug='telegram-start-clinic',
            address='Test address',
            phone_number='+998901234501',
            email='clinic.tg.start@test.uz',
            registration_number='REG-TG-START-001',
            status='active',
        )

        doctor_user = CustomUser.objects.create_user(
            username='doctor_tg_start_user',
            email='doctor.tg.start@example.com',
            password='Pass12345!',
            role='doctor',
            first_name='Start',
            last_name='Doctor',
        )
        doctor = Doctor.objects.create(
            user=doctor_user,
            clinic=clinic,
            license_number='LIC-TG-START-001',
            working_days='Mon,Tue,Wed,Thu,Fri,Sat,Sun',
            available_from='09:00',
            available_until='18:00',
        )

        patient_user = CustomUser.objects.create_user(
            username='patient_tg_start_user',
            email='patient.tg.start@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Start',
            last_name='Patient',
        )
        patient = Patient.objects.create(user=patient_user)

        self.telegram_user_id = 909001
        self.telegram_chat_id = 909001
        self.appointment = Appointment.objects.create(
            patient=patient,
            doctor=doctor,
            clinic=clinic,
            status=Appointment.Status.PENDING_TELEGRAM_CONFIRMATION,
            scheduled_date=timezone.now() + timedelta(hours=2),
            duration_minutes=30,
            telegram_token=uuid4(),
            telegram_token_expires_at=timezone.now() + timedelta(minutes=20),
        )

    def test_start_accepts_compact_uuid_payload(self):
        sent_messages = []
        service = TelegramBotService()
        cast(Any, service).client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        compact_token = self.appointment.telegram_token.hex
        service.handle_update({
            'message': {
                'from': {'id': self.telegram_user_id},
                'chat': {'id': self.telegram_chat_id},
                'text': f'/start {compact_token}',
            }
        })

        self.appointment.refresh_from_db()
        self.assertEqual(self.appointment.status, Appointment.Status.SCHEDULED)
        self.assertIsNone(self.appointment.telegram_token)
        self.assertEqual(self.appointment.telegram_user_id, self.telegram_user_id)
        self.assertEqual(self.appointment.telegram_chat_id, self.telegram_chat_id)
        self.assertTrue(any('Tasdiqlandi' in item.get('text', '') for item in sent_messages))

    def test_start_without_token_shows_current_appointments_for_linked_user(self):
        self.appointment.status = Appointment.Status.SCHEDULED
        self.appointment.telegram_user_id = self.telegram_user_id
        self.appointment.telegram_chat_id = self.telegram_chat_id
        self.appointment.telegram_token = None
        self.appointment.telegram_token_expires_at = None
        self.appointment.save(update_fields=['status', 'telegram_user_id', 'telegram_chat_id', 'telegram_token', 'telegram_token_expires_at', 'updated_at'])

        sent_messages = []
        service = TelegramBotService()
        cast(Any, service).client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        service.handle_update({
            'message': {
                'from': {'id': self.telegram_user_id},
                'chat': {'id': self.telegram_chat_id},
                'text': '/start',
            }
        })

        self.assertTrue(sent_messages)
        self.assertIn('Yaqin randevular', sent_messages[-1]['text'])

    def test_start_with_invalid_token_falls_back_to_menu_and_appointments_for_linked_user(self):
        self.appointment.status = Appointment.Status.SCHEDULED
        self.appointment.telegram_user_id = self.telegram_user_id
        self.appointment.telegram_chat_id = self.telegram_chat_id
        self.appointment.telegram_token = None
        self.appointment.telegram_token_expires_at = None
        self.appointment.save(update_fields=['status', 'telegram_user_id', 'telegram_chat_id', 'telegram_token', 'telegram_token_expires_at', 'updated_at'])

        sent_messages = []
        service = TelegramBotService()
        cast(Any, service).client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        service.handle_update({
            'message': {
                'from': {'id': self.telegram_user_id},
                'chat': {'id': self.telegram_chat_id},
                'text': '/start invalid-token',
            }
        })

        self.assertGreaterEqual(len(sent_messages), 2)
        self.assertIn('Bu token yaroqsiz yoki ishlatilgan.', sent_messages[0]['text'])
        self.assertIn('Yaqin randevular', sent_messages[-1]['text'])


class TelegramArrivalQueueUpdateTests(MedicalApiTestCase):
    def setUp(self):
        owner_user = CustomUser.objects.create_user(
            username='clinic_owner_arrive',
            email='clinic.arrive@example.com',
            password='Pass12345!',
            role='clinic',
            first_name='Clinic',
            last_name='Owner',
        )
        clinic = Clinic.objects.create(
            owner=owner_user,
            name='Arrival Clinic',
            slug='arrival-clinic',
            address='Test address',
            phone_number='+998901234560',
            email='clinic.arrive@test.uz',
            registration_number='REG-ARRIVE-001',
            status='active',
        )

        doctor_user = CustomUser.objects.create_user(
            username='doctor_arrive_user',
            email='doctor.arrive@example.com',
            password='Pass12345!',
            role='doctor',
            first_name='Arrival',
            last_name='Doctor',
        )
        self.doctor = Doctor.objects.create(
            user=doctor_user,
            clinic=clinic,
            license_number='LIC-ARRIVE-001',
            working_days='Mon,Tue,Wed,Thu,Fri,Sat,Sun',
            slot_minutes=30,
        )

        self.patient1_user = CustomUser.objects.create_user(
            username='patient_arrive_1',
            email='patient.arrive.1@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Arrive',
            last_name='One',
        )
        self.patient1 = Patient.objects.create(user=self.patient1_user)
        self.patient2_user = CustomUser.objects.create_user(
            username='patient_arrive_2',
            email='patient.arrive.2@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Arrive',
            last_name='Two',
        )
        self.patient2 = Patient.objects.create(user=self.patient2_user)

        self.patient3_user = CustomUser.objects.create_user(
            username='patient_arrive_3',
            email='patient.arrive.3@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Arrive',
            last_name='Three',
        )
        self.patient3 = Patient.objects.create(user=self.patient3_user)

        now = safe_queue_base_now()
        self.appt1 = Appointment.objects.create(
            patient=self.patient1,
            doctor=self.doctor,
            clinic=clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=1,
            scheduled_date=now + timedelta(minutes=20),
            duration_minutes=30,
            telegram_user_id=910001,
            telegram_chat_id=910001,
        )
        self.appt2 = Appointment.objects.create(
            patient=self.patient2,
            doctor=self.doctor,
            clinic=clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=2,
            scheduled_date=now + timedelta(minutes=50),
            duration_minutes=30,
            telegram_user_id=910002,
            telegram_chat_id=910002,
        )
        self.appt3 = Appointment.objects.create(
            patient=self.patient3,
            doctor=self.doctor,
            clinic=clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=3,
            scheduled_date=now + timedelta(minutes=80),
            duration_minutes=30,
            telegram_user_id=910003,
            telegram_chat_id=910003,
        )

    def test_arrive_recalculates_today_queue_with_30min_and_skips_second_message_for_same_patient(self):
        self.doctor.slot_minutes = 20
        self.doctor.save(update_fields=['slot_minutes', 'updated_at'])

        sent_messages = []

        service = TelegramBotService()
        cast(Any, service).client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        now_before = timezone.localtime().replace(second=0, microsecond=0)
        service._confirm_arrival_from_bot(
            telegram_user_id=910001,
            chat_id=910001,
            appointment_id=str(self.appt1.id),
        )
        now_after = timezone.localtime().replace(second=0, microsecond=0)

        self.appt1.refresh_from_db()
        self.appt2.refresh_from_db()
        self.appt3.refresh_from_db()

        self.assertIsNotNone(self.appt1.patient_arrival_confirmed_at)
        self.assertGreaterEqual(self.appt1.scheduled_date, now_before)
        self.assertLessEqual(self.appt1.scheduled_date, now_after)

        self.assertEqual(
            int((self.appt2.scheduled_date - self.appt1.scheduled_date).total_seconds() // 60),
            20,
        )
        self.assertEqual(
            int((self.appt3.scheduled_date - self.appt2.scheduled_date).total_seconds() // 60),
            20,
        )

        own_texts = [m['text'] for m in sent_messages if m['chat_id'] == 910001]
        self.assertTrue(any('Qabulga borishingiz tasdiqlandi' in text for text in own_texts))
        self.assertFalse(any('Navbat vaqtingiz yangilandi' in text for text in own_texts))

        self.assertTrue(any(m['chat_id'] == 910002 and 'Oldingizda faqat 1 ta bemor bor' in m['text'] for m in sent_messages))
        self.assertTrue(any(m['chat_id'] == 910003 and 'Oldingizda faqat 2 ta odam qoldi' in m['text'] for m in sent_messages))

    def test_arrive_recalculates_and_notifies_even_when_selected_is_in_progress(self):
        self.doctor.slot_minutes = 30
        self.doctor.save(update_fields=['slot_minutes', 'updated_at'])

        self.appt1.status = Appointment.Status.IN_PROGRESS
        self.appt1.save(update_fields=['status', 'updated_at'])

        sent_messages = []

        service = TelegramBotService()
        cast(Any, service).client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        service._confirm_arrival_from_bot(
            telegram_user_id=910001,
            chat_id=910001,
            appointment_id=str(self.appt1.id),
        )

        self.appt1.refresh_from_db()
        self.appt2.refresh_from_db()
        self.appt3.refresh_from_db()

        self.assertIsNotNone(self.appt1.patient_arrival_confirmed_at)
        self.assertEqual(
            int((self.appt2.scheduled_date - self.appt1.scheduled_date).total_seconds() // 60),
            30,
        )
        self.assertEqual(
            int((self.appt3.scheduled_date - self.appt2.scheduled_date).total_seconds() // 60),
            30,
        )

        own_texts = [m['text'] for m in sent_messages if m['chat_id'] == 910001]
        self.assertFalse(any('Navbat vaqtingiz yangilandi' in text for text in own_texts))
        self.assertTrue(any(m['chat_id'] == 910002 and 'Oldingizda faqat 1 ta bemor bor' in m['text'] for m in sent_messages))
        self.assertTrue(any(m['chat_id'] == 910003 and 'Oldingizda faqat 2 ta odam qoldi' in m['text'] for m in sent_messages))

    def test_arrive_shifts_only_following_patients(self):
        now = safe_queue_base_now()
        self.appt1.queue_position = 2
        self.appt1.scheduled_date = now + timedelta(minutes=30)
        self.appt1.save(update_fields=['queue_position', 'scheduled_date', 'updated_at'])

        self.appt2.queue_position = 3
        self.appt2.scheduled_date = now + timedelta(minutes=80)
        self.appt2.save(update_fields=['queue_position', 'scheduled_date', 'updated_at'])

        self.appt3.queue_position = 4
        self.appt3.scheduled_date = now + timedelta(minutes=120)
        self.appt3.save(update_fields=['queue_position', 'scheduled_date', 'updated_at'])

        patient0_user = CustomUser.objects.create_user(
            username='patient_arrive_0',
            email='patient.arrive.0@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Arrive',
            last_name='Zero',
        )
        patient0 = Patient.objects.create(user=patient0_user)
        appt0 = Appointment.objects.create(
            patient=patient0,
            doctor=self.doctor,
            clinic=self.appt1.clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=1,
            scheduled_date=now + timedelta(minutes=10),
            duration_minutes=30,
            telegram_user_id=910000,
            telegram_chat_id=910000,
        )
        old_appt0_dt = appt0.scheduled_date

        sent_messages = []
        service = TelegramBotService()
        cast(Any, service).client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append({'chat_id': chat_id, 'text': text}),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        service._confirm_arrival_from_bot(
            telegram_user_id=910001,
            chat_id=910001,
            appointment_id=str(self.appt1.id),
        )

        appt0.refresh_from_db()
        self.appt1.refresh_from_db()
        self.appt2.refresh_from_db()
        self.appt3.refresh_from_db()

        self.assertEqual(appt0.queue_position, 1)
        self.assertEqual(appt0.scheduled_date, old_appt0_dt)
        self.assertEqual(self.appt1.queue_position, 2)
        self.assertEqual(self.appt2.queue_position, 3)
        self.assertEqual(self.appt3.queue_position, 4)
        self.assertEqual(int((self.appt2.scheduled_date - self.appt1.scheduled_date).total_seconds() // 60), 30)
        self.assertEqual(int((self.appt3.scheduled_date - self.appt2.scheduled_date).total_seconds() // 60), 30)
        self.assertFalse(any(m['chat_id'] == 910000 and 'Navbat vaqtingiz yangilandi' in m['text'] for m in sent_messages))


class AutoQueueCycleTests(MedicalApiTestCase):
    def setUp(self):
        self.fixed_now = safe_queue_base_now()
        owner_user = CustomUser.objects.create_user(
            username='clinic_owner_auto_cycle',
            email='clinic.auto.cycle@example.com',
            password='Pass12345!',
            role='clinic',
            first_name='Clinic',
            last_name='Owner',
        )
        self.clinic = Clinic.objects.create(
            owner=owner_user,
            name='Auto Queue Clinic',
            slug='auto-queue-clinic',
            address='Test address',
            phone_number='+998901239901',
            email='clinic.auto.queue@test.uz',
            registration_number='REG-AUTO-QUEUE-001',
            status='active',
        )

        doctor_user = CustomUser.objects.create_user(
            username='doctor_auto_cycle_user',
            email='doctor.auto.cycle@example.com',
            password='Pass12345!',
            role='doctor',
            first_name='Auto',
            last_name='Doctor',
        )
        self.doctor = Doctor.objects.create(
            user=doctor_user,
            clinic=self.clinic,
            license_number='LIC-AUTO-CYCLE-001',
            working_days='Mon,Tue,Wed,Thu,Fri,Sat,Sun',
            available_from='00:00',
            available_until='23:59',
            slot_minutes=40,
            is_checked_in=True,
        )

        self.p1_user = CustomUser.objects.create_user(
            username='patient_auto_cycle_1',
            email='patient.auto.cycle.1@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Auto',
            last_name='One',
        )
        self.p2_user = CustomUser.objects.create_user(
            username='patient_auto_cycle_2',
            email='patient.auto.cycle.2@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Auto',
            last_name='Two',
        )
        self.p3_user = CustomUser.objects.create_user(
            username='patient_auto_cycle_3',
            email='patient.auto.cycle.3@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Auto',
            last_name='Three',
        )
        self.p1 = Patient.objects.create(user=self.p1_user)
        self.p2 = Patient.objects.create(user=self.p2_user)
        self.p3 = Patient.objects.create(user=self.p3_user)

        now = self.fixed_now
        self.appt1 = Appointment.objects.create(
            patient=self.p1,
            doctor=self.doctor,
            clinic=self.clinic,
            status=Appointment.Status.IN_PROGRESS,
            queue_position=1,
            scheduled_date=now,
            duration_minutes=40,
            telegram_user_id=920001,
            telegram_chat_id=920001,
            auto_turn_started_at=now - timedelta(minutes=45),
            auto_turn_prompt_sent_at=now - timedelta(minutes=35),
        )
        self.appt2 = Appointment.objects.create(
            patient=self.p2,
            doctor=self.doctor,
            clinic=self.clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=2,
            scheduled_date=now + timedelta(minutes=40),
            duration_minutes=40,
            telegram_user_id=920002,
            telegram_chat_id=920002,
        )
        self.appt3 = Appointment.objects.create(
            patient=self.p3,
            doctor=self.doctor,
            clinic=self.clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=3,
            scheduled_date=now + timedelta(minutes=80),
            duration_minutes=40,
            telegram_user_id=920003,
            telegram_chat_id=920003,
        )

        original_localtime = timezone.localtime

        def fixed_localtime(*args, **kwargs):
            if not args and 'value' not in kwargs:
                return self.fixed_now
            value = args[0] if args else kwargs.get('value')
            if value is None:
                return self.fixed_now
            return original_localtime(*args, **kwargs)

        fixed_now = self.fixed_now
        self._queue_time_patches = [
            patch('django.utils.timezone.localtime', side_effect=fixed_localtime),
            patch('django.utils.timezone.now', side_effect=lambda: fixed_now),
        ]
        for patcher in self._queue_time_patches:
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_auto_queue_cycle_cancels_and_shifts_when_no_response_for_30_minutes(self):
        sent_messages = []
        fake_client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        with patch('apps.medical.telegram_bot_service.TelegramBotService._require_client', return_value=fake_client):
            result = run_auto_queue_cycle()

        self.appt1.refresh_from_db()
        self.appt2.refresh_from_db()
        self.appt3.refresh_from_db()

        self.assertEqual(self.appt1.status, Appointment.Status.CANCELLED)
        self.assertEqual(self.appt2.queue_position, 1)
        self.assertEqual(self.appt3.queue_position, 2)
        self.assertEqual(self.appt2.status, Appointment.Status.IN_PROGRESS)
        self.assertIsNotNone(self.appt2.auto_turn_started_at)
        self.assertGreaterEqual(result.get('queues_shifted', 0), 1)
        self.assertTrue(any(msg['chat_id'] == 920001 and '30 daqiqa ichida javob kelmadi' in msg['text'] for msg in sent_messages))
        self.assertTrue(any(msg['chat_id'] == 920002 and 'Endi sizning navbatingiz' in msg['text'] for msg in sent_messages))
        self.assertTrue(any(msg['chat_id'] == 920003 and 'Yangi tartibda sizning taxminiy vaqtingiz' in msg['text'] for msg in sent_messages))

    def test_auto_queue_sends_prompt_immediately_when_turn_starts(self):
        Appointment.objects.filter(id=self.appt1.id).update(
            status=Appointment.Status.SCHEDULED,
            auto_turn_started_at=None,
            auto_turn_prompt_sent_at=None,
            auto_turn_last_reminder_at=None,
            auto_turn_response=None,
            auto_turn_responded_at=None,
            scheduled_date=self.fixed_now,
        )

        sent_messages = []
        fake_client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        with patch('apps.medical.telegram_bot_service.TelegramBotService._require_client', return_value=fake_client):
            run_auto_queue_cycle()

        self.appt1.refresh_from_db()

        self.assertIsNotNone(self.appt1.auto_turn_started_at)
        self.assertIsNotNone(self.appt1.auto_turn_prompt_sent_at)
        self.assertTrue(any(msg['chat_id'] == 920001 and 'Sizning navbat vaqtingiz keldi' in msg['text'] for msg in sent_messages))
        self.assertTrue(any(msg['chat_id'] == 920001 and 'Doktor qabuliga kirdingizmi' in msg['text'] for msg in sent_messages))

    def test_auto_queue_does_not_notify_next_as_entered_before_kirdim(self):
        now = timezone.localtime().replace(second=0, microsecond=0)
        Appointment.objects.filter(id=self.appt1.id).update(
            status=Appointment.Status.WAITING,
            auto_turn_started_at=None,
            auto_turn_prompt_sent_at=None,
            auto_turn_last_reminder_at=None,
            auto_turn_response=None,
            auto_turn_responded_at=None,
            scheduled_date=now - timedelta(minutes=10),
        )
        Appointment.objects.filter(id=self.appt2.id).update(
            status=Appointment.Status.SCHEDULED,
            scheduled_date=now + timedelta(minutes=30),
        )

        sent_messages = []
        fake_client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        with patch('apps.medical.telegram_bot_service.TelegramBotService._require_client', return_value=fake_client):
            run_auto_queue_cycle()

        self.assertFalse(any(
            msg['chat_id'] == 920002 and 'Oldingizdagi bemor qabulga kirdi' in msg['text']
            for msg in sent_messages
        ))

    def test_auto_queue_callback_yes_saves_response(self):
        sent_messages = []
        service = TelegramBotService()
        cast(Any, service).client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        with patch('apps.medical.tasks.run_auto_queue_cycle.delay') as mocked_auto_cycle:
            service._handle_callback_query({
                'id': 'cb-autoq-yes',
                'data': f'autoq:yes:{self.appt1.id}',
                'from': {'id': 920001},
                'message': {'chat': {'id': 920001}},
            })
            mocked_auto_cycle.assert_called_once()

        self.appt1.refresh_from_db()
        self.assertEqual(self.appt1.auto_turn_response, 'yes')
        self.assertIsNotNone(self.appt1.auto_turn_responded_at)
        self.assertIsNotNone(self.appt1.patient_arrival_confirmed_at)
        self.assertTrue(any("Ma'lumotingiz qabul qilindi" in msg['text'] for msg in sent_messages))
        self.assertTrue(any(msg.get('reply_markup') and 'rate:' in str(msg.get('reply_markup')) for msg in sent_messages))

    def test_auto_queue_callback_cancel_saves_response(self):
        sent_messages = []
        service = TelegramBotService()
        cast(Any, service).client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        service._handle_callback_query({
            'id': 'cb-autoq-cancel',
            'data': f'autoq:cancel:{self.appt1.id}',
            'from': {'id': 920001},
            'message': {'chat': {'id': 920001}},
        })

        self.appt1.refresh_from_db()
        self.assertEqual(self.appt1.auto_turn_response, 'cancel')
        self.assertIsNotNone(self.appt1.auto_turn_responded_at)
        self.assertTrue(any('Navbat bekor qilinadi' in msg['text'] for msg in sent_messages))

    def test_auto_queue_wait_keeps_position_and_sends_15min_followup_with_cancel(self):
        sent_messages = []
        service = TelegramBotService()
        cast(Any, service).client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        service._handle_callback_query({
            'id': 'cb-autoq-wait',
            'data': f'autoq:wait:{self.appt1.id}',
            'from': {'id': 920001},
            'message': {'chat': {'id': 920001}},
        })

        appt1_before = self.appt1.scheduled_date
        appt2_before = self.appt2.scheduled_date
        appt3_before = self.appt3.scheduled_date

        with patch('apps.medical.telegram_bot_service.TelegramBotService._require_client', return_value=cast(Any, service).client):
            run_auto_queue_cycle()

        self.appt1.refresh_from_db()
        self.appt2.refresh_from_db()
        self.appt3.refresh_from_db()

        self.assertEqual(self.appt1.queue_position, 1)
        self.assertEqual(self.appt2.queue_position, 2)
        self.assertEqual(self.appt3.queue_position, 3)
        self.assertEqual(self.appt1.status, Appointment.Status.WAITING)
        self.assertEqual(
            int((self.appt1.scheduled_date - appt1_before).total_seconds() // 60),
            15,
        )
        self.assertEqual(
            int((self.appt2.scheduled_date - appt2_before).total_seconds() // 60),
            15,
        )
        self.assertEqual(
            int((self.appt3.scheduled_date - appt3_before).total_seconds() // 60),
            15,
        )
        self.assertEqual(
            int((self.appt3.scheduled_date - self.appt2.scheduled_date).total_seconds() // 60),
            40,
        )
        self.assertTrue(any(
            msg['chat_id'] == 920001 and "Yangi taxminiy vaqtingiz" in msg['text']
            for msg in sent_messages
        ))
        self.assertTrue(any(
            msg['chat_id'] == 920002 and "Yangi taxminiy vaqtingiz" in msg['text']
            for msg in sent_messages
        ))
        self.assertTrue(any(
            msg['chat_id'] == 920003 and "Yangi taxminiy vaqtingiz" in msg['text']
            for msg in sent_messages
        ))
        self.assertTrue(any(
            msg['chat_id'] == 920002 and "15 daqiqaga kechiktirildi" in msg['text']
            for msg in sent_messages
        ))
        self.assertFalse(any(
            msg['chat_id'] == 920001 and "Navbat qayta hisoblanmoqda" in msg['text']
            for msg in sent_messages
        ))

        processed_wait_messages = [
            msg for msg in sent_messages
            if msg['chat_id'] == 920001 and "Yangi taxminiy vaqtingiz" in msg['text']
        ]
        self.assertEqual(len(processed_wait_messages), 1)

        with patch('apps.medical.telegram_bot_service.TelegramBotService._require_client', return_value=cast(Any, service).client):
            run_auto_queue_cycle()

        processed_wait_messages_after_second_tick = [
            msg for msg in sent_messages
            if msg['chat_id'] == 920001 and "Yangi taxminiy vaqtingiz" in msg['text']
        ]
        self.assertEqual(len(processed_wait_messages_after_second_tick), 1)

        Appointment.objects.filter(id=self.appt1.id).update(
            auto_turn_responded_at=timezone.now() - timedelta(minutes=16),
            auto_turn_last_reminder_at=timezone.now() - timedelta(minutes=17),
        )

        with patch('apps.medical.telegram_bot_service.TelegramBotService._require_client', return_value=cast(Any, service).client):
            run_auto_queue_cycle()

        self.assertTrue(any(
            msg['chat_id'] == 920001 and msg.get('reply_markup') and 'autoq:cancel' in str(msg['reply_markup'])
            for msg in sent_messages
        ))

    def test_auto_queue_wait_recalculates_eta_from_now_for_overdue_turn(self):
        now = timezone.localtime().replace(second=0, microsecond=0)
        Appointment.objects.filter(id=self.appt1.id).update(
            status=Appointment.Status.WAITING,
            scheduled_date=now - timedelta(hours=1),
            auto_turn_started_at=now - timedelta(hours=1),
            auto_turn_prompt_sent_at=now - timedelta(minutes=20),
            auto_turn_response='wait',
            auto_turn_responded_at=now,
            auto_turn_last_reminder_at=now - timedelta(minutes=1),
        )

        sent_messages = []
        fake_client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        with patch('apps.medical.telegram_bot_service.TelegramBotService._require_client', return_value=fake_client):
            run_auto_queue_cycle()

        self.appt1.refresh_from_db()
        self.appt2.refresh_from_db()

        self.assertGreaterEqual(
            int((self.appt1.scheduled_date - now).total_seconds() // 60),
            14,
        )
        self.assertEqual(
            int((self.appt2.scheduled_date - self.appt1.scheduled_date).total_seconds() // 60),
            40,
        )

    def test_auto_queue_duplicate_wait_tap_for_same_prompt_does_not_shift_twice(self):
        sent_messages = []
        service = TelegramBotService()
        cast(Any, service).client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        with patch('apps.medical.tasks.run_auto_queue_cycle.delay'):
            service._handle_callback_query({
                'id': 'cb-autoq-wait-dup-1',
                'data': f'autoq:wait:{self.appt1.id}',
                'from': {'id': 920001},
                'message': {'chat': {'id': 920001}},
            })
            service._handle_callback_query({
                'id': 'cb-autoq-wait-dup-2',
                'data': f'autoq:wait:{self.appt1.id}',
                'from': {'id': 920001},
                'message': {'chat': {'id': 920001}},
            })

        appt1_before = self.appt1.scheduled_date
        appt2_before = self.appt2.scheduled_date
        appt3_before = self.appt3.scheduled_date

        with patch('apps.medical.telegram_bot_service.TelegramBotService._require_client', return_value=cast(Any, service).client):
            run_auto_queue_cycle()

        self.appt1.refresh_from_db()
        self.appt2.refresh_from_db()
        self.appt3.refresh_from_db()

        self.assertEqual(int((self.appt1.scheduled_date - appt1_before).total_seconds() // 60), 15)
        self.assertEqual(int((self.appt2.scheduled_date - appt2_before).total_seconds() // 60), 15)
        self.assertEqual(int((self.appt3.scheduled_date - appt3_before).total_seconds() // 60), 15)
        self.assertTrue(any("allaqachon qabul qilingan" in m['text'] for m in sent_messages))

    def test_auto_queue_response_ignored_for_non_leader(self):
        sent_messages = []
        service = TelegramBotService()
        cast(Any, service).client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        Appointment.objects.filter(id=self.appt1.id).update(
            status=Appointment.Status.WAITING,
        )

        with patch('apps.medical.tasks.run_auto_queue_cycle.delay'):
            service._handle_callback_query({
                'id': 'cb-autoq-non-leader',
                'data': f'autoq:wait:{self.appt2.id}',
                'from': {'id': 920002},
                'message': {'chat': {'id': 920002}},
            })

        self.appt2.refresh_from_db()
        self.assertIsNone(self.appt2.auto_turn_response)
        self.assertTrue(any("tugma hozir faol emas" in m['text'] for m in sent_messages))

    def test_auto_queue_leader_uses_scheduled_time_not_stale_queue_position(self):
        sent_messages = []
        service = TelegramBotService()
        cast(Any, service).client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        # Intentionally make queue_position inconsistent with actual scheduled order.
        Appointment.objects.filter(id=self.appt1.id).update(
            queue_position=9,
            scheduled_date=timezone.now() + timedelta(minutes=30),
            status=Appointment.Status.WAITING,
        )
        Appointment.objects.filter(id=self.appt2.id).update(
            queue_position=2,
            scheduled_date=timezone.now() + timedelta(minutes=5),
            status=Appointment.Status.WAITING,
        )

        with patch('apps.medical.tasks.run_auto_queue_cycle.delay'):
            service._handle_callback_query({
                'id': 'cb-autoq-stale-queue-pos',
                'data': f'autoq:wait:{self.appt1.id}',
                'from': {'id': 920001},
                'message': {'chat': {'id': 920001}},
            })

        self.appt1.refresh_from_db()
        self.assertIsNone(self.appt1.auto_turn_response)
        self.assertTrue(any("tugma hozir faol emas" in m['text'] for m in sent_messages))

    def test_auto_queue_supports_legacy_large_interval_values(self):
        self.doctor.slot_minutes = 90
        self.doctor.save(update_fields=['slot_minutes', 'updated_at'])
        Appointment.objects.filter(id=self.appt1.id).update(
            auto_turn_started_at=timezone.now() - timedelta(minutes=95),
            auto_turn_prompt_sent_at=timezone.now() - timedelta(minutes=35),
        )

        sent_messages = []
        fake_client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        with patch('apps.medical.telegram_bot_service.TelegramBotService._require_client', return_value=fake_client):
            run_auto_queue_cycle()

        self.appt2.refresh_from_db()
        self.appt3.refresh_from_db()
        self.assertEqual(
            int((self.appt3.scheduled_date - self.appt2.scheduled_date).total_seconds() // 60),
            90,
        )

    def test_auto_queue_does_not_modify_tomorrow_appointments(self):
        tomorrow = timezone.localtime(self.appt1.scheduled_date) + timedelta(days=1)
        tomorrow_appt = Appointment.objects.create(
            patient=self.p1,
            doctor=self.doctor,
            clinic=self.clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=7,
            scheduled_date=tomorrow,
            duration_minutes=40,
            telegram_user_id=930001,
            telegram_chat_id=930001,
        )
        expected_scheduled = tomorrow_appt.scheduled_date

        fake_client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: None,
            answer_callback_query=lambda *args, **kwargs: None,
        )

        with patch('apps.medical.telegram_bot_service.TelegramBotService._require_client', return_value=fake_client):
            run_auto_queue_cycle()

        tomorrow_appt.refresh_from_db()
        self.assertEqual(tomorrow_appt.status, Appointment.Status.SCHEDULED)
        self.assertEqual(tomorrow_appt.queue_position, 7)
        self.assertEqual(tomorrow_appt.scheduled_date, expected_scheduled)

    def test_auto_queue_starts_for_not_checked_in_doctor_when_first_time_arrives(self):
        self.doctor.is_checked_in = False
        self.doctor.save(update_fields=['is_checked_in', 'updated_at'])

        Appointment.objects.filter(id=self.appt1.id).update(
            status=Appointment.Status.SCHEDULED,
            scheduled_date=timezone.now() - timedelta(minutes=5),
            auto_turn_started_at=None,
            auto_turn_prompt_sent_at=None,
            auto_turn_last_reminder_at=None,
            auto_turn_response=None,
            auto_turn_responded_at=None,
        )

        fake_client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: None,
            answer_callback_query=lambda *args, **kwargs: None,
        )

        with patch('apps.medical.telegram_bot_service.TelegramBotService._require_client', return_value=fake_client):
            run_auto_queue_cycle()

        self.appt1.refresh_from_db()
        self.assertEqual(self.appt1.status, Appointment.Status.IN_PROGRESS)
        self.assertIsNotNone(self.appt1.auto_turn_started_at)

    def test_auto_queue_waits_for_scheduled_time_if_doctor_not_checked_in(self):
        self.doctor.is_checked_in = False
        self.doctor.save(update_fields=['is_checked_in', 'updated_at'])

        Appointment.objects.filter(id=self.appt1.id).update(
            status=Appointment.Status.SCHEDULED,
            scheduled_date=timezone.now() + timedelta(minutes=30),
            auto_turn_started_at=None,
            auto_turn_prompt_sent_at=None,
            auto_turn_last_reminder_at=None,
            auto_turn_response=None,
            auto_turn_responded_at=None,
        )

        fake_client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: None,
            answer_callback_query=lambda *args, **kwargs: None,
        )

        with patch('apps.medical.telegram_bot_service.TelegramBotService._require_client', return_value=fake_client):
            run_auto_queue_cycle()

        self.appt1.refresh_from_db()
        self.assertEqual(self.appt1.status, Appointment.Status.SCHEDULED)
        self.assertIsNone(self.appt1.auto_turn_started_at)


class MorningFirstQueueReminderTests(MedicalApiTestCase):
    def setUp(self):
        cache.clear()
        owner_user = CustomUser.objects.create_user(
            username='clinic_owner_morning_queue',
            email='clinic.morning.queue@example.com',
            password='Pass12345!',
            role='clinic',
            first_name='Clinic',
            last_name='Owner',
        )
        self.clinic = Clinic.objects.create(
            owner=owner_user,
            name='Morning Queue Clinic',
            slug='morning-queue-clinic',
            address='Test address',
            phone_number='+998901239902',
            email='clinic.morning.queue@test.uz',
            registration_number='REG-MORNING-QUEUE-001',
            status='active',
        )

        doctor_user = CustomUser.objects.create_user(
            username='doctor_morning_queue_user',
            email='doctor.morning.queue@example.com',
            password='Pass12345!',
            role='doctor',
            first_name='Morning',
            last_name='Doctor',
        )
        self.doctor = Doctor.objects.create(
            user=doctor_user,
            clinic=self.clinic,
            license_number='LIC-MORNING-QUEUE-001',
            working_days='Mon,Tue,Wed,Thu,Fri,Sat,Sun',
            available_from='08:00',
            available_until='20:00',
            slot_minutes=80,
            is_checked_in=False,
        )

        p1_user = CustomUser.objects.create_user(
            username='patient_morning_queue_1',
            email='patient.morning.queue.1@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Morning',
            last_name='One',
        )
        p2_user = CustomUser.objects.create_user(
            username='patient_morning_queue_2',
            email='patient.morning.queue.2@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Morning',
            last_name='Two',
        )
        self.p1 = Patient.objects.create(user=p1_user)
        self.p2 = Patient.objects.create(user=p2_user)

        now = timezone.localtime().replace(second=0, microsecond=0)
        doctor_start = now + timedelta(minutes=30)
        self.doctor.available_from = doctor_start.time()
        self.doctor.save(update_fields=['available_from', 'updated_at'])

        self.today_first = Appointment.objects.create(
            patient=self.p1,
            doctor=self.doctor,
            clinic=self.clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=1,
            scheduled_date=now + timedelta(hours=2),
            duration_minutes=80,
            telegram_user_id=940001,
            telegram_chat_id=940001,
        )
        self.today_second = Appointment.objects.create(
            patient=self.p2,
            doctor=self.doctor,
            clinic=self.clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=2,
            scheduled_date=now + timedelta(hours=3, minutes=20),
            duration_minutes=80,
            telegram_user_id=940002,
            telegram_chat_id=940002,
        )
        self.tomorrow_appt = Appointment.objects.create(
            patient=self.p2,
            doctor=self.doctor,
            clinic=self.clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=1,
            scheduled_date=now + timedelta(days=1, hours=1),
            duration_minutes=80,
            telegram_user_id=940003,
            telegram_chat_id=940003,
        )

    def test_morning_first_queue_reminder_sends_only_to_today_first_patient(self):
        sent_messages = []
        fake_client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        with override_settings(AUTO_QUEUE_START_REMINDER_WINDOW_MINUTES=180):
            with patch('apps.medical.telegram_bot_service.TelegramBotService._require_client', return_value=fake_client):
                result = send_today_first_queue_reminders()

        self.assertEqual(result.get('sent'), 1)
        self.assertTrue(any(m['chat_id'] == 940001 for m in sent_messages))
        self.assertFalse(any(m['chat_id'] == 940002 for m in sent_messages))
        self.assertFalse(any(m['chat_id'] == 940003 for m in sent_messages))
        self.assertTrue(any('1-navbatdasiz' in m['text'] for m in sent_messages))
        self.assertTrue(any('80 daqiqa' in m['text'] for m in sent_messages))

    def test_morning_first_queue_reminder_is_idempotent_same_day(self):
        sent_messages = []
        fake_client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        with override_settings(AUTO_QUEUE_START_REMINDER_WINDOW_MINUTES=180):
            with patch('apps.medical.telegram_bot_service.TelegramBotService._require_client', return_value=fake_client):
                first_result = send_today_first_queue_reminders()
                second_result = send_today_first_queue_reminders()

        self.assertEqual(first_result.get('sent'), 1)
        self.assertEqual(second_result.get('sent'), 0)
        self.assertGreaterEqual(second_result.get('skipped_already_sent', 0), 1)
        self.assertEqual(len(sent_messages), 1)

    def test_morning_first_queue_reminder_skips_outside_start_minus_30_window(self):
        sent_messages = []
        fake_client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        self.doctor.available_from = (timezone.localtime() + timedelta(hours=4)).time()
        self.doctor.save(update_fields=['available_from', 'updated_at'])

        with override_settings(AUTO_QUEUE_START_REMINDER_WINDOW_MINUTES=1):
            with patch('apps.medical.telegram_bot_service.TelegramBotService._require_client', return_value=fake_client):
                result = send_today_first_queue_reminders()

        self.assertEqual(result.get('sent'), 0)
        self.assertGreaterEqual(result.get('skipped_not_in_window', 0), 1)
        self.assertEqual(len(sent_messages), 0)

    def test_legacy_15min_prompt_is_skipped_for_today_auto_queue_appointments(self):
        result = send_telegram_appointment_15min_prompt(str(self.today_first.id))
        self.assertEqual(result.get('status'), 'skipped')
        self.assertEqual(result.get('reason'), 'managed_by_auto_queue')


class TelegramDoctorPatientsListTests(MedicalApiTestCase):
    def setUp(self):
        owner_user = CustomUser.objects.create_user(
            username='clinic_owner_doc_list',
            email='clinic.doc.list@example.com',
            password='Pass12345!',
            role='clinic',
            first_name='Clinic',
            last_name='Owner',
        )
        clinic = Clinic.objects.create(
            owner=owner_user,
            name='Doctor List Clinic',
            slug='doctor-list-clinic',
            address='Test address',
            phone_number='+998901234502',
            email='clinic.doc.list@test.uz',
            registration_number='REG-DOC-LIST-001',
            status='active',
        )

        doctor_user = CustomUser.objects.create_user(
            username='doctor_list_user',
            email='doctor.list@example.com',
            password='Pass12345!',
            role='doctor',
            first_name='List',
            last_name='Doctor',
        )
        self.telegram_user_id = 900777
        self.telegram_chat_id = 900777
        self.doctor = Doctor.objects.create(
            user=doctor_user,
            clinic=clinic,
            license_number='LIC-DOC-LIST-001',
            working_days='Mon,Tue,Wed,Thu,Fri,Sat,Sun',
            telegram_user_id=self.telegram_user_id,
            telegram_chat_id=self.telegram_chat_id,
        )

        patient_user_1 = CustomUser.objects.create_user(
            username='patient_doc_list_1',
            email='patient.doc.list.1@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Ali',
            last_name='Valiyev',
            phone_number='+998901111001',
        )
        patient_user_2 = CustomUser.objects.create_user(
            username='patient_doc_list_2',
            email='patient.doc.list.2@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Hasan',
            last_name='Karimov',
            phone_number='+998901111002',
        )

        patient_1 = Patient.objects.create(user=patient_user_1, phone_number='+998901111001')
        patient_2 = Patient.objects.create(user=patient_user_2, phone_number='+998901111002')

        today = timezone.localdate()
        Appointment.objects.create(
            patient=patient_2,
            doctor=self.doctor,
            clinic=clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=2,
            scheduled_date=timezone.make_aware(datetime.combine(today, datetime.strptime('10:30', '%H:%M').time())),
            duration_minutes=30,
        )
        Appointment.objects.create(
            patient=patient_1,
            doctor=self.doctor,
            clinic=clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=1,
            scheduled_date=timezone.make_aware(datetime.combine(today, datetime.strptime('09:30', '%H:%M').time())),
            duration_minutes=30,
        )

    def test_doctorpatients_command_returns_sorted_numbered_list(self):
        sent_messages = []
        service = TelegramBotService()
        cast(Any, service).client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        service.handle_update({
            'message': {
                'from': {'id': self.telegram_user_id},
                'chat': {'id': self.telegram_chat_id},
                'text': '/doctorpatients',
            }
        })

        self.assertTrue(sent_messages)
        text = sent_messages[-1]['text']
        self.assertIn("bemorlar ro'yxati", text.lower())
        self.assertIn('1. #1', text)
        self.assertIn('09:30', text)
        self.assertIn('2. #2', text)
        self.assertIn('10:30', text)

    def test_doctorpatients_callback_sends_list(self):
        sent_messages = []
        answered_callbacks = []
        service = TelegramBotService()
        cast(Any, service).client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda callback_query_id, text=None: answered_callbacks.append(
                {'callback_query_id': callback_query_id, 'text': text}
            ),
        )

        service.handle_update({
            'callback_query': {
                'id': 'cb-doc-list',
                'data': 'doctorpatients:today',
                'from': {'id': self.telegram_user_id},
                'message': {'chat': {'id': self.telegram_chat_id}},
            }
        })

        self.assertTrue(sent_messages)
        self.assertIn("bemorlar ro'yxati", sent_messages[-1]['text'].lower())
        self.assertTrue(answered_callbacks)
        self.assertEqual(answered_callbacks[-1]['text'], "Ro'yxat yuborildi")

    def test_doctorpatients_sorts_by_time_and_uses_sequential_numbers(self):
        Appointment.objects.filter(doctor=self.doctor).delete()

        patient_user_early = CustomUser.objects.create_user(
            username='patient_doc_list_early',
            email='patient.doc.list.early@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Early',
            last_name='Patient',
            phone_number='+998901111003',
        )
        patient_user_late = CustomUser.objects.create_user(
            username='patient_doc_list_late',
            email='patient.doc.list.late@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Late',
            last_name='Patient',
            phone_number='+998901111004',
        )

        patient_early = Patient.objects.create(user=patient_user_early, phone_number='+998901111003')
        patient_late = Patient.objects.create(user=patient_user_late, phone_number='+998901111004')

        today = timezone.localdate()
        Appointment.objects.create(
            patient=patient_late,
            doctor=self.doctor,
            clinic=self.doctor.clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=1,
            scheduled_date=timezone.make_aware(datetime.combine(today, datetime.strptime('14:30', '%H:%M').time())),
            duration_minutes=30,
        )
        Appointment.objects.create(
            patient=patient_early,
            doctor=self.doctor,
            clinic=self.doctor.clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=2,
            scheduled_date=timezone.make_aware(datetime.combine(today, datetime.strptime('14:00', '%H:%M').time())),
            duration_minutes=30,
        )

        sent_messages = []
        service = TelegramBotService()
        cast(Any, service).client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        service.handle_update({
            'message': {
                'from': {'id': self.telegram_user_id},
                'chat': {'id': self.telegram_chat_id},
                'text': '/doctorpatients',
            }
        })

        self.assertTrue(sent_messages)
        lines = sent_messages[-1]['text'].splitlines()
        patient_lines = [line for line in lines if line[:1].isdigit()]
        self.assertEqual(len(patient_lines), 2)
        self.assertIn('1. #1 • Early Patient • 14:00', patient_lines[0])
        self.assertIn('2. #2 • Late Patient • 14:30', patient_lines[1])


class TelegramMyAppointmentsQueueOrderTests(MedicalApiTestCase):
    def setUp(self):
        owner_user = CustomUser.objects.create_user(
            username='clinic_owner_myappts_queue',
            email='clinic.myappts.queue@example.com',
            password='Pass12345!',
            role='clinic',
            first_name='Clinic',
            last_name='Owner',
        )
        clinic = Clinic.objects.create(
            owner=owner_user,
            name='MyAppointments Queue Clinic',
            slug='myappointments-queue-clinic',
            address='Test address',
            phone_number='+998901234503',
            email='clinic.myappts.queue@test.uz',
            registration_number='REG-MYAPPTS-QUEUE-001',
            status='active',
        )

        doctor_user = CustomUser.objects.create_user(
            username='doctor_myappts_queue_user',
            email='doctor.myappts.queue@example.com',
            password='Pass12345!',
            role='doctor',
            first_name='Queue',
            last_name='Doctor',
        )
        self.doctor = Doctor.objects.create(
            user=doctor_user,
            clinic=clinic,
            license_number='LIC-MYAPPTS-QUEUE-001',
            working_days='Mon,Tue,Wed,Thu,Fri,Sat,Sun',
        )

        patient_user_target = CustomUser.objects.create_user(
            username='patient_myappts_target',
            email='patient.myappts.target@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Charos',
            last_name='Hudaniyev',
            phone_number='+9989223456789',
        )
        self.target_patient = Patient.objects.create(user=patient_user_target, phone_number='+9989223456789')

        patient_user_before_1 = CustomUser.objects.create_user(
            username='patient_myappts_before_1',
            email='patient.myappts.before.1@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Shaxlo',
            last_name='Karimova',
            phone_number='+9989219999902',
        )
        patient_before_1 = Patient.objects.create(user=patient_user_before_1, phone_number='+9989219999902')

        patient_user_before_2 = CustomUser.objects.create_user(
            username='patient_myappts_before_2',
            email='patient.myappts.before.2@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Farangiz',
            last_name='Farimuva',
            phone_number='+9989223456788',
        )
        patient_before_2 = Patient.objects.create(user=patient_user_before_2, phone_number='+9989223456788')

        patient_user_before_3 = CustomUser.objects.create_user(
            username='patient_myappts_before_3',
            email='patient.myappts.before.3@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Dilshoda',
            last_name='Raximova',
            phone_number='+9989334567890',
        )
        patient_before_3 = Patient.objects.create(user=patient_user_before_3, phone_number='+9989334567890')

        patient_user_after = CustomUser.objects.create_user(
            username='patient_myappts_after',
            email='patient.myappts.after@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Umida',
            last_name='Karimova',
            phone_number='+998911234567',
        )
        patient_after = Patient.objects.create(user=patient_user_after, phone_number='+998911234567')

        now = timezone.localtime().replace(second=0, microsecond=0) + timedelta(hours=1)
        Appointment.objects.create(
            patient=patient_before_1,
            doctor=self.doctor,
            clinic=clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=5,
            scheduled_date=now + timedelta(minutes=10),
            duration_minutes=30,
        )
        Appointment.objects.create(
            patient=patient_before_2,
            doctor=self.doctor,
            clinic=clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=1,
            scheduled_date=now + timedelta(minutes=20),
            duration_minutes=30,
        )
        Appointment.objects.create(
            patient=patient_before_3,
            doctor=self.doctor,
            clinic=clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=2,
            scheduled_date=now + timedelta(minutes=30),
            duration_minutes=30,
        )
        self.target_appointment = Appointment.objects.create(
            patient=self.target_patient,
            doctor=self.doctor,
            clinic=clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=9,
            scheduled_date=now + timedelta(minutes=45),
            duration_minutes=30,
            telegram_user_id=991234,
            telegram_chat_id=991234,
        )
        Appointment.objects.create(
            patient=patient_after,
            doctor=self.doctor,
            clinic=clinic,
            status=Appointment.Status.SCHEDULED,
            queue_position=2,
            scheduled_date=now + timedelta(minutes=70),
            duration_minutes=30,
        )

    def test_myappointments_uses_dashboard_queue_order_for_ahead_count(self):
        sent_messages = []
        service = TelegramBotService()
        cast(Any, service).client = SimpleNamespace(
            send_message=lambda chat_id, text, reply_markup=None: sent_messages.append(
                {'chat_id': chat_id, 'text': text, 'reply_markup': reply_markup}
            ),
            answer_callback_query=lambda *args, **kwargs: None,
        )

        service.handle_update({
            'message': {
                'from': {'id': 991234},
                'chat': {'id': 991234},
                'text': '/myappointments',
            }
        })

        self.assertTrue(sent_messages)
        text = sent_messages[-1]['text']
        self.assertIn('Yaqin randevular', text)
        self.assertIn('Oldinda: 3 ta odam', text)
        self.assertIn('Oldindagi bemorlar:', text)
        self.assertIn('#1 Shaxlo Karimova', text)
        self.assertIn('#2 Farangiz Farimuva', text)
        self.assertIn('#3 Dilshoda Raximova', text)
        self.assertNotIn('Oldinda: 8 ta odam', text)
