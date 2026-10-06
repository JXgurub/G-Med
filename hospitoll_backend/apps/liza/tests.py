import base64
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import Mock, patch

from django.core.cache import cache
from django.test import SimpleTestCase, TestCase
from django.utils import timezone
from rest_framework.test import APIRequestFactory, force_authenticate

from apps.clinics.models import Clinic, ClinicDepartment
from apps.doctors.models import Doctor, DoctorSpecialization, Specialization
from apps.medical.models import Appointment
from apps.patients.models import Patient
from apps.users.models import CustomUser

from .services import get_command_action, get_command_action_data, handle_command
from .views import CommandView, SpeechView, VoiceView, WakeView


class LizaCommandTests(SimpleTestCase):
    def test_command_endpoint_requires_authentication(self):
        request = APIRequestFactory().post(
            '/api/v1/liza/command/',
            {'message': 'salom'},
            format='json',
        )

        response = CommandView.as_view()(request)

        self.assertEqual(response.status_code, 401)

    @patch('apps.liza.views.handle_command', return_value='Bugungi qabullaringiz yo‘q.')
    def test_authenticated_command_returns_reply(self, handle_command_mock):
        user = SimpleNamespace(is_authenticated=True, pk='test-user', role='doctor')
        request = APIRequestFactory().post(
            '/api/v1/liza/command/',
            {'message': 'Bugungi qabullarim'},
            format='json',
        )
        force_authenticate(request, user=user)

        response = CommandView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['reply'], 'Bugungi qabullaringiz yo‘q.')
        handle_command_mock.assert_called_once_with(user=user, message='Bugungi qabullarim')

    @patch('apps.liza.views.handle_command', return_value='Internet qidiruvi natijalari.')
    def test_command_endpoint_passes_enabled_internet_search_mode(self, handle_command_mock):
        user = SimpleNamespace(is_authenticated=True, pk='test-user', role='patient')
        request = APIRequestFactory().post(
            '/api/v1/liza/command/',
            {'message': 'Python 3.12 yangiliklari', 'internet_search': True},
            format='json',
        )
        force_authenticate(request, user=user)

        response = CommandView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        handle_command_mock.assert_called_once_with(
            user=user,
            message='Python 3.12 yangiliklari',
            internet_search_enabled=True,
        )

    @patch('apps.liza.views.handle_command')
    def test_command_endpoint_rejects_non_boolean_internet_search_mode(self, handle_command_mock):
        user = SimpleNamespace(is_authenticated=True, pk='test-user', role='patient')
        request = APIRequestFactory().post(
            '/api/v1/liza/command/',
            {'message': 'Python yangiliklari', 'internet_search': 'yes'},
            format='json',
        )
        force_authenticate(request, user=user)

        response = CommandView.as_view()(request)

        self.assertEqual(response.status_code, 400)
        handle_command_mock.assert_not_called()

    def test_profile_navigation_is_patient_only_and_not_a_profile_edit(self):
        patient = SimpleNamespace(role='patient', pk='patient-user')
        doctor = SimpleNamespace(role='doctor')

        self.assertEqual(get_command_action(user=patient, message="Profilimga o't"), 'open_profile')
        self.assertEqual(get_command_action(user=patient, message="Profelimga o't"), 'open_profile')
        self.assertIsNone(get_command_action(user=doctor, message="Profilimga o't"))
        self.assertIsNone(get_command_action(user=patient, message='Vaznimni 72 ga o‘zgartir'))

    def test_patient_can_stop_liza_but_other_roles_cannot(self):
        patient = SimpleNamespace(role='patient', pk='patient-user')
        doctor = SimpleNamespace(role='doctor', pk='doctor-user')

        self.assertEqual(get_command_action(user=patient, message="Liza to'xta"), 'stop_listening')
        self.assertEqual(get_command_action(user=patient, message='toxta'), 'stop_listening')
        self.assertIsNone(get_command_action(user=doctor, message="Liza to'xta"))

    def test_dentist_request_asks_for_a_followup_confirmation_turn(self):
        patient = SimpleNamespace(role='patient', pk='patient-user')

        self.assertEqual(
            get_command_action(user=patient, message="Tishim og'riyapti"),
            'await_booking_confirmation',
        )

    @patch('apps.liza.views.handle_command', return_value='Profilim bo‘limini ochyapman.')
    @patch('apps.liza.views.import_string')
    def test_voice_profile_navigation_returns_open_profile_action(self, import_string_mock, _handle_command_mock):
        from django.core.files.uploadedfile import SimpleUploadedFile

        import_string_mock.return_value = Mock(return_value="Profelimga o't")
        user = SimpleNamespace(is_authenticated=True, pk='patient-user', role='patient')
        request = APIRequestFactory().post(
            '/api/v1/liza/voice/',
            {'audio': SimpleUploadedFile('command.wav', b'audio', content_type='audio/wav')},
            format='multipart',
        )
        force_authenticate(request, user=user)

        response = VoiceView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['transcript'], "Profelimga o't")
        self.assertEqual(response.data['action'], 'open_profile')

    @patch('apps.liza.views.handle_command', return_value='Internet qidiruvi natijalari.')
    @patch('apps.liza.views.import_string')
    def test_voice_endpoint_passes_enabled_internet_search_mode(
        self,
        import_string_mock,
        handle_command_mock,
    ):
        from django.core.files.uploadedfile import SimpleUploadedFile

        import_string_mock.return_value = Mock(return_value='Python yangiliklari')
        user = SimpleNamespace(is_authenticated=True, pk='voice-search-user', role='patient')
        request = APIRequestFactory().post(
            '/api/v1/liza/voice/',
            {
                'audio': SimpleUploadedFile('command.wav', b'audio', content_type='audio/wav'),
                'internet_search': 'true',
            },
            format='multipart',
        )
        force_authenticate(request, user=user)

        response = VoiceView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        handle_command_mock.assert_called_once_with(
            user=user,
            message='Python yangiliklari',
            internet_search_enabled=True,
        )

    @patch('apps.liza.services.Appointment.objects.filter')
    def test_doctor_command_only_queries_own_appointments(self, filter_appointments):
        doctor = SimpleNamespace(id='doctor-1', is_active=True)
        user = SimpleNamespace(role='doctor', doctor=doctor)
        appointment = SimpleNamespace(scheduled_date=timezone.now(), queue_position=4)
        queryset = Mock()
        queryset.count.return_value = 1
        queryset.order_by.return_value = [appointment]
        filter_appointments.return_value.exclude.return_value = queryset

        reply = handle_command(user=user, message='Bugungi qabullarim')

        self.assertIn('navbat 4', reply)
        filter_appointments.assert_called_once_with(
            doctor=doctor,
            scheduled_date__date=timezone.localtime().date(),
        )

    @patch('apps.liza.services.Appointment.objects.filter')
    @patch('apps.liza.services.Patient.objects.filter')
    def test_patient_command_only_queries_own_future_appointments(self, filter_patient, filter_appointments):
        patient = SimpleNamespace(id='patient-1')
        user = SimpleNamespace(role='patient', patient=patient, pk='patient-user-1')
        filter_patient.return_value.first.return_value = patient
        appointment = SimpleNamespace(
            scheduled_date=timezone.now(),
            doctor_name='Doktor',
            doctor_id=None,
            doctor=None,
            clinic=None,
            clinic_name='',
        )
        queryset = Mock()
        queryset.count.return_value = 1
        queryset.order_by.return_value = [appointment]
        filter_appointments.return_value.filter.return_value.select_related.return_value.order_by.return_value = [appointment]

        reply = handle_command(user=user, message='Mening qabulim qachon?')

        self.assertIn('Yaqin qabullaringiz', reply)
        filter_appointments.assert_called_once()
        filter_patient.assert_called_once_with(user=user)
        self.assertEqual(filter_appointments.call_args.kwargs['patient'], patient)
        self.assertTrue(filter_appointments.call_args.kwargs['status__in'])

    @patch('apps.liza.services.requests.get')
    def test_weather_command_uses_open_meteo(self, get_mock):
        geocoding_response = Mock()
        geocoding_response.json.return_value = {
            'results': [{'name': 'Toshkent', 'country_code': 'UZ', 'latitude': 41.3, 'longitude': 69.2}],
        }
        forecast_response = Mock()
        forecast_response.json.return_value = {
            'current': {'temperature_2m': 20, 'wind_speed_10m': 4, 'weather_code': 0},
        }
        get_mock.side_effect = [geocoding_response, forecast_response]

        user = SimpleNamespace(role='patient', pk='weather-user')
        reply = handle_command(user=user, message='Toshkentda ob havo qanday?')

        self.assertIn('Toshkentda hozir ochiq', reply)
        self.assertEqual(get_mock.call_count, 2)

    @patch('apps.liza.services.requests.get')
    def test_weather_question_extracts_city_from_uzbek_inflections(self, get_mock):
        geocoding_response = Mock()
        geocoding_response.json.return_value = {
            'results': [{'name': 'Beruniy', 'country_code': 'UZ', 'latitude': 41.7, 'longitude': 60.8}],
        }
        forecast_response = Mock()
        forecast_response.json.return_value = {
            'current': {'temperature_2m': 18, 'wind_speed_10m': 2, 'weather_code': 1},
        }
        get_mock.side_effect = [geocoding_response, forecast_response]

        user = SimpleNamespace(role='patient', pk='weather-inflection-user')
        reply = handle_command(
            user=user,
            message="Beruniy ob-havosi haqida ma'lumot ber",
        )

        self.assertIn('Beruniyda hozir asosan ochiq', reply)
        self.assertEqual(get_mock.call_args_list[0].kwargs['params']['name'], 'beruniy')

    @patch('apps.liza.services.cache.set')
    @patch('apps.liza.services.cache.get', return_value=None)
    @patch('apps.liza.services.requests.get')
    def test_internet_search_mode_returns_web_results_with_sources_and_redacts_pii(
        self,
        get_mock,
        _cache_get_mock,
        _cache_set_mock,
    ):
        response = Mock()
        response.text = (
            '<a class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Fpython">'
            '<span>Python release notes</span></a>'
            '<a class="result__snippet">Official Python release information.</a>'
            '<a class="result__a" href="https://docs.example.org/python">Python documentation</a>'
            '<a class="result__snippet">Documentation for the Python language.</a>'
        )
        get_mock.return_value = response
        user = SimpleNamespace(role='patient', pk='internet-search-user')

        reply = handle_command(
            user=user,
            message='Python 3.12 haqida user@example.com ga yubor +998 90 123 45 67',
            internet_search_enabled=True,
        )

        self.assertIn('Python release notes', reply)
        self.assertIn('Official Python release information.', reply)
        self.assertIn('https://example.com/python', reply)
        self.assertIn('https://docs.example.org/python', reply)
        query = get_mock.call_args.kwargs['params']['q']
        self.assertIn('python', query.casefold())
        self.assertNotIn('user@example.com', query)
        self.assertNotIn('998', query)
        self.assertEqual(get_mock.call_args.args[0], 'https://html.duckduckgo.com/html/')

    @patch('apps.liza.services.requests.get')
    def test_internet_search_mode_keeps_profile_navigation_local(self, get_mock):
        user = SimpleNamespace(role='patient', pk='internet-booking-user')

        reply = handle_command(
            user=user,
            message='Profilimni och',
            internet_search_enabled=True,
        )

        self.assertIn('Profilim bo‘limini ochyapman', reply)
        get_mock.assert_not_called()

    @patch('apps.liza.services._youtube_search_results', return_value=[
        {'id': 'abcdefghijk', 'title': 'Sevara Nazarkhan'},
        {'id': 'bcdefghijkl', 'title': 'Sevara Nazarkhan 2'},
    ])
    def test_youtube_command_returns_playable_video_action(self, youtube_search_mock):
        user = SimpleNamespace(role='patient', pk='youtube-user')
        message = "Yutubedan Sevara Nazarkhan qo'shig'ini qo'yib ber"
        reply = handle_command(user=user, message=message)
        action = get_command_action_data(user=user, message=message)

        self.assertIn('Sevara Nazarkhan', reply)
        self.assertEqual(action['action'], 'play_youtube')
        self.assertEqual(action['video_id'], 'abcdefghijk')
        self.assertEqual(action['queue_count'], 2)
        youtube_search_mock.assert_called_once_with('sevara nazarkhan')

    @patch('yt_dlp.YoutubeDL')
    @patch('apps.liza.services.cache.get', return_value=None)
    def test_youtube_search_keeps_flat_results_without_fetching_video_pages(self, _cache_get, youtube_dl_mock):
        from apps.liza.services import _youtube_search_results

        youtube = youtube_dl_mock.return_value.__enter__.return_value
        youtube.extract_info.return_value = {
            'entries': [
                {'id': 'abcdefghijk', 'title': 'Xamdam Sobirov'},
                {'id': None, 'title': 'Unavailable result'},
            ],
        }

        results = _youtube_search_results('xamdam sobirov')

        self.assertEqual(results, [{'id': 'abcdefghijk', 'title': 'Xamdam Sobirov'}])
        options = youtube_dl_mock.call_args.args[0]
        self.assertEqual(options['extract_flat'], 'in_playlist')
        youtube.extract_info.assert_called_once_with('ytsearch5:xamdam sobirov', download=False)

    @patch('apps.liza.services.requests.get')
    @patch('yt_dlp.YoutubeDL')
    @patch('apps.liza.services.cache.get', return_value=None)
    def test_youtube_page_search_is_used_when_extractor_is_blocked(
        self,
        _cache_get,
        youtube_dl_mock,
        get_mock,
    ):
        from apps.liza.services import _youtube_search_results

        youtube = youtube_dl_mock.return_value.__enter__.return_value
        youtube.extract_info.side_effect = RuntimeError('YouTube blocked the extractor request')
        response = Mock()
        response.text = (
            'var ytInitialData = {"contents":{"videoRenderer":{"videoId":"abcdefghijk",'
            '"title":{"runs":[{"text":"Xamdam Sobirov"}]}}}};'
        )
        get_mock.return_value = response

        results = _youtube_search_results('xamdam sobirov')

        self.assertEqual(results, [{'id': 'abcdefghijk', 'title': 'Xamdam Sobirov'}])
        get_mock.assert_called_once()
        self.assertEqual(get_mock.call_args.args[0], 'https://www.youtube.com/results')

    @patch('apps.liza.services._youtube_search_results', return_value=[
        {'id': 'abcdefghijk', 'title': 'Birinchi qo‘shiq'},
        {'id': 'bcdefghijkl', 'title': 'Ikkinchi qo‘shiq'},
        {'id': 'cdefghijklm', 'title': 'Uchinchi qo‘shiq'},
    ])
    def test_youtube_queue_moves_next_previous_and_pauses(self, youtube_search_mock):
        user = SimpleNamespace(role='patient', pk='youtube-queue-user')
        handle_command(user=user, message='YouTube da Yulduz qo‘shiqlar')

        next_reply = handle_command(user=user, message='keyingi qo‘shiq')
        next_action = get_command_action_data(user=user, message='keyingi qo‘shiq')
        self.assertIn('Ikkinchi qo‘shiq', next_reply)
        self.assertEqual(next_action['control'], 'next')
        self.assertEqual(next_action['video_id'], 'bcdefghijkl')

        previous_reply = handle_command(user=user, message='oldingi qo‘shiq')
        previous_action = get_command_action_data(user=user, message='oldingi qo‘shiq')
        self.assertIn('Birinchi qo‘shiq', previous_reply)
        self.assertEqual(previous_action['control'], 'previous')
        self.assertEqual(previous_action['video_id'], 'abcdefghijk')

        pause_reply = handle_command(user=user, message='shitob')
        pause_action = get_command_action_data(user=user, message='shitob')
        self.assertIn('to‘xtatdim', pause_reply)
        self.assertEqual(pause_action['control'], 'pause')

        play_reply = handle_command(user=user, message='davom ettir')
        play_action = get_command_action_data(user=user, message='davom ettir')
        self.assertIn('davom ettiryapman', play_reply)
        self.assertEqual(play_action['control'], 'play')

        rewind_reply = handle_command(user=user, message='10 soniya orqaga')
        rewind_action = get_command_action_data(user=user, message='10 soniya orqaga')
        self.assertIn('10 soniya orqaga', rewind_reply)
        self.assertEqual(rewind_action['control'], 'rewind')
        youtube_search_mock.assert_called_once()

    @patch('apps.liza.services._youtube_search_results', return_value=[
        {'id': 'abcdefghijk', 'title': 'Hamd am Sobirov'},
    ])
    def test_liza_wake_word_ducks_music_before_followup_command(self, _youtube_search_mock):
        user = SimpleNamespace(role='patient', pk='youtube-wake-user')
        handle_command(user=user, message='YouTube da Hamdam Sobirov qo‘shiqlari')

        wake_reply = handle_command(user=user, message='Liza')
        wake_action = get_command_action_data(user=user, message='Liza')
        self.assertIn('Buyruqni ayting', wake_reply)
        self.assertEqual(wake_action['action'], 'youtube_duck')

        next_reply = handle_command(user=user, message='keyingisiga o‘t')
        next_action = get_command_action_data(user=user, message='keyingisiga o‘t')
        self.assertIn('Keyingi qo‘shiq', next_reply)
        self.assertEqual(next_action['control'], 'next')

    @patch('apps.liza.services._youtube_search_results', return_value=[
        {'id': 'abcdefghijk', 'title': 'Birinchi qo‘shiq'},
        {'id': 'bcdefghijkl', 'title': 'Ikkinchi qo‘shiq'},
    ])
    def test_liza_prefixed_song_controls_do_not_stop_listening(self, _youtube_search_mock):
        user = SimpleNamespace(role='patient', pk='youtube-prefixed-user')
        handle_command(user=user, message='YouTube da Yulduz qo‘shiqlar')

        next_reply = handle_command(user=user, message='Liza keyingisiga o‘t')
        next_action = get_command_action_data(user=user, message='Liza keyingisiga o‘t')
        self.assertIn('Ikkinchi qo‘shiq', next_reply)
        self.assertEqual(next_action['control'], 'next')

        pause_reply = handle_command(user=user, message='Liza qo‘shiqni to‘xtat')
        pause_action = get_command_action_data(user=user, message='Liza qo‘shiqni to‘xtat')
        self.assertIn('to‘xtatdim', pause_reply)
        self.assertEqual(pause_action['control'], 'pause')

        stop_reply = handle_command(user=user, message='Liza to‘xta')
        self.assertIn('suhbatni to‘xtatdi', stop_reply)

    @patch('apps.liza.services._youtube_search_results', return_value=[
        {'id': 'abcdefghijk', 'title': 'Yulduz Usmonova'},
    ])
    def test_youtube_command_without_title_then_searches_followup_title(self, youtube_search_mock):
        user = SimpleNamespace(role='patient', pk='youtube-user')

        for message in (
            "Menga yutubda muzika qo'yib ber",
            "yutobedan qo'shiq qo'y",
            "YouTube dan qo'shiq qo'y",
        ):
            with self.subTest(message=message):
                reply = handle_command(user=user, message=message)
                self.assertIn('qo‘shiq yoki video nomini ayting', reply)

        youtube_search_mock.assert_not_called()
        followup_reply = handle_command(user=user, message='Yulduz Usmonova')
        action = get_command_action_data(user=user, message='Yulduz Usmonova')
        self.assertIn('Yulduz Usmonova', followup_reply)
        self.assertEqual(action['action'], 'play_youtube')
        self.assertEqual(action['video_id'], 'abcdefghijk')
        youtube_search_mock.assert_called_once_with('yulduz usmonova')

    @patch('apps.liza.services.requests.get')
    def test_internet_search_returns_external_summary(self, get_mock):
        html_response = Mock()
        html_response.text = ''
        response = Mock()
        response.json.return_value = {
            'AbstractText': 'Toshkent O‘zbekiston poytaxti.',
            'AbstractURL': 'https://example.com/tashkent',
        }
        get_mock.side_effect = [html_response, response]

        user = SimpleNamespace(role='patient', pk='search-user')
        reply = handle_command(user=user, message='Internetda Toshkent haqida qidir')

        self.assertIn('Toshkent O‘zbekiston poytaxti', reply)
        self.assertIn('https://example.com/tashkent', reply)


