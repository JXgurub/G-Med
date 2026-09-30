import json
import logging
import os
import re
import wave
import asyncio
from datetime import datetime
from functools import lru_cache

from django.conf import settings
from django.core.cache import cache
from django.db.models import F, Q
from django.utils import timezone

from apps.doctors.models import Doctor
from apps.medical.models import Appointment
from apps.patients.serializers import PatientSerializer
from apps.patients.models import Patient

logger = logging.getLogger(__name__)

PROFILE_CONFIRM_TTL_SECONDS = 120
SPECIALTY_BOOKING_TTL_SECONDS = 180
SPECIALTY_SYMPTOM_RULES = (
    ('LOR', ('quloq', 'qulog', 'burun', 'tomoq', 'lor', 'ent', 'otit', 'eshitish'), ('lor', 'ent', 'otorinolaring')),
    ('stomatologiya', ('tish', 'stomat', 'dentist', 'dent'), ('stomat', 'dent')),
    ('kardiologiya', ('yurak', 'yurag', 'kardio', 'ko‘krak', 'kokrak'), ('kardio',)),
    ('nevrologiya', ('bosh og', 'boshim og', 'migren', 'asab', 'nevro', 'uyush'), ('nevro',)),
    ('oftalmologiya', ('ko‘z', 'koz', 'ko‘rish', 'korish', 'oftalm'), ('oftalm', 'opht')),
    ('gastroenterologiya', ('oshqozon', 'oshqoz', 'qorin', 'ichak', 'hazm', 'gastro'), ('gastro',)),
    ('ginekologiya', ('ayollar', 'ginekolog', 'homilador', 'bachadon'), ('ginekolog', 'ginekol')),
    ('pediatriya', ('bola', 'bolam', 'farzand', 'pediatr'), ('pediatr',)),
    ('dermatologiya', ('teri', 'toshma', 'qichish', 'dermatolog', 'dermat'), ('dermat',)),
    ('endokrinologiya', ('qalqonsimon', 'diabet', 'qandli', 'endokrin'), ('endokrin', 'diabet')),
    ('urologiya', ('siydik', 'buyrak', 'urolog'), ('urolog',)),
    ('nefrologiya', ('buyrak', 'nefrolog'), ('nefrolog',)),
    ('ortopediya va travmatologiya', ('suyak', 'bo‘g‘im', 'bogim', 'sinib', 'ortoped', 'travma'), ('ortoped', 'travmat')),
    ('pulmonologiya', ('nafas', 'o‘pka', 'opka', 'yo‘tal', 'yotal', 'pulmonolog'), ('pulmon', 'pulmo')),
    ('allergologiya', ('allergiya', 'allergolog'), ('allerg')),
    ('mammologiya', ('ko‘krak bezi', 'kokrak bezi', 'mammolog'), ('mammolog',)),
    ('revmatologiya', ('bo‘g‘im', 'bogim', 'revmatolog'), ('revmat',)),
    ('psixiatriya va psixoterapiya', ('ruhiy', 'depressiya', 'bezovta', 'psixolog', 'psixiatr'), ('psix', 'psy')),
    ('onkologiya', ('o‘sma', 'osma', 'saraton', 'onkolog'), ('onkolog',)),
    ('gematologiya', ('qon kasallik', 'gematolog'), ('gematolog',)),
    ('proktologiya', ('gemorroy', 'proktolog'), ('proktolog',)),
    ('andrologiya', ('androlog', 'erkaklar salomat'), ('androlog',)),
    ('flebologiya', ('varikoz', 'tomir', 'flebolog'), ('flebolog',)),
    ('reabilitatologiya', ('reabilitatsiya', 'tiklanish', 'reabilitolog'), ('reabilit',)),
)
BOOKING_REQUEST_WORDS = frozenset((
    'kerak', 'top', 'qidir', 'yozil', 'yozdir', 'qabulga', 'uchrashuv', 'navbat',
    'doktor', 'shifokor', 'mutaxassis', 'klinika',
))
SPECIALTY_STOP_WORDS = frozenset((
    'menga', 'men', 'uchun', 'kerak', 'top', 'topib', 'ber', 'qidir', 'qidirib',
    'yozil', 'yozdir', 'qabulga', 'uchrashuv', 'navbat', 'doktor', 'shifokor',
    'doktori', 'doktorini', 'doktorni', 'mutaxassis', 'klinika', 'klinikasini', 'klinikasidan', 'iltimos',
    'ayt', 'bering', 'va', 'da',
))
PROFILE_FIELD_ALIASES = (
    ('blood_type', 'Qon guruhi', ('qon guruhimni', 'qon guruhini')),
    ('date_of_birth', 'Tug‘ilgan sana', ("tug‘ilgan sanamni", "tug‘ilgan sanani", "tug'ilgan sanamni", "tug'ilgan sanani")),
    ('weight_kg', 'Vazn', ('vaznimni', 'vaznni')),
    ('height_cm', 'Bo‘y', ('bo‘yimni', 'bo‘yini', "bo'yimni", "bo'yini", 'boyimni', 'boyini')),
    ('drug_allergies', 'Dorilarga allergiya', ('dori allergiyamni', 'doriga allergiyamni', 'dorilar allergiyamni')),
    ('animal_allergies', 'Hayvonlarga allergiya', ('hayvon allergiyamni', 'hayvonlarga allergiyamni')),
)
PROFILE_EDITABLE_FIELDS = {field for field, _, _ in PROFILE_FIELD_ALIASES}
PATIENT_QUEUE_STATUSES = (
    Appointment.Status.SCHEDULED,
    Appointment.Status.CONFIRMED,
    Appointment.Status.WAITING,
)
PATIENT_ACTIVE_STATUSES = (*PATIENT_QUEUE_STATUSES, Appointment.Status.IN_PROGRESS)
WEEKDAY_NAMES = {
    'Mon': 'dushanba',
    'Tue': 'seshanba',
    'Wed': 'chorshanba',
    'Thu': 'payshanba',
    'Fri': 'juma',
    'Sat': 'shanba',
    'Sun': 'yakshanba',
}


