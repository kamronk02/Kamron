import asyncio
import logging
import os
from aiohttp import web
from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton
)
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError
import database as db

logging.basicConfig(level=logging.INFO)
TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_ID_RAW = os.getenv("ADMIN_ID", "").strip()
ADMIN_ID = int(ADMIN_ID_RAW) if ADMIN_ID_RAW.isdigit() else 0
PORT = int(os.getenv("PORT", "10000"))

if not TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi. Render Environment bo'limiga bot tokenini kiriting.")
if not ADMIN_ID:
    raise RuntimeError("ADMIN_ID noto'g'ri. Render Environment bo'limiga Telegram raqamli ID'ingizni kiriting.")

bot = Bot(TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()


class AddMovie(StatesGroup):
    video = State()
    title = State()
    year = State()
    genre = State()
    description = State()


class SearchMovie(StatesGroup):
    query = State()


class SearchYear(StatesGroup):
    year = State()


class SearchGenre(StatesGroup):
    genre = State()


class Broadcast(StatesGroup):
    message = State()


class SetChannel(StatesGroup):
    channel = State()


def main_keyboard(is_admin=False):
    rows = [
        [KeyboardButton(text="🔎 Kino qidirish"), KeyboardButton(text="🎭 Janr bo‘yicha")],
        [KeyboardButton(text="📅 Yil bo‘yicha"), KeyboardButton(text="📚 Barcha kinolar")],
    ]
    if is_admin:
        rows.append([KeyboardButton(text="👑 Admin panel")])
    return ReplyKeyboardMarkup(keyboard=rows, resize_keyboard=True)


def admin_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Kino qo‘shish", callback_data="admin:add")],
        [InlineKeyboardButton(text="🗑 Kino o‘chirish", callback_data="admin:delete")],
        [InlineKeyboardButton(text="📢 Ommaviy xabar", callback_data="admin:broadcast")],
        [InlineKeyboardButton(text="🔒 Majburiy obuna", callback_data="admin:channel")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data="admin:stats")],
        [InlineKeyboardButton(text="👥 Foydalanuvchilar", callback_data="admin:users")],
    ])


def is_admin(user_id):
    return user_id == ADMIN_ID


async def subscribed(user_id: int) -> bool:
    channel = await db.get_setting("required_channel")
    if not channel:
        return True
    channel = channel.strip()
    if not channel:
        return True
    try:
        member = await bot.get_chat_member(channel, user_id)
        return member.status not in ("left", "kicked")
    except Exception:
        # Bot kanalga administrator qilib qo'yilmagan yoki kanal username/ID noto'g'ri bo'lishi mumkin.
        return False


async def subscription_gate(message: Message) -> bool:
    if is_admin(message.from_user.id):
        return True
    channel = await db.get_setting("required_channel")
    if not channel:
        return True
    if await subscribed(message.from_user.id):
        return True
    username = channel if channel.startswith("@") else channel
    await message.answer(
        "🔒 Botdan foydalanish uchun avval kanalga obuna bo‘ling.\n"
        f"📢 Kanal: {username}\n\nObuna bo‘lgach, /start buyrug‘ini bosing."
    )
    return False


async def send_movie_list(message: Message, movies):
    if not movies:
        await message.answer("😕 Hozircha bazada kino topilmadi.")
        return
    buttons = []
    for movie in movies[:30]:
        movie_id, title, year, genre, *_ = movie
        buttons.append([InlineKeyboardButton(
            text=f"🎬 {title} ({year})",
            callback_data=f"movie:{movie_id}"
        )])
    await message.answer("🎞 Topilgan kinolar:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))


async def show_movie(callback: CallbackQuery, movie_id: int):
    movie = await db.get_movie(movie_id)
    if not movie:
        await callback.answer("Kino topilmadi.", show_alert=True)
        return
    _, title, year, genre, description, file_id, added_by = movie
    caption = f"🎬 <b>{title}</b>\n📅 Yili: {year}\n🎭 Janr: {genre}"
    if description:
        caption += f"\n\n📝 {description}"
    try:
        await bot.send_video(
            chat_id=callback.from_user.id,
            video=file_id,
            caption=caption,
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Menyu", callback_data="menu:home")]
            ])
        )
    except TelegramBadRequest:
        await bot.send_message(callback.from_user.id, caption)
    await callback.answer()


