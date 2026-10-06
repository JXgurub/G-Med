import json
import logging
import os
import re
import wave
import asyncio
import hashlib
from datetime import datetime
from functools import lru_cache
from html.parser import HTMLParser
from urllib.parse import parse_qs, quote_plus, unquote, urlparse

import requests

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
INTERNET_SEARCH_WORDS = frozenset((
    'internet', 'qidir', 'qidiruv', 'izla', 'izlash', 'ma’lumot', 'malumot',
    'yangilik', 'yangiliklar', 'google', 'web',
))
YOUTUBE_WORDS = frozenset(('youtube', 'youtub', 'yutub', 'qo‘shiq', 'qoshiq', 'musiqa', 'muzika'))
YOUTUBE_TRIGGER = re.compile(r'\b(?:youtube|youtub|yutub|yutube|yutobe)(?:\s*)?(?:dan|da|ga)?\b')
YOUTUBE_QUEUE_TTL_SECONDS = 3600
YOUTUBE_TITLE_TTL_SECONDS = 180
INTERNET_SEARCH_CACHE_TTL_SECONDS = 180


class _DuckDuckGoResultsParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.results = []
        self.current_result = None
        self.capture_field = None
        self.capture_tag = None
        self.capture_depth = 0
        self.capture_text = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        classes = set((attributes.get('class') or '').split())
        if tag == 'a' and 'result__a' in classes:
            self._finish_result()
            self.current_result = {
                'title': '',
                'url': attributes.get('href', ''),
                'snippet': '',
            }
            self.capture_field = 'title'
            self.capture_tag = tag
            self.capture_depth = 0
            self.capture_text = []
        elif self.current_result and 'result__snippet' in classes:
            self.capture_field = 'snippet'
            self.capture_tag = tag
            self.capture_depth = 0
            self.capture_text = []
        elif self.capture_field:
            self.capture_depth += 1

    def handle_data(self, data):
        if self.capture_field:
            self.capture_text.append(data)

    def handle_endtag(self, tag):
        if not self.capture_field:
            return
        if tag == self.capture_tag and self.capture_depth == 0:
            self.current_result[self.capture_field] = ' '.join(' '.join(self.capture_text).split())
            was_snippet = self.capture_field == 'snippet'
            self.capture_field = None
            self.capture_tag = None
            self.capture_text = []
            if was_snippet:
                self._finish_result()
            return
        if self.capture_depth:
            self.capture_depth -= 1

    def _finish_result(self):
        if self.current_result and self.current_result.get('title'):
            self.results.append(self.current_result)
        self.current_result = None


def _external_query(normalized, words):
    query = normalized
    for phrase in words:
        query = re.sub(rf'\b{re.escape(phrase)}\b', ' ', query)
    query = re.sub(r'\b(?:liza|top|ber|qidirib|qidirib ber|internetda|internetdan|youtube da|youtubeda)\b', ' ', query)
    return ' '.join(query.split()).strip(' ,.?!')


def _youtube_query(normalized):
    query = YOUTUBE_TRIGGER.sub(' ', normalized)
    query = re.sub(
        r"\b(?:menga|iltimos|qo'shiq(?:ni|lar|larni)?|qo'shig(?:'ini|'i|'lar|'larni)?|"
        r"qoshiq(?:ni|lar|larni)?|qoshig(?:'ini|'i|'lar|'larni)?|musiqa|muzika|"
        r"qo'yib ber|qoyib ber|qo'y|qoy|ijro et(?:ib ber)?)\b",
        ' ',
        query,
    )
    return ' '.join(query.split()).strip(' ,.?!')