def synthesize_madina(text):
    import edge_tts

    async def synthesize():
        communicator = edge_tts.Communicate(
            text,
            voice=settings.LIZA_TTS_VOICE,
            rate=settings.LIZA_TTS_RATE,
            volume='+0%',
        )
        audio_chunks = []
        async for chunk in communicator.stream():
            if chunk['type'] == 'audio':
                audio_chunks.append(chunk['data'])
        if not audio_chunks:
            raise RuntimeError('Madina TTS audio was empty')
        return b''.join(audio_chunks)

    return asyncio.run(synthesize())


class TranscriptionUnavailable(Exception):
    pass


@lru_cache(maxsize=1)
def _load_vosk_model(model_path):
    from vosk import Model

    return Model(model_path)


def transcribe_audio(*, user, audio_file):
    model_path = settings.LIZA_VOSK_MODEL_PATH
    if not os.path.isdir(model_path):
        raise TranscriptionUnavailable('Uzbek Vosk model topilmadi.')

    try:
        import vosk
    except ImportError as error:
        raise TranscriptionUnavailable('Vosk paketi o‘rnatilmagan.') from error

    try:
        with wave.open(audio_file, 'rb') as audio:
            if audio.getnchannels() != 1 or audio.getsampwidth() != 2 or audio.getframerate() != 16000:
                raise ValueError('Audio WAV 16 kHz, mono, 16-bit PCM bo‘lishi kerak.')
            recognizer = vosk.KaldiRecognizer(_load_vosk_model(model_path), 16000)
            while True:
                frames = audio.readframes(4000)
                if not frames:
                    break
                recognizer.AcceptWaveform(frames)
            return json.loads(recognizer.FinalResult()).get('text', '')
    except (wave.Error, EOFError) as error:
        raise ValueError('Audio fayli noto‘g‘ri WAV formatida.') from error


def _normalize_command(message):
    normalized = str(message or '').casefold().strip()
    return re.sub(r'[‘’ʻ`]', "'", normalized)


def _is_analysis_read_request(normalized):
    has_analysis = any(word in normalized for word in ('tahlil', 'taxlil', 'analiz'))
    has_read_intent = any(verb in normalized for verb in (
        'oqi', "o'qi", 'oqib', "o'qib", 'oqib ber', "o'qib ber", 'eshittir', 'eshitmoq',
    ))
    return has_analysis and has_read_intent