class LizaPatientFunctionsTests(TestCase):
    def setUp(self):
        cache.clear()
        self.owner = CustomUser.objects.create_user(
            username='liza_clinic_owner',
            email='liza.clinic@example.com',
            password='Pass12345!',
            role='clinic',
        )
        self.clinic = Clinic.objects.create(
            owner=self.owner,
            name='Liza Test Clinic',
            slug='liza-test-clinic',
            address='Toshkent, Test ko‘chasi 1',
            phone_number='+998901112233',
            email='liza-clinic@example.com',
            registration_number='LIZA-TEST-001',
            status='active',
            working_hours='08:00 - 20:00',
        )
        self.doctor_user = CustomUser.objects.create_user(
            username='liza_doctor',
            email='liza.doctor@example.com',
            password='Pass12345!',
            role='doctor',
            first_name='Ali',
            last_name='Valiyev',
        )
        self.doctor = Doctor.objects.create(
            user=self.doctor_user,
            clinic=self.clinic,
            license_number='LIZA-DOCTOR-001',
            working_days='Mon,Wed,Fri',
            available_from='09:00',
            available_until='17:00',
            lunch_break_start='13:00',
            lunch_break_end='14:00',
        )
        self.patient_user = CustomUser.objects.create_user(
            username='liza_patient',
            email='liza.patient@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Dilnoza',
            last_name='Karimova',
        )
        self.patient = Patient.objects.create(user=self.patient_user)
        self.other_user = CustomUser.objects.create_user(
            username='liza_other_patient',
            email='liza.other@example.com',
            password='Pass12345!',
            role='patient',
            first_name='Other',
            last_name='Patient',
        )
        self.other_patient = Patient.objects.create(user=self.other_user)

    def tearDown(self):
        cache.clear()

    def make_appointment(self, patient, minutes, *, queue_position, status=Appointment.Status.SCHEDULED, doctor=None):
        return Appointment.objects.create(
            patient=patient,
            doctor=doctor or self.doctor,
            clinic=self.clinic,
            status=status,
            queue_position=queue_position,
            scheduled_date=timezone.now() + timedelta(minutes=minutes),
        )

    def test_patient_queue_uses_dashboard_order_and_only_its_doctor_day(self):
        self.make_appointment(self.other_patient, 5, queue_position=1)
        self.make_appointment(self.other_patient, 10, queue_position=1, status=Appointment.Status.CANCELLED)
        self.make_appointment(self.other_patient, 15, queue_position=99)
        target = self.make_appointment(self.patient, 45, queue_position=9)
        self.make_appointment(self.other_patient, 55, queue_position=2)

        reply = handle_command(
            user=self.patient_user,
            message='Navbat raqamim nechanchi, oldinda nechta odam bor?',
        )

        self.assertIn('Navbat raqamingiz 9', reply)
        self.assertIn('oldinda 2 ta odam bor', reply)
        self.assertIn(self.clinic.name, reply)
        self.assertIn(self.doctor_user.get_full_name(), reply)
        self.assertNotIn(self.other_user.get_full_name(), reply)
        self.assertNotIn(str(target.patient_id), reply)

    def test_patient_can_hear_clinic_and_doctor_working_hours(self):
        self.make_appointment(self.patient, 45, queue_position=1)

        reply = handle_command(user=self.patient_user, message='Doktorim va klinikam ish vaqti qanday?')

        self.assertIn('dushanba, chorshanba, juma', reply)
        self.assertIn('09:00–17:00', reply)
        self.assertIn('13:00–14:00', reply)
        self.assertIn('08:00 - 20:00', reply)

    def test_profile_change_requires_confirmation_from_same_patient(self):
        request_reply = handle_command(user=self.patient_user, message='Vaznimni 72 ga o‘zgartir')
        self.patient.refresh_from_db()
        self.assertIn('tasdiqlayman', request_reply)
        self.assertIsNone(self.patient.weight_kg)

        other_reply = handle_command(user=self.other_user, message='tasdiqlayman')
        self.patient.refresh_from_db()
        self.assertIn('kutilayotgan profil o‘zgarishi yo‘q', other_reply)
        self.assertIsNone(self.patient.weight_kg)

        confirm_reply = handle_command(user=self.patient_user, message='tasdiqlayman')
        self.patient.refresh_from_db()
        self.assertIn('muvaffaqiyatli yangilandi', confirm_reply)
        self.assertEqual(self.patient.weight_kg, Decimal('72.00'))

    def test_profile_weight_accepts_spoken_uzbek_number_words(self):
        request_reply = handle_command(
            user=self.patient_user,
            message="Vaznimni yetmish ikki ga o'zgartir",
        )

        self.assertIn('yangilash so‘rovi tayyor', request_reply)
        self.assertIn('tasdiqlayman', request_reply)
        confirm_reply = handle_command(user=self.patient_user, message='tasdiqlayman')
        self.patient.refresh_from_db()

        self.assertIn('muvaffaqiyatli yangilandi', confirm_reply)
        self.assertEqual(self.patient.weight_kg, Decimal('72.00'))

    def test_profile_weight_accepts_number_attached_to_ga(self):
        request_reply = handle_command(
            user=self.patient_user,
            message="Vaznimni 72ga o'zgartir",
        )

        self.assertIn('yangilash so‘rovi tayyor', request_reply)
        confirm_reply = handle_command(user=self.patient_user, message='tasdiqlayman')
        self.patient.refresh_from_db()

        self.assertIn('muvaffaqiyatli yangilandi', confirm_reply)
        self.assertEqual(self.patient.weight_kg, Decimal('72.00'))

    def test_tooth_pain_finds_dentist_and_opens_booking_only_after_yes(self):
        specialization = Specialization.objects.get(name='Stomatologiya')
        price = DoctorSpecialization.objects.create(
            doctor=self.doctor,
            specialization=specialization,
            consultation_fee=Decimal('150000'),
        )

        reply = handle_command(user=self.patient_user, message="Tishim og'riyapti")

        self.assertIn(self.doctor_user.get_full_name(), reply)
        self.assertIn(self.clinic.name, reply)
        self.assertIn('Ha yoki yo‘q', reply)
        self.assertEqual(
            get_command_action_data(user=self.patient_user, message="Tishim og'riyapti")['action'],
            'await_booking_confirmation',
        )

        consent_reply = handle_command(user=self.patient_user, message='ha')
        action = get_command_action_data(user=self.patient_user, message='ha')

        self.assertIn('yozilish oynasini', consent_reply)
        self.assertEqual(action['action'], 'open_booking')
        self.assertEqual(action['booking']['doctor_id'], str(self.doctor.id))
        self.assertEqual(action['booking']['clinic_id'], str(self.clinic.id))
        self.assertEqual(action['booking']['specialty_price_ids'], [str(price.id)])
        self.assertNotIn('booking', get_command_action_data(user=self.other_user, message='ha'))

    def test_speakable_text_reads_zero_and_phone_digits(self):
        from .services import speakable_text

        self.assertEqual(speakable_text('+998 90 111 22 33'), 'to\'qqiz to\'qqiz sakkiz to\'qqiz nol bir bir bir ikki ikki uch uch')
        self.assertEqual(speakable_text('09:00–18:00'), "soat to'qqiz dan soat o'n sakkiz gacha")
        self.assertEqual(speakable_text('150000 so\'m'), "bir yuz ellik ming so'm")
        self.assertNotIn('0', speakable_text('Telefon 0 va 100'))

    def test_specialty_request_lists_every_matching_doctor_and_selects_by_ordinal(self):
        specialization = Specialization.objects.get(name='Stomatologiya')
        DoctorSpecialization.objects.create(
            doctor=self.doctor, specialization=specialization, consultation_fee=Decimal('150000'),
        )
        second_user = CustomUser.objects.create_user(
            username='liza_second_dentist', password='pass12345', role='doctor',
            first_name='Qodir', last_name='Tishchi',
        )
        second_doctor = Doctor.objects.create(
            user=second_user, clinic=self.clinic, consultation_fee=Decimal('90000'),
            available_from=self.doctor.available_from, available_until=self.doctor.available_until,
        )
        DoctorSpecialization.objects.create(
            doctor=second_doctor, specialization=specialization, consultation_fee=Decimal('90000'),
        )

        reply = handle_command(user=self.patient_user, message="Tishim og'riyapti, stomatologiya topib ber")

        self.assertIn(self.doctor_user.get_full_name(), reply)
        self.assertIn('Qodir Tishchi', reply)
        self.assertIn('Qaysi doktorga', reply)
        self.assertEqual(
            get_command_action_data(user=self.patient_user, message='ha')['action'],
            'await_doctor_selection',
        )
        self.assertEqual(
            get_command_action_data(
                user=self.patient_user,
                message="Tishim og'riyapti, stomatologiya topib ber",
            )['action'],
            'await_doctor_selection',
        )
        for selection, expected_doctor_id in (
            ('ikkinchisi', str(second_doctor.id)),
            ('2', str(second_doctor.id)),
            ('Qodir', str(second_doctor.id)),
            ('bir', str(self.doctor.id)),
        ):
            with self.subTest(selection=selection):
                handle_command(user=self.patient_user, message="Tishim og'riyapti, stomatologiya topib ber")
                selected_reply = handle_command(user=self.patient_user, message=selection)
                action = get_command_action_data(user=self.patient_user, message=selection)

                self.assertIn('yozilish oynasini ochyapman', selected_reply)
                self.assertEqual(action['action'], 'open_booking')
                self.assertEqual(action['booking']['doctor_id'], expected_doctor_id)

    def test_ear_pain_finds_lor_specialist_across_clinic_specialties(self):
        specialization = Specialization.objects.get(name='Otorinolaringologiya (LOR)')
        price = DoctorSpecialization.objects.create(
            doctor=self.doctor,
            specialization=specialization,
            consultation_fee=Decimal('90000'),
        )
        request = "Qulog'im og'riyapti, LOR doktor kerak"

        reply = handle_command(user=self.patient_user, message=request)

        self.assertIn(self.doctor_user.get_full_name(), reply)
        self.assertIn(self.clinic.name, reply)
        self.assertIn('LOR', reply)
        self.assertEqual(get_command_action_data(user=self.patient_user, message=request)['action'], 'await_booking_confirmation')

        consent_reply = handle_command(user=self.patient_user, message='ha')
        action = get_command_action_data(user=self.patient_user, message='ha')

        self.assertIn('yozilish oynasini', consent_reply)
        self.assertEqual(action['action'], 'open_booking')
        self.assertEqual(action['booking']['doctor_id'], str(self.doctor.id))
        self.assertEqual(action['booking']['specialty_price_ids'], [str(price.id)])

    def test_clinic_custom_specialty_can_be_found_by_its_entered_name(self):
        specialization = Specialization.objects.create(
            name='Liza custom direction',
            code='LIZA-CUSTOM-DIRECTION',
        )
        price = DoctorSpecialization.objects.create(
            doctor=self.doctor,
            specialization=specialization,
            custom_name='Nutq terapiyasi',
            doctor_custom=True,
            consultation_fee=Decimal('80000'),
        )
        request = 'Nutq terapiyasi doktori kerak'

        reply = handle_command(user=self.patient_user, message=request)
        action = get_command_action_data(user=self.patient_user, message=request)

        self.assertIn(self.doctor_user.get_full_name(), reply)
        self.assertIn('Nutq terapiyasi', reply)
        self.assertEqual(action['action'], 'await_booking_confirmation')

        handle_command(user=self.patient_user, message='ha')
        booking_action = get_command_action_data(user=self.patient_user, message='ha')
        self.assertEqual(booking_action['action'], 'open_booking')
        self.assertEqual(booking_action['booking']['specialty_price_ids'], [str(price.id)])

    def test_therapy_request_finds_doctor_specialization_without_price_row(self):
        specialization = Specialization.objects.get(name='Terapiya')
        self.doctor.specializations.add(specialization)

        request = 'Menga terapiya doktorini top'
        reply = handle_command(user=self.patient_user, message=request)

        self.assertIn(self.doctor_user.get_full_name(), reply)
        action = get_command_action_data(user=self.patient_user, message=request)
        self.assertEqual(action['action'], 'await_booking_confirmation')
        handle_command(user=self.patient_user, message='ha')
        booking_action = get_command_action_data(user=self.patient_user, message='ha')
        self.assertEqual(booking_action['action'], 'open_booking')
        self.assertEqual(booking_action['booking']['doctor_id'], str(self.doctor.id))
        self.assertEqual(booking_action['booking']['specialty_price_ids'], [])

    def test_clinic_department_direction_finds_its_head_doctor(self):
        department = ClinicDepartment.objects.create(
            clinic=self.clinic,
            name='Terapiya',
            head_doctor=self.doctor,
        )

        reply = handle_command(user=self.patient_user, message='Terapiya klinikasidan doktor kerak')

        self.assertIn(self.doctor_user.get_full_name(), reply)
        action = get_command_action_data(user=self.patient_user, message='Terapiya klinikasidan doktor kerak')
        self.assertEqual(action['action'], 'await_booking_confirmation')
        handle_command(user=self.patient_user, message='ha')
        booking_action = get_command_action_data(user=self.patient_user, message='ha')
        self.assertEqual(booking_action['action'], 'open_booking')
        self.assertEqual(booking_action['booking']['clinic_id'], str(department.clinic_id))
        self.assertEqual(booking_action['booking']['specialty_price_ids'], [])

    def test_dentist_confirmation_accepts_speech_recognition_variants(self):
        cache_key = f'liza:patient-specialty-booking:{self.patient_user.pk}'
        booking = {'doctor_name': 'Ali Valiyev'}
        for message in ('ha, iltimos oching', 'Xa!', 'haa', 'mayli', 'xo‘p'):
            with self.subTest(message=message):
                cache.set(cache_key, booking, 180)
                self.assertEqual(
                    get_command_action_data(user=self.patient_user, message=message)['action'],
                    'open_booking',
                )

        cache.set(cache_key, booking, 180)
        self.assertIn('bekor qilindi', handle_command(user=self.patient_user, message='yo‘q, kerak emas'))
        self.assertIsNone(get_command_action(user=self.patient_user, message='ha'))

    @patch('apps.liza.views.import_string')
    def test_voice_yes_variant_returns_booking_action(self, import_string_mock):
        from django.core.files.uploadedfile import SimpleUploadedFile

        specialization = Specialization.objects.get(name='Stomatologiya')
        price = DoctorSpecialization.objects.create(
            doctor=self.doctor,
            specialization=specialization,
            consultation_fee=Decimal('150000'),
        )
        handle_command(user=self.patient_user, message='Stomatologiya topib ber')
        import_string_mock.return_value = Mock(return_value='Ha, iltimos oching')
        request = APIRequestFactory().post(
            '/api/v1/liza/voice/',
            {'audio': SimpleUploadedFile('confirmation.wav', b'audio', content_type='audio/wav')},
            format='multipart',
        )
        force_authenticate(request, user=self.patient_user)

        response = VoiceView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['action'], 'open_booking')
        self.assertEqual(response.data['booking']['doctor_id'], str(self.doctor.id))
        self.assertEqual(response.data['booking']['specialty_price_ids'], [str(price.id)])

    @patch('apps.liza.views.import_string')
    def test_voice_doctor_list_returns_selection_action(self, import_string_mock):
        from django.core.files.uploadedfile import SimpleUploadedFile

        specialization = Specialization.objects.get(name='Stomatologiya')
        DoctorSpecialization.objects.create(
            doctor=self.doctor,
            specialization=specialization,
            consultation_fee=Decimal('150000'),
        )
        second_user = CustomUser.objects.create_user(
            username='liza_voice_second_dentist',
            password='pass12345',
            role='doctor',
            first_name='Qodir',
            last_name='Tishchi',
        )
        second_doctor = Doctor.objects.create(
            user=second_user,
            clinic=self.clinic,
            consultation_fee=Decimal('90000'),
            available_from=self.doctor.available_from,
            available_until=self.doctor.available_until,
        )
        DoctorSpecialization.objects.create(
            doctor=second_doctor,
            specialization=specialization,
            consultation_fee=Decimal('90000'),
        )
        import_string_mock.return_value = Mock(return_value="Tishim og'riyapti stomatologiya topib ber")
        request = APIRequestFactory().post(
            '/api/v1/liza/voice/',
            {'audio': SimpleUploadedFile('booking.wav', b'audio', content_type='audio/wav')},
            format='multipart',
        )
        force_authenticate(request, user=self.patient_user)

        response = VoiceView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['action'], 'await_doctor_selection')
        self.assertIn('Ismini yoki 1, 2, 3', response.data['reply'])

    def test_analysis_read_request_is_patient_scoped(self):
        self.assertEqual(
            get_command_action(user=self.patient_user, message="AI tahlil bo‘limidagi tahlil javoblarini ham o‘qib ber"),
            'read_analysis',
        )
        self.assertIsNone(get_command_action(user=self.doctor_user, message='Tahlil javobimni o‘qi'))


