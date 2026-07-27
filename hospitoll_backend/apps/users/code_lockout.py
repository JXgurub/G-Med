from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import CodeVerificationLockState


LOCK_RULES = {
    1: {'max_attempts': 5, 'block_seconds': 5 * 60},
    2: {'max_attempts': 3, 'block_seconds': 10 * 60},
    3: {'max_attempts': 2, 'block_seconds': 60 * 60},
}
MAX_STAGE = 3
NEW_ADMIN_BOT_URL = 'https://t.me/JXgroup_bot'


def _admin_telegram_link() -> str:
    return NEW_ADMIN_BOT_URL


def _seconds_left(dt_value) -> int:
    if not dt_value:
        return 0
    delta = int((dt_value - timezone.now()).total_seconds())
    return delta if delta > 0 else 0


def _rule(stage: int) -> dict:
    safe_stage = min(max(int(stage or 1), 1), MAX_STAGE)
    return LOCK_RULES[safe_stage]


def _blocked_payload(*, state: CodeVerificationLockState, detail: str) -> dict:
    remaining = _seconds_left(state.blocked_until)
    rule = _rule(state.lock_stage)

    payload = {
        'detail': detail,
        'error_code': 'code_locked',
        'blocked_seconds': remaining,
        'attempts_left': 0,
        'attempts_limit': rule['max_attempts'],
        'lock_stage': int(state.lock_stage),
        'support_required': int(state.lock_stage) >= MAX_STAGE,
    }

    if payload['support_required']:
        payload['admin_telegram'] = _admin_telegram_link()

    return payload


def _get_or_create_state(user, channel: str) -> CodeVerificationLockState:
    state, _ = CodeVerificationLockState.objects.get_or_create(
        user=user,
        channel=channel,
        defaults={'lock_stage': 1, 'failed_attempts': 0},
    )
    return state


def ensure_not_blocked(user, channel: str):
    with transaction.atomic():
        state = _get_or_create_state(user, channel)
        now = timezone.now()

        if state.blocked_until and state.blocked_until > now:
            detail = "Kodni kiritish vaqtincha bloklangan."
            if int(state.lock_stage) >= MAX_STAGE:
                detail = "Kodni kiritish 1 soatga bloklandi. Endi adminga murojaat qiling."
            return _blocked_payload(state=state, detail=detail)

        if state.blocked_until and state.blocked_until <= now:
            state.blocked_until = None
            state.failed_attempts = 0
            # Escalate to the next stage only after the current block window has elapsed.
            if int(state.lock_stage or 1) < MAX_STAGE:
                state.lock_stage = int(state.lock_stage or 1) + 1
                state.save(update_fields=['blocked_until', 'failed_attempts', 'lock_stage', 'updated_at'])
            else:
                state.save(update_fields=['blocked_until', 'failed_attempts', 'updated_at'])

    return None


def register_failed_code_attempt(user, channel: str) -> dict:
    with transaction.atomic():
        state = _get_or_create_state(user, channel)
        now = timezone.now()

        if state.blocked_until and state.blocked_until > now:
            detail = "Kodni kiritish vaqtincha bloklangan."
            if int(state.lock_stage) >= MAX_STAGE:
                detail = "Kodni kiritish 1 soatga bloklandi. Endi adminga murojaat qiling."
            return _blocked_payload(state=state, detail=detail)

        if state.blocked_until and state.blocked_until <= now:
            state.blocked_until = None
            state.failed_attempts = 0

        current_stage = min(max(int(state.lock_stage or 1), 1), MAX_STAGE)
        rule = _rule(current_stage)

        state.failed_attempts = int(state.failed_attempts or 0) + 1

        if state.failed_attempts >= rule['max_attempts']:
            block_seconds = rule['block_seconds']
            state.blocked_until = now + timedelta(seconds=block_seconds)
            state.failed_attempts = 0
            state.save(update_fields=['failed_attempts', 'blocked_until', 'lock_stage', 'updated_at'])

            if current_stage >= MAX_STAGE:
                payload = _blocked_payload(
                    state=state,
                    detail="Kod 2 marta noto'g'ri kiritildi. 1 soatga bloklandi. Endi adminga murojaat qiling.",
                )
            elif current_stage == 2:
                payload = _blocked_payload(
                    state=state,
                    detail="Kod 3 marta noto'g'ri kiritildi. 10 daqiqaga bloklandi.",
                )
            else:
                payload = _blocked_payload(
                    state=state,
                    detail="Kod 5 marta noto'g'ri kiritildi. 5 daqiqaga bloklandi.",
                )

            payload['error_code'] = 'code_locked'
            return payload

        attempts_left = rule['max_attempts'] - state.failed_attempts
        state.save(update_fields=['failed_attempts', 'blocked_until', 'lock_stage', 'updated_at'])

        return {
            'detail': "Kod noto'g'ri.",
            'error_code': 'code_invalid',
            'attempts_left': attempts_left,
            'attempts_limit': rule['max_attempts'],
            'lock_stage': current_stage,
            'blocked_seconds': 0,
            'support_required': False,
        }


def clear_lock_state(user, channel: str):
    CodeVerificationLockState.objects.filter(user=user, channel=channel).update(
        failed_attempts=0,
        blocked_until=None,
        lock_stage=1,
    )