def _normalize_specialty_text(value):
    normalized = _normalize_command(value).replace("'", '')
    return re.sub(r'[^a-z0-9а-яё]+', ' ', normalized).strip()


def _specialty_tokens(value):
    return _normalize_specialty_text(value).split()


def _specialty_alias_matches(query_tokens, alias):
    alias_tokens = _specialty_tokens(alias)
    if not alias_tokens or len(alias_tokens) > len(query_tokens):
        return False
    for start_index in range(len(query_tokens) - len(alias_tokens) + 1):
        if all(
            query_tokens[start_index + offset] == alias_token
            or query_tokens[start_index + offset].startswith(alias_token)
            for offset, alias_token in enumerate(alias_tokens)
        ):
            return True
    return False


def _matched_specialty_rules(normalized):
    query_tokens = _specialty_tokens(normalized)
    matched_rules = []
    for label, aliases, search_terms in SPECIALTY_SYMPTOM_RULES:
        if any(_specialty_alias_matches(query_tokens, alias) for alias in aliases):
            matched_rules.append((label, search_terms))
    return matched_rules


def _specialty_name_matches_request(normalized, specialty_name, matched_rules=()):
    normalized_name = _normalize_specialty_text(specialty_name)
    if not normalized_name:
        return False
    if matched_rules:
        return any(term in normalized_name for _, terms in matched_rules for term in terms)

    query_tokens = {
        token for token in _specialty_tokens(normalized)
        if len(token) >= 4 and token not in SPECIALTY_STOP_WORDS
    }
    name_tokens = {
        token for token in _specialty_tokens(specialty_name)
        if len(token) >= 4 and token not in SPECIALTY_STOP_WORDS
    }
    return any(
        query_token == name_token
        or (len(query_token) >= 5 and name_token.startswith(query_token))
        or (len(name_token) >= 5 and query_token.startswith(name_token))
        for query_token in query_tokens
        for name_token in name_tokens
    )


def _specialty_search_terms(normalized, matched_rules):
    if matched_rules:
        return tuple(dict.fromkeys(
            term
            for _, terms in matched_rules
            for term in terms
        ))
    return tuple(dict.fromkeys(
        token for token in _specialty_tokens(normalized)
        if len(token) >= 3 and token not in SPECIALTY_STOP_WORDS
    ))


def _specialty_search_query(normalized, matched_rules):
    query = Q(pk__isnull=True)
    for term in _specialty_search_terms(normalized, matched_rules):
        query |= (
            Q(specializations__is_active=True, specializations__name__icontains=term)
            | Q(specialty_prices__is_active=True, specialty_prices__specialization__name__icontains=term)
            | Q(specialty_prices__is_active=True, specialty_prices__doctor_custom=True, specialty_prices__custom_name__icontains=term)
            | Q(
                headed_departments__is_active=True,
                headed_departments__clinic__is_blocked=False,
                headed_departments__clinic__status='active',
                headed_departments__clinic_id=F('clinic_id'),
                headed_departments__name__icontains=term,
            )
        )
    return query


def _has_active_specialty_name(normalized):
    return bool(_specialty_candidates(normalized))


def _is_specialty_booking_request(normalized):
    if _matched_specialty_rules(normalized):
        return True
    query_tokens = set(_specialty_tokens(normalized))
    if not any(
        token == marker or token.startswith(marker)
        for token in query_tokens
        for marker in BOOKING_REQUEST_WORDS
    ):
        return False
    return _has_active_specialty_name(normalized)


def _is_stop_listening_request(normalized):
    words = set(normalized.split())
    wake_seen = bool(words.intersection({'liza', 'lisa', 'liz', 'lizza', 'lizaa'}))
    stop_seen = any(word in words for word in ('toxta', "to'xta", 'toxtat', "to'xtat", 'bas', 'tugat'))
    return wake_seen and stop_seen or normalized in {'toxta', "to'xta", 'toxtat', "to'xtat"}


