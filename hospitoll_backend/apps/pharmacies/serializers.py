from rest_framework import serializers
from django.utils.text import slugify
from django.db import transaction

from apps.users.models import CustomUser
from .models import Pharmacy, Medicine, PharmacyMarchandise


MEDICINE_COUNTRY_OPTIONS = {
    "Rossiya",
    "O'zbekiston",
    'Vetnam',
    'Boshqa',
}


def normalize_medicine_country(value):
    country = str(value or '').strip()
    normalized = country.lower()
    if not normalized:
        return 'Boshqa'

    aliases = {
        "o'zbekiston": "O'zbekiston",
        'ozbekiston': "O'zbekiston",
        'uzbekistan': "O'zbekiston",
        'rossiya': 'Rossiya',
        'rassiya': 'Rossiya',
        'russia': 'Rossiya',
        'vetnam': 'Vetnam',
        'vietnam': 'Vetnam',
        'boshqa': 'Boshqa',
        'other': 'Boshqa',
    }

    if normalized in aliases:
        return aliases[normalized]
    if country in MEDICINE_COUNTRY_OPTIONS:
        return country
    return 'Boshqa'


class PharmacySerializer(serializers.ModelSerializer):
    owner_email = serializers.EmailField(source='owner.email', read_only=True)
    owner_name = serializers.SerializerMethodField()
    is_active_status = serializers.BooleanField(read_only=True)
    medicines = serializers.SerializerMethodField()
    subscription = serializers.SerializerMethodField()

    class Meta:
        model = Pharmacy
        fields = [
            'id',
            'owner',
            'owner_email',
            'owner_name',
            'owner_passport_id',
            'name',
            'slug',
            'description',
            'registration_number',
            'license_document',
            'address',
            'phone_number',
            'email',
            'website',
            'logo',
            'status',
            'is_verified',
            'is_blocked',
            'rating',
            'total_ratings',
            'working_hours',
            'established_date',
            'amount',
            'payment_date',
            'created_at',
            'updated_at',
            'is_active_status',
            'medicines',
            'subscription',
        ]

    def get_owner_name(self, obj):
        return obj.owner.get_full_name() if obj.owner else ''

    def get_medicines(self, obj):
        medicines = obj.medicines.select_related('medicine').filter(is_available=True)
        return PharmacyMarchandiseListSerializer(medicines, many=True).data
    
    def get_subscription(self, obj):
        """Include subscription status for pharmacy owner"""
        if hasattr(obj, 'subscription'):
            subscription = obj.subscription
            # Auto-update expired status
            subscription.auto_deactivate_if_expired()
            subscription.refresh_from_db()
            return {
                'status': subscription.status,
                'is_expired': subscription.is_expired(),
                'end_date': subscription.end_date.isoformat() if subscription.end_date else None,
                'days_remaining': subscription.days_remaining(),
                'start_date': subscription.start_date.isoformat() if subscription.start_date else None,
            }
        return None


class PharmacyMarchandiseListSerializer(serializers.ModelSerializer):
    """Serializer for medicines list in pharmacy detail"""
    name = serializers.CharField(source='medicine.name', read_only=True)
    category = serializers.CharField(source='medicine.category', read_only=True)
    strength = serializers.CharField(source='medicine.strength', read_only=True)
    dosage_form = serializers.CharField(source='medicine.dosage_form', read_only=True)
    country_of_origin = serializers.CharField(source='medicine.country_of_origin', read_only=True)
    expiry_date = serializers.DateField(read_only=True)
    stock = serializers.IntegerField(source='quantity_in_stock', read_only=True)
    price = serializers.DecimalField(max_digits=10, decimal_places=2, source='unit_price', read_only=True)

    class Meta:
        model = PharmacyMarchandise
        fields = ['id', 'name', 'category', 'strength', 'dosage_form', 'country_of_origin', 'expiry_date', 'stock', 'price']


