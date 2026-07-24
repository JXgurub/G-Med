"""
Test suite for Analytics API endpoints and service methods.
"""

from datetime import timedelta
import time
from typing import Any, cast

from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase, APIClient

from apps.clinics.models import Clinic
from apps.doctors.models import Doctor
from apps.medical.models import Appointment
from apps.patients.models import Patient
from apps.users.models import CustomUser
from core.analytics_service import AnalyticsService


class AnalyticsBaseTestCase(APITestCase):
    def setUp(self):
        self.owner_user = CustomUser.objects.create_user(
            username='analytics_owner',
            email='analytics.owner@example.com',
            password='Pass12345!',
            role='clinic',
            first_name='Analytics',
            last_name='Owner',
        )

        self.clinic = Clinic.objects.create(
            owner=self.owner_user,
            name='Analytics Test Clinic',
            slug='analytics-test-clinic',
            address='123 Analytics St',
            phone_number='+998901111111',
            email='analytics.clinic@test.uz',
            registration_number='REG-AN-001',
            status='active',
        )

        self.doctor_user = CustomUser.objects.create_user(
            username='analytics_doctor',
            email='analytics.doctor@example.com',
            password='Pass12345!',
            role='doctor',
            first_name='Analytics',
            last_name='Doctor',
        )
        self.doctor = Doctor.objects.create(
            user=self.doctor_user,
            clinic=self.clinic,
            license_number='LIC-AN-001',
            working_days='Mon,Tue,Wed,Thu,Fri',
            slot_minutes=30,
        )

        self.patient_user = CustomUser.objects.create_user(
            username='analytics_patient',
            email='analytics.patient@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Analytics',
            last_name='Patient',
        )
        self.patient = Patient.objects.create(
            user=self.patient_user,
            phone_number='+998902222222',
        )
        self.patient.clinics.add(self.clinic)

        self.appointment = Appointment.objects.create(
            patient=self.patient,
            doctor=self.doctor,
            clinic=self.clinic,
            status=Appointment.Status.SCHEDULED,
            scheduled_date=timezone.now() + timedelta(days=1),
            duration_minutes=30,
        )


class AnalyticsServiceTestCase(AnalyticsBaseTestCase):
    def test_get_clinic_overview(self):
        data = AnalyticsService.get_clinic_overview(self.clinic.id, days=30)
        self.assertIsNotNone(data)
        self.assertIn('clinic_id', data)
        self.assertIn('total_doctors', data)
        self.assertIn('total_patients', data)
        self.assertEqual(str(data['clinic_id']), str(self.clinic.id))

    def test_get_clinic_metrics(self):
        data = AnalyticsService.get_clinic_metrics(self.clinic.id, date_range='month')
        self.assertIsNotNone(data)
        self.assertIn('total_appointments', data)
        self.assertIn('doctor_utilization', data)

    def test_get_doctor_performance(self):
        data = AnalyticsService.get_doctor_performance(self.doctor.id, days=30)
        self.assertIsNotNone(data)
        self.assertIn('doctor_id', data)
        self.assertIn('total_appointments', data)

    def test_get_patient_statistics(self):
        data = AnalyticsService.get_patient_statistics(self.clinic.id, days=30)
        self.assertIsNotNone(data)
        self.assertIn('total_patients', data)
        self.assertIn('patient_gender_distribution', data)

    def test_get_revenue_analytics(self):
        data = AnalyticsService.get_revenue_analytics(self.clinic.id, date_range='month')
        self.assertIsNotNone(data)
        self.assertIn('total_revenue', data)
        self.assertIn('revenue_by_day', data)

    def test_get_subscription_analytics(self):
        data = AnalyticsService.get_subscription_analytics(self.clinic.id)
        self.assertIsNotNone(data)
        self.assertIn('total_subscriptions', data)

    def test_get_appointment_trends(self):
        data = AnalyticsService.get_appointment_trends(self.clinic.id, days=30)
        self.assertIsNotNone(data)
        self.assertIn('trend_data', data)

    def test_get_revenue_trends(self):
        data = AnalyticsService.get_revenue_trends(self.clinic.id, months=12)
        self.assertIsNotNone(data)
        self.assertIn('revenue_trend', data)

    def test_get_system_health(self):
        data = AnalyticsService.get_system_health(self.clinic.id)
        self.assertIsNotNone(data)
        self.assertIn('active_doctors', data)
        self.assertIn('api_response_time', data)


