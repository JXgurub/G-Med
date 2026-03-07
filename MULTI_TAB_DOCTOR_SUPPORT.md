# Multi-Tab Doctor Login Support - Ko'p Tabda Doktorlar Kirishi

## Muammo

Bir kompyuterda ikkita doktor panelini ochib (turli brauzer tablarda), har birida turli doktorlar kirishda quyidagi muammolar yuz bergan:

1. **Ikkinchi doktor kirganda birinchisining sessiyasi o'chiriladi**
2. **Oxirgi kirgan doktorning ma'lumotlari ikkalasida ham ko'rsatiladi**
3. **Ikkala tab ham bir xil token'larni ishlatadi**

### Sabab

`localStorage` barcha brauzer tablari va oynalari uchun **umumiy storage**. Shuning uchun:

1. Tab 1: Doktor A kiradi → `localStorage` ga A ning tokenini saqlaydi
2. Tab 2: Doktor B kiradi → `localStorage` ga B ning tokenini yozadi (A niki ustiga)
3. Tab 1: Sahifani yangilaydi → B ning tokenini oladi va B sifatida ishlaydi! ❌

## Yechim: sessionStorage

`sessionStorage` har bir brauzer tab uchun **alohida storage**:
- Tab 1: Doktor A ning tokenlari → Tabni yopgunga qadar saqlanadi
- Tab 2: Doktor B ning tokenlari → Mustaqil saqlanadi
- Tab 3: Doktor C ning tokenlari → Alohida saqlanadi

## O'zgarishlar

### 1. DoctorContext.jsx

**Oldin:**
```javascript
const ACCESS_TOKEN_KEY = 'access_token'
const REFRESH_TOKEN_KEY = 'refresh_token'
const DOCTOR_CACHE_KEY = 'doctor_profile'

// Token saqlash
localStorage.setItem(ACCESS_TOKEN_KEY, data.access)
localStorage.setItem(REFRESH_TOKEN_KEY, data.refresh)

// Token olish
const token = localStorage.getItem(ACCESS_TOKEN_KEY)
```

**Keyin:**
```javascript
// Doktorlar uchun alohida key'lar
const ACCESS_TOKEN_KEY = 'doctor_access_token'
const REFRESH_TOKEN_KEY = 'doctor_refresh_token'
const DOCTOR_CACHE_KEY = 'doctor_profile'

// sessionStorage ishlatish (har tab uchun alohida)
sessionStorage.setItem(ACCESS_TOKEN_KEY, data.access)
sessionStorage.setItem(REFRESH_TOKEN_KEY, data.refresh)

// Token olish
const token = sessionStorage.getItem(ACCESS_TOKEN_KEY)
```

