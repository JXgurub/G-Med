from __future__ import annotations

import re

from django.core.management.base import BaseCommand
from django.db import transaction


def _norm_passport(value: str | None) -> str:
    if not value:
        return ''
    value = str(value).strip().upper()
    return re.sub(r"\s+", "", value)


class Command(BaseCommand):
    help = "Deduplicate Patient rows by normalized national_id (ignore whitespace/case). Dry-run by default."

    def add_arguments(self, parser):
        parser.add_argument(
            '--apply',
            action='store_true',
            help='Apply changes (re-point relations and delete duplicates). If omitted, prints what would happen.',
        )

    def handle(self, *args, **options):
        apply_changes = options.get('apply', False)

        from apps.patients.models import Patient

        patients = list(Patient.objects.select_related('user').all())
        groups: dict[str, list[Patient]] = {}
        for patient in patients:
            key = _norm_passport(patient.national_id)
            if not key:
                continue
            groups.setdefault(key, []).append(patient)

        duplicate_groups = {k: v for k, v in groups.items() if len(v) > 1}
        if not duplicate_groups:
            self.stdout.write(self.style.SUCCESS('No duplicate passport IDs found.'))
            return

        self.stdout.write(f"Found {len(duplicate_groups)} duplicate passport group(s).")
        if not apply_changes:
            self.stdout.write(self.style.WARNING('DRY-RUN mode (use --apply to make changes).'))

        for passport_norm, group in duplicate_groups.items():
            # Choose keeper: prefer the one with most related objects; fallback oldest created.
            keeper = self._pick_keeper(group)
            others = [p for p in group if p.id != keeper.id]

            self.stdout.write("\n" + ('-' * 72))
            self.stdout.write(f"PASSPORT: {passport_norm}")
            self.stdout.write(f"KEEP   : {keeper.id} | user={getattr(keeper.user, 'email', None)} | national_id={keeper.national_id}")
            for dup in others:
                self.stdout.write(f"DUP    : {dup.id} | user={getattr(dup.user, 'email', None)} | national_id={dup.national_id}")

            if not apply_changes:
                continue

            with transaction.atomic():
                # First clear duplicate national_id values to avoid UNIQUE constraint conflicts
                # when normalizing the keeper.
                for dup in others:
                    if dup.national_id:
                        dup.national_id = None
                        dup.save(update_fields=['national_id'])

                for dup in others:
                    self._merge_patient_into(dup, keeper)

        if apply_changes:
            self.stdout.write(self.style.SUCCESS('Deduplication completed.'))

    def _pick_keeper(self, patients):
        def score(p):
            # Count related objects generically; prefer more related (more likely "real" record)
            related_total = 0
            for rel in p._meta.related_objects:
                if not rel.auto_created:
                    continue
                accessor = rel.get_accessor_name()
                if accessor.endswith('+'):
                    continue
                try:
                    manager = getattr(p, accessor)
                    # Some accessors are single objects (OneToOne), others are managers (FK).
                    if hasattr(manager, 'all'):
                        related_total += manager.all().count()
                    else:
                        related_total += 1 if manager is not None else 0
                except Exception:
                    continue
            return (related_total, getattr(p, 'created_at', None) or 0)

        # Max score -> keeper. If tie, earliest created_at.
        best = None
        best_score = None
        for p in patients:
            s = score(p)
            if best is None:
                best, best_score = p, s
                continue
            if s[0] > best_score[0]:
                best, best_score = p, s
            elif s[0] == best_score[0]:
                # Prefer older record
                if getattr(p, 'created_at', None) and getattr(best, 'created_at', None):
                    if p.created_at < best.created_at:
                        best, best_score = p, s
        return best

    def _merge_patient_into(self, dup, keeper):
        # Merge M2M clinics
        try:
            keeper.clinics.add(*dup.clinics.all())
        except Exception:
            pass

        # Special-case: PatientDoctorRating often has a UNIQUE(patient, doctor) constraint.
        # If both dup and keeper have ratings for the same doctor, keep keeper's and delete dup's.
        try:
            if hasattr(dup, 'doctor_ratings') and hasattr(keeper, 'doctor_ratings'):
                for rating in dup.doctor_ratings.all():
                    try:
                        doctor_id = getattr(rating, 'doctor_id', None)
                        if doctor_id and keeper.doctor_ratings.filter(doctor_id=doctor_id).exists():
                            rating.delete()
                        else:
                            rating.patient = keeper
                            rating.save(update_fields=['patient'])
                    except Exception:
                        continue
        except Exception:
            pass

        # Re-point all FK relations from dup -> keeper
        for rel in dup._meta.related_objects:
            if not rel.auto_created:
                continue
            accessor = rel.get_accessor_name()
            if accessor.endswith('+'):
                continue
            # Skip the reverse relation from CustomUser.patient (OneToOne)
            if rel.one_to_one:
                continue
            if not rel.one_to_many:
                continue

            # Already handled above with per-row logic.
            if rel.related_model.__name__ == 'PatientDoctorRating':
                continue

            try:
                manager = getattr(dup, accessor)
                if not hasattr(manager, 'all'):
                    continue
                related_qs = manager.all()
                if related_qs.exists():
                    related_qs.update(**{rel.field.name: keeper})
            except Exception:
                continue

        dup_user = getattr(dup, 'user', None)

        # Delete duplicate patient (and its user if present)
        try:
            dup.delete()
        except Exception:
            # If delete fails (e.g. protected relations), make it non-duplicate and inactive.
            try:
                dup.is_active = False
                dup.national_id = f"DUP-{dup.id}"
                dup.save(update_fields=['is_active', 'national_id'])
            except Exception:
                pass

        if dup_user and getattr(dup_user, 'id', None) and getattr(keeper, 'user_id', None) != dup_user.id:
            try:
                dup_user.delete()
            except Exception:
                try:
                    dup_user.is_active = False
                    dup_user.save(update_fields=['is_active'])
                except Exception:
                    pass
