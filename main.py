import os
import asyncio
import logging
import aiosqlite
from aiohttp import web
from datetime import datetime
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, FSInputFile
)

MAIN_BOT_TOKEN = "8772504288:AAGpe_SVTkVH3epiJ0JTGvP2B3P4OEFJWGU"  # ⚠️ O'zingizning bot tokeningizni kiriting

# --- ADMIN LOGIN VA PAROL ---
ADMIN_LOGIN = "admin"
ADMIN_PASSWORD = "admin712"

if not os.path.exists("media"):
    os.makedirs("media")

logging.basicConfig(level=logging.INFO)
main_bot = Bot(token=MAIN_BOT_TOKEN)
main_dp = Dispatcher()

# --- FSM HOLATLARI ---
class NewBotState(StatesGroup):
    waiting_for_name = State()
    waiting_for_token = State()

class AddButtonState(StatesGroup):
    waiting_for_name = State()
    waiting_for_value = State()

class AddContentState(StatesGroup):
    waiting_for_code = State()
    waiting_for_file = State()

class BroadcastState(StatesGroup):
    waiting_for_message = State()

class AdminLoginState(StatesGroup):
    waiting_for_login = State()
    waiting_for_password = State()

class GlobalBroadcastState(StatesGroup):
    waiting_for_message = State()

class AdminReplyState(StatesGroup):
    waiting_for_reply_text = State()

class FeedbackState(StatesGroup):
    waiting_for_msg = State()