def _youtube_search_results(query):
    cache_key = f"liza:youtube-search:{hashlib.sha256(query.casefold().encode('utf-8')).hexdigest()}"
    cached = cache.get(cache_key)
    if cached:
        return cached
    results = []
    try:
        from yt_dlp import YoutubeDL

        options = {
            'quiet': True,
            'no_warnings': True,
            'skip_download': True,
            'noplaylist': True,
            'extract_flat': 'in_playlist',
            'socket_timeout': 8,
            'retries': 1,
            'extractor_retries': 1,
        }
        with YoutubeDL(options) as youtube:
            search = youtube.extract_info(f'ytsearch5:{query}', download=False)
        results = [
            {'id': item['id'], 'title': item.get('title') or query}
            for item in (search or {}).get('entries', [])
            if item and isinstance(item.get('id'), str) and re.fullmatch(r'[\w-]{11}', item['id'])
        ]
    except Exception:
        logger.warning('Liza YouTube extractor search failed; trying YouTube page results', exc_info=True)

    if not results:
        try:
            response = requests.get(
                'https://www.youtube.com/results',
                params={'search_query': query},
                timeout=12,
                headers={
                    'User-Agent': (
                        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                        'AppleWebKit/537.36 (KHTML, like Gecko) '
                        'Chrome/131.0.0.0 Safari/537.36'
                    ),
                    'Accept-Language': 'uz,en-US;q=0.9,en;q=0.8',
                },
            )
            response.raise_for_status()
            initial_data = re.search(r'(?:var\s+)?ytInitialData\s*=\s*', response.text)
            if not initial_data:
                raise ValueError('YouTube search page did not contain initial search data.')
            data, _ = json.JSONDecoder().raw_decode(response.text, initial_data.end())
            seen_ids = set()

            def collect_videos(value):
                if len(results) >= 5:
                    return
                if isinstance(value, dict):
                    renderer = value.get('videoRenderer')
                    if renderer:
                        video_id = renderer.get('videoId')
                        title_data = renderer.get('title') or {}
                        title = title_data.get('simpleText') or ''.join(
                            run.get('text', '') for run in title_data.get('runs', [])
                        )
                        if (
                            isinstance(video_id, str)
                            and re.fullmatch(r'[\w-]{11}', video_id)
                            and video_id not in seen_ids
                            and title
                        ):
                            seen_ids.add(video_id)
                            results.append({'id': video_id, 'title': title})
                    for child in value.values():
                        collect_videos(child)
                elif isinstance(value, list):
                    for child in value:
                        collect_videos(child)

            collect_videos(data)
        except (requests.RequestException, ValueError, TypeError, json.JSONDecodeError):
            logger.warning('Liza YouTube page search failed', exc_info=True)

    if results:
        cache.set(cache_key, results, 300)
    return results


def _youtube_queue_key(user):
    return f'liza:youtube-queue:{user.pk}'


def _youtube_title_key(user):
    return f'liza:youtube-await-title:{user.pk}'


def _is_liza_wake_request(normalized):
    tokens = re.findall(r"[a-z']+", normalized)
    return len(tokens) == 1 and tokens[0] in {'liza', 'lisa', 'lizza', 'lizaa'}


def _youtube_control_intent(normalized):
    words = set(re.findall(r"[a-z']+", normalized))
    if words.intersection({'keyingi', 'keyingisi', 'keyingisiga', 'next'}):
        return 'next'
    if words.intersection({'oldingi', 'avvalgi', 'previous', 'prev'}) or 'orqaga qaytar' in normalized:
        return 'previous'
    if words.intersection({'orqaga', 'ortga', 'rewind'}) or 'soniya orqaga' in normalized:
        return 'rewind'
    if words.intersection({'davom', 'play', 'boshlat'}) or any(phrase in normalized for phrase in ('davom et', 'davom ettir')):
        return 'play'
    if words.intersection({'pauza', 'pause', 'shitob', 'shittob', 'shitop', 'stop', 'toxta', "to'xta", 'toxtat', "to'xtat"}):
        return 'pause'
    return None


def _handle_youtube_control(*, user, control):
    queue = cache.get(_youtube_queue_key(user))
    videos = queue.get('videos', []) if isinstance(queue, dict) else []
    if not videos:
        return 'Avval YouTube’da qo‘shiq nomini aytib, ijroni boshlang.'

    index = min(max(int(queue.get('index', 0)), 0), len(videos) - 1)
    if control == 'next':
        index = (index + 1) % len(videos)
        queue['index'] = index
        cache.set(_youtube_queue_key(user), queue, YOUTUBE_QUEUE_TTL_SECONDS)
        return f"Keyingi qo‘shiq: {videos[index]['title']}."
    if control == 'previous':
        index = (index - 1) % len(videos)
        queue['index'] = index
        cache.set(_youtube_queue_key(user), queue, YOUTUBE_QUEUE_TTL_SECONDS)
        return f"Oldingi qo‘shiq: {videos[index]['title']}."
    if control == 'pause':
        return 'Qo‘shiqni to‘xtatdim.'
    if control == 'play':
        return 'Qo‘shiqni davom ettiryapman.'
    if control == 'rewind':
        return 'Qo‘shiqni 10 soniya orqaga qaytaryapman.'
    return 'YouTube buyrug‘ini tushunmadim.'