class PharmacyCreateSerializer(serializers.ModelSerializer):
    owner_email = serializers.EmailField(write_only=True)
    owner_password = serializers.CharField(write_only=True)
    owner_first_name = serializers.CharField(write_only=True)
    owner_last_name = serializers.CharField(write_only=True)
    owner_passport_id = serializers.CharField(write_only=True, required=False, allow_blank=True)
    owner_phone_number = serializers.CharField(write_only=True, required=False, allow_blank=True)
    slug = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = Pharmacy
        fields = [
            'id',
            'owner_email',
            'owner_password',
            'owner_first_name',
            'owner_last_name',
            'owner_passport_id',
            'owner_phone_number',
            'name',
            'slug',
            'description',
            'registration_number',
            'address',
            'phone_number',
            'email',
            'website',
            'working_hours',
            'status',
            'is_verified',
            'is_blocked',
            'established_date',
        ]

    def validate_owner_email(self, value):
        if CustomUser.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("Bu email allaqachon ro'yxatdan o'tgan.")
        return value

    def validate_slug(self, value):
        if value and Pharmacy.objects.filter(slug=value).exists():
            raise serializers.ValidationError("Bu slug allaqachon mavjud.")
        return value

    @transaction.atomic
    def create(self, validated_data):
        owner_email = validated_data.pop('owner_email')
        owner_password = validated_data.pop('owner_password')
        owner_first_name = validated_data.pop('owner_first_name')
        owner_last_name = validated_data.pop('owner_last_name')
        owner_passport_id = str(validated_data.pop('owner_passport_id', '') or '').strip().upper().replace(' ', '')
        owner_phone_number = validated_data.pop('owner_phone_number', '')

        slug = validated_data.get('slug')
        if not slug:
            validated_data['slug'] = slugify(validated_data.get('name', 'pharmacy'))

        owner = CustomUser.objects.create_user(
            username=owner_email,
            email=owner_email,
            password=owner_password,
            first_name=owner_first_name,
            last_name=owner_last_name,
            phone_number=owner_phone_number,
            role='pharmacy'
        )

        pharmacy = Pharmacy.objects.create(owner=owner, owner_passport_id=owner_passport_id, **validated_data)
        return pharmacy


class MedicineSerializer(serializers.ModelSerializer):
    class Meta:
        model = Medicine
        fields = [
            'id',
            'name',
            'generic_name',
            'atc_code',
            'description',
            'category',
            'dosage_form',
            'strength',
            'manufacturer',
            'country_of_origin',
            'is_prescription_required',
            'is_active',
            'created_at',
        ]

    def validate_name(self, value):
        return ' '.join(str(value or '').strip().split())

    def validate_country_of_origin(self, value):
        return normalize_medicine_country(value)

    @staticmethod
    def _normalize_identity_value(value):
        return ' '.join(str(value or '').strip().lower().split())

    def _build_identity(self, data):
        return {
            'name': self._normalize_identity_value(data.get('name')),
            'strength': self._normalize_identity_value(data.get('strength')),
            'dosage_form': self._normalize_identity_value(data.get('dosage_form')),
            'category': self._normalize_identity_value(data.get('category') or 'Boshqa'),
            'generic_name': self._normalize_identity_value(data.get('generic_name')),
            'atc_code': self._normalize_identity_value(data.get('atc_code')),
            'manufacturer': self._normalize_identity_value(data.get('manufacturer')),
            'country_of_origin': self._normalize_identity_value(data.get('country_of_origin')),
            'description': self._normalize_identity_value(data.get('description')),
        }

    def _find_existing_by_identity(self, identity):
        if not identity['name']:
            return None

        candidates = Medicine.objects.filter(
            name__iexact=identity['name'],
            strength__iexact=identity['strength'],
            dosage_form__iexact=identity['dosage_form'],
            category__iexact=identity['category'],
        )

        for candidate in candidates:
            candidate_identity = self._build_identity({
                'name': candidate.name,
                'strength': candidate.strength,
                'dosage_form': candidate.dosage_form,
                'category': candidate.category,
                'generic_name': candidate.generic_name,
                'atc_code': candidate.atc_code,
                'manufacturer': candidate.manufacturer,
                'country_of_origin': candidate.country_of_origin,
                'description': candidate.description,
            })
            if candidate_identity == identity:
                return candidate

        return None

    def create(self, validated_data):
        validated_data['name'] = ' '.join(str(validated_data.get('name') or '').strip().split())
        validated_data['description'] = str(validated_data.get('description') or '').strip()
        validated_data['category'] = str(validated_data.get('category') or '').strip() or 'Boshqa'
        validated_data['strength'] = str(validated_data.get('strength') or '').strip()
        validated_data['dosage_form'] = str(validated_data.get('dosage_form') or '').strip()
        validated_data['generic_name'] = str(validated_data.get('generic_name') or '').strip()
        validated_data['atc_code'] = str(validated_data.get('atc_code') or '').strip()
        validated_data['manufacturer'] = str(validated_data.get('manufacturer') or '').strip()
        validated_data['country_of_origin'] = normalize_medicine_country(validated_data.get('country_of_origin'))

        identity = self._build_identity(validated_data)
        existing = self._find_existing_by_identity(identity)
        if existing:
            return existing

        return super().create(validated_data)


