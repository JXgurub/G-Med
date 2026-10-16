# G-MED Printer Service

Bu folder G-MED tizimi uchun qabulxona va dorixona POS kompyuterida ishlaydigan mahalliy Windows printer service'ini o'z ichiga oladi.

## Maqsad
- Klinikada ulangan printerni avtomatik aniqlash
- Xprinter termal printerni topish
- G-MED serverdan print joblarni olish
- qog'oz navbat taloni va dorixona cheklarini ESC/POS formatida chop etish
- printer holatini serverga yuborish
- qabulxona xodimi faqat o'z klinikasiga tegishli printerdan foydalanishi

## Foydalanish

1. `requirements.txt` dan paketlarni o'rnating.
2. `config.example.json` ni `config.json`ga ko'chiring.
3. Ma'lumotlarni to'ldiring:
   - `api_base_url`
   - `device_token`
   - `clinic_id`
   - `reception_room_id`
4. Windowsda service sifatida ishlatish uchun:
   - `install_service.ps1` ni PowerShell bilan ishga tushiring.
5. Yoki oddiy lokal launcher bilan ishlatish uchun:
   - `python printer_service.py`

## Windows service

`windows_service.py` - Windows uchun background service skeleton'i.

Agar PyInstaller bilan exe yasamoqchi bo'lsangiz:

```powershell
pyinstaller --onefile --noconsole windows_service.py
```

Yoki:

```powershell
pyinstaller --onefile --windowed windows_service.py
```

## Xprinter taxminiya ishlash sxemasi

- Printer ulanganmi?
- Xprinter nomi topildimi?
- Serverga heartbeat jo'natiladimi?
- Pending joblar mavjudmi?
- Job olindi => printerga chop etildi => status completed
- Xato bo'lsa => status failed

## Muhim

Qabulxona va dorixona uchun printer qurilmalari, tokenlari va server navbatlari alohida ishlaydi. Mavjud qabulxona sozlamasi bilan onlayn navbat/doktor oqimi o‘zgarmaydi.

## Dorixona POS printeri

Printer installer oynasida **Dorixona** tashkilot turini tanlab, dorixona egasining login emaili va parolini kiriting. Installer loginni serverda tekshiradi, printer tokenini ro‘yxatdan o‘tkazadi va Windows printer service’ni o‘zi o‘rnatadi. Parol service sozlamalariga saqlanmaydi.

Dorixona printeri `GMedPharmacyPrinterService` nomli alohida Windows xizmati sifatida ishlaydi. Bu klinikalardagi mavjud `GMedPrinterService` xizmatini o‘chirmaydi yoki almashtirmaydi. Printer servisini dorixona loginidan keyin sozlagach, POS sotuv cheklarini server orqali ushbu printerga yuboradi. Dorixona xizmatida oddiy A4/default printerga zaxira bosib chiqarish o‘chirilgan: faqat Xprinter/termal chek printeri aniqlansa xizmat tayyor holatga o‘tadi.

Dorixona chek-navbati qabulxona printeridan alohida. POS sotuv va chek tugmasi bosilganda chek printer tayyor bo‘lsa ESC/POS formatida termal printer navbatiga avtomatik yuboriladi. Printer tayyor bo‘lmasa brauzerning A4/PDF oynasi avtomatik ochilmaydi; kerak bo‘lsa chekni alohida qo‘lda chop etish tugmasi orqali chiqarish mumkin.

## Chek va navbat qog‘ozi sozlamalari

- Klinika egasi dashboardidagi **Sozlamalar → Navbat qog‘ozi sozlamalari** bo‘limidan navbat raqami o‘lchamini (katta/o‘rtacha/kichik), talonda klinika manzili, telefoni va Instagram/sayt havolasi chiqishini, shuningdek talon nomi va manzil/havola matnini boshqarishi mumkin.
- Dorixona egasi `pharmacy-owner-dashboard/pos` sahifasida **Dorixona ma’lumotlari → O‘zgartirilsin** bo‘limidan manzil, telefon, sayt va Instagram ma’lumotlarini hamda chekda ko‘rsatish tanlovlarini saqlaydi. Bu tanlovlar termal printer va brauzerda qo‘lda chiqariladigan chekda bir xil ishlaydi.
- Sozlamalar serverda dorixona yoki klinika bo‘yicha saqlanadi. Yangi maydonlar uchun backend `clinics` va `pharmacies` migratsiyalarini deploy vaqtida qo‘llang.