@dp.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    await db.add_user(message.from_user.id, message.from_user.username or "", message.from_user.full_name)
    if await db.is_banned(message.from_user.id):
        await message.answer("⛔ Siz botdan foydalanishdan cheklangansiz.")
        return
    if not await subscription_gate(message):
        return
    await message.answer(
        "🎬 <b>Kino botga xush kelibsiz!</b>\n\n"
        "Kino nomi, yili yoki janri orqali qidiring.",
        reply_markup=main_keyboard(is_admin(message.from_user.id))
    )


@dp.message(Command("admin"))
async def admin_command(message: Message, state: FSMContext):
    await state.clear()
    if not is_admin(message.from_user.id):
        await message.answer("⛔ Bu bo‘lim faqat admin uchun.")
        return
    await message.answer("👑 <b>Admin panel</b>", reply_markup=admin_keyboard())


@dp.message(F.text == "👑 Admin panel")
async def admin_button(message: Message, state: FSMContext):
    await state.clear()
    if not is_admin(message.from_user.id):
        return
    await message.answer("👑 <b>Admin panel</b>", reply_markup=admin_keyboard())


@dp.message(F.text == "🔎 Kino qidirish")
async def search_start(message: Message, state: FSMContext):
    if not await subscription_gate(message):
        return
    await state.set_state(SearchMovie.query)
    await message.answer("🔎 Kino nomini yozing:")


@dp.message(SearchMovie.query)
async def search_query(message: Message, state: FSMContext):
    if not await subscription_gate(message):
        return
    query = (message.text or "").strip()
    if not query:
        await message.answer("Iltimos, kino nomini matn ko‘rinishida yuboring.")
        return
    movies = await db.search_movies(query)
    await state.clear()
    await send_movie_list(message, movies)


@dp.message(F.text == "📅 Yil bo‘yicha")
async def year_start(message: Message, state: FSMContext):
    if not await subscription_gate(message):
        return
    await state.set_state(SearchYear.year)
    await message.answer("📅 Kino yilini yozing (masalan: 2024):")


@dp.message(SearchYear.year)
async def year_search(message: Message, state: FSMContext):
    if not await subscription_gate(message):
        return
    year = (message.text or "").strip()
    if not year.isdigit() or len(year) != 4:
        await message.answer("Yilni 4 ta raqam bilan yozing. Masalan: 2024")
        return
    movies = await db.movies_by_year(year)
    await state.clear()
    await send_movie_list(message, movies)


@dp.message(F.text == "🎭 Janr bo‘yicha")
async def genre_start(message: Message, state: FSMContext):
    if not await subscription_gate(message):
        return
    await state.set_state(SearchGenre.genre)
    await message.answer("🎭 Janr nomini yozing (masalan: Komediya):")


@dp.message(SearchGenre.genre)
async def genre_search(message: Message, state: FSMContext):
    if not await subscription_gate(message):
        return
    genre = (message.text or "").strip()
    if not genre:
        await message.answer("Janr nomini yozing.")
        return
    movies = await db.movies_by_genre(genre)
    await state.clear()
    await send_movie_list(message, movies)


@dp.message(F.text == "📚 Barcha kinolar")
async def all_movies(message: Message):
    if not await subscription_gate(message):
        return
    await send_movie_list(message, await db.all_movies())


@dp.callback_query(F.data.startswith("movie:"))
async def movie_callback(callback: CallbackQuery):
    if not is_admin(callback.from_user.id) and not await subscribed(callback.from_user.id):
        await callback.answer("Avval majburiy kanalga obuna bo‘ling.", show_alert=True)
        return
    try:
        movie_id = int(callback.data.split(":", 1)[1])
    except (ValueError, IndexError):
        await callback.answer("Noto‘g‘ri so‘rov.", show_alert=True)
        return
    await show_movie(callback, movie_id)