def _is_weather_request(normalized):
    return any(term in normalized for term in ('ob-havo', 'ob havo', 'obxavo', 'pogoda', 'weather'))


def _weather_reply(normalized):
    location = re.sub(
        r'\b(?:ob[\s-]?havo|obxavo)(?:si|ni|dagi|ning|ga|dan)?\b|\b(?:pogoda|weather)\b',
        ' ',
        normalized,
    )
    location = re.sub(
        r"\b(?:bugun(?:gi)?|hozir|qanaqa|qanday|today|now|in|at|da|uchun|"
        r"haqida|ma[' ]?lumot(?:ni|lar(?:ni)?)?|ber(?:ing)?|ayt(?:ing)?|"
        r"shahrida|shaharida|shaharda|shahri|shahar)\b",
        ' ',
        location,
    )
    location = ' '.join(location.split()).strip(' ,.?!')
    if not location:
        return 'Ob-havoni tekshirish uchun shahar nomini ham ayting. Masalan: Toshkentda ob-havo qanday?'
    try:
        location_candidates = [location]
        if location.lower().endswith('da') and len(location) > 4:
            location_candidates.append(location[:-2])
        response = requests.get(
            'https://geocoding-api.open-meteo.com/v1/search',
            params={'name': location_candidates[-1], 'count': 5, 'language': 'uz', 'format': 'json'},
            timeout=8,
        )
        response.raise_for_status()
        places = response.json().get('results', [])
        place = next((item for item in places if item.get('country_code') == 'UZ'), None) or (places[0] if places else None)
        if not place:
            return f'{location} nomli shahar topilmadi.'
        response = requests.get(
            'https://api.open-meteo.com/v1/forecast',
            params={
                'latitude': place['latitude'],
                'longitude': place['longitude'],
                'current': 'temperature_2m,apparent_temperature,weather_code,wind_speed_10m',
                'timezone': 'auto',
            },
            timeout=8,
        )
        response.raise_for_status()
        current = response.json()['current']
        descriptions = {
            0: 'ochiq', 1: 'asosan ochiq', 2: 'qisman bulutli', 3: 'bulutli',
            45: 'tumanli', 48: 'tumanli', 51: 'mayda yomg‘irli', 53: 'yomg‘irli',
            55: 'kuchli yomg‘irli', 61: 'yomg‘irli', 63: 'yomg‘irli', 65: 'kuchli yomg‘irli',
            71: 'qorli', 73: 'qorli', 75: 'kuchli qorli', 80: 'yomg‘ir yog‘ishi mumkin',
            81: 'yomg‘ir yog‘ishi mumkin', 82: 'kuchli yomg‘ir yog‘ishi mumkin', 95: 'momaqaldiroqli',
        }
        return (
            f"{place['name']}da hozir {descriptions.get(current['weather_code'], 'noma’lum')}, "
            f"harorat {current['temperature_2m']} daraja, shamol {current['wind_speed_10m']} kilometr soatiga."
        )
    except (requests.RequestException, KeyError, TypeError, ValueError):
        logger.warning('Liza weather lookup failed', exc_info=True)
        return 'Ob-havo ma’lumotini hozir olib bo‘lmadi. Birozdan keyin qayta urinib ko‘ring.'


