"""Umumiy (tashxis qo'ymaydigan) ogohlantirish chegaralari.

Chegaralar faqat shifokorga e'tibor qaratish uchun signal beradi va
shifokorning shaxsiy tavsiyasini almashtirmaydi.
"""
from decimal import Decimal

BLOOD_PRESSURE = 'blood_pressure'
BLOOD_GLUCOSE = 'blood_glucose'

NORMAL = 'normal'
ATTENTION = 'attention'
URGENT = 'urgent'

SEVERITY_RANK = {NORMAL: 0, ATTENTION: 1, URGENT: 2}


def _max_severity(first, second):
    return first if SEVERITY_RANK[first[0]] >= SEVERITY_RANK[second[0]] else second


def evaluate_blood_pressure(systolic, diastolic):
    result = (NORMAL, '')
    if systolic >= 180 or diastolic >= 120:
        result = _max_severity(result, (URGENT, 'Qon bosimi juda yuqori.'))
    elif systolic >= 140 or diastolic >= 90:
        result = _max_severity(result, (ATTENTION, 'Qon bosimi yuqori.'))

    if systolic < 80 or diastolic < 50:
        result = _max_severity(result, (URGENT, 'Qon bosimi juda past.'))
    elif systolic < 90 or diastolic < 60:
        result = _max_severity(result, (ATTENTION, 'Qon bosimi past.'))
    return result


def evaluate_blood_glucose(glucose_mmol, context):
    glucose = Decimal(glucose_mmol)
    if glucose < Decimal('3.0'):
        return URGENT, 'Qon qandi juda past.'
    if glucose > Decimal('16.7'):
        return URGENT, 'Qon qandi juda yuqori.'
    if glucose < Decimal('3.9'):
        return ATTENTION, 'Qon qandi past.'
    if context == 'fasting' and glucose > Decimal('7.2'):
        return ATTENTION, 'Och qoringa qon qandi yuqori.'
    if context in ('after_meal', 'random') and glucose > Decimal('10.0'):
        return ATTENTION, 'Qon qandi yuqori.'
    return NORMAL, ''


def evaluate_liver_result(value, reference_min, reference_max):
    result = Decimal(value)
    if reference_min is not None and result < Decimal(reference_min):
        return ATTENTION, 'Natija laboratoriya ko‘rsatgan me’yordan past.'
    if reference_max is not None and result > Decimal(reference_max):
        return ATTENTION, 'Natija laboratoriya ko‘rsatgan me’yordan yuqori.'
    return NORMAL, ''