@dp.callback_query(F.data == "menu:home")
async def home_callback(callback: CallbackQuery):
    await callback.message.answer("Asosiy menyu:", reply_markup=main_keyboard(is_admin(callback.from_user.id)))
    await callback.answer()


@dp.callback_query(F.data.startswith("admin:"))
async def admin_callbacks(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("Bu bo‘lim faqat admin uchun.", show_alert=True)
        return
    action = callback.data.split(":", 1)[1]
    await callback.answer()
    if action == "add":
        await state.clear()
        await state.set_state(AddMovie.video)
        await callback.message.answer("➕ Kino videosini yuboring (Telegram video fayli sifatida). Bekor qilish: /cancel")
    elif action == "delete":
        await callback.message.answer("O‘chirish uchun kino ID raqamini yuboring.\nID va nomlarni ko‘rish: /movies")
    elif action == "broadcast":
        await state.set_state(Broadcast.message)
        await callback.message.answer("📢 Barcha foydalanuvchilarga yuboriladigan matn yoki postni yuboring. Bekor qilish: /cancel")
    elif action == "channel":
        current = await db.get_setting("required_channel") or "O‘rnatilmagan"
        await state.set_state(SetChannel.channel)
        await callback.message.answer(
            f"🔒 Hozirgi majburiy kanal: <code>{current}</code>\n"
            "Yangi kanal username yoki ID sini yuboring (masalan: @kanal). O‘chirish uchun: off\n"
            "Bot kanalga administrator qilib qo‘yilishi kerak."
        )
    elif action == "stats":
        users = await db.user_count()
        movies = await db.movie_count()
        await callback.message.answer(f"📊 <b>Statistika</b>\n👥 Foydalanuvchilar: {users}\n🎬 Kinolar: {movies}")
    elif action == "users":
        users = await db.latest_users(30)
        if not users:
            await callback.message.answer("Hozircha foydalanuvchi yo‘q.")
        else:
            lines = ["👥 <b>Oxirgi foydalanuvchilar:</b>"]
            for user_id, username, full_name, banned in users:
                status = "🚫 bloklangan" if banned else "✅ faol"
                name = (full_name or "Ismsiz").replace("<", "").replace(">", "")
                lines.append(f"• <code>{user_id}</code> — {name} — {status}")
            await callback.message.answer("\n".join(lines))
    else:
        await callback.message.answer("Noma’lum bo‘lim.")


@dp.message(AddMovie.video)
async def add_video(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    if not message.video:
        await message.answer("Iltimos, kino videosini yuboring. Telegram video sifatida jo‘nating.")
        return
    await state.update_data(file_id=message.video.file_id)
    await state.set_state(AddMovie.title)
    await message.answer("✅ Video qabul qilindi.\nEndi kino nomini yozing:")


@dp.message(AddMovie.title)
async def add_title(message: Message, state: FSMContext):
    title = (message.text or "").strip()
    if not title:
        await message.answer("Kino nomini yozing.")
        return
    await state.update_data(title=title)
    await state.set_state(AddMovie.year)
    await message.answer("📅 Kino yilini yozing (masalan: 2024):")


@dp.message(AddMovie.year)
async def add_year(message: Message, state: FSMContext):
    year = (message.text or "").strip()
    if not year.isdigit() or len(year) != 4:
        await message.answer("Yilni 4 ta raqam bilan yozing. Masalan: 2024")
        return
    await state.update_data(year=year)
    await state.set_state(AddMovie.genre)
    await message.answer("🎭 Kino janrini yozing (masalan: Komediya, Drama):")


@dp.message(AddMovie.genre)
async def add_genre(message: Message, state: FSMContext):
    genre = (message.text or "").strip()
    if not genre:
        await message.answer("Janrni yozing.")
        return
    await state.update_data(genre=genre)
    await state.set_state(AddMovie.description)
    await message.answer("📝 Kino tavsifini yozing yoki tavsif kerak bo‘lmasa — yozing: yo‘q")


@dp.message(AddMovie.description)
async def add_description(message: Message, state: FSMContext):
    data = await state.get_data()
    description = (message.text or "").strip()
    if description.lower() in ("yo‘q", "yo'q", "yoq", "-", "none"):
        description = ""
    movie_id = await db.add_movie(
        title=data["title"], year=data["year"], genre=data["genre"],
        description=description, file_id=data["file_id"], added_by=message.from_user.id
    )
    await state.clear()
    await message.answer(f"✅ Kino bazaga qo‘shildi!\n🆔 ID: <code>{movie_id}</code>\n🎬 {data['title']}")


@dp.message(Broadcast.message)
async def broadcast_message(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    users = await db.all_user_ids()
    sent = 0
    failed = 0
    status = await message.answer(f"📢 Xabar yuborilmoqda: {len(users)} ta foydalanuvchi...")
    for user_id in users:
        try:
            await message.copy_to(chat_id=user_id)
            sent += 1
        except (TelegramForbiddenError, TelegramBadRequest):
            failed += 1
        except Exception:
            failed += 1
        await asyncio.sleep(0.04)
    await state.clear()
    await status.edit_text(f"✅ Ommaviy xabar yakunlandi.\nYuborildi: {sent}\nYuborilmadi: {failed}")


@dp.message(SetChannel.channel)
async def set_channel(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    channel = (message.text or "").strip()
    if channel.lower() in ("off", "o‘chirish", "ochirish", "none"):
        await db.set_setting("required_channel", "")
        await state.clear()
        await message.answer("✅ Majburiy obuna o‘chirildi.")
        return
    if not channel.startswith("@") and not channel.startswith("-100"):
        await message.answer("Kanalni @username yoki -100... ko‘rinishida yuboring.")
        return
    await db.set_setting("required_channel", channel)
    await state.clear()
    await message.answer(f"✅ Majburiy obuna kanali saqlandi: <code>{channel}</code>\nBotni o‘sha kanalga administrator qiling.")


@dp.message(Command("movies"))
async def admin_movies(message: Message):
    if not is_admin(message.from_user.id):
        return
    movies = await db.all_movies()
    if not movies:
        await message.answer("Bazaga hali kino qo‘shilmagan.")
        return
    lines = ["🎬 <b>Kinolar (ID — nomi):</b>"]
    for movie in movies[:100]:
        lines.append(f"<code>{movie[0]}</code> — {movie[1]} ({movie[2]})")
    lines.append("\nO‘chirish: /delete ID")
    await message.answer("\n".join(lines))


@dp.message(Command("delete"))
async def delete_movie_command(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Foydalanish: /delete 12\nID lar ro‘yxati: /movies")
        return
    removed = await db.delete_movie(int(parts[1]))
    await message.answer("✅ Kino o‘chirildi." if removed else "Bunday ID bilan kino topilmadi.")


@dp.message(Command("ban"))
async def ban_user_command(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Foydalanish: /ban USER_ID")
        return
    await db.set_banned(int(parts[1]), True)
    await message.answer("🚫 Foydalanuvchi bloklandi.")


@dp.message(Command("unban"))
async def unban_user_command(message: Message):
    if not is_admin(message.from_user.id):
        return
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Foydalanish: /unban USER_ID")
        return
    await db.set_banned(int(parts[1]), False)
    await message.answer("✅ Foydalanuvchi blokdan chiqarildi.")


@dp.message(Command("cancel"))
async def cancel_command(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Amal bekor qilindi.", reply_markup=main_keyboard(is_admin(message.from_user.id)))


async def health(request):
    return web.Response(text="Kino bot ishlayapti")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health)
    app.router.add_get("/health", health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info("Health server %s-portda ishga tushdi", PORT)
    return runner


async def main():
    await db.init_db()
    runner = await start_web_server()
    try:
        logging.info("Kino bot ishga tushmoqda.")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await runner.cleanup()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
