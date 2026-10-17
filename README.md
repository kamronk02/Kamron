# Kino Telegram bot — alohida fayllar

## Fayllar
- `main.py` — botning asosiy kodi, menyular va admin panel.
- `database.py` — kinolar, foydalanuvchilar va sozlamalar bazasi.
- `requirements.txt` — kerakli Python kutubxonalari.
- `render.yaml` — Render uchun boshlang‘ich sozlama.
- `.env.example` — kerakli environment variables namunasi.

## Render'ga joylash
1. GitHub'da yangi repository oching.
2. Ushbu fayllarning barchasini ZIP qilmasdan repository'ga alohida-alohida yuklang.
3. Render'da **New + → Web Service** ni tanlab repository'ni ulang.
4. Build Command: `pip install -r requirements.txt`
5. Start Command: `python main.py`
6. Environment Variables qo‘shing:
   - `BOT_TOKEN` — BotFather bergan bot tokeni.
   - `ADMIN_ID` — Telegram raqamli ID'ingiz.
   - `DB_PATH` — `kino_bot.db` (doimiy disk ishlatsangiz `/var/data/kino_bot.db`).
7. Deploy qiling.

## Muhim
- Bot tokenini hech kimga yubormang va kod ichiga ochiq yozmang.
- Majburiy obuna ishlashi uchun botni o‘sha kanalga administrator qilib qo‘ying.
- `ADMIN_ID` ni Telegram raqamli ID bilan kiriting, username bilan emas.
- Render bepul xizmatida mahalliy fayllar qayta deploy/restart vaqtida yo‘qolishi mumkin. Bazani saqlab qolish uchun Render persistent disk (mount path `/var/data`) yoki tashqi PostgreSQL bazasi kerak. Agar persistent disk mavjud bo‘lmasa, `DB_PATH=kino_bot.db` qilib ishlating, ammo ma'lumotlar doimiy saqlanishiga kafolat yo‘q.
- Telegram botning o‘zi videoni serverga qayta yuklamaydi: Telegram video `file_id` qiymatini saqlaydi.

## Admin buyruqlari
- `/admin` — admin panel
- `/movies` — kinolar ID va nomlari
- `/delete ID` — kino o‘chirish
- `/ban USER_ID` — foydalanuvchini bloklash
- `/unban USER_ID` — blokdan chiqarish
- `/cancel` — joriy amalni bekor qilish

## Kino qo‘shish
Admin panel → **Kino qo‘shish**:
1. Video yuboring.
2. Kino nomini yozing.
3. Yilini yozing.
4. Janrini yozing.
5. Tavsifini yozing yoki `yo‘q` deb yozing.

Bu dastlabki to‘liq ishlaydigan versiya. Deploydan keyin Render Logs'da xato chiqsa, logning oxirgi qismini yuboring.
