# G-MED Printer Service

Bu folder G-MED tizimi uchun qabulxona sharoitida ishlaydigan mahalliy Windows printer service'ini o'z ichiga oladi.

## Maqsad
- Klinikada ulangan printerni avtomatik aniqlash
- Xprinter termal printerni topish
- G-MED serverdan print joblarni olish
- qog'oz navbat talonini ESC/POS formatida chop etish
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

Bu service faqat qabulxona va lokal klinika kompyuterida ishlaydi. Onlayn navbat yaratish jarayoni va mavjud doktor/queue logikasi buzilmaydi.
