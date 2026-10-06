import logging
import re
import base64
from difflib import SequenceMatcher

from django.conf import settings
from django.utils.module_loading import import_string
from rest_framework import permissions, status
from rest_framework.views import APIView
from rest_framework.parsers import JSONParser, MultiPartParser, FormParser
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle

from .services import TranscriptionUnavailable, get_command_action, get_command_action_data, handle_command, synthesize_madina

logger = logging.getLogger(__name__)
MAX_MESSAGE_LENGTH = 2000
MAX_AUDIO_BYTES = 10 * 1024 * 1024
ALLOWED_AUDIO_TYPES = {'audio/webm', 'audio/mp4', 'audio/ogg', 'audio/wav', 'audio/x-wav'}


class CommandView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'liza_command'

    def post(self, request):
        message = request.data.get('message') if isinstance(request.data, dict) else None
        if not isinstance(message, str) or not message.strip():
            return Response({'error': "Xabar bo'sh bo'lmasligi kerak."}, status=status.HTTP_400_BAD_REQUEST)
        message = message.strip()
        if len(message) > MAX_MESSAGE_LENGTH:
            return Response({'error': 'Xabar juda uzun.'}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        internet_search_enabled = request.data.get('internet_search', False)
        if not isinstance(internet_search_enabled, bool):
            return Response({'error': 'Internet-qidiruv holati noto‘g‘ri.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            if internet_search_enabled:
                reply = handle_command(
                    user=request.user,
                    message=message,
                    internet_search_enabled=True,
                )
            else:
                reply = handle_command(user=request.user, message=message)
        except Exception:
            logger.exception('Liza command handler failed')
            return Response({'error': 'Buyruqni bajarishda xatolik yuz berdi.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({'reply': reply, **get_command_action_data(user=request.user, message=message)})


class VoiceView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'liza_voice'

    def post(self, request):
        audio_file = request.FILES.get('audio')
        if audio_file is None:
            return Response({'error': 'Ovoz fayli yuborilmadi.'}, status=status.HTTP_400_BAD_REQUEST)
        if audio_file.size > MAX_AUDIO_BYTES:
            return Response({'error': "Ovoz yozuvi 10 MB dan oshmasligi kerak."}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        if audio_file.content_type.split(';')[0] not in ALLOWED_AUDIO_TYPES:
            return Response({'error': "Ovoz formati qo'llab-quvvatlanmaydi."}, status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

        transcriber_path = getattr(settings, 'LIZA_TRANSCRIBE_HANDLER', '')
        if not transcriber_path:
            return Response({'error': 'Mahalliy transkripsiya xizmati sozlanmagan.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            transcriber = import_string(transcriber_path)
            transcript = transcriber(user=request.user, audio_file=audio_file)
        except TranscriptionUnavailable as error:
            return Response({'error': str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except ValueError as error:
            return Response({'error': str(error)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception('Liza transcription handler failed')
            return Response({'error': 'Ovozni matnga aylantirib bo‘lmadi.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        if not isinstance(transcript, str) or not transcript.strip():
            return Response({'error': 'Ovozdan matn aniqlanmadi.'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)
        transcript = transcript.strip()
        if len(transcript) > MAX_MESSAGE_LENGTH:
            return Response({'error': 'Aniqlangan matn juda uzun.'}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        logger.info('Liza voice transcript accepted: user=%s characters=%s', request.user.pk, len(transcript))
        internet_search_value = request.data.get('internet_search', 'false')
        if internet_search_value not in {'true', 'false'}:
            return Response({'error': 'Internet-qidiruv holati noto‘g‘ri.'}, status=status.HTTP_400_BAD_REQUEST)
        internet_search_enabled = internet_search_value == 'true'

        try:
            if internet_search_enabled:
                reply = handle_command(
                    user=request.user,
                    message=transcript,
                    internet_search_enabled=True,
                )
            else:
                reply = handle_command(user=request.user, message=transcript)
        except Exception:
            logger.exception('Liza command handler failed after transcription')
            return Response({'error': 'Buyruqni bajarishda xatolik yuz berdi.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response({
            'transcript': transcript,
            'reply': reply,
            **get_command_action_data(user=request.user, message=transcript),
        })


class WakeView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'liza_wake'

    def post(self, request):
        audio_file = request.FILES.get('audio')
        if audio_file is None:
            return Response({'error': 'Ovoz fayli yuborilmadi.'}, status=status.HTTP_400_BAD_REQUEST)
        if audio_file.size > 256 * 1024:
            return Response({'error': 'Uyg‘otuvchi so‘z audio bo‘lagi juda katta.'}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)
        if audio_file.content_type.split(';')[0] not in {'audio/wav', 'audio/x-wav'}:
            return Response({'error': 'Uyg‘otuvchi so‘z uchun WAV formati kerak.'}, status=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE)

        transcriber_path = getattr(settings, 'LIZA_TRANSCRIBE_HANDLER', '')
        if not transcriber_path:
            return Response({'error': 'Mahalliy transkripsiya xizmati sozlanmagan.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        try:
            transcriber = import_string(transcriber_path)
            transcript = transcriber(user=request.user, audio_file=audio_file)
        except TranscriptionUnavailable as error:
            return Response({'error': str(error)}, status=status.HTTP_503_SERVICE_UNAVAILABLE)
        except ValueError as error:
            return Response({'error': str(error)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception('Liza wake-word transcription failed')
            return Response({'error': 'Uyg‘otuvchi so‘zni aniqlab bo‘lmadi.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        normalized = re.sub(r'[^a-z]+', ' ', transcript.casefold()).split()
        detected = any(
            word in {'liza', 'lisa', 'lizza', 'lizaa'}
            or (3 <= len(word) <= 5 and SequenceMatcher(None, word, 'liza').ratio() >= 0.78)
            for word in normalized
        )
        action = get_command_action(user=request.user, message=transcript)
        profile_navigation = action == 'open_profile'
        logger.info(
            'Liza wake segment checked: user=%s detected=%s profile_navigation=%s',
            request.user.pk,
            detected,
            profile_navigation,
        )
        return Response({
            'wake': detected or profile_navigation,
            'transcript': transcript[:160],
            'action': action,
        })


class SpeechView(APIView):
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [JSONParser]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'liza_speech'

    def post(self, request):
        text = request.data.get('text') if isinstance(request.data, dict) else None
        if not isinstance(text, str) or not text.strip():
            return Response({'error': 'Ovozga aylantiriladigan matn bo‘sh.'}, status=status.HTTP_400_BAD_REQUEST)
        text = text.strip()
        if len(text) > MAX_MESSAGE_LENGTH:
            return Response({'error': 'Ovozga aylantiriladigan matn juda uzun.'}, status=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE)

        try:
            audio = synthesize_madina(text)
        except Exception:
            logger.exception('Liza Madina TTS failed')
            return Response({'error': 'Madina ovozini yaratib bo‘lmadi.'}, status=status.HTTP_503_SERVICE_UNAVAILABLE)

        response = Response({'audio': base64.b64encode(audio).decode('ascii'), 'content_type': 'audio/mpeg'})
        response['Cache-Control'] = 'no-store'
        return response