def _internet_search_results(query):
    cache_key = (
        f"liza:internet-search:{hashlib.sha256(query.casefold().encode('utf-8')).hexdigest()}"
    )
    cached = cache.get(cache_key)
    if cached:
        return cached

    response = requests.get(
        'https://html.duckduckgo.com/html/',
        params={'q': query},
        timeout=10,
        headers={
            'User-Agent': (
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                'AppleWebKit/537.36 (KHTML, like Gecko) '
                'Chrome/131.0.0.0 Safari/537.36'
            ),
            'Accept-Language': 'uz,en-US;q=0.9,en;q=0.8',
        },
    )
    response.raise_for_status()
    parser = _DuckDuckGoResultsParser()
    parser.feed(response.text)
    results = []
    seen_urls = set()
    for item in parser.results:
        href = item['url']
        parsed = urlparse(href)
        if parsed.hostname and parsed.hostname.endswith('duckduckgo.com'):
            href = parse_qs(parsed.query).get('uddg', [''])[0]
        elif href.startswith('//'):
            href = f'https:{href}'
        elif href.startswith('/'):
            continue
        href = unquote(href)
        parsed = urlparse(href)
        if (
            parsed.scheme not in {'http', 'https'}
            or not parsed.hostname
            or parsed.hostname.endswith('duckduckgo.com')
            or href in seen_urls
        ):
            continue
        seen_urls.add(href)
        results.append({
            'title': item['title'][:240],
            'snippet': item['snippet'][:500],
            'url': href,
        })
        if len(results) == 5:
            break
    if results:
        cache.set(cache_key, results, INTERNET_SEARCH_CACHE_TTL_SECONDS)
    return results


def _safe_external_query(query):
    query = re.sub(r'\b[\w.+-]+@[\w.-]+\.[a-zA-Z]{2,}\b', ' ', query)
    query = re.sub(r'(?<!\w)\+?\d[\d\s().-]{6,}\d(?!\w)', ' ', query)
    query = re.sub(r'\s+', ' ', query).strip(' ,.?!')
    return query[:300]


def _internet_search_reply(query):
    query = _safe_external_query(query)
    if not query:
        return 'Shaxsiy ma’lumotlarni qidiruvga yubormadim. Savolni shaxsiy ma’lumotlarsiz qayta yozing.'

    try:
        results = _internet_search_results(query)
    except requests.RequestException:
        logger.warning('Liza internet search request failed', exc_info=True)
        results = []

    if results:
        lines = ['Internet qidiruvi natijalari:']
        for index, result in enumerate(results, start=1):
            snippet = f" — {result['snippet']}" if result['snippet'] else ''
            lines.append(f"{index}. {result['title']}{snippet}")
        lines.append('Manbalar:')
        lines.extend(f"{index}. {item['url']}" for index, item in enumerate(results, start=1))
        return '\n'.join(lines)

    try:
        response = requests.get(
            'https://api.duckduckgo.com/',
            params={'q': query, 'format': 'json', 'no_html': 1, 'skip_disambig': 1},
            timeout=8,
            headers={'User-Agent': 'G-MED-Liza/1.0'},
        )
        response.raise_for_status()
        data = response.json()
        text = data.get('AbstractText') or data.get('Answer')
        source = data.get('AbstractURL') or data.get('Redirect')
        if text:
            suffix = f'\nManba:\n{source}' if source else ''
            return f'{text[:900]}{suffix}'
        related = next((item for item in data.get('RelatedTopics', []) if item.get('Text')), None)
        if related:
            source = related.get('FirstURL', '')
            suffix = f'\nManba:\n{source}' if source else ''
            return f"{related['Text'][:900]}{suffix}"
        return (
            'Qidiruv natijasi topilmadi. To‘g‘ridan-to‘g‘ri ko‘rish: '
            f'https://duckduckgo.com/?q={quote_plus(query)}'
        )
    except (requests.RequestException, ValueError, TypeError):
        logger.warning('Liza internet search fallback failed', exc_info=True)
        return 'Internet qidiruvi hozir ishlamadi. Birozdan keyin qayta urinib ko‘ring.'


