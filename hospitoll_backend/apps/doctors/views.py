from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from django_filters.rest_framework import DjangoFilterBackend
from django.utils import timezone
from django.utils.timezone import localdate, localtime
from django.db import transaction
from datetime import datetime, timedelta

from .models import Doctor, Specialization, DoctorAvailability, DoctorWorkRecord, DoctorSpecialization
from apps.patients.models import PatientDoctorRating
from .serializers import (
    DoctorSerializer,
    DoctorCreateSerializer,
    DoctorSelfUpdateSerializer,
    SpecializationSerializer,
    DoctorAvailabilitySerializer,
    DoctorRatingSerializer,
    DoctorRatingCreateSerializer,
    DoctorSpecializationSerializer,
)
from core.error_logging import ErrorLogger


class DoctorViewSet(viewsets.ModelViewSet):
    queryset = Doctor.objects.select_related('user', 'clinic').prefetch_related('specializations')
    filterset_fields = ['clinic', 'is_active']

    def _build_schedule_slots_for_date(self, doctor, target_date):
        """Return expected (start_time, end_time) slot tuples for a specific date based on doctor's schedule."""
        day_key = target_date.strftime('%a')
        working_days = [d.strip() for d in (doctor.working_days or '').split(',') if d.strip()]
        if working_days and day_key not in working_days:
            return set()

        start_dt = datetime.combine(target_date, doctor.available_from)
        end_dt = datetime.combine(target_date, doctor.available_until)
        lunch_start_dt = None
        lunch_end_dt = None
        if doctor.lunch_break_start and doctor.lunch_break_end:
            lunch_start_dt = datetime.combine(target_date, doctor.lunch_break_start)
            lunch_end_dt = datetime.combine(target_date, doctor.lunch_break_end)
            if lunch_start_dt >= lunch_end_dt:
                lunch_start_dt = None
                lunch_end_dt = None

        duration_minutes = int(getattr(doctor, 'slot_minutes', 30) or 30)
        if duration_minutes not in (15, 20, 30):
            duration_minutes = 30
        step = timedelta(minutes=duration_minutes)

        if start_dt >= end_dt:
            return set()

        slots = set()
        cursor = start_dt
        while cursor + step <= end_dt:
            slot_end = cursor + step
            if lunch_start_dt and lunch_end_dt and (cursor < lunch_end_dt and slot_end > lunch_start_dt):
                cursor += step
                continue
            slots.add((cursor.time(), slot_end.time()))
            cursor += step
        return slots

    def _sync_doctor_availability_slots(self, doctor, days_ahead=30):
        """Sync future availability slots with doctor's updated schedule.

        - Creates newly needed slots as 'available'.
        - Removes slots outside schedule only when they are still 'available'.
        - Keeps booked/unavailable slots untouched to avoid breaking existing flows.
        """
        today = localdate()

        for day_offset in range(0, days_ahead + 1):
            target_date = today + timedelta(days=day_offset)
            desired_slots = self._build_schedule_slots_for_date(doctor, target_date)

            existing_qs = DoctorAvailability.objects.filter(doctor=doctor, date=target_date)
            existing_pairs = {(slot.start_time, slot.end_time): slot for slot in existing_qs}

            # Add missing slots
            for start_time, end_time in desired_slots:
                if (start_time, end_time) not in existing_pairs:
                    DoctorAvailability.objects.create(
                        doctor=doctor,
                        date=target_date,
                        start_time=start_time,
                        end_time=end_time,
                        status='available'
                    )

            # Remove obsolete available slots
            for pair, slot in existing_pairs.items():
                if pair not in desired_slots and slot.status == 'available':
                    slot.delete()

    def get_permissions(self):
        if self.action in ['list', 'retrieve']:
            return [permissions.AllowAny()]
        if self.action in ['my', 'check_in', 'check_out', 'terminate']:
            return [permissions.IsAuthenticated()]
        return [permissions.IsAuthenticated()]

    def create(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return Response({'detail': 'Ruxsat berilmagan.'}, status=status.HTTP_403_FORBIDDEN)
        if not (request.user.is_clinic or request.user.is_superuser or request.user.is_staff):
            return Response({'detail': 'Faqat klinika egasi doktor qo\'sha oladi.'}, status=status.HTTP_403_FORBIDDEN)

        data = request.data.copy()
        if request.user.is_clinic:
            clinic = getattr(request.user, 'clinic', None)
            if not clinic:
                return Response({'detail': 'Klinika topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
            data['clinic'] = str(clinic.id)

        serializer = self.get_serializer(data=data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def destroy(self, request, *args, **kwargs):
        return Response(
            {'detail': 'Doktor profilini o‘chirish taqiqlangan. Faqat klinikadan bo‘shatish mumkin.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return DoctorCreateSerializer
        return DoctorSerializer
    
    def update(self, request, *args, **kwargs):
        """Update doctor with optimistic locking to prevent concurrent updates"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()

        is_owner = bool(request.user.is_clinic and instance.clinic_id and instance.clinic.owner_id == request.user.id)
        is_self_doctor = bool(request.user.is_doctor and instance.user_id == request.user.id)
        is_admin = bool(request.user.is_superuser or request.user.is_staff)

        if not (is_owner or is_self_doctor or is_admin):
            return Response({'detail': 'Ruxsat berilmagan.'}, status=status.HTTP_403_FORBIDDEN)

        if is_self_doctor and not (is_owner or is_admin):
            allowed_fields = {'bio', 'profile_image', 'version'}
            incoming_fields = set(request.data.keys())
            if incoming_fields - allowed_fields:
                return Response({'detail': 'Faqat shaxsiy profil ma\'lumotlarini o\'zgartirish mumkin.'}, status=status.HTTP_403_FORBIDDEN)

        old_schedule = {
            'available_from': instance.available_from,
            'available_until': instance.available_until,
            'lunch_break_start': instance.lunch_break_start,
            'lunch_break_end': instance.lunch_break_end,
            'working_days': instance.working_days,
            'slot_minutes': instance.slot_minutes,
        }
        
        # Check version for optimistic locking
        client_version = request.data.get('version')
        if client_version:
            from django.utils.dateparse import parse_datetime
            client_version_dt = parse_datetime(client_version)
            if client_version_dt and instance.updated_at > client_version_dt:
                return Response({
                    'detail': 'Ma\'lumot boshqa foydalanuvchi tomonidan o\'zgartirilgan. Iltimos, sahifani yangilang.',
                    'error_code': 'VERSION_CONFLICT',
                    'current_version': instance.updated_at.isoformat()
                }, status=status.HTTP_409_CONFLICT)
        
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            self.perform_update(serializer)

            updated_instance = serializer.instance
            schedule_changed = (
                old_schedule['available_from'] != updated_instance.available_from
                or old_schedule['available_until'] != updated_instance.available_until
                or old_schedule['lunch_break_start'] != updated_instance.lunch_break_start
                or old_schedule['lunch_break_end'] != updated_instance.lunch_break_end
                or old_schedule['working_days'] != updated_instance.working_days
                or old_schedule['slot_minutes'] != updated_instance.slot_minutes
            )

            if schedule_changed:
                try:
                    self._sync_doctor_availability_slots(updated_instance, days_ahead=30)
                except Exception as sync_error:
                    ErrorLogger.log_exception(sync_error, {
                        'source': 'doctor_update_schedule_sync',
                        'doctor_id': str(getattr(updated_instance, 'id', '')),
                        'user_id': str(getattr(request.user, 'id', '')),
                        'path': request.path,
                    })
        
        return Response(serializer.data)
    
    def partial_update(self, request, *args, **kwargs):
        """Partial update with optimistic locking"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    @action(detail=False, methods=['get'])
    def my(self, request):
        if not request.user.is_authenticated or not request.user.is_doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=404)
        doctor = Doctor.objects.filter(user=request.user).first()
        if not doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=404)
        
        serializer = DoctorSerializer(doctor)
        return Response(serializer.data)

    @action(detail=False, methods=['patch'], url_path='my/update', url_name='my-update')
    def my_update(self, request):
        if not request.user.is_authenticated or not request.user.is_doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=404)

        doctor = Doctor.objects.filter(user=request.user).first()
        if not doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=404)

        forbidden_fields = {
            'available_from',
            'available_until',
            'lunch_break_start',
            'lunch_break_end',
            'working_days',
        }
        if any(field in request.data for field in forbidden_fields):
            return Response(
                {'detail': 'Ish vaqti va ish kunlarini doktor o\'zi o\'zgartira olmaydi.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = DoctorSelfUpdateSerializer(doctor, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        old_slot_minutes = int(getattr(doctor, 'slot_minutes', 30) or 30)
        updated_doctor = serializer.save()

        new_slot_minutes = int(getattr(updated_doctor, 'slot_minutes', 30) or 30)
        if old_slot_minutes != new_slot_minutes:
            try:
                self._sync_doctor_availability_slots(updated_doctor, days_ahead=30)
            except Exception as sync_error:
                ErrorLogger.log_exception(sync_error, {
                    'source': 'doctor_my_update_slot_sync',
                    'doctor_id': str(getattr(updated_doctor, 'id', '')),
                    'user_id': str(getattr(request.user, 'id', '')),
                    'path': request.path,
                    'old_slot_minutes': old_slot_minutes,
                    'new_slot_minutes': new_slot_minutes,
                })

        return Response(DoctorSerializer(updated_doctor).data, status=status.HTTP_200_OK)

    @action(detail=False, methods=['post'])
    def check_in(self, request):
        """Doctor check-in endpoint"""
        if not request.user.is_authenticated or not request.user.is_doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=404)
        
        doctor = Doctor.objects.filter(user=request.user).first()
        if not doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=404)

        if not doctor.clinic_id:
            return Response({
                'detail': 'Siz hozircha klinikaga biriktirilmagansiz. Faqat profilingizni tahrirlashingiz mumkin.'
            }, status=403)
        
        # Check if doctor is suspended/inactive
        if not doctor.is_active:
            return Response({
                'detail': 'Sizning hisobingiz vaqtincha to\'xtatilgan. Klinika egasi bilan bog\'laning.'
            }, status=403)
        
        if doctor.is_checked_in:
            return Response({
                'detail': 'Siz allaqachon ishga kelgansiz.',
                'is_checked_in': True,
                'checked_in_at': doctor.checked_in_at.isoformat() if doctor.checked_in_at else None
            }, status=400)
        
        now = timezone.now()
        doctor.is_checked_in = True
        doctor.checked_in_at = now
        doctor.checked_out_at = None
        doctor.save()
        
        # Create work record for today using local timezone
        today = localdate()  # Get today's date in Asia/Tashkent timezone
        checked_in_time = localtime(now).time()  # Get time in Asia/Tashkent timezone
        work_record, created = DoctorWorkRecord.objects.get_or_create(
            doctor=doctor,
            date=today,
            defaults={'checked_in_at': checked_in_time}
        )
        if not created:
            work_record.checked_in_at = checked_in_time
            work_record.checked_out_at = None
            work_record.save()
        
        serializer = DoctorSerializer(doctor)
        return Response({
            'detail': 'Siz muvaffaqiyatli ishga keldiniz.',
            'doctor': serializer.data
        }, status=200)

    @action(detail=False, methods=['post'])
    def check_out(self, request):
        """Doctor check-out endpoint"""
        if not request.user.is_authenticated or not request.user.is_doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=404)
        
        doctor = Doctor.objects.filter(user=request.user).first()
        if not doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=404)

        if not doctor.clinic_id:
            return Response({
                'detail': 'Siz hozircha klinikaga biriktirilmagansiz. Faqat profilingizni tahrirlashingiz mumkin.'
            }, status=403)
        
        # Check if doctor is suspended/inactive
        if not doctor.is_active:
            return Response({
                'detail': 'Sizning hisobingiz vaqtincha to\'xtatilgan. Klinika egasi bilan bog\'laning.'
            }, status=403)
        
        if not doctor.is_checked_in:
            return Response({
                'detail': 'Siz ishga kelmagansiz.',
                'is_checked_in': False
            }, status=400)
        
        now = timezone.now()
        doctor.is_checked_in = False
        doctor.checked_out_at = now
        doctor.save()
        
        # Update work record for today using local timezone
        today = localdate()  # Get today's date in Asia/Tashkent timezone
        checked_out_time = localtime(now).time()  # Get time in Asia/Tashkent timezone
        work_record, created = DoctorWorkRecord.objects.get_or_create(
            doctor=doctor,
            date=today,
            defaults={'checked_out_at': checked_out_time}
        )
        if not created:
            work_record.checked_out_at = checked_out_time
            if not work_record.checked_in_at and doctor.checked_in_at:
                work_record.checked_in_at = localtime(doctor.checked_in_at).time()
            work_record.save()
        elif doctor.checked_in_at:
            work_record.checked_in_at = localtime(doctor.checked_in_at).time()
            work_record.save()
        
        serializer = DoctorSerializer(doctor)
        return Response({
            'detail': 'Siz muvaffaqiyatli ishdan chiqib kettingiz.',
            'doctor': serializer.data
        }, status=200)

    @action(detail=True, methods=['post'])
    def terminate(self, request, pk=None):
        """Clinic owner can only fire doctor from their clinic, without deleting profile."""
        if not request.user.is_authenticated or not request.user.is_clinic:
            return Response({'detail': 'Ruxsat berilmagan.'}, status=status.HTTP_403_FORBIDDEN)

        doctor = self.get_object()
        if not doctor.clinic_id or doctor.clinic.owner_id != request.user.id:
            return Response({'detail': 'Faqat o\'z klinikangiz doktorini bo\'shata olasiz.'}, status=status.HTTP_403_FORBIDDEN)

        now = timezone.now()
        doctor.is_checked_in = False
        doctor.checked_out_at = now
        doctor.is_active = False
        doctor.clinic = None
        doctor.save(update_fields=['is_checked_in', 'checked_out_at', 'is_active', 'clinic', 'updated_at'])

        return Response({'detail': 'Doktor klinikadan bo\'shatildi. Profil saqlandi.'}, status=status.HTTP_200_OK)

    @action(detail=False, methods=['get'])
    def work_stats(self, request):
        """Get doctor work statistics for current month"""
        if not request.user.is_authenticated or not request.user.is_doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=404)
        
        doctor = Doctor.objects.filter(user=request.user).first()
        if not doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=404)
        
        # Check if doctor is suspended/inactive
        if not doctor.is_active:
            return Response({
                'detail': 'Sizning hisobingiz vaqtincha to\'xtatilgan. Klinika egasi bilan bog\'laning.'
            }, status=403)
        
        # Get current month records using local timezone
        today = localdate()
        start_of_month = today.replace(day=1)
        # Get last day of month
        if today.month == 12:
            end_of_month = today.replace(day=31)
        else:
            end_of_month = (today.replace(month=today.month + 1, day=1) - timedelta(days=1))
        
        records = DoctorWorkRecord.objects.filter(
            doctor=doctor,
            date__gte=start_of_month,
            date__lte=end_of_month
        ).order_by('-date')
        
        total_hours = sum(float(r.work_duration) for r in records)
        today_record = DoctorWorkRecord.objects.filter(
            doctor=doctor,
            date=today
        ).first()
        
        today_hours = float(today_record.work_duration) if today_record else 0
        today_checked_in = today_record.checked_in_at if today_record else None
        today_checked_out = today_record.checked_out_at if today_record else None
        
        return Response({
            'current_month': f"{today.year}-{today.month:02d}",
            'total_hours_this_month': round(total_hours, 2),
            'work_days_this_month': len(records),
            'today_hours': round(today_hours, 2),
            'today_checked_in': today_checked_in,
            'today_checked_out': today_checked_out,
            'is_checked_in_now': doctor.is_checked_in,
            'checked_in_at': doctor.checked_in_at.isoformat() if doctor.checked_in_at else None,
            'recent_records': [
                {
                    'date': r.date.isoformat(),
                    'checked_in': r.checked_in_at.isoformat() if r.checked_in_at else None,
                    'checked_out': r.checked_out_at.isoformat() if r.checked_out_at else None,
                    'hours': float(r.work_duration)
                } for r in records[:7]
            ]
        }, status=200)


