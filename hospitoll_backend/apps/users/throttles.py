from rest_framework.throttling import ScopedRateThrottle


class LoginScopedRateThrottle(ScopedRateThrottle):
    """Throttle login attempts by IP+email to avoid NAT-wide blocking."""

    scope = 'auth'

    def get_cache_key(self, request, view):
        if request.method == 'OPTIONS':
            return None

        ident = self.get_ident(request)

        email = ''
        try:
            email = str(request.data.get('email') or '').strip().lower()
        except Exception:
            email = ''

        # Keep endpoint in key so different auth endpoints do not share counters.
        endpoint = str(request.path or '').strip().lower()
        composed_ident = f"{ident}:{email}:{endpoint}" if email else f"{ident}:{endpoint}"

        return self.cache_format % {'scope': self.scope, 'ident': composed_ident}


class _BasePasswordResetScopedRateThrottle(ScopedRateThrottle):
    """Throttle password reset attempts by IP+identity to reduce false positives."""

    identity_fields = ()

    def get_cache_key(self, request, view):
        if request.method == 'OPTIONS':
            return None

        ident = self.get_ident(request)
        endpoint = str(request.path or '').strip().lower()

        identity_parts = []
        try:
            for field in self.identity_fields:
                value = request.data.get(field)
                if value is None:
                    continue

                value_str = str(value).strip().lower()
                if not value_str:
                    continue

                identity_parts.append(f"{field}:{value_str}")
        except Exception:
            identity_parts = []

        identity = '|'.join(identity_parts)
        composed_ident = f"{ident}:{endpoint}:{identity}" if identity else f"{ident}:{endpoint}"
        return self.cache_format % {'scope': self.scope, 'ident': composed_ident}


class PasswordResetRequestThrottle(_BasePasswordResetScopedRateThrottle):
    scope = 'password_reset_request'
    identity_fields = ('passport_id', 'phone_number', 'birth_date', 'pinfl')


class PasswordResetVerifyThrottle(_BasePasswordResetScopedRateThrottle):
    scope = 'password_reset_verify'
    identity_fields = ('passport_id', 'phone_number', 'birth_date', 'pinfl')


class PasswordResetConfirmThrottle(_BasePasswordResetScopedRateThrottle):
    scope = 'password_reset_confirm'
    identity_fields = ('token',)