def _internet_reply(normalized, user=None, internet_search_enabled=False):
    if _is_weather_request(normalized):
        return _weather_reply(normalized)

    awaiting_title = (
        getattr(user, 'role', '') == 'patient'
        and getattr(user, 'pk', None) is not None
        and cache.get(_youtube_title_key(user))
    )
    if YOUTUBE_TRIGGER.search(normalized) or any(word in normalized for word in YOUTUBE_WORDS) or awaiting_title:
        query = _youtube_query(normalized)
        if not query:
            if user is not None:
                cache.set(_youtube_title_key(user), True, YOUTUBE_TITLE_TTL_SECONDS)
            return 'YouTube’da qidirish uchun qo‘shiq yoki video nomini ayting.'
        videos = _youtube_search_results(query)
        if not videos:
            return 'YouTube’dan mos video topilmadi yoki xizmat hozir ishlamayapti. Birozdan keyin qayta urinib ko‘ring.'
        if user is not None:
            cache.delete(_youtube_title_key(user))
            cache.set(
                _youtube_queue_key(user),
                {'query': query, 'videos': videos, 'index': 0},
                YOUTUBE_QUEUE_TTL_SECONDS,
            )
        return f"YouTube’da “{videos[0]['title']}” qo‘shig‘ini ijro etyapman."

    if _matched_specialty_rules(normalized):
        return None

    if internet_search_enabled:
        if get_command_action(user=user, message=normalized):
            return None
        if any(term in normalized for term in (
            'profil', 'qon guruh', 'tugilgan sana', 'vazn', 'boyim', 'allergiya',
            'parol', 'qabulim', 'navbatim', 'qabulga yozil',
        )):
            return None

    if not internet_search_enabled and not any(word in normalized for word in INTERNET_SEARCH_WORDS):
        return None
    query = _external_query(normalized, INTERNET_SEARCH_WORDS) if any(
        word in normalized for word in INTERNET_SEARCH_WORDS
    ) else normalized
    if not query:
        return 'Internetda nimani qidiray? Masalan: internetda bugungi yangiliklarni qidir.'
    return _internet_search_reply(query)


_ONES = ('', 'bir', 'ikki', 'uch', "to'rt", 'besh', 'olti', 'yetti', 'sakkiz', "to'qqiz")
_TENS = ('', "o'n", 'yigirma', "o'ttiz", 'qirq', 'ellik', 'oltmish', 'yetmish', 'sakson', "to'qson")
_MONTHS = (
    'yanvar', 'fevral', 'mart', 'aprel', 'may', 'iyun',
    'iyul', 'avgust', 'sentabr', 'oktabr', 'noyabr', 'dekabr',
)
_DIGIT_WORDS = ('nol',) + _ONES[1:]


