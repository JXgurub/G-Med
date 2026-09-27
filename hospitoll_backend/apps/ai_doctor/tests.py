from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch
from apps.users.models import CustomUser
from .models import AnalysisResult


class AiDoctorApiTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.user = CustomUser.objects.create_user(
            username='ai_test_user@example.com',
            email='ai_test_user@example.com',
            password='TestPassword123!',
            first_name='Test',
            last_name='User',
            role='patient'
        )

    @override_settings(GEMINI_API_KEY='test-key')
    @patch('apps.ai_doctor.views.analyze_image_task.delay')
    def test_upload_analysis_guest(self, mock_task):
        mock_task.return_value.id = 'test-job-id'
        url = reverse('ai-doctor-upload')
        image_content = b'GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x01\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;'
        uploaded_file = SimpleUploadedFile("tahlil_test.png", image_content, content_type="image/png")

        response = self.client.post(
            url,
            {'file': uploaded_file, 'session_key': 'test_session_123'},
            format='multipart'
        )

        self.assertIn(response.status_code, [status.HTTP_200_OK, status.HTTP_202_ACCEPTED])
        data = response.json()
        self.assertIn('analysis', data)
        self.assertEqual(data['analysis']['file_type'], 'image')

    @override_settings(GEMINI_API_KEY='')
    def test_upload_is_rejected_without_ai_key_and_not_saved(self):
        uploaded_file = SimpleUploadedFile('lab.png', b'image', content_type='image/png')
        response = self.client.post(
            reverse('ai-doctor-upload'),
            {'file': uploaded_file, 'session_key': 'test_session_no_key'},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_503_SERVICE_UNAVAILABLE)
        self.assertEqual(AnalysisResult.objects.count(), 0)

    @override_settings(GEMINI_API_KEY='test-key')
    def test_guest_upload_requires_session_key(self):
        uploaded_file = SimpleUploadedFile('lab.png', b'image', content_type='image/png')
        response = self.client.post(
            reverse('ai-doctor-upload'),
            {'file': uploaded_file},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(AnalysisResult.objects.count(), 0)

    @override_settings(GEMINI_API_KEY='test-key')
    def test_guest_upload_rejects_session_key_longer_than_database_column(self):
        uploaded_file = SimpleUploadedFile('lab.png', b'image', content_type='image/png')
        response = self.client.post(
            reverse('ai-doctor-upload'),
            {'file': uploaded_file, 'session_key': 's' * 65},
            format='multipart'
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(AnalysisResult.objects.count(), 0)

    def test_list_analyses_session_key(self):
        AnalysisResult.objects.create(
            session_key='test_session_456',
            file_type='pdf',
            status='completed',
            result_text='Hemoglobin: 135 g/L (Normal)'
        )

        url = reverse('ai-doctor-list')
        response = self.client.get(url, {'session_key': 'test_session_456'})

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        data = response.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]['file_type'], 'pdf')

    def test_guest_cannot_access_analysis_without_session_key(self):
        analysis = AnalysisResult.objects.create(
            session_key='private_session',
            file='',
            file_type='pdf',
            status='completed',
        )
        url = reverse('ai-doctor-detail', args=[analysis.id])

        self.assertEqual(self.client.get(url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.delete(url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertTrue(AnalysisResult.objects.filter(id=analysis.id).exists())