def get_command_action(*, user, message):
    if getattr(user, 'role', '') != 'patient':
        return None
    normalized = ' '.join(_normalize_command(message).split())
    profile_navigation_phrases = (
        "profilimga o't",
        "profilimga ot",
        "profelimga o't",
        "profelimga ot",
        "profilmga o't",
        "profilga o't",
        "profilga ot",
        "profilimni och",
        "profil bo'limiga o't",
        "profil bo'limiga ot",
        "profil bo'limini och",
        "shaxsiy profilimni och",
    )
    if any(phrase in normalized for phrase in profile_navigation_phrases):
        return 'open_profile'
    if _is_stop_listening_request(normalized):
        return 'stop_listening'
    if _is_analysis_read_request(normalized):
        return 'read_analysis'
    if _is_specialty_booking_request(normalized):
        return 'await_booking_confirmation'
    if cache.get(_booking_cache_key(user)) and _is_affirmative(normalized):
        return 'open_booking'
    return None


def get_command_action_data(*, user, message):
    action = get_command_action(user=user, message=message)
    result = {'action': action}
    if action == 'open_booking':
        cache_key = _booking_cache_key(user)
        pending = cache.get(cache_key)
        if pending:
            result['booking'] = pending
            cache.delete(cache_key)
    return result


def _is_affirmative(normalized):
    words = re.sub(r"[^a-z0-9']+", ' ', normalized).split()
    if _is_negative(normalized) or not words:
        return False
    return words[0] in {
        'ha', 'haa', 'xa', 'xaaa', 'albatta', 'mayli', 'hop', 'xop', "xo'p",
        'boladi', 'roziman', 'yoziling', 'oching',
    } or normalized in {'qabulga yozilaman', 'ha yoziling'}


def _is_negative(normalized):
    words = set(re.sub(r"[^a-z0-9']+", ' ', normalized).split())
    return bool(words.intersection({'yoq', "yo'q", 'bekor', 'yozilmang'})) or {
        'kerak', 'emas',
    }.issubset(words)


def _patient_appointments(patient, now):
    return list(
        Appointment.objects.filter(patient=patient, status__in=PATIENT_ACTIVE_STATUSES)
        .filter(Q(scheduled_date__gte=now) | Q(status=Appointment.Status.IN_PROGRESS, scheduled_date__date=now.date()))
        .select_related('doctor__user', 'doctor__clinic', 'clinic')
        .order_by('scheduled_date', 'created_at', 'queue_position')[:10]
    )


def _appointment_clinic(appointment):
    return appointment.clinic or getattr(appointment.doctor, 'clinic', None)


def _format_appointment(appointment):
    local_date = timezone.localtime(appointment.scheduled_date)
    doctor_name = appointment.doctor_name or (
        appointment.doctor.user.get_full_name() if appointment.doctor_id else ''
    ) or 'shifokor ko‘rsatilmagan'
    clinic = _appointment_clinic(appointment)
    clinic_name = appointment.clinic_name or (clinic.name if clinic else '') or 'klinika ko‘rsatilmagan'
    parts = [
        f"{local_date.strftime('%d.%m.%Y soat %H:%M')} dagi qabul",
        f'klinika: {clinic_name}',
        f'doktor: {doctor_name}',
    ]
    if clinic:
        if clinic.address:
            parts.append(f'manzil: {clinic.address}')
        if clinic.phone_number:
            parts.append(f'telefon: {clinic.phone_number}')
    return ', '.join(parts)


def _queue_details(appointment):
    if not appointment.doctor_id:
        return None, None
    appointment_day = timezone.localtime(appointment.scheduled_date).date()
    queue_items = list(
        Appointment.objects.filter(
            doctor_id=appointment.doctor_id,
            scheduled_date__date=appointment_day,
            status__in=PATIENT_QUEUE_STATUSES,
        ).order_by('scheduled_date', 'created_at', 'queue_position')
    )
    queue_ids = [str(item.id) for item in queue_items]
    try:
        queue_index = queue_ids.index(str(appointment.id))
    except ValueError:
        return appointment.queue_position or None, None
    ticket_number = appointment.queue_position or queue_index + 1
    return ticket_number, queue_index


