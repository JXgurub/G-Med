#!/usr/bin/env python
"""
Run inside the backend container:
  python manage.py shell < /tmp/clear_medicine_base.py
Clears the shared medicine catalogue and all linked inventory rows.
"""
import sys, os
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from apps.pharmacies.models import Medicine, PharmacyMarchandise

mc = Medicine.objects.count()
ic = PharmacyMarchandise.objects.count()
Medicine.objects.all().delete()
mc_after = Medicine.objects.count()
ic_after = PharmacyMarchandise.objects.count()
print(f"medicines_deleted={mc}")
print(f"inventory_deleted={ic}")
print(f"remaining_medicines={mc_after}")
print(f"remaining_inventory={ic_after}")