class PharmacyMarchandiseSerializer(serializers.ModelSerializer):
    medicine_name = serializers.CharField(source='medicine.name', read_only=True)
    medicine_category = serializers.CharField(source='medicine.category', read_only=True)
    medicine_strength = serializers.CharField(source='medicine.strength', read_only=True)
    medicine_dosage_form = serializers.CharField(source='medicine.dosage_form', read_only=True)
    medicine_country_of_origin = serializers.CharField(source='medicine.country_of_origin', read_only=True)

    class Meta:
        model = PharmacyMarchandise
        fields = [
            'id',
            'pharmacy',
            'medicine',
            'medicine_name',
            'medicine_category',
            'medicine_strength',
            'medicine_dosage_form',
            'medicine_country_of_origin',
            'batch_number',
            'expiry_date',
            'quantity_in_stock',
            'unit_price',
            'is_available',
            'created_at',
            'updated_at',
        ]

    def validate(self, attrs):
        pharmacy = attrs.get('pharmacy') or getattr(self.instance, 'pharmacy', None)
        medicine = attrs.get('medicine') or getattr(self.instance, 'medicine', None)

        if pharmacy and medicine:
            duplicate_qs = PharmacyMarchandise.objects.filter(
                pharmacy=pharmacy,
                medicine=medicine,
            )
            if self.instance:
                duplicate_qs = duplicate_qs.exclude(pk=self.instance.pk)
            if duplicate_qs.exists():
                raise serializers.ValidationError({
                    'medicine': 'Bu dori dorixonada allaqachon mavjud. Mavjud yozuvni tahrirlang.'
                })

        return attrs

class PharmacyUpdateSerializer(serializers.ModelSerializer):
    owner_password = serializers.CharField(write_only=True, required=False, allow_blank=True)

    class Meta:
        model = Pharmacy
        fields = [
            'id',
            'name',
            'owner_password',
            'description',
            'address',
            'phone_number',
            'email',
            'website',
            'logo',
            'working_hours',
            'status',
            'amount',
            'payment_date',
            'payment_description',
        ]
        extra_kwargs = {
            'logo': {'required': False, 'allow_null': True},
        }

    def update(self, instance, validated_data):
        owner_password = validated_data.pop('owner_password', None)
        
        # Update pharmacy fields
        instance = super().update(instance, validated_data)
        
        # Update owner password if provided
        if owner_password:
            instance.owner.set_password(owner_password)
            instance.owner.save()
        
        return instance