def _hours_reply(appointment):
    doctor = appointment.doctor
    clinic = _appointment_clinic(appointment)
    lines = []
    if doctor:
        day_names = [
            WEEKDAY_NAMES.get(day.strip(), day.strip())
            for day in (doctor.working_days or '').split(',')
            if day.strip()
        ]
        days_text = ', '.join(day_names) if day_names else 'ish kunlari ko‘rsatilmagan'
        line = f"Doktor ish vaqti: {days_text}, {doctor.available_from.strftime('%H:%M')}–{doctor.available_until.strftime('%H:%M')}"
        if doctor.lunch_break_start and doctor.lunch_break_end:
            line += f", tanaffus {doctor.lunch_break_start.strftime('%H:%M')}–{doctor.lunch_break_end.strftime('%H:%M')}"
        lines.append(line + '.')
    else:
        lines.append('Doktorning ish vaqti topilmadi.')
    if clinic:
        lines.append(f"Klinika ish vaqti: {clinic.working_hours or 'ko‘rsatilmagan'}.")
    else:
        lines.append('Klinikaning ish vaqti topilmadi.')
    return ' '.join(lines)


def _profile_cache_key(user):
    return f'liza:patient-profile-confirm:{user.pk}'


def _booking_cache_key(user):
    return f'liza:patient-specialty-booking:{user.pk}'


def _specialty_candidates(normalized):
    matched_rules = _matched_specialty_rules(normalized)
    doctors = Doctor.objects.filter(
        is_active=True,
        clinic__isnull=False,
        clinic__is_blocked=False,
        clinic__status='active',
    ).filter(_specialty_search_query(normalized, matched_rules)).select_related(
        'user', 'clinic'
    ).prefetch_related(
        'specializations', 'specialty_prices__specialization', 'headed_departments'
    ).order_by(
        '-rating', '-total_ratings', 'user__first_name', 'user__last_name'
    )

    candidates = []
    for doctor in doctors:
        prices = [price for price in doctor.specialty_prices.all() if price.is_active]
        matching_prices = []
        matching_names = []

        for specialty in doctor.specializations.all():
            if specialty.is_active and _specialty_name_matches_request(
                normalized, specialty.name, matched_rules
            ):
                matching_names.append(specialty.name)

        for price in prices:
            specialty_name = (
                price.custom_name.strip()
                if price.doctor_custom and price.custom_name.strip()
                else price.specialization.name
            )
            if _specialty_name_matches_request(normalized, specialty_name, matched_rules):
                matching_prices.append(price)
                matching_names.append(specialty_name)

        for department in doctor.headed_departments.all():
            if (
                department.is_active
                and department.clinic_id == doctor.clinic_id
                and _specialty_name_matches_request(normalized, department.name, matched_rules)
            ):
                department_name = department.name
                matching_names.append(department_name)

        if not matching_names:
            continue

        clinic = doctor.clinic
        candidate_fee = (
            matching_prices[0].consultation_fee
            if matching_prices
            else doctor.consultation_fee
        )
        candidates.append({
            'doctor_id': str(doctor.id),
            'doctor_name': doctor.user.get_full_name().strip() or doctor.user.username,
            'clinic_id': str(clinic.id),
            'clinic_name': clinic.name,
            'clinic_address': clinic.address,
            'clinic_phone': clinic.phone_number,
            'specialty_price_ids': list(dict.fromkeys(str(price.id) for price in matching_prices)),
            'specialty_name': ', '.join(dict.fromkeys(matching_names)),
            'consultation_fee': str(candidate_fee or 0),
            'doctor_hours': f"{doctor.available_from.strftime('%H:%M')}–{doctor.available_until.strftime('%H:%M')}",
        })

    return candidates[:10]


def _requested_specialty_label(normalized):
    labels = list(dict.fromkeys(label for label, _ in _matched_specialty_rules(normalized)))
    if labels:
        return ', '.join(labels)
    return ' '.join(
        token for token in _specialty_tokens(normalized)
        if token not in SPECIALTY_STOP_WORDS
    ) or 'so‘ralgan'