class SpecializationViewSet(viewsets.ModelViewSet):
    queryset = Specialization.objects.all()
    serializer_class = SpecializationSerializer
    permission_classes = [permissions.AllowAny]


class DoctorAvailabilityViewSet(viewsets.ModelViewSet):
    queryset = DoctorAvailability.objects.select_related('doctor').all()
    serializer_class = DoctorAvailabilitySerializer
    filterset_fields = ['doctor', 'date', 'status']

    @staticmethod
    def _ranges_overlap(start_a, end_a, start_b, end_b):
        return start_a < end_b and end_a > start_b

    def get_permissions(self):
        if self.action == 'available':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]

    @action(detail=False, methods=['get'])
    def available(self, request):
        doctor_id = request.query_params.get('doctor')
        date_str = request.query_params.get('date')
        requested_duration = request.query_params.get('duration_minutes')

        if not doctor_id or not date_str:
            return Response({'detail': 'doctor va date parametrlari kerak.'}, status=status.HTTP_400_BAD_REQUEST)
        # Slot duration is configured per doctor; ignore arbitrary durations to keep a consistent grid.

        target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
        doctor = Doctor.objects.select_related('clinic').filter(id=doctor_id).first()
        if not doctor:
            return Response({'detail': 'Doktor topilmadi.'}, status=status.HTTP_404_NOT_FOUND)
        if not doctor.is_active or not doctor.clinic or not doctor.clinic.is_active_status:
            return Response({'detail': 'Doktor yoki klinika faol emas.'}, status=status.HTTP_400_BAD_REQUEST)

        duration_minutes = int(getattr(doctor, 'slot_minutes', 30) or 30)
        if requested_duration is not None:
            try:
                if int(requested_duration) != duration_minutes:
                    return Response({'detail': 'duration_minutes ushbu doktor uchun ruxsat etilmagan.'}, status=status.HTTP_400_BAD_REQUEST)
            except Exception:
                return Response({'detail': 'duration_minutes noto‘g‘ri.'}, status=status.HTTP_400_BAD_REQUEST)
        if duration_minutes not in (15, 20, 30):
            duration_minutes = 30

        day_key = target_date.strftime('%a')
        working_days = [d.strip() for d in (doctor.working_days or '').split(',') if d.strip()]
        if working_days and day_key not in working_days:
            return Response([], status=status.HTTP_200_OK)

        start_dt = datetime.combine(target_date, doctor.available_from)
        end_dt = datetime.combine(target_date, doctor.available_until)
        lunch_start_dt = None
        lunch_end_dt = None
        if doctor.lunch_break_start and doctor.lunch_break_end:
            lunch_start_dt = datetime.combine(target_date, doctor.lunch_break_start)
            lunch_end_dt = datetime.combine(target_date, doctor.lunch_break_end)
            if lunch_start_dt >= lunch_end_dt:
                lunch_start_dt = None
                lunch_end_dt = None
        step = timedelta(minutes=duration_minutes)
        slot_cursor = start_dt

        if start_dt >= end_dt:
            return Response([], status=status.HTTP_200_OK)

        existing_slots = list(
            DoctorAvailability.objects.filter(
                doctor=doctor,
                date=target_date,
            ).order_by('start_time', 'created_at')
        )
        blocked_ranges = [
            (
                datetime.combine(target_date, slot.start_time),
                datetime.combine(target_date, slot.end_time),
            )
            for slot in existing_slots
            if slot.status != 'available'
        ]

        desired_slots = []
        while slot_cursor + step <= end_dt:
            slot_end_dt = slot_cursor + step
            if lunch_start_dt and lunch_end_dt and (slot_cursor < lunch_end_dt and slot_end_dt > lunch_start_dt):
                slot_cursor += step
                continue

            overlaps_blocked = any(
                self._ranges_overlap(slot_cursor, slot_end_dt, blocked_start, blocked_end)
                for blocked_start, blocked_end in blocked_ranges
            )
            if not overlaps_blocked:
                desired_slots.append((slot_cursor.time(), slot_end_dt.time()))

            slot_cursor += step

        desired_by_start = {start_time: end_time for start_time, end_time in desired_slots}

        for slot in existing_slots:
            if slot.status != 'available':
                continue

            target_end = desired_by_start.get(slot.start_time)
            if not target_end:
                slot.delete()
                continue

            if slot.end_time != target_end:
                slot.end_time = target_end
                slot.save(update_fields=['end_time'])

        existing_available_starts = set(
            DoctorAvailability.objects.filter(
                doctor=doctor,
                date=target_date,
                status='available',
            ).values_list('start_time', flat=True)
        )
        for start_time, end_time in desired_slots:
            if start_time in existing_available_starts:
                continue
            DoctorAvailability.objects.create(
                doctor=doctor,
                date=target_date,
                start_time=start_time,
                end_time=end_time,
                status='available',
            )

        slots = DoctorAvailability.objects.filter(
            doctor=doctor,
            date=target_date,
            status='available'
        ).order_by('start_time')

        if target_date == localdate():
            now = localtime()
            open_time = (start_dt + timedelta(minutes=10)).time()
            close_time = (end_dt - timedelta(minutes=30)).time()
            if now.time() > close_time:
                return Response([], status=status.HTTP_200_OK)
            min_time = open_time if now.time() < open_time else now.time()
            slots = slots.filter(start_time__gte=min_time, start_time__lte=close_time)

        serializer = DoctorAvailabilitySerializer(slots, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)