# --- BAZANI SOZLASH VA MIGRATSIYA ---
async def init_db():
    async with aiosqlite.connect("constructor_database.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS user_bots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                bot_name TEXT,
                bot_token TEXT UNIQUE
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_buttons (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_token TEXT,
                button_name TEXT,
                reply_text TEXT,
                button_type TEXT DEFAULT 'reply',
                url TEXT,
                media_path TEXT,
                media_type TEXT DEFAULT 'text'
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS child_bot_users (
                bot_token TEXT,
                user_id INTEGER,
                lang TEXT DEFAULT 'uz',
                is_banned INTEGER DEFAULT 0,
                PRIMARY KEY (bot_token, user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS chat_sessions (
                bot_token TEXT,
                user_id INTEGER,
                admin_id INTEGER,
                PRIMARY KEY (bot_token, user_id)
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS bot_contents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                bot_token TEXT,
                content_code TEXT,
                file_id TEXT,
                file_type TEXT,
                caption TEXT
            )
        """)
        
        for col_query in [
            "ALTER TABLE bot_buttons ADD COLUMN url TEXT",
            "ALTER TABLE bot_buttons ADD COLUMN button_type TEXT DEFAULT 'reply'",
            "ALTER TABLE bot_buttons ADD COLUMN media_path TEXT",
            "ALTER TABLE bot_buttons ADD COLUMN media_type TEXT DEFAULT 'text'",
            "ALTER TABLE child_bot_users ADD COLUMN lang TEXT DEFAULT 'uz'",
            "ALTER TABLE child_bot_users ADD COLUMN is_banned INTEGER DEFAULT 0"
        ]:
            try:
                await db.execute(col_query)
            except Exception:
                pass
        await db.commit()

# --- MAIN BOT ENGINE ---

@main_dp.message(Command("start"))
async def start_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "⚡ **Vortex712 Bot Constructor Engine (Pro v3)**\n\n"
        "➕ Yangi bot qo'shish: /newbot\n"
        "📱 Botlarni boshqarish: /mybots\n"
        "🔐 Admin Panel: /admin",
        parse_mode="Markdown"
    )

# --- ADMIN PANEL LOGIKASI ---

@main_dp.message(Command("admin"))
async def admin_login_start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("🔐 **Admin panelga kirish**\n\nLoginni kiriting:", parse_mode="Markdown")
    await state.set_state(AdminLoginState.waiting_for_login)

@main_dp.message(AdminLoginState.waiting_for_login)
async def admin_get_login(message: types.Message, state: FSMContext):
    if message.text.strip() == ADMIN_LOGIN:
        await message.answer("Parolni kiriting:")
        await state.set_state(AdminLoginState.waiting_for_password)
    else:
        await message.answer("❌ Login noto'g'ri! /admin buyrug'idan qaytadan boshlang.")
        await state.clear()

@main_dp.message(AdminLoginState.waiting_for_password)
async def admin_get_password(message: types.Message, state: FSMContext):
    if message.text.strip() == ADMIN_PASSWORD:
        await state.clear()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="📊 Umumiy Statistika", callback_data="adm_stats")],
            [InlineKeyboardButton(text="📢 Global Rassilka (Barchaga)", callback_data="adm_global_bc")],
            [InlineKeyboardButton(text="🤖 Barcha Botlar Ro'yxati", callback_data="adm_list_bots")]
        ])
        await message.answer("✅ **Xush kelibsiz, Bosh Admin!**\nKerakli bo'limni tanlang:", reply_markup=kb, parse_mode="Markdown")
    else:
        await message.answer("❌ Parol noto'g'ri! /admin buyrug'idan qaytadan boshlang.")
        await state.clear()

@main_dp.callback_query(F.data == "adm_stats")
async def admin_stats_handler(call: CallbackQuery):
    async with aiosqlite.connect("constructor_database.db") as db:
        async with db.execute("SELECT COUNT(*) FROM user_bots") as c1:
            total_bots = (await c1.fetchone())[0]
        async with db.execute("SELECT COUNT(DISTINCT user_id) FROM child_bot_users") as c2:
            total_users = (await c2.fetchone())[0]

    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm_back")]])
    await call.message.edit_text(
        f"📊 **Global Statistika:**\n\n"
        f"🤖 Jami yaratilgan botlar: **{total_bots}** ta\n"
        f"👥 Barcha botlardagi jami foydalanuvchilar: **{total_users}** ta",
        reply_markup=kb,
        parse_mode="Markdown"
    )

@main_dp.callback_query(F.data == "adm_list_bots")
async def admin_list_bots(call: CallbackQuery):
    async with aiosqlite.connect("constructor_database.db") as db:
        async with db.execute("SELECT id, bot_name, bot_token, user_id FROM user_bots") as cursor:
            bots = await cursor.fetchall()

    if not bots:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm_back")]])
        await call.message.edit_text("Hali birorta bot yaratilmagan.", reply_markup=kb)
        return

    kb_list = [[InlineKeyboardButton(text=f"🤖 {b[1]} (ID: {b[3]})", callback_data=f"adm_delbot_{b[2]}")] for b in bots]
    kb_list.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data="adm_back")])
    await call.message.edit_text("🗑 O'chirmoqchi bo'lgan botni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb_list))

@main_dp.callback_query(F.data.startswith("adm_delbot_"))
async def admin_delete_specific_bot(call: CallbackQuery):
    token = call.data.replace("adm_delbot_", "")
    async with aiosqlite.connect("constructor_database.db") as db:
        await db.execute("DELETE FROM user_bots WHERE bot_token = ?", (token,))
        await db.execute("DELETE FROM bot_buttons WHERE bot_token = ?", (token,))
        await db.execute("DELETE FROM child_bot_users WHERE bot_token = ?", (token,))
        await db.execute("DELETE FROM chat_sessions WHERE bot_token = ?", (token,))
        await db.execute("DELETE FROM bot_contents WHERE bot_token = ?", (token,))
        await db.commit()
    await call.answer("✅ Bot tizimdan o'chirildi!", show_alert=True)
    await admin_list_bots(call)

@main_dp.callback_query(F.data == "adm_global_bc")
async def admin_global_broadcast_start(call: CallbackQuery, state: FSMContext):
    await call.message.edit_text("📢 Barcha botlarning obunachilariga yuboriladigan xabar matnini kiriting:")
    await state.set_state(GlobalBroadcastState.waiting_for_message)

@main_dp.message(GlobalBroadcastState.waiting_for_message)
async def admin_execute_global_bc(message: types.Message, state: FSMContext):
    text = message.text
    async with aiosqlite.connect("constructor_database.db") as db:
        async with db.execute("SELECT DISTINCT bot_token FROM child_bot_users") as cursor:
            tokens = await cursor.fetchall()

    if not tokens:
        await message.answer("Obunachilar topilmadi.")
        await state.clear()
        return

    await message.answer("🚀 Global rassilka boshlandi...")
    success = 0
    for (token,) in tokens:
        c_bot = Bot(token=token)
        async with aiosqlite.connect("constructor_database.db") as db:
            async with db.execute("SELECT user_id FROM child_bot_users WHERE bot_token = ? AND is_banned = 0", (token,)) as cursor:
                users = await cursor.fetchall()
        for (u_id,) in users:
            try:
                await c_bot.send_message(u_id, f"📢 <b>Adminlar e'loni:</b>\n\n{text}", parse_mode="HTML")
                success += 1
                await asyncio.sleep(0.03)
            except Exception:
                pass
        try:
            await c_bot.session.close()
        except Exception:
            pass

    await message.answer(f"✅ **Global rassilka yakunlandi!**\nJami {success} ta foydalanuvchiga yetib bordi.", parse_mode="Markdown")
    await state.clear()

@main_dp.callback_query(F.data == "adm_back")
async def admin_back_main(call: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📊 Umumiy Statistika", callback_data="adm_stats")],
        [InlineKeyboardButton(text="📢 Global Rassilka (Barchaga)", callback_data="adm_global_bc")],
        [InlineKeyboardButton(text="🤖 Barcha Botlar Ro'yxati", callback_data="adm_list_bots")]
    ])
    await call.message.edit_text("🔐 **Admin Paneli:**", reply_markup=kb, parse_mode="Markdown")

# --- BOTLARNI BOSHQARISH VA YARATISH ---

@main_dp.message(Command("mybots"))
async def mybots_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    async with aiosqlite.connect("constructor_database.db") as db:
        async with db.execute("SELECT id, bot_name, bot_token FROM user_bots WHERE user_id = ?", (message.from_user.id,)) as cursor:
            bots = await cursor.fetchall()

    if not bots:
        await message.answer("Sizda hali botlar yo'q. /newbot orqali qo'shing!")
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"🤖 {b[1]}", callback_data=f"manage_bot_{b[2]}")] for b in bots
    ])
    await message.answer("Boshqarmoqchi bo'lgan botingizni tanlang:", reply_markup=keyboard)

@main_dp.message(Command("newbot"))
async def newbot_cmd(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Yangi botingiz nomini kiriting:")
    await state.set_state(NewBotState.waiting_for_name)

@main_dp.message(NewBotState.waiting_for_name)
async def process_name(message: types.Message, state: FSMContext):
    await state.update_data(bot_name=message.text)
    await message.answer("Bot API Tokenini yuboring:")
    await state.set_state(NewBotState.waiting_for_token)

@main_dp.message(NewBotState.waiting_for_token)
async def process_token(message: types.Message, state: FSMContext):
    token = message.text.strip()
    data = await state.get_data()
    
    try:
        async with aiosqlite.connect("constructor_database.db") as db:
            await db.execute(
                "INSERT INTO user_bots (user_id, bot_name, bot_token) VALUES (?, ?, ?)",
                (message.from_user.id, data["bot_name"], token)
            )
            await db.commit()
        
        asyncio.create_task(run_child_bot(token))
        await message.answer(f"✅ **{data['bot_name']}** ishga tushdi!\nSozlash uchun /mybots buyrug'ini bosing.", parse_mode="Markdown")
    except Exception:
        await message.answer("❌ Bu token allaqachon mavjud yoki xatolik yuz berdi.")
    await state.clear()

# --- FOYDALANUVCHI BOT BOSHQARUVI ---

@main_dp.callback_query(F.data.startswith("manage_bot_"))
async def manage_bot_handler(call: CallbackQuery):
    token = call.data.replace("manage_bot_", "")
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Reply Tugma (Menyu)", callback_data=f"add_btn_{token}_reply")],
        [InlineKeyboardButton(text="💳 Karta (Donat)", callback_data=f"add_btn_{token}_inline")],
        [InlineKeyboardButton(text="📁 Fayl / Kino Qo'shish", callback_data=f"add_content_{token}")],
        [InlineKeyboardButton(text="🗑 Tugmalarni O'chirish", callback_data=f"list_btn_{token}")],
        [InlineKeyboardButton(text="📊 Statistika", callback_data=f"stats_bot_{token}")],
        [InlineKeyboardButton(text="📢 Rassilka", callback_data=f"broadcast_{token}")],
        [InlineKeyboardButton(text="❌ Botni O'chirish", callback_data=f"del_userbot_{token}")]
    ])
    await call.message.edit_text("⚙️ **Bot Boshqaruv Paneli (Pro v3):**", reply_markup=keyboard, parse_mode="Markdown")

# --- KINO / FAYL QO'SHISH ---

@main_dp.callback_query(F.data.startswith("add_content_"))
async def add_content_start(call: CallbackQuery, state: FSMContext):
    token = call.data.replace("add_content_", "")
    await state.update_data(active_token=token)
    await call.message.edit_text("Fayl yoki kino uchun **raqamli kod** yuboring (Masalan: `101`):", parse_mode="Markdown")
    await state.set_state(AddContentState.waiting_for_code)

@main_dp.message(AddContentState.waiting_for_code)
async def add_content_code(message: types.Message, state: FSMContext):
    await state.update_data(content_code=message.text.strip())
    await message.answer("Endi o'sha **Fayl, Video, Rasm yoki Dokumentni** yuboring:")
    await state.set_state(AddContentState.waiting_for_file)

@main_dp.message(AddContentState.waiting_for_file)
async def add_content_file(message: types.Message, state: FSMContext):
    data = await state.get_data()
    token = data.get("active_token")
    code = data.get("content_code")

    file_type = "text"
    file_id = ""
    caption = message.caption or message.text or ""

    if message.photo:
        file_type = "photo"
        file_id = message.photo[-1].file_id
    elif message.video:
        file_type = "video"
        file_id = message.video.file_id
    elif message.document:
        file_type = "document"
        file_id = message.document.file_id
    elif message.audio:
        file_type = "audio"
        file_id = message.audio.file_id
    else:
        file_type = "text"

    async with aiosqlite.connect("constructor_database.db") as db:
        await db.execute(
            "INSERT INTO bot_contents (bot_token, content_code, file_id, file_type, caption) VALUES (?, ?, ?, ?, ?)",
            (token, code, file_id, file_type, caption)
        )
        await db.commit()

    await message.answer(f"✅ **{code}** kodli fayl bazaga qo'shildi!", parse_mode="Markdown")
    await state.clear()

# --- TUGMA QO'SHISH ---

@main_dp.callback_query(F.data.startswith("add_btn_"))
async def add_btn_start(call: CallbackQuery, state: FSMContext):
    data_str = call.data.replace("add_btn_", "")
    token, b_type = data_str.rsplit("_", 1)
    
    await state.update_data(active_token=token, btn_type=b_type)
    if b_type == "reply":
        await call.message.edit_text("Asosiy menyuga qo'shiladigan tugma nomini kiriting:")
    else:
        await call.message.edit_text("Karta (donat) tugmasi nomini kiriting:")
    await state.set_state(AddButtonState.waiting_for_name)

@main_dp.message(AddButtonState.waiting_for_name)
async def process_btn_name(message: types.Message, state: FSMContext):
    await state.update_data(btn_name=message.text.strip())
    data = await state.get_data()

    if data.get("btn_type") == "inline":
        await message.answer("Tugma bosilganda ochiladigan **havolani (URL)** yuboring (`https://...`):", parse_mode="Markdown")
    else:
        await message.answer("Tugma bosilganda chiqadigan matn yoki media yuboring:")
    await state.set_state(AddButtonState.waiting_for_value)

@main_dp.message(AddButtonState.waiting_for_value)
async def process_btn_value(message: types.Message, state: FSMContext):
    data = await state.get_data()
    token = data.get("active_token")
    b_type = data.get("btn_type")
    btn_name = data.get("btn_name")

    media_path = None
    media_type = "text"
    val = ""

    if b_type == "inline":
        val = message.text.strip() if message.text else ""
    else:
        if message.photo:
            media_type = "photo"
            file_id = message.photo[-1].file_id
            file = await main_bot.get_file(file_id)
            media_path = f"media/{file_id}.jpg"
            await main_bot.download_file(file.file_path, destination=media_path)
            val = message.caption or ""
        elif message.video:
            media_type = "video"
            file_id = message.video.file_id
            file = await main_bot.get_file(file_id)
            media_path = f"media/{file_id}.mp4"
            await main_bot.download_file(file.file_path, destination=media_path)
            val = message.caption or ""
        elif message.document:
            media_type = "document"
            file_id = message.document.file_id
            file = await main_bot.get_file(file_id)
            ext = os.path.splitext(message.document.file_name)[1] if message.document.file_name else ""
            media_path = f"media/{file_id}{ext}"
            await main_bot.download_file(file.file_path, destination=media_path)
            val = message.caption or ""
        else:
            media_type = "text"
            val = message.text or ""

    async with aiosqlite.connect("constructor_database.db") as db:
        await db.execute(
            "INSERT INTO bot_buttons (bot_token, button_name, reply_text, button_type, url, media_path, media_type) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (token, btn_name, val if b_type == "reply" else "", b_type, val if b_type == "inline" else None, media_path, media_type)
        )
        await db.commit()

    await message.answer(f"✅ **{btn_name}** saqlandi!", parse_mode="Markdown")
    await state.clear()

# --- ADMIN CHAT VA BAN TIZIMI ---

@main_dp.callback_query(F.data.startswith("rep_"))
async def reply_to_user_start(call: CallbackQuery, state: FSMContext):
    parts = call.data.split("_")
    bot_db_id, u_id = parts[1], parts[2]
    
    async with aiosqlite.connect("constructor_database.db") as db:
        async with db.execute("SELECT bot_token FROM user_bots WHERE id = ?", (bot_db_id,)) as cursor:
            row = await cursor.fetchone()
    if not row:
        await call.answer("❌ Bot topilmadi!", show_alert=True)
        return
    c_token = row[0]
    
    async with aiosqlite.connect("constructor_database.db") as db:
        async with db.execute("SELECT user_id FROM user_bots WHERE id = ?", (bot_db_id,)) as cursor:
            adm_row = await cursor.fetchone()
        admin_id = adm_row[0] if adm_row else call.from_user.id
        await db.execute("INSERT OR REPLACE INTO chat_sessions (bot_token, user_id, admin_id) VALUES (?, ?, ?)", (c_token, int(u_id), admin_id))
        await db.commit()

    await state.update_data(rep_token=c_token, rep_user_id=u_id)
    await call.message.answer(f"💬 <b>Chat rejimi:</b>\nFoydalanuvchiga (ID: {u_id}) javobingizni yuboring:", parse_mode="HTML")
    await state.set_state(AdminReplyState.waiting_for_reply_text)

@main_dp.message(AdminReplyState.waiting_for_reply_text)
async def send_reply_to_user(message: types.Message, state: FSMContext):
    data = await state.get_data()
    c_token = data.get("rep_token")
    u_id = int(data.get("rep_user_id"))

    c_bot = Bot(token=c_token)
    try:
        reply_text = message.text or message.caption or "[Media]"
        if message.photo:
            await c_bot.send_photo(u_id, photo=message.photo[-1].file_id, caption=f"👨‍💻 <b>Admin:</b> {reply_text}", parse_mode="HTML")
        elif message.video:
            await c_bot.send_video(u_id, video=message.video.file_id, caption=f"👨‍💻 <b>Admin:</b> {reply_text}", parse_mode="HTML")
        elif message.document:
            await c_bot.send_document(u_id, document=message.document.file_id, caption=f"👨‍💻 <b>Admin:</b> {reply_text}", parse_mode="HTML")
        else:
            await c_bot.send_message(u_id, f"👨‍💻 <b>Admin:</b>\n\n{reply_text}", parse_mode="HTML")
        await message.answer("✅ Javob yuborildi!")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")
    finally:
        await c_bot.session.close()

@main_dp.callback_query(F.data.startswith("ban_"))
async def ban_user_handler(call: CallbackQuery):
    parts = call.data.split("_")
    bot_db_id, u_id = parts[1], parts[2]
    async with aiosqlite.connect("constructor_database.db") as db:
        async with db.execute("SELECT bot_token FROM user_bots WHERE id = ?", (bot_db_id,)) as cursor:
            row = await cursor.fetchone()
    if not row:
        await call.answer("❌ Bot topilmadi!", show_alert=True)
        return
    c_token = row[0]

    async with aiosqlite.connect("constructor_database.db") as db:
        await db.execute("UPDATE child_bot_users SET is_banned = 1 WHERE bot_token = ? AND user_id = ?", (c_token, int(u_id)))
        await db.commit()
    
    await call.answer("🚫 Foydalanuvchi ban qilindi!", show_alert=True)
    await call.message.edit_reply_markup(reply_markup=None)

# --- TUGMA O'CHIRISH VA STATISTIKA ---

@main_dp.callback_query(F.data.startswith("list_btn_"))
async def list_buttons(call: CallbackQuery):
    token = call.data.replace("list_btn_", "")
    async with aiosqlite.connect("constructor_database.db") as db:
        async with db.execute("SELECT id, button_name, button_type FROM bot_buttons WHERE bot_token = ?", (token,)) as cursor:
            buttons = await cursor.fetchall()

    if not buttons:
        await call.message.edit_text("Bu botda hali tugmalar yo'q.")
        return

    kb = [[InlineKeyboardButton(text=f"🗑 [{b[2]}] {b[1]}", callback_data=f"del_btn_{b[0]}_{token}")] for b in buttons]
    kb.append([InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"manage_bot_{token}")])
    await call.message.edit_text("O'chirmoqchi bo'lgan tugmani tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@main_dp.callback_query(F.data.startswith("del_btn_"))
async def delete_button(call: CallbackQuery):
    parts = call.data.split("_")
    btn_id, token = parts[2], parts[3]
    async with aiosqlite.connect("constructor_database.db") as db:
        await db.execute("DELETE FROM bot_buttons WHERE id = ?", (btn_id,))
        await db.commit()
    await call.answer("Tugma o'chirildi!", show_alert=True)
    await list_buttons(call)

@main_dp.callback_query(F.data.startswith("stats_bot_"))
async def bot_stats_handler(call: CallbackQuery):
    token = call.data.replace("stats_bot_", "")
    async with aiosqlite.connect("constructor_database.db") as db:
        async with db.execute("SELECT COUNT(*) FROM child_bot_users WHERE bot_token = ?", (token,)) as c1:
            u_count = (await c1.fetchone())[0]
        async with db.execute("SELECT COUNT(*) FROM bot_buttons WHERE bot_token = ?", (token,)) as c2:
            b_count = (await c2.fetchone())[0]

    await call.message.edit_text(
        f"📊 **Statistika:**\n\n👥 Obunachilar: **{u_count}**\n🔘 Tugmalar: **{b_count}**",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"manage_bot_{token}")]])
    )

@main_dp.callback_query(F.data.startswith("del_userbot_"))
async def delete_userbot(call: CallbackQuery):
    token = call.data.replace("del_userbot_", "")
    async with aiosqlite.connect("constructor_database.db") as db:
        await db.execute("DELETE FROM user_bots WHERE bot_token = ?", (token,))
        await db.execute("DELETE FROM bot_buttons WHERE bot_token = ?", (token,))
        await db.execute("DELETE FROM child_bot_users WHERE bot_token = ?", (token,))
        await db.execute("DELETE FROM chat_sessions WHERE bot_token = ?", (token,))
        await db.execute("DELETE FROM bot_contents WHERE bot_token = ?", (token,))
        await db.commit()
    await call.message.edit_text("✅ Bot o'chirildi.")

# --- RASSILKA TIZIMI ---

@main_dp.callback_query(F.data.startswith("broadcast_"))
async def broadcast_start(call: CallbackQuery, state: FSMContext):
    token = call.data.replace("broadcast_", "")
    await state.update_data(active_token=token)
    await call.message.edit_text("📢 Rassilka uchun xabar matnini yuboring:")
    await state.set_state(BroadcastState.waiting_for_message)

@main_dp.message(BroadcastState.waiting_for_message)
async def broadcast_get_msg(message: types.Message, state: FSMContext):
    data = await state.get_data()
    token = data.get("active_token")
    text = message.text

    async with aiosqlite.connect("constructor_database.db") as db:
        async with db.execute("SELECT user_id FROM child_bot_users WHERE bot_token = ? AND is_banned = 0", (token,)) as cursor:
            users = await cursor.fetchall()
    if not users:
        await message.answer("Obunachilar topilmadi.")
        await state.clear()
        return

    c_bot = Bot(token=token)
    success = 0
    for (u_id,) in users:
        try:
            await c_bot.send_message(u_id, text)
            success += 1
            await asyncio.sleep(0.04)
        except Exception:
            pass
    try:
        await c_bot.session.close()
    except Exception:
        pass

    await message.answer(f"📢 **Rassilka tugadi!** Yetib bordi: {success}", parse_mode="Markdown")
    await state.clear()

# --- CHILD BOT ENGINE (MIJOZ BOTLARI - 4 TA TIL BILAN) ---

async def run_child_bot(token: str):
    try:
        c_bot = Bot(token=token)
        c_dp = Dispatcher()

        TEXTS = {
            "uz": {
                "welcome": "Xush kelibsiz! Kerakli bo'limni tanlang yoki kod yuboring:",
                "lang_selected": "🇺🇿 O'zbek tili tanlandi!",
                "feedback_btn": "✍️ Adminga yozish",
                "lang_btn": "🌐 Tilni o'zgartirish",
                "ask_feedback": "Adminga yozmoqchi bo'lgan xabaringizni yuboring:",
                "feedback_sent": "✅ Xabaringiz adminga yetkazildi!",
                "unknown": "Bunday buyruq yoki kod topilmadi. Menyudan foydalaning.",
                "banned": "🚫 Siz botdan bloklangansiz!"
            },
            "ru": {
                "welcome": "Добро пожаловать! Выберите раздел или отправьте код:",
                "lang_selected": "🇷🇺 Выбран русский язык!",
                "feedback_btn": "✍️ Написать админу",
                "lang_btn": "🌐 Изменить язык",
                "ask_feedback": "Напишите сообщение администратору:",
                "feedback_sent": "✅ Ваше сообщение отправлено админу!",
                "unknown": "Команда или код не найдены. Используйте меню.",
                "banned": "🚫 Вы заблокированы в этом боте!"
            },
            "en": {
                "welcome": "Welcome! Choose a section or send a code:",
                "lang_selected": "🇬🇧 English language selected!",
                "feedback_btn": "✍️ Contact Admin",
                "lang_btn": "🌐 Change Language",
                "ask_feedback": "Send your message to the admin:",
                "feedback_sent": "✅ Your message has been sent to the admin!",
                "unknown": "Command or code not found. Use the menu.",
                "banned": "🚫 You are banned from this bot!"
            },
            "kk": {
                "welcome": "Xoş keldiñiz! Kerekli bólimdi tañlañız:",
                "lang_selected": "🇰🇿 Qazaq tili tañlandı!",
                "feedback_btn": "✍️ Ákimge jazıw",
                "lang_btn": "🌐 Tildi ózgertiw",
                "ask_feedback": "Ákimge xabarıñızdı jazıñız:",
                "feedback_sent": "✅ Xabarıñız ákimge jetkizildi!",
                "unknown": "Bunday buyrıq yamasa kod tabılmadı.",
                "banned": "🚫 Siz botta bloklangansiz!"
            }
        }

        @c_dp.message(Command("start"))
        async def child_start(msg: types.Message):
            async with aiosqlite.connect("constructor_database.db") as db:
                async with db.execute("SELECT lang, is_banned FROM child_bot_users WHERE bot_token = ? AND user_id = ?", (token, msg.from_user.id)) as cursor:
                    row = await cursor.fetchone()

            if row and row[1] == 1:
                await msg.answer("🚫 Siz administrator tomonidan bloklangansiz.")
                return

            if not row:
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="set_lang_uz"),
                     InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang_ru")],
                    [InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en"),
                     InlineKeyboardButton(text="🇰🇿 Қазақша", callback_data="set_lang_kk")]
                ])
                await msg.answer("Tilni tanlang / Choose language:", reply_markup=kb)
            else:
                await send_child_main_menu(msg, row[0])

        @c_dp.callback_query(F.data.startswith("set_lang_"))
        async def set_language(call: CallbackQuery):
            lang = call.data.replace("set_lang_", "")
            async with aiosqlite.connect("constructor_database.db") as db:
                await db.execute("INSERT OR REPLACE INTO child_bot_users (bot_token, user_id, lang, is_banned) VALUES (?, ?, ?, 0)", (token, call.from_user.id, lang))
                await db.commit()
            
            await call.answer(TEXTS[lang]["lang_selected"])
            await send_child_main_menu(call.message, lang)

        async def send_child_main_menu(msg: types.Message, lang: str):
            async with aiosqlite.connect("constructor_database.db") as db:
                async with db.execute("SELECT button_name FROM bot_buttons WHERE bot_token = ? AND button_type = 'reply'", (token,)) as cursor:
                    r_btns = await cursor.fetchall()
                async with db.execute("SELECT button_name, url FROM bot_buttons WHERE bot_token = ? AND button_type = 'inline'", (token,)) as cursor:
                    i_btns = await cursor.fetchall()

            keyboard_rows = [[KeyboardButton(text=r[0])] for r in r_btns]
            keyboard_rows.append([KeyboardButton(text=TEXTS[lang]["feedback_btn"]), KeyboardButton(text=TEXTS[lang]["lang_btn"])])
            
            reply_markup = ReplyKeyboardMarkup(keyboard=keyboard_rows, resize_keyboard=True)
            inline_markup = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=b[0], url=b[1])] for b in i_btns]) if i_btns else None

            await msg.answer(TEXTS[lang]["welcome"], reply_markup=reply_markup)
            if inline_markup:
                await msg.answer("💳 Havolalar:", reply_markup=inline_markup)

        @c_dp.message()
        async def child_message_handler(msg: types.Message, state: FSMContext):
            async with aiosqlite.connect("constructor_database.db") as db:
                async with db.execute("SELECT lang, is_banned FROM child_bot_users WHERE bot_token = ? AND user_id = ?", (token, msg.from_user.id)) as cursor:
                    row = await cursor.fetchone()

            if not row:
                lang = "uz"
            else:
                lang, is_banned = row[0], row[1]
                if is_banned == 1:
                    return

            text = msg.text.strip() if msg.text else ""

            if text in [TEXTS["uz"]["lang_btn"], TEXTS["ru"]["lang_btn"], TEXTS["en"]["lang_btn"], TEXTS["kk"]["lang_btn"]]:
                kb = InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🇺🇿 O'zbekcha", callback_data="set_lang_uz"),
                     InlineKeyboardButton(text="🇷🇺 Русский", callback_data="set_lang_ru")],
                    [InlineKeyboardButton(text="🇬🇧 English", callback_data="set_lang_en"),
                     InlineKeyboardButton(text="🇰🇿 Қазақша", callback_data="set_lang_kk")]
                ])
                await msg.answer("Tilni tanlang / Choose language:", reply_markup=kb)
                return

            if text in [TEXTS["uz"]["feedback_btn"], TEXTS["ru"]["feedback_btn"], TEXTS["en"]["feedback_btn"], TEXTS["kk"]["feedback_btn"]]:
                await state.set_state(FeedbackState.waiting_for_msg)
                await msg.answer(TEXTS[lang]["ask_feedback"])
                return

            current_state = await state.get_state()
            if current_state == FeedbackState.waiting_for_msg.state:
                async with aiosqlite.connect("constructor_database.db") as db:
                    async with db.execute("SELECT user_id, id FROM user_bots WHERE bot_token = ?", (token,)) as cursor:
                        b_row = await cursor.fetchone()
                
                if b_row:
                    bot_owner_id, bot_db_id = b_row[0], b_row[1]
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [
                            InlineKeyboardButton(text="💬 Javob berish", callback_data=f"rep_{bot_db_id}_{msg.from_user.id}"),
                            InlineKeyboardButton(text="🚫 Ban qilish", callback_data=f"ban_{bot_db_id}_{msg.from_user.id}")
                        ]
                    ])
                    try:
                        user_info = f"👤 Foydalanuvchi: {msg.from_user.full_name} (@{msg.from_user.username or 'yoq'})"
                        await c_bot.send_message(bot_owner_id, f"📩 **Yangi xabar!**\n{user_info}\nID: `{msg.from_user.id}`\n\n{text}", reply_markup=kb, parse_mode="Markdown")
                        await msg.answer(TEXTS[lang]["feedback_sent"])
                    except Exception:
                        pass
                await state.clear()
                return

            async with aiosqlite.connect("constructor_database.db") as db:
                async with db.execute("SELECT reply_text, media_path, media_type FROM bot_buttons WHERE bot_token = ? AND button_name = ?", (token, text)) as cursor:
                    btn_data = await cursor.fetchone()

            if btn_data:
                r_text, m_path, m_type = btn_data[0], btn_data[1], btn_data[2]
                if m_type == "photo" and m_path and os.path.exists(m_path):
                    await msg.answer_photo(FSInputFile(m_path), caption=r_text)
                elif m_type == "video" and m_path and os.path.exists(m_path):
                    await msg.answer_video(FSInputFile(m_path), caption=r_text)
                elif m_type == "document" and m_path and os.path.exists(m_path):
                    await msg.answer_document(FSInputFile(m_path), caption=r_text)
                else:
                    await msg.answer(r_text or "Ma'lumot topilmadi.")
                return

            async with aiosqlite.connect("constructor_database.db") as db:
                async with db.execute("SELECT file_id, file_type, caption FROM bot_contents WHERE bot_token = ? AND content_code = ?", (token, text)) as cursor:
                    content = await cursor.fetchone()

            if content:
                f_id, f_type, f_caption = content[0], content[1], content[2]
                if f_type == "photo":
                    await msg.answer_photo(f_id, caption=f_caption)
                elif f_type == "video":
                    await msg.answer_video(f_id, caption=f_caption)
                elif f_type == "document":
                    await msg.answer_document(f_id, caption=f_caption)
                elif f_type == "audio":
                    await msg.answer_audio(f_id, caption=f_caption)
                else:
                    await msg.answer(f_caption or f_id)
                return

            await msg.answer(TEXTS[lang]["unknown"])

    except Exception as e:
        logging.error(f"Child bot error ({token}): {e}")
    finally:
        try:
            await c_bot.session.close()
        except Exception:
            pass

# --- STARTUP VA ASOSIY WEB SERVER LOOP ---

async def on_startup():
    await init_db()
    async with aiosqlite.connect("constructor_database.db") as db:
        async with db.execute("SELECT bot_token FROM user_bots") as cursor:
            tokens = await cursor.fetchall()
    for (token,) in tokens:
        asyncio.create_task(run_child_bot(token))
    logging.info("✅ Barcha botlar bazadan yuklandi va ishga tushirildi!")

async def handle_ping(request):
    return web.Response(text="Bot is running!")

async def web_server():
    app = web.Application()
    app.router.add_get("/", handle_ping)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    port = int(os.environ.get("PORT", 8080))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    print(f"🌐 Web server {port}-portda ishga tushdi!")

async def main():
    await on_startup()
    asyncio.create_task(web_server())
    await main_dp.start_polling(main_bot)

if __name__ == "__main__":
    asyncio.run(main())