**Barcha o'zgarishlar:**
- ✅ `localStorage` → `sessionStorage` (8 joyda)
- ✅ Token key'lari o'zgartirildi (`doctor_` prefiks qo'shildi)
- ✅ Barcha get/set/remove operatsiyalari yangilandi

### 2. api.js (API Service)

API service endi **dinamik storage** ishlatadi:

```javascript
// Storage tanlash: doktor → sessionStorage, qolganlari → localStorage
const getStorage = () => {
  const userRole = sessionStorage.getItem('user_role') || localStorage.getItem('user_role')
  return userRole === 'doctor' ? sessionStorage : localStorage
}

// Token key'larini tanlash
const getTokenKey = (baseKey) => {
  const storage = getStorage()
  if (storage === sessionStorage) {
    return baseKey === ACCESS_TOKEN_KEY ? 'doctor_access_token' : 'doctor_refresh_token'
  }
  return baseKey
}

// Token olish
const storage = getStorage()
const token = storage.getItem(getTokenKey(ACCESS_TOKEN_KEY))
```

**Afzalliklari:**
- ✅ Doktorlar: `sessionStorage` ishlatadi (multi-tab)
- ✅ Boshqa userlar (clinic, patient, pharmacy, admin): `localStorage` (single session)
- ✅ Bitta API service hamma uchun ishlaydi

## Qanday Ishlaydi?

### Senariy 1: Ikkita Doktor Bir Vaqtda

1. **Tab 1: Doktor Aliyev kiradi**
   ```
   sessionStorage (Tab 1):
   - doctor_access_token: "token_aliyev_123"
   - doctor_refresh_token: "refresh_aliyev_123"
   - user_role: "doctor"
   - doctor_profile: {id: "uuid1", fullName: "Aliyev"}
   ```

2. **Tab 2: Doktor Karimova kiradi**
   ```
   sessionStorage (Tab 2):
   - doctor_access_token: "token_karimova_456"
   - doctor_refresh_token: "refresh_karimova_456"
   - user_role: "doctor"
   - doctor_profile: {id: "uuid2", fullName: "Karimova"}
   ```

3. **Natija:**
   - Tab 1: Aliyev ismi va ma'lumotlari ✅
   - Tab 2: Karimova ismi va ma'lumotlari ✅
   - Bir-biriga ta'sir qilmaydi! ✅

### Senariy 2: Clinic Owner + Doctor

1. **Tab 1: Clinic Owner kiradi → localStorage**
   ```
   localStorage (global):
   - access_token: "token_clinic_789"
   - refresh_token: "refresh_clinic_789"
   - user_role: "clinic"
   ```

2. **Tab 2: Doctor kiradi → sessionStorage**
   ```
   sessionStorage (Tab 2):
   - doctor_access_token: "token_doctor_123"
   - doctor_refresh_token: "refresh_doctor_123"
   - user_role: "doctor"
   ```

3. **Natija:**
   - Ikkalasi ham mustaqil ishlaydi ✅
   - Har xil storage ishlatilgani uchun konflikt yo'q ✅

## Storage Farqi

| Xususiyat | localStorage | sessionStorage |
|-----------|--------------|----------------|
| **Scope** | Barcha tablar | Faqat bitta tab |
| **Lifecycle** | Foydalanuvchi o'chirmaguncha | Tab yopilgunga qadar |
| **Sharing** | Domain bo'yicha ulashiladi | Tab bo'yicha alohida |
| **Use case** | Single session users | Multi-session users |

## Test Qilish

### 1. Serverni Ishga Tushirish
```bash
# Backend
cd C:\Hospitoll\hospitoll_backend
python manage.py runserver

# Frontend
cd C:\Hospitoll\hospitoll_frontend
npm run dev
```

### 2. Test Bosqichlari

**Test 1: Ikkita Doktor**
1. Chrome Tab 1: http://localhost:5173/doctor-login
2. Doktor A login qiling (masalan: `doctor1@example.com`)
3. Chrome Tab 2: http://localhost:5173/doctor-login  
4. Doktor B login qiling (masalan: `doctor2@example.com`)
5. **Natija:** Ikkalasi ham o'z dashboardlarini ko'radi ✅

**Test 2: Sahifani Yangilash**
1. Tab 1 (Doktor A): Sahifani yangilang (F5)
2. **Kutilgan:** Doktor A ismi va ma'lumotlari ✅
3. Tab 2 (Doktor B): Sahifani yangilang (F5)
4. **Kutilgan:** Doktor B ismi va ma'lumotlari ✅

**Test 3: Logout va Yangi Login**
1. Tab 1: Doktor A logout qiladi
2. Tab 2: Doktor B hali ham kirgan ✅
3. Tab 1: Doktor C login qiladi
4. **Natija:** Tab 1 = Doktor C, Tab 2 = Doktor B ✅

**Test 4: Tab Yopish**
1. Tab 1 ni yoping
2. Yangi tab oching va http://localhost:5173/doctor-login ga boring
3. **Natija:** Login sahifasi (session o'chirildi) ✅
4. Tab 2: Hali ham kirgan ✅

### 3. DevTools Tekshirish

**Application → Storage:**
```
sessionStorage (Tab 1):
  doctor_access_token: "eyJ0eXAiOiJKV1QiLCJhb..."
  doctor_refresh_token: "eyJ0eXAiOiJKV1QiLCJhb..."
  user_role: "doctor"
  doctor_profile: "{\"id\":\"uuid1\",\"fullName\":\"Dr. Aliyev\"}"

sessionStorage (Tab 2):
  doctor_access_token: "eyJ0eXAiOiJKV1QiLCJhb..."  ← Boshqa token!
  doctor_refresh_token: "eyJ0eXAiOiJKV1QiLCJhb..." ← Boshqa token!
  user_role: "doctor"
  doctor_profile: "{\"id\":\"uuid2\",\"fullName\":\"Dr. Karimova\"}"
```

## Qo'shimcha Ma'lumot

### Session Lifetime

**localStorage:**
- Foydalanuvchi o'chirmaguncha saqlanadi
- Brauzer yopilsa ham qoladi
- Manual clear qilish kerak

**sessionStorage:**
- Tab yopilganda o'chiriladi
- Brauzer restart qilsa o'chiriladi
- Yangi tab ochsa yangi session

### Boshqa Context'lar

Quyidagi context'lar hali ham `localStorage` ishlatadi (to'g'ri):
- ✅ `ClinicContext` - Bitta clinic owner per device
- ✅ `PatientContext` - Bitta patient per device
- ✅ `PharmacyContext` - Bitta pharmacy owner per device
- ✅ `AdminContext` - Bitta admin per device

Faqat **DoctorContext** `sessionStorage` ishlatadi chunki:
- Bir klinikada ko'p doktorlar bo'lishi mumkin
- Ular bir kompyuterda navbat bilan ishlashlari mumkin
- Har biri o'z ma'lumotlarini ko'rishi kerak

## Xavfsizlik

### Token Xavfsizligi

**sessionStorage afzalliklari:**
- ✅ Tab yopilganda avtomatik o'chiriladi
- ✅ XSS hujumlaridan relative xavfsizroq
- ✅ Har tab alohida, bir tabdagi breach boshqasiga ta'sir qilmaydi

### Best Practices

1. **Har doim HTTPS ishlatish** (production'da)
2. **Token expiry time qisqa qiling** (15-30 daqiqa)
3. **Refresh token faqat kerakda ishlating**
4. **Logout tugmasini ko'rinishda qoldiring**

## Kelajakda Yaxshilash

- [ ] Auto-logout after inactivity (harakatsizlikdan keyin)
- [ ] Warning message boshqa tabda login bo'lganda
- [ ] Session management dashboard (admin uchun)
- [ ] Multi-device session tracking
- [ ] Concurrent session limit (maksimal tablar soni)

## Muammolar va Yechimlar

### Muammo: Eski tab'da token expired

**Yechim:** Token refresh mechanism ishlaydi:
```javascript
// api.js da token refresh
if (response.status === 401 && !isRetry) {
  const newToken = await refreshAccessToken()
  if (newToken) {
    return api.request(endpoint, { ...options, _retry: true })
  }
}
```

### Muammo: Tab duplicate qilganda

**Natija:** Yangi tab old tab'ning sessionStorage'ini nusxalaydi.
- Bu kutilgan xatti-harakat
- Ikkalasi ham bir xil doktor sifatida ishlaydi
- Muammo yo'q

### Muammo: localStorage'dan sessionStorage'ga migratsiya

**Yechim:** User logout qilib qayta login qilishi kerak.

---

## Xulosa

✅ **Muammo hal qilindi:** Endi bir kompyuterda bir vaqtda ko'p doktorlar o'z panellarida ishlashlari mumkin!

✅ **Zero breaking changes:** Boshqa user tiplariga ta'sir yo'q

✅ **Better UX:** Har bir doktor o'z ma'lumotlarini ko'radi

✅ **Xavfsizroq:** Tab yopilganda session avtomatik o'chiriladi