class DoctorRatingViewSet(viewsets.ModelViewSet):
    queryset = PatientDoctorRating.objects.select_related('doctor', 'patient').all()
    permission_classes = [permissions.IsAuthenticated]
    filter_backends = [DjangoFilterBackend, OrderingFilter]
    filterset_fields = ['doctor', 'patient', 'rating']
    ordering = ['-created_at']
    ordering_fields = ['created_at', 'rating']
    
    def get_serializer_class(self):
        if self.action in ['create', 'update', 'partial_update']:
            return DoctorRatingCreateSerializer
        return DoctorRatingSerializer
    
    def create(self, request, *args, **kwargs):
        """Create a new rating with error handling"""
        serializer = self.get_serializer(data=request.data)
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_create(serializer)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    def update(self, request, *args, **kwargs):
        """Update an existing rating"""
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        try:
            serializer.is_valid(raise_exception=True)
            self.perform_update(serializer)
            return Response(serializer.data)
        except Exception as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=False, methods=['get'])
    def by_doctor(self, request):
        """Get all ratings for a specific doctor"""
        doctor_id = request.query_params.get('doctor_id')
        if not doctor_id:
            return Response({'detail': 'doctor_id parametri kerak.'}, status=status.HTTP_400_BAD_REQUEST)
        
        ratings = PatientDoctorRating.objects.filter(doctor_id=doctor_id).order_by('-created_at')
        serializer = DoctorRatingSerializer(ratings, many=True)
        return Response(serializer.data)