def _spoken_uzbek_number(value):
    number_words = {
        'nol': 0,
        'bir': 1,
        'ikki': 2,
        'uch': 3,
        'tort': 4,
        'besh': 5,
        'olti': 6,
        'yetti': 7,
        'sakkiz': 8,
        'toqqiz': 9,
        'on': 10,
        'yigirma': 20,
        'ottiz': 30,
        'qirq': 40,
        'ellik': 50,
        'oltmish': 60,
        'yetmish': 70,
        'sakson': 80,
        'toqson': 90,
    }
    tokens = re.findall(r"[a-z']+", value.casefold())
    total = 0
    current = 0
    seen_number = False
    decimal_digits = ''
    decimal_mode = False

    for raw_token in tokens:
        token = raw_token.replace("'", '')
        if token in {'nuqta', 'butun', 'yarim'} and seen_number:
            decimal_mode = True
            if token == 'yarim':
                decimal_digits = '5'
                break
            continue
        if token == 'yuz':
            current = max(current, 1) * 100
            seen_number = True
            continue
        word_number = number_words.get(token)
        if word_number is None:
            break
        seen_number = True
        if decimal_mode:
            decimal_digits += str(word_number)
        else:
            current += word_number

    if not seen_number:
        return None
    whole = total + current
    return f'{whole}.{decimal_digits}' if decimal_digits else str(whole)


def _extract_profile_update(message):
    for field, label, aliases in PROFILE_FIELD_ALIASES:
        for alias in aliases:
            match = re.search(rf'(?<!\w){re.escape(alias)}\s+(.+)$', message)
            if not match:
                continue
            value = match.group(1).strip().rstrip('. ')
            value = re.sub(r"\s+(?:ga\s+)?(?:o'zgartir(?:ing)?|qil(?:ing)?|saqla(?:ng)?)\s*$", '', value)
            value = re.sub(r'\s+ga\s*$', '', value).strip(' .')
            if not value:
                return field, label, ''

            if field in {'weight_kg', 'height_cm'}:
                number = re.search(r'\d+(?:[.,]\d+)?', value)
                value = number.group(0).replace(',', '.') if number else (_spoken_uzbek_number(value) or value)
            elif field == 'date_of_birth':
                for date_format in ('%d.%m.%Y', '%d-%m-%Y'):
                    try:
                        value = datetime.strptime(value, date_format).date().isoformat()
                        break
                    except ValueError:
                        pass
            elif field == 'blood_type':
                value = re.sub(r'\s+', '', value).upper()
            return field, label, value
    return None


def _handle_patient_profile_command(*, user, patient, normalized):
    cache_key = _profile_cache_key(user)
    pending = cache.get(cache_key)
    if normalized in {'bekor', 'bekor qil', 'bekor qilaman', 'toxtat', "to'xtat"}:
        cache.delete(cache_key)
        return 'Profil o‘zgarishi bekor qilindi.'

    if normalized in {'tasdiqlayman', 'tasdiq', 'saqlansin', 'ha tasdiqlayman'}:
        if not pending:
            logger.info('Liza profile confirmation had no pending change: user=%s', user.pk)
            return 'Tasdiqlash uchun kutilayotgan profil o‘zgarishi yo‘q.'
        serializer = PatientSerializer(patient, data={pending['field']: pending['value']}, partial=True)
        if not serializer.is_valid():
            cache.delete(cache_key)
            errors = serializer.errors.get(pending['field'], ['Qiymat noto‘g‘ri.'])
            logger.warning('Liza profile confirmation rejected: user=%s field=%s', user.pk, pending['field'])
            return f"Profil yangilanmadi: {errors[0]}"
        serializer.save()
        cache.delete(cache_key)
        logger.info('Liza profile change confirmed: user=%s field=%s', user.pk, pending['field'])
        return 'Profil ma’lumotingiz muvaffaqiyatli yangilandi.'

    update = _extract_profile_update(normalized)
    if update:
        field, label, value = update
        if not value:
            return 'Qiymatni ham ayting. Masalan: “Vaznimni 70 ga o‘zgartir”.'
        serializer = PatientSerializer(patient, data={field: value}, partial=True)
        if not serializer.is_valid():
            errors = serializer.errors.get(field, ['Qiymat noto‘g‘ri.'])
            logger.info('Liza profile value rejected: user=%s field=%s', user.pk, field)
            return f"{label} uchun qiymat qabul qilinmadi: {errors[0]}"
        cache.set(cache_key, {'field': field, 'value': serializer.validated_data[field]}, PROFILE_CONFIRM_TTL_SECONDS)
        logger.info('Liza profile change is awaiting confirmation: user=%s field=%s', user.pk, field)
        return f"{label} maydonini yangilash so‘rovi tayyor. Saqlash uchun “tasdiqlayman”, bekor qilish uchun “bekor qil” deng."

    if 'parol' in normalized or 'password' in normalized:
        return 'Parolni o‘zgartirish uchun Bemor sahifasi → Profilim bo‘limidagi joriy parol formasidan foydalaning.'
    return (
        'Profil bo‘limidagi qon guruhi, tug‘ilgan sana, vazn, bo‘y va allergiya maydonlarini '
        'Liza orqali yangilashingiz mumkin. O‘zgarish faqat alohida tasdiqdan keyin saqlanadi. '
        'Parol esa Profilim bo‘limida joriy parol bilan o‘zgartiriladi.'
    )