class LizaWakeWordTests(SimpleTestCase):
    def _post_wake_audio(self, transcript):
        from django.core.files.uploadedfile import SimpleUploadedFile

        request = APIRequestFactory().post(
            '/api/v1/liza/wake/',
            {'audio': SimpleUploadedFile('wake.wav', b'wav-data', content_type='audio/wav')},
            format='multipart',
        )
        user = SimpleNamespace(is_authenticated=True, pk='test-user', role='patient')
        force_authenticate(request, user=user)
        with patch('apps.liza.views.import_string', return_value=Mock(return_value=transcript)):
            return WakeView.as_view()(request)

    def test_wake_endpoint_requires_authentication(self):
        from django.core.files.uploadedfile import SimpleUploadedFile

        request = APIRequestFactory().post(
            '/api/v1/liza/wake/',
            {'audio': SimpleUploadedFile('wake.wav', b'wav-data', content_type='audio/wav')},
            format='multipart',
        )

        response = WakeView.as_view()(request)

        self.assertEqual(response.status_code, 401)

    def test_wake_endpoint_detects_liza_word(self):
        response = self._post_wake_audio('bugun liza')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['wake'])
        self.assertEqual(response.data['transcript'], 'bugun liza')

    def test_wake_endpoint_accepts_close_uzbek_recognition(self):
        response = self._post_wake_audio('liz')

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['wake'])

    def test_wake_endpoint_allows_patient_profile_navigation_without_wake_token(self):
        response = self._post_wake_audio("Profilimga o't")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data['wake'])
        self.assertEqual(response.data['action'], 'open_profile')

    def test_wake_endpoint_ignores_other_words(self):
        response = self._post_wake_audio('bugungi qabulim')

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data['wake'])