def _number_words(value):
    if value == 0:
        return 'nol'

    def below_thousand(number):
        words = []
        if number >= 100:
            words += [_ONES[number // 100], 'yuz']
        words += [_TENS[(number % 100) // 10], _ONES[number % 10]]
        return [word for word in words if word]

    words = []
    for size, name in ((10**9, 'milliard'), (10**6, 'million'), (1000, 'ming')):
        if value >= size:
            words += below_thousand(value // size) + [name]
            value %= size
    words += below_thousand(value)
    return ' '.join(words)


def _digits_words(digits):
    return ' '.join(_DIGIT_WORDS[int(char)] for char in digits if char.isdigit())


def _time_words(hour, minute):
    words = f'soat {_number_words(int(hour))}'
    return words if int(minute) == 0 else f'{words} {_number_words(int(minute))}'


def speakable_text(text):
    """Replaces digits with Uzbek words so TTS never reads "0" as a letter."""
    text = str(text or '')
    text = re.sub(
        r'\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b',
        lambda m: (
            f'{_number_words(int(m[1]))} '
            f'{_MONTHS[int(m[2]) - 1] if 1 <= int(m[2]) <= 12 else _number_words(int(m[2]))} '
            f'{_number_words(int(m[3]))}'
        ),
        text,
    )
    text = re.sub(
        r'\b(\d{1,2}):(\d{2})\s*[–—-]\s*(\d{1,2}):(\d{2})\b',
        lambda m: f'{_time_words(m[1], m[2])} dan {_time_words(m[3], m[4])} gacha',
        text,
    )
    text = re.sub(r'\b(\d{1,2}):(\d{2})\b', lambda m: _time_words(m[1], m[2]), text)

    def phone_or_number(match):
        raw = match[0]
        digits = re.sub(r'\D', '', raw)
        if raw.startswith('+') or len(digits) >= 9:
            return _digits_words(digits)
        return _number_words(int(digits))

    text = re.sub(r'\+?\d(?:[\s\-()]?\d){6,}', lambda m: _digits_words(re.sub(r'\D', '', m[0])), text)
    text = re.sub(r'(\d+)[.,](\d+)', lambda m: f'{_number_words(int(m[1]))} nuqta {_digits_words(m[2])}', text)
    return re.sub(r'\+?\d+', phone_or_number, text)


def synthesize_madina(text):
    import edge_tts

    text = speakable_text(text)

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
    pending = cache.get(_booking_cache_key(user))
    if _is_specialty_booking_request(normalized):
        if pending and len(_pending_candidates(pending)) > 1:
            return 'await_doctor_selection'
        return 'await_booking_confirmation'
    if pending and _select_pending_candidate(pending, normalized):
        return 'open_booking'
    if pending and _is_affirmative(normalized):
        return 'await_doctor_selection' if len(_pending_candidates(pending)) > 1 else 'open_booking'
    return None


def get_command_action_data(*, user, message):
    action = get_command_action(user=user, message=message)
    result = {'action': action}
    normalized = ' '.join(_normalize_command(message).split())
    control = _youtube_control_intent(normalized)
    is_patient = getattr(user, 'role', '') == 'patient' and getattr(user, 'pk', None) is not None
    queue = cache.get(_youtube_queue_key(user)) if is_patient else None
    if queue and queue.get('videos') and _is_liza_wake_request(normalized):
        result.update({'action': 'youtube_duck'})
    elif control and queue and queue.get('videos'):
        videos = queue['videos']
        index = min(max(int(queue.get('index', 0)), 0), len(videos) - 1)
        result.update({
            'action': 'youtube_control',
            'control': control,
            'video_id': videos[index]['id'],
            'video_title': videos[index]['title'],
            'queue_position': index + 1,
            'queue_count': len(videos),
        })
    elif (
        YOUTUBE_TRIGGER.search(normalized)
        or any(word in normalized for word in YOUTUBE_WORDS)
        or (is_patient and cache.get(_youtube_title_key(user)))
        or (queue and queue.get('query') == _youtube_query(normalized))
    ):
        query = _youtube_query(normalized)
        if queue and queue.get('query') == query and queue.get('videos'):
            video = queue['videos'][0]
            result.update({'action': 'play_youtube', 'video_id': video['id'], 'video_title': video['title'], 'queue_count': len(queue['videos'])})
    if action == 'open_booking':
        cache_key = _booking_cache_key(user)
        pending = cache.get(cache_key)
        if pending:
            chosen = _select_pending_candidate(pending, normalized) or _pending_candidates(pending)[0]
            result['booking'] = chosen
            cache.delete(cache_key)
    return result


ORDINAL_WORDS = (
    ('birinchi', 'birinchisi', 'birinchini', 'avvalgi'),
    ('ikkinchi', 'ikkinchisi', 'ikkinchini'),
    ('uchinchi', 'uchinchisi', 'uchinchini'),
    ("to'rtinchi", "to'rtinchisi", 'tortinchi', 'tortinchisi'),
    ('beshinchi', 'beshinchisi'),
    ('oltinchi', 'oltinchisi'),
    ('yettinchi', 'yettinchisi'),
    ('sakkizinchi', 'sakkizinchisi'),
    ("to'qqizinchi", "to'qqizinchisi", 'toqqizinchi', 'toqqizinchisi'),
    ("o'ninchi", "o'ninchisi", 'oninchi', 'oninchisi'),
)


def _pending_candidates(pending):
    candidates = pending.get('candidates')
    if candidates:
        return candidates
    return [{key: value for key, value in pending.items() if key != 'candidates'}]


def _select_pending_candidate(pending, normalized):
    candidates = _pending_candidates(pending)
    words = re.sub(r"[^a-z0-9']+", ' ', normalized).split()
    digits = re.findall(r'(?<!\w)\d+(?!\w)', normalized)
    if len(digits) == 1:
        candidate_index = int(digits[0]) - 1
        if 0 <= candidate_index < len(candidates):
            return candidates[candidate_index]

    cardinal_words = (
        ('bir',),
        ('ikki',),
        ('uch',),
        ('tort', "to'rt"),
        ('besh',),
        ('olti',),
        ('yetti',),
        ('sakkiz',),
        ('toqqiz', "to'qqiz"),
        ('on', "o'n"),
    )
    for index, forms in enumerate(ORDINAL_WORDS[:len(candidates)]):
        spoken_numbers = cardinal_words[index] if index < len(cardinal_words) else ()
        if any(word in forms or word in spoken_numbers for word in words):
            return candidates[index]
    if not candidates:
        return None
    matches = []
    for candidate in candidates:
        name_tokens = [token for token in _specialty_tokens(candidate['doctor_name']) if len(token) >= 3]
        if any(
            word == token or (len(word) >= 4 and len(token) >= 4 and word[:4] == token[:4])
            for word in _specialty_tokens(normalized)
            for token in name_tokens
        ):
            matches.append(candidate)
    return matches[0] if len(matches) == 1 else None


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
    seen_doctor_ids = set()
    for doctor in doctors:
        if doctor.id in seen_doctor_ids:
            continue
        seen_doctor_ids.add(doctor.id)
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
    if pending_booking:
        chosen = _select_pending_candidate(pending_booking, normalized)
        if chosen is None and _is_affirmative(normalized):
            if len(_pending_candidates(pending_booking)) > 1:
                return 'Qaysi doktorni tanlaysiz? Ismini yoki 1, 2, 3 deb ayting.'
            chosen = _pending_candidates(pending_booking)[0]
        if chosen:
            return f"{chosen['doctor_name']} doktor qabuli uchun yozilish oynasini ochyapman."
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
        clinic_order = list(dict.fromkeys(item['clinic_id'] for item in candidates))
        candidates = sorted(candidates, key=lambda item: clinic_order.index(item['clinic_id']))
        cache.set(
            pending_booking_key,
            {**candidates[0], 'candidates': candidates},
            SPECIALTY_BOOKING_TTL_SECONDS,
        )
        if len(candidates) == 1:
            specialist = candidates[0]
            return (
                f"{specialist['specialty_name']} yo‘nalishida mos doktor topdim: {specialist['doctor_name']}, "
                f"{specialist['clinic_name']} klinikasida. Manzil: {specialist['clinic_address']}. "
                f"Telefon: {specialist['clinic_phone']}. Ish vaqti: {specialist['doctor_hours']}. "
                'Shu doktorga qabulga yozilish oynasini ochaymi? Ha yoki yo‘q deb javob bering.'
            )
        specialty_label = _requested_specialty_label(normalized)
        parts = [f'{specialty_label} yo‘nalishida {len(candidates)} ta doktor topdim.']
        for clinic_id in clinic_order:
            group = [
                (index, item) for index, item in enumerate(candidates) if item['clinic_id'] == clinic_id
            ]
            doctors_text = '; '.join(
                f"{ORDINAL_WORDS[index][0]}: {item['doctor_name']}, ish vaqti {item['doctor_hours']}"
                for index, item in group
            )
            parts.append(f"{group[0][1]['clinic_name']} klinikasida: {doctors_text}.")
        parts.append('Qaysi doktorga yozilay? Ismini yoki 1, 2, 3 deb ayting.')
        return ' '.join(parts)

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


def handle_command(*, user, message, internet_search_enabled=False):
    normalized = ' '.join(_normalize_command(message).split())
    youtube_queue = (
        cache.get(_youtube_queue_key(user))
        if getattr(user, 'role', '') == 'patient' and getattr(user, 'pk', None) is not None
        else None
    )
    if youtube_queue and youtube_queue.get('videos') and _is_liza_wake_request(normalized):
        return 'Ha, eshitaman. Buyruqni ayting.'
    if normalized in {'salom', 'assalomu alaykum', 'liza', 'yordam'} or 'nima qila olasan' in normalized:
        return (
            "Men G-MED yordamchisiman. Qabulingiz, navbat raqamingiz, klinika va doktor ish vaqti "
            "hamda profilingiz bo‘yicha yordam beraman. Internetdan qidirish, ob-havo va YouTube bo‘yicha ham yordam beraman."
        )

    youtube_control = _youtube_control_intent(normalized)
    music_target = any(term in normalized for term in ('qo\'shiq', 'qoshiq', 'musiqa', 'muzika', 'youtube', 'yutub', 'yutob'))
    is_patient = getattr(user, 'role', '') == 'patient'
    if is_patient and _is_stop_listening_request(normalized) and not music_target:
        return 'Liza suhbatni to‘xtatdi. Qayta ishlatish uchun Liza tugmasini bosing.'
    if youtube_control:
        return _handle_youtube_control(user=user, control=youtube_control)

    external_reply = _internet_reply(
        normalized,
        user=user,
        internet_search_enabled=internet_search_enabled,
    )
    if external_reply is not None:
        return external_reply

    command_action = get_command_action(user=user, message=message)
    if command_action == 'open_profile':
        return 'Profilim bo‘limini ochyapman.'

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