def _handle_patient_command(*, user, message):
    patient = Patient.objects.filter(user=user).first()
    if patient is None:
        return 'Bemor profilingiz topilmadi. G-MED qo‘llab-quvvatlash xizmatiga murojaat qiling.'

    normalized = _normalize_command(message)
    if cache.get(_profile_cache_key(user)) or normalized in {
        'bekor', 'bekor qil', 'bekor qilaman', 'toxtat', "to'xtat",
        'tasdiqlayman', 'tasdiq', 'saqlansin', 'ha tasdiqlayman',
    }:
        return _handle_patient_profile_command(user=user, patient=patient, normalized=normalized)
    if any(word in normalized for word in ('profil', 'qon guruh', 'tug\'ilgan sana', 'tug‘ilgan sana', 'vazn', 'bo‘y', 'boy', 'allergiya', 'parol')):
        return _handle_patient_profile_command(user=user, patient=patient, normalized=normalized)

    pending_booking_key = _booking_cache_key(user)
    pending_booking = cache.get(pending_booking_key)
    if pending_booking and _is_affirmative(normalized):
        return f"{pending_booking['doctor_name']} doktor qabuli uchun yozilish oynasini ochyapman."
    if pending_booking and _is_negative(normalized):
        cache.delete(pending_booking_key)
        return 'Xo‘p, mutaxassis qabuliga yozilish bekor qilindi.'

    if _is_analysis_read_request(normalized):
        return 'Ko‘rinib turgan tayyor AI tahlil javobini Madina ovozida o‘qishga uzatyapman.'

    if _is_specialty_booking_request(normalized):
        candidates = _specialty_candidates(normalized)
        if not candidates:
            specialty_label = _requested_specialty_label(normalized)
            return (
                f"Hozir G-MED klinikalarida {specialty_label} yo‘nalishida faol doktor topilmadi. "
                'Boshqa yo‘nalishni ayting yoki klinikaga qo‘ng‘iroq qilib aniqlashtiring.'
            )
        specialist = candidates[0]
        cache.set(pending_booking_key, specialist, SPECIALTY_BOOKING_TTL_SECONDS)
        return (
            f"{specialist['specialty_name']} yo‘nalishida mos doktor topdim: {specialist['doctor_name']}, "
            f"{specialist['clinic_name']} klinikasida. Manzil: {specialist['clinic_address']}. "
            f"Telefon: {specialist['clinic_phone']}. Ish vaqti: {specialist['doctor_hours']}. "
            'Shu doktorga qabulga yozilish oynasini ochaymi? Ha yoki yo‘q deb javob bering.'
        )

    now = timezone.localtime()
    appointments = _patient_appointments(patient, now)
    if not appointments:
        if any(word in normalized for word in ('qabul', 'navbat', 'uchrashuv', 'doktor', 'shifokor', 'klinika', 'ish vaqti')):
            return 'Sizda hozir faol yoki kelgusi qabul topilmadi.'
        return 'Men qabulingiz, navbat holati, klinika va doktor ish vaqti hamda profilingiz bo‘yicha yordam bera olaman.'

    appointment = appointments[0]
    queue_intent = any(word in normalized for word in ('navbat', 'oldinda', 'qator', 'nechta odam'))
    hours_intent = any(word in normalized for word in ('ish vaqti', 'ishlaydi', 'ish kunlari', 'qachon ochiq'))

    if queue_intent:
        if appointment.status == Appointment.Status.IN_PROGRESS:
            return f"{_format_appointment(appointment)}. Doktor sizni qabul qilyapti."
        ticket_number, ahead_count = _queue_details(appointment)
        if ticket_number is None:
            return f"{_format_appointment(appointment)}. Navbat raqami hali belgilanmagan."
        if ahead_count is None:
            return f"{_format_appointment(appointment)}. Navbat raqamingiz {ticket_number}; oldindagi odamlar soni hali aniqlanmagan."
        return f"{_format_appointment(appointment)}. Navbat raqamingiz {ticket_number}; oldinda {ahead_count} ta odam bor."

    if hours_intent:
        return f"{_format_appointment(appointment)}. {_hours_reply(appointment)}"

    if any(word in normalized for word in ('qabul', 'uchrashuv', 'doktor', 'shifokor', 'klinika', 'manzil')):
        details = [_format_appointment(item) for item in appointments[:3]]
        return 'Yaqin qabullaringiz: ' + '; '.join(details) + '.'

    return 'Men qabulingiz, navbat holati, klinika va doktor ish vaqti hamda profilingiz bo‘yicha yordam bera olaman.'