class LizaSpeechTests(SimpleTestCase):
    def test_speech_endpoint_requires_authentication(self):
        request = APIRequestFactory().post(
            '/api/v1/liza/speech/',
            {'text': 'Assalomu alaykum'},
            format='json',
        )

        response = SpeechView.as_view()(request)

        self.assertEqual(response.status_code, 401)

    @patch('apps.liza.views.synthesize_madina', return_value=b'mp3-audio')
    def test_authenticated_speech_returns_madina_audio(self, synthesize_mock):
        user = SimpleNamespace(is_authenticated=True, pk='test-user')
        request = APIRequestFactory().post(
            '/api/v1/liza/speech/',
            {'text': 'Bugun sizda ikkita qabul bor.'},
            format='json',
        )
        force_authenticate(request, user=user)

        response = SpeechView.as_view()(request)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data['content_type'], 'audio/mpeg')
        self.assertEqual(base64.b64decode(response.data['audio']), b'mp3-audio')
        self.assertEqual(response['Cache-Control'], 'no-store')
        synthesize_mock.assert_called_once_with('Bugun sizda ikkita qabul bor.')

    def test_speech_endpoint_rejects_empty_text(self):
        user = SimpleNamespace(is_authenticated=True, pk='test-user')
        request = APIRequestFactory().post(
            '/api/v1/liza/speech/',
            {'text': '   '},
            format='json',
        )
        force_authenticate(request, user=user)

        response = SpeechView.as_view()(request)

        self.assertEqual(response.status_code, 400)