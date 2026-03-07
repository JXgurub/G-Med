import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

os.chdir(PROJECT_ROOT)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

import django  # noqa: E402

django.setup()

from django.apps import apps  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.db import transaction  # noqa: E402

from apps.clinics.models import Clinic  # noqa: E402
from apps.pharmacies.models import Pharmacy  # noqa: E402


User = get_user_model()


def main() -> None:
    keep_user_ids = set(User.objects.filter(is_superuser=True).values_list('id', flat=True))
    keep_user_ids.update(Clinic.objects.exclude(owner_id__isnull=True).values_list('owner_id', flat=True))
    keep_user_ids.update(Pharmacy.objects.exclude(owner_id__isnull=True).values_list('owner_id', flat=True))

    cleanup_apps = [
        'analytics',
        'doctors',
        'medical',
        'patients',
        'payments',
        'search',
        'site_settings',
        'subscriptions',
        'sessions',
    ]

    summary: list[tuple[str, int]] = []

    with transaction.atomic():
        for app_label in cleanup_apps:
            try:
                app_config = apps.get_app_config(app_label)
            except LookupError:
                continue

            for model in reversed(list(app_config.get_models())):
                if app_label == 'doctors' and model.__name__ == 'Specialization':
                    continue
                deleted_count, _ = model.objects.all().delete()
                if deleted_count:
                    summary.append((f'{app_label}.{model.__name__}', deleted_count))

        for model in reversed(list(apps.get_app_config('users').get_models())):
            if model is User:
                deleted_count, _ = User.objects.exclude(id__in=keep_user_ids).delete()
                if deleted_count:
                    summary.append(('users.CustomUser(excluding_kept)', deleted_count))
            else:
                deleted_count, _ = model.objects.all().delete()
                if deleted_count:
                    summary.append((f'users.{model.__name__}', deleted_count))

    print('KEPT_USERS', len(keep_user_ids))
    print('DELETION_SUMMARY_START')
    for model_label, count in summary:
        print(model_label, count)
    print('DELETION_SUMMARY_END')


if __name__ == '__main__':
    main()