def handle_command(*, user, message):
    normalized = ' '.join(_normalize_command(message).split())
    if normalized in {'salom', 'assalomu alaykum', 'liza', 'yordam'} or 'nima qila olasan' in normalized:
        return (
            "Men G-MED yordamchisiman. Qabulingiz, navbat raqamingiz, klinika va doktor ish vaqti "
            "hamda profilingiz bo‘yicha yordam beraman."
        )

    if get_command_action(user=user, message=message) == 'open_profile':
        return 'Profilim bo‘limini ochyapman.'
    if get_command_action(user=user, message=message) == 'stop_listening':
        return 'Liza suhbatni to‘xtatdi. Qayta ishlatish uchun Liza tugmasini bosing.'

    if user.role == 'patient':
        return _handle_patient_command(user=user, message=message)

    if not any(word in normalized for word in ('qabul', 'navbat', 'uchrashuv')):
        return "Hozircha qabul va navbatlar bo'yicha savollarga javob bera olaman. 'Bugungi qabullarim' deb so'rang."

    now = timezone.localtime()
    if user.role == 'doctor':
        doctor = getattr(user, 'doctor', None)
        if doctor is None or not doctor.is_active:
            return "Faol shifokor profilingiz topilmadi. Klinikangiz administratoriga murojaat qiling."
        today_appointments = Appointment.objects.filter(
            doctor=doctor,
            scheduled_date__date=now.date(),
        ).exclude(status__in=(Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW))
        appointment_count = today_appointments.count()
        appointments = today_appointments.order_by('scheduled_date')[:5]
        if not appointment_count:
            return "Bugun sizda qabul rejalashtirilmagan."
        details = [
            f"{timezone.localtime(appointment.scheduled_date).strftime('%H:%M')} da, navbat {appointment.queue_position or 'belgilanmagan'}"
            for appointment in appointments
        ]
        return f"Bugun sizda {appointment_count} ta qabul bor. " + '; '.join(details) + '.'

    if user.role == 'patient':
        patient = getattr(user, 'patient', None)
        if patient is None:
            return "Bemor profilingiz topilmadi. G-MED qo'llab-quvvatlash xizmatiga murojaat qiling."
        upcoming_appointments = Appointment.objects.filter(
            patient=patient,
            scheduled_date__gte=now,
        ).exclude(status__in=(Appointment.Status.CANCELLED, Appointment.Status.NO_SHOW))
        appointment_count = upcoming_appointments.count()
        appointments = upcoming_appointments.order_by('scheduled_date')[:5]
        if not appointment_count:
            return "Sizda kelgusi qabul rejalashtirilmagan."
        details = [
            f"{timezone.localtime(appointment.scheduled_date).strftime('%d.%m.%Y %H:%M')} da"
            + (f", {appointment.doctor_name or appointment.doctor.user.get_full_name()} bilan" if appointment.doctor_id else '')
            for appointment in appointments
        ]
        return f"Sizda {appointment_count} ta kelgusi qabul bor. " + '; '.join(details) + '.'

    return "Qabullar bo'yicha ma'lumot faqat bemor va shifokor profillari uchun mavjud."