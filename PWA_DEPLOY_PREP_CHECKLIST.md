# PWA + Deploy Preparation Checklist

## 1) Frontend PWA setup (Vite)
- [ ] `vite-plugin-pwa` o'rnatish
- [ ] `vite.config.js` ichida `VitePWA(...)` pluginini yoqish
- [ ] `manifest` (app nomi, icons, theme_color, display: standalone) qo'shish
- [ ] `public/icons/` ga 192x192 va 512x512 ikonka qo'yish
- [ ] Service worker strategiyasini tanlash (`generateSW` yoki `injectManifest`)
- [ ] Offline fallback sahifasi qo'shish (kamida home shell)
- [ ] `main.jsx` da PWA registration (`registerSW`) qo'shish

## 2) API + Auth for PWA
- [ ] Token saqlash strategiyasini qayta tekshirish (local/session storage)
- [ ] Offline holatda xatolik UX (toasts/messages) qo'shish
- [ ] API timeout/retry siyosatini aniqlash

## 3) Build & QA
- [ ] `npm install` va `npm run build` muvaffaqiyatli ishlashini tekshirish
- [ ] Lighthouse PWA audit (Installable, Offline, Best Practices)
- [ ] Android Chrome'da "Add to Home Screen" test

## 4) Backend deploy readiness
- [ ] `DEBUG=False`, `ALLOWED_HOSTS`, `CORS` ni productionga moslash
- [ ] Static/media serving (Nginx yoki CDN) tekshirish
- [ ] Production DB (PostgreSQL) migratsiyalarini tekshirish
- [ ] HTTPS majburiy qilish (secure cookies + HSTS)

## 5) Server deploy
- [ ] Domain va SSL sertifikatlar
- [ ] Environment variables (`.env`) production qiymatlari
- [ ] `docker compose` yoki systemd orqali process management
- [ ] Monitoring/log rotation (backend logs)

## Notes
- Frontendda PWA konfiguratsiyasi mavjud (`vite-plugin-pwa`, `VitePWA(...)`).
- Hozir `node_modules`, backend `venv`, va frontend `dist` mavjud holatda.

## 6) Security release checklist
- [x] User parollari DBda hash ko'rinishida saqlanishi tekshirildi (`pbkdf2_sha256$...`).
- [x] Parol reset kodi hash ko'rinishida saqlanishi tekshirildi (`code_hash`, `make_password`).
- [x] Admin dashboard'da dorixona yaratilganda parolni alert'da ko'rsatish olib tashlandi.
- [x] Klinik kartadagi test parol badge olib tashlandi.
- [x] `init.sql` ichidagi hardcoded DB role parollari olib tashlandi.
- [x] `init.sql` endi psql variable talab qiladi: `HOSPITOLL_ADMIN_PASSWORD`, `HOSPITOLL_APP_PASSWORD`.

### `init.sql` ishga tushirish namunasi
- `psql -v HOSPITOLL_ADMIN_PASSWORD=yourStrongAdminPass -v HOSPITOLL_APP_PASSWORD=yourStrongAppPass -f init.sql`

### Tavsiya etiladigan keyingi qadamlar
- [ ] Productionga chiqishdan oldin JWT `SECRET_KEY` va DB credential'larni rotate qilish.
- [ ] `DEBUG=False`, `ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS` qiymatlarini yakuniy domain bilan tekshirish.
- [ ] Ngrok/public testdan keyin vaqtinchalik token va URL'larni yangilash yoki bekor qilish.