class AnalyticsAPITestCase(AnalyticsBaseTestCase):
    def setUp(self):
        super().setUp()
        self.auth_client: APIClient = APIClient()
        self.auth_client.force_authenticate(user=self.owner_user)

    def _api_get(self, url):
        return cast(Any, self.auth_client).get(url)

    def test_clinic_overview_endpoint(self):
        url = reverse('analytics-clinic-overview')
        response = self._api_get(f'{url}?clinic_id={self.clinic.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('success'), True)

    def test_clinic_metrics_endpoint(self):
        url = reverse('analytics-clinic-metrics')
        response = self._api_get(f'{url}?clinic_id={self.clinic.id}&date_range=month')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('success'), True)

    def test_revenue_analytics_endpoint(self):
        url = reverse('analytics-revenue-analytics')
        response = self._api_get(f'{url}?clinic_id={self.clinic.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('success'), True)

    def test_patient_statistics_endpoint(self):
        url = reverse('analytics-patient-statistics')
        response = self._api_get(f'{url}?clinic_id={self.clinic.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('success'), True)

    def test_subscriptions_endpoint(self):
        url = reverse('analytics-subscriptions')
        response = self._api_get(f'{url}?clinic_id={self.clinic.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('success'), True)

    def test_appointment_trends_endpoint(self):
        url = reverse('analytics-appointment-trends')
        response = self._api_get(f'{url}?clinic_id={self.clinic.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('success'), True)

    def test_revenue_trends_endpoint(self):
        url = reverse('analytics-revenue-trends')
        response = self._api_get(f'{url}?clinic_id={self.clinic.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('success'), True)

    def test_system_health_endpoint(self):
        url = reverse('analytics-system-health')
        response = self._api_get(f'{url}?clinic_id={self.clinic.id}')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get('success'), True)

    def test_dashboard_endpoint(self):
        url = reverse('analytics-dashboard')
        response = self._api_get(f'{url}?clinic_id={self.clinic.id}')
        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data.get('success'), True)
        self.assertIn('dashboard', data)

    def test_missing_clinic_id_returns_400(self):
        url = reverse('analytics-clinic-overview')
        response = self._api_get(url)
        self.assertEqual(response.status_code, 400)

    def test_invalid_clinic_id_returns_500(self):
        url = reverse('analytics-clinic-overview')
        response = self._api_get(f'{url}?clinic_id=99999999-9999-9999-9999-999999999999')
        self.assertEqual(response.status_code, 500)

    def test_date_range_variations(self):
        url = reverse('analytics-clinic-metrics')
        for date_range in ['week', 'month', 'quarter', 'year']:
            response = self._api_get(f'{url}?clinic_id={self.clinic.id}&date_range={date_range}')
            self.assertEqual(response.status_code, 200)


class AnalyticsPerformanceTestCase(AnalyticsBaseTestCase):
    def setUp(self):
        super().setUp()
        self.auth_client: APIClient = APIClient()
        self.auth_client.force_authenticate(user=self.owner_user)

    def _api_get(self, url):
        return cast(Any, self.auth_client).get(url)

    def test_large_dataset_performance(self):
        url = reverse('analytics-clinic-overview')
        start_time = time.time()
        response = self._api_get(f'{url}?clinic_id={self.clinic.id}')
        elapsed_ms = (time.time() - start_time) * 1000

        self.assertLess(elapsed_ms, 5000)
        self.assertEqual(response.status_code, 200)

    def test_caching_effectiveness(self):
        url = reverse('analytics-clinic-overview')

        start = time.time()
        response1 = self._api_get(f'{url}?clinic_id={self.clinic.id}')
        first_ms = (time.time() - start) * 1000

        start = time.time()
        response2 = self._api_get(f'{url}?clinic_id={self.clinic.id}')
        second_ms = (time.time() - start) * 1000

        self.assertEqual(response1.status_code, 200)
        self.assertEqual(response2.status_code, 200)
        self.assertLessEqual(second_ms, first_ms * 2.5)
