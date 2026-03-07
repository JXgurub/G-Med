# Doktorlarni Bir Vaqtda Yangilash Muammosi - Yechim

## Muammo
Ikkita brauzer tabda bir xil yoki turli doktorlarni ochib, yangilaganingizda ma'lumotlar bir-biriga qo'shilib ketgan yoki bir tab'dagi o'zgarishlar ikkinchi tab tomonidan bekor qilingan.

Bu **Race Condition** (bir vaqtda ishlash muammosi) deb ataladi:
1. Tab 1 doktor ma'lumotlarini yuklaydi (masalan, kl 10:00)
2. Tab 2 ham o'sha doktor ma'lumotlarini yuklaydi (10:00)
3. Tab 1 doktorni yangilaydi (10:01) - muvaffaqiyatli saqlandi
4. Tab 2 doktorni yangilaydi (10:02) - Tab 1 o'zgarishlarini bekor qiladi!

## Yechim: Optimistic Locking (Versiya Nazorati)

### Backend O'zgarishlar

#### 1. DoctorSerializer (`apps/doctors/serializers.py`)
`version` maydonini qo'shdik:
```python
class DoctorSerializer(serializers.ModelSerializer):
    # ... boshqa maydonlar ...
    version = serializers.DateTimeField(source='updated_at', read_only=False, required=False)
    
    class Meta:
        model = Doctor
        fields = [
            # ... boshqa maydonlar ...
            'version',  # Yangi maydon
        ]
```

#### 2. DoctorViewSet (`apps/doctors/views.py`)
Update metodini override qildik versiya tekshirish uchun:
```python
def update(self, request, *args, **kwargs):
    """Update doctor with optimistic locking to prevent concurrent updates"""
    partial = kwargs.pop('partial', False)
    instance = self.get_object()
    
    # Versiya tekshirish
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
    self.perform_update(serializer)
    
    return Response(serializer.data)
```

### Frontend O'zgarishlar

#### 1. ClinicContext (`src/context/ClinicContext.jsx`)

**mapDoctor funksiyasiga version qo'shdik:**
```javascript
const mapDoctor = (doctor) => {
  return {
    // ... boshqa maydonlar ...
    version: doctor.updated_at || doctor.version,  // Yangi maydon
    raw: doctor
  }
}
```

**toggleDoctorStatus versiya bilan:**
```javascript
const toggleDoctorStatus = async (clinicId, doctorId) => {
  try {
    const doctor = clinicDoctors.find((d) => d.id === doctorId)
    
    const updateData = { 
      is_active: !currentIsActive,
      version: doctor.version  // Versiyani yuborish
    }
    
    try {
      const updateResponse = await doctorsApi.update(doctorId, updateData)
      await fetchClinicDoctors(clinicId)
      return { success: true, newStatus: nextIsActive }
    } catch (error) {
      // 409 Conflict xatosini ushlab olish
      if (error.response?.status === 409) {
        await fetchClinicDoctors(clinicId)
        throw new Error('Ma\'lumot boshqa foydalanuvchi tomonidan o\'zgartirilgan. Iltimos, qaytadan urinib ko\'ring.')
      }
      throw error
    }
  } catch (error) {
    throw error
  }
}
```

**updateDoctorSchedule versiya bilan:**
```javascript
const updateDoctorSchedule = async (clinicId, doctorId, scheduleData) => {
  try {
    const doctor = clinicDoctors.find((d) => d.id === doctorId)
    
    const payload = {
      available_from: scheduleData.availableFrom,
      available_until: scheduleData.availableUntil,
      working_days: scheduleData.workingDays,
      version: doctor?.version  // Versiyani yuborish
    }
    
    try {
      const updated = await doctorsApi.update(doctorId, payload)
      await fetchClinicDoctors(clinicId)
      return updated
    } catch (error) {
      // 409 Conflict xatosini ushlab olish
      if (error.response?.status === 409) {
        await fetchClinicDoctors(clinicId)
        throw new Error('Ma\'lumot boshqa foydalanuvchi tomonidan o\'zgartirilgan. Iltimos, sahifani yangilang va qaytadan urinib ko\'ring.')
      }
      throw error
    }
  } catch (error) {
    throw error
  }
}
```

## Qanday Ishlaydi?

1. **Doktor ma'lumotlarini yuklash:**
   - Backend doktor ma'lumotlarini `updated_at` (oxirgi yangilanish vaqti) bilan birga yuboradi
   - Frontend bu versiyani saqlaydi

2. **Doktorni yangilash:**
   - Frontend doktorni yangilashda versiyani ham yuboradi
   - Backend joriy versiyani tekshiradi
   - Agar versiya mos kelmasa → 409 Conflict xatosi qaytaradi
   - Frontend xatoni ushlab, yangi ma'lumotlarni yuklaydi va foydalanuvchiga xabar beradi

3. **Foydalanuvchi tajribasi:**
   - Agar ikki tab bir vaqtda yangilasa:
     - Birinchi yangilanish muvaffaqiyatli
     - Ikkinchi yangilanish rad etiladi
     - Foydalanuvchi xabar oladi: "Ma'lumot boshqa foydalanuvchi tomonidan o'zgartirilgan. Iltimos, sahifani yangilang."
     - Sahifani yangilash orqali eng yangi ma'lumotlarni oladi

## To'g'ri Ishlashi Uchun

1. **Serverda:**
   ```bash
   cd C:\Hospitoll\hospitoll_backend
   python manage.py runserver
   ```

2. **Frontendda:**
   ```bash
   cd C:\Hospitoll\hospitoll_frontend
   npm run dev
   ```

3. **Test qilish:**
   - Ikkita brauzer tab ochib, bir xil doktorni tahrirlang
   - Birinchisini saqlang ✅
   - Ikkinchisini saqlang → Xato chiqadi ⚠️
   - Sahifani yangilang → Eng yangi ma'lumotlar ko'rsatiladi ✅

## Afzalliklari

✅ Ma'lumotlar bir-biriga qo'shilmaydi  
✅ Foydalanuvchi xabardor bo'ladi  
✅ Minimal kod o'zgarishlari  
✅ Boshqa modellar uchun ham ishlatish mumkin  

## Kelajakda Yaxshilash

- WebSocket bilan real-time ma'lumot yangilanishi
- Automatic refresh qilish versiya conflict bo'lganda
- Boshqa modellar (Patient, Clinic, etc.) uchun ham qo'llash
