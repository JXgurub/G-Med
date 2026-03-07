from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from apps.clinics.models import Clinic
from apps.pharmacies.models import Pharmacy


class Command(BaseCommand):
    help = "Check and suspend clinics and pharmacies if payment expires after 30 days"

    def handle(self, *args, **options):
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        # Check Clinics
        clinics_to_suspend = Clinic.objects.filter(
            status='active',
            payment_date__isnull=False,
            payment_date__lte=thirty_days_ago
        )
        
        clinic_count = 0
        for clinic in clinics_to_suspend:
            clinic.status = 'suspended'
            clinic.save()
            clinic_count += 1
            self.stdout.write(
                self.style.WARNING(f"Suspended clinic: {clinic.name}")
            )
        
        # Check Pharmacies
        pharmacies_to_suspend = Pharmacy.objects.filter(
            status='active',
            payment_date__isnull=False,
            payment_date__lte=thirty_days_ago
        )
        
        pharmacy_count = 0
        for pharmacy in pharmacies_to_suspend:
            pharmacy.status = 'suspended'
            pharmacy.save()
            pharmacy_count += 1
            self.stdout.write(
                self.style.WARNING(f"Suspended pharmacy: {pharmacy.name}")
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                f'Successfully suspended {clinic_count} clinics and {pharmacy_count} pharmacies'
            )
        )
