
import sqlite3
import datetime
import random
import string
import asyncio
import re
import uuid
from aiogram import Bot, Dispatcher, Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage

# ==================== КОНФИГ ====================
BOT_TOKEN = "8807568631:AAH9KM0Voiw1yqBMpRwJQNGDCZrDNuifVOs"
BOT_USERNAME = "ChuGurVPNbot"

ADMIN_USERNAMES = ["Suguru", "W_u_u_W1", "Dexter"]
ADMIN_PASSWORDS = ["2a3d4g5j", "2a3D4g5J"]
PAYMENT_CARD = "2200153288930010"
PAYMENT_BANK = "Альфа-Банк"

# Промокоды
PROMOCODES = {
    "Banana": {"discount": 15, "name": "Banana (15%)", "type": "discount"},
    "Batek": {"discount": 100, "name": "Batek (навсегда)", "type": "forever"},
    "2026": {"discount": 10, "name": "2026 (10%)", "type": "discount"},
    "dildo": {"discount": 5, "name": "dildo (5%)", "type": "discount"},
    "ВПН": {"discount": 15, "name": "ВПН (15%)", "type": "discount"},
    "Четвертый": {"discount": 4, "name": "Четвертый (4%)", "type": "discount"},
    "Пятый": {"discount": 5, "name": "Пятый (5%)", "type": "discount"},
    "42": {"discount": 42, "name": "42 (42%)", "type": "discount"},
    "Сигна": {"discount": 0, "name": "Сигна (создатели)", "type": "special"},
    "Чугур": {"discount": 20, "name": "Чугур (20%)", "type": "discount"},
    "Дерево": {"discount": 0, "name": "Дерево (фото)", "type": "special"},
    "Школа": {"discount": 9, "name": "Школа (9%)", "type": "discount"},
    "11класс": {"discount": 11, "name": "11класс (11%)", "type": "discount"},
    "Сладость": {"discount": 25, "name": "Сладость (25%)", "type": "discount"},
    "ЯраЯраМомент": {"discount": 50, "name": "ЯраЯраМомент (50%)", "type": "discount"},
    "Паспорт": {"discount": 14, "name": "Паспорт (14%)", "type": "discount"},
}

TARIFFS = {
    "14_days": {"name": "14 дней", "price": 50, "days": 14},
    "1_month": {"name": "1 месяц", "price": 90, "days": 30},
    "2_months": {"name": "2 месяца", "price": 180, "days": 60},
    "6_months": {"name": "6 месяцев", "price": 800, "days": 180},
    "1_year": {"name": "1 год", "price": 1200, "days": 365},
}

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# ==================== БАЗА ДАННЫХ ====================
def init_db():
    conn = sqlite3.connect("vpn_bot.db")
    cur = conn.cursor()

    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            personal_code TEXT UNIQUE,
            subscription_end TEXT,
            subscription_link TEXT,
            is_admin INTEGER DEFAULT 0,
            has_active_sub INTEGER DEFAULT 0,
            ref_code TEXT UNIQUE,
            ref_by INTEGER,
            ref_bonus_given INTEGER DEFAULT 0,
            promo_used TEXT DEFAULT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            personal_code TEXT,
            tariff TEXT,
            price INTEGER,
            days INTEGER,
            discount INTEGER DEFAULT 0,
            promo_code TEXT DEFAULT NULL,
            status TEXT DEFAULT 'waiting_payment',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cur.execute("""
        CREATE TABLE IF NOT EXISTS promo_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            personal_code TEXT,
            promo_code TEXT,
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

# ==================== ФУНКЦИИ БД ====================
def get_user(user_id):
    conn = sqlite3.connect("vpn_bot.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cur.fetchone()
    conn.close()
    return user

def get_user_by_ref_code(ref_code):
    conn = sqlite3.connect("vpn_bot.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE ref_code = ?", (ref_code,))
    user = cur.fetchone()
    conn.close()
    return user

def is_admin(user_id):
    user = get_user(user_id)
    return user is not None and user[6] == 1

def add_user(user_id, username, first_name, ref_code=None):
    conn = sqlite3.connect("vpn_bot.db")
    cur = conn.cursor()
    existing = get_user(user_id)
    if not existing:
        code = generate_unique_code()
        ref = str(uuid.uuid4())[:8]
        ref_by = None
        if ref_code:
            referrer = get_user_by_ref_code(ref_code)
            if referrer and referrer[0] != user_id:
                ref_by = referrer[0]
        cur.execute(
            "INSERT INTO users (user_id, username, first_name, personal_code, ref_code, ref_by) VALUES (?, ?, ?, ?, ?, ?)",
            (user_id, username, first_name, code, ref, ref_by)
        )
        conn.commit()
        conn.close()
        return True, code, ref, ref_by
    conn.close()
    return False, existing[3], existing[8], existing[9]

def generate_unique_code():
    conn = sqlite3.connect("vpn_bot.db")
    cur = conn.cursor()
    cur.execute("SELECT personal_code FROM users")
    existing_codes = {row[0] for row in cur.fetchall()}
    conn.close()
    while True:
        code = ''.join(random.choices(string.digits, k=5))
        if code not in existing_codes:
            return code

def set_admin(user_id):
    conn = sqlite3.connect("vpn_bot.db")
    cur = conn.cursor()
    cur.execute("UPDATE users SET is_admin = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def get_admins():
    conn = sqlite3.connect("vpn_bot.db")
    cur = conn.cursor()
    cur.execute("SELECT user_id FROM users WHERE is_admin = 1")
    admins = [row[0] for row in cur.fetchall()]
    conn.close()
    return admins

def check_promo_used(user_id, promo_code):
    user = get_user(user_id)
    if user and user[11]:
        used_promos = user[11].split(",")
        if promo_code in used_promos:
            return True
    return False

def mark_promo_used(user_id, promo_code):
    conn = sqlite3.connect("vpn_bot.db")
    cur = conn.cursor()
    user = get_user(user_id)
    if user and user[11]:
        new_promos = user[11] + f",{promo_code}"
    else:
        new_promos = promo_code
    cur.execute("UPDATE users SET promo_used = ? WHERE user_id = ?", (new_promos, user_id))
    conn.commit()
    conn.close()

def create_payment(user_id, code, tariff, price, days, discount=0, promo_code=None):
    conn = sqlite3.connect("vpn_bot.db")
    cur = conn.cursor()
    final_price = price - (price * discount // 100)
    cur.execute(
        "INSERT INTO payments (user_id, personal_code, tariff, price, days, discount, promo_code) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (user_id, code, tariff, final_price, days, discount, promo_code)
    )
    conn.commit()
    conn.close()
    return final_price

def create_promo_request(user_id, code, promo_code):
    conn = sqlite3.connect("vpn_bot.db")
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO promo_requests (user_id, personal_code, promo_code) VALUES (?, ?, ?)",
        (user_id, code, promo_code)
    )
    conn.commit()
    conn.close()

def confirm_payment(user_id):
    conn = sqlite3.connect("vpn_bot.db")
    cur = conn.cursor()
    cur.execute("UPDATE payments SET status = 'pending' WHERE user_id = ? AND status = 'waiting_payment'", (user_id,))
    conn.commit()
    conn.close()

def get_user_pending_payment(user_id):
    conn = sqlite3.connect("vpn_bot.db")
    cur = conn.cursor()
    cur.execute("SELECT * FROM payments WHERE user_id = ? AND status = 'waiting_payment' ORDER BY created_at DESC LIMIT 1", (user_id,))
    payment = cur.fetchone()
    conn.close()
    return payment

def get_pending_payments():
    conn = sqlite3.connect("vpn_bot.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT p.user_id, p.personal_code, u.username, p.tariff, p.price, p.days, p.discount, p.promo_code 
        FROM payments p JOIN users u ON p.user_id = u.user_id 
        WHERE p.status = 'pending'
    """)
    pending = cur.fetchall()
    conn.close()
    return pending

def get_pending_promo_requests():
    conn = sqlite3.connect("vpn_bot.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT pr.user_id, pr.personal_code, u.username, pr.promo_code 
        FROM promo_requests pr JOIN users u ON pr.user_id = u.user_id 
        WHERE pr.status = 'pending'
    """)
    requests = cur.fetchall()
    conn.close()
    return requests

def activate_forever_subscription(user_id, link):
    end_date_str = "31:12:2099 23:59"
    conn = sqlite3.connect("vpn_bot.db")
    cur = conn.cursor()
    cur.execute(
        "UPDATE users SET subscription_end = ?, subscription_link = ?, has_active_sub = 1 WHERE user_id = ?",
        (end_date_str, link, user_id)
    )
    cur.execute("UPDATE promo_requests SET status = 'approved' WHERE user_id = ? AND status = 'pending'", (user_id,))
    conn.commit()
    conn.close()
    return end_date_str

def activate_subscription(user_id, link, end_date_str, days):
    conn = sqlite3.connect("vpn_bot.db")
    cur = conn.cursor()
    user = get_user(user_id)
    if user and user[4]:
        current_end = datetime.datetime.strptime(user[4], "%d:%m:%Y %H:%M")
        new_end = current_end + datetime.timedelta(days=days)
        new_end_str = new_end.strftime("%d:%m:%Y %H:%M")
    else:
        new_end = datetime.datetime.now() + datetime.timedelta(days=days)
        new_end_str = new_end.strftime("%d:%m:%Y %H:%M")
    cur.execute(
        "UPDATE users SET subscription_end = ?, subscription_link = ?, has_active_sub = 1 WHERE user_id = ?",
        (new_end_str, link, user_id)
    )
    cur.execute("UPDATE payments SET status = 'approved' WHERE user_id = ? AND status = 'pending'", (user_id,))
    conn.commit()
    conn.close()
    return new_end_str

def reject_payment_db(user_id):
    conn = sqlite3.connect("vpn_bot.db")
    cur = conn.cursor()
    cur.execute("UPDATE payments SET status = 'rejected' WHERE user_id = ? AND status = 'pending'", (user_id,))
    conn.commit()
    conn.close()

def reject_promo_request(user_id):
    conn = sqlite3.connect("vpn_bot.db")
    cur = conn.cursor()
    cur.execute("UPDATE promo_requests SET status = 'rejected' WHERE user_id = ? AND status = 'pending'", (user_id,))
    conn.commit()
    conn.close()

def get_all_active_subscriptions():
    conn = sqlite3.connect("vpn_bot.db")
    cur = conn.cursor()
    cur.execute("""
        SELECT user_id, personal_code, username, subscription_end, subscription_link 
        FROM users WHERE has_active_sub = 1
    """)
    subs = cur.fetchall()
    conn.close()
    return subs

def cancel_subscription(user_id):
    conn = sqlite3.connect("vpn_bot.db")
    cur = conn.cursor()
    cur.execute("UPDATE users SET subscription_end = NULL, subscription_link = NULL, has_active_sub = 0 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def extend_subscription(user_id, days):
    conn = sqlite3.connect("vpn_bot.db")
    cur = conn.cursor()
    user = get_user(user_id)
    if user and user[4]:
        current_end = datetime.datetime.strptime(user[4], "%d:%m:%Y %H:%M")
        new_end = current_end + datetime.timedelta(days=days)
        new_end_str = new_end.strftime("%d:%m:%Y %H:%M")
        cur.execute("UPDATE users SET subscription_end = ? WHERE user_id = ?", (new_end_str, user_id))
    else:
        new_end = datetime.datetime.now() + datetime.timedelta(days=days)
        new_end_str = new_end.strftime("%d:%m:%Y %H:%M")
        cur.execute("UPDATE users SET subscription_end = ?, has_active_sub = 1 WHERE user_id = ?", (new_end_str, user_id))
    conn.commit()
    conn.close()

def give_ref_bonus(user_id):
    conn = sqlite3.connect("vpn_bot.db")
    cur = conn.cursor()
    cur.execute("UPDATE users SET ref_bonus_given = 1 WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

# ==================== КЛАВИАТУРЫ ====================
def main_menu_keyboard(user_id):
    buttons = [
        [InlineKeyboardButton(text="💳 Выбрать тариф", callback_data="select_tariff")],
        [InlineKeyboardButton(text="🎁 Промо", callback_data="promo_menu")],
        [InlineKeyboardButton(text="👥 Реферальная ссылка", callback_data="ref_info")],
        [InlineKeyboardButton(text="🔐 Админ панель", callback_data="admin_panel")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)

def tariff_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📅 14 дней - 50₽", callback_data="tariff_14_days")],
        [InlineKeyboardButton(text="📅 1 месяц - 90₽", callback_data="tariff_1_month")],
        [InlineKeyboardButton(text="📅 2 месяца - 180₽", callback_data="tariff_2_months")],
        [InlineKeyboardButton(text="📅 6 месяцев - 800₽", callback_data="tariff_6_months")],
        [InlineKeyboardButton(text="📅 1 год - 1200₽", callback_data="tariff_1_year")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])

def i_paid_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Я оплатил", callback_data="i_paid")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])

def admin_decision_keyboard(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Выдать ссылку", callback_data=f"approve_{user_id}"),
            InlineKeyboardButton(text="❌ Отказ", callback_data=f"reject_{user_id}")
        ]
    ])

def admin_panel_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📋 Активные подписки", callback_data="admin_list_subs")],
        [InlineKeyboardButton(text="📝 Ожидают модерации", callback_data="admin_list_pending")],
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])

def subscription_action_keyboard(user_id):
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🔒 Забрать подписку", callback_data=f"take_{user_id}"),
            InlineKeyboardButton(text="🔄 Продлить +1 день", callback_data=f"keep_{user_id}")
        ]
    ])

def back_to_main_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Главное меню", callback_data="back_to_main")]
    ])

# ==================== FSM ====================
class AdminAuth(StatesGroup):
    waiting_for_username = State()
    waiting_for_password = State()

class AdminSendLink(StatesGroup):
    waiting_for_link = State()
    waiting_for_date = State()

class AdminRejectReason(StatesGroup):
    waiting_for_reason = State()

class AdminTakeReason(StatesGroup):
    waiting_for_reason = State()

class PromoInput(StatesGroup):
    waiting_for_code = State()

admin_temp_data = {}
user_promo_cache = {}

# ==================== ХЕНДЛЕРЫ ====================

@router.message(CommandStart())
async def cmd_start(message: Message):
    user_id = message.from_user.id
    username = message.from_user.username or "unknown"
    first_name = message.from_user.first_name or "unknown"

    ref_code = None
    args = message.text.split()
    if len(args) > 1:
        ref_code = args[1]

    is_new, code, ref, ref_by = add_user(user_id, username, first_name, ref_code)

    if is_new:
        admins = get_admins()
        for admin_id in admins:
            try:
                msg = f"🆕 Новый пользователь!\n👤 @{username}\n📛 {first_name}\n🔑 Код: {code}"
                if ref_by:
                    ref_user = get_user(ref_by)
                    if ref_user:
                        msg += f"\n👥 Пришёл по реф. ссылке от @{ref_user[1]}"
                await bot.send_message(admin_id, msg)
            except:
                pass

        if ref_by:
            ref_user = get_user(ref_by)
            if ref_user and ref_user[10] == 0:
                give_ref_bonus(ref_by)
                extend_subscription(ref_by, 1)
                try:
                    await bot.send_message(ref_by, f"🎁 По вашей ссылке зарегистрировался @{username}\n+1 день подписки!")
                except:
                    pass
                for admin_id in admins:
                    try:
                        await bot.send_message(admin_id, f"👥 Реферал! @{ref_user[1]} пригласил @{username}\n+1 день начислен!")
                    except:
                        pass

    await message.answer(
        f"👋 Добро пожаловать в ChugurVPN!\n\n"
        f"⚠️ Ваш персональный номер: {code}\n"
        f"ЗАПОМНИТЕ ЕГО!\n\n"
        f"Выберите действие:",
        reply_markup=main_menu_keyboard(user_id)
    )

# ==================== ПРОМО ====================
@router.callback_query(F.data == "promo_menu")
async def promo_menu(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.answer(
        "🎁 Введите секретный промокод:\n\n"
        "Если у вас есть промокод — введите его и получите бонус!\n"
        "Один промокод можно использовать только 1 раз.\n\n"
        "Для отмены нажмите /start"
    )
    await state.set_state(PromoInput.waiting_for_code)

@router.message(PromoInput.waiting_for_code)
async def promo_check(message: Message, state: FSMContext):
    promo_code = message.text.strip()
    user_id = message.from_user.id
    user = get_user(user_id)
    code = user[3]
    
    promo = PROMOCODES.get(promo_code)
    if not promo:
        await message.answer(
            "❌ Такого промокода не существует!\n\n"
            "Проверьте правильность ввода и попробуйте снова.\n"
            "Для отмены нажмите /start"
        )
        return
    
    if check_promo_used(user_id, promo_code):
        await message.answer(
            "❌ Вы уже использовали этот промокод!\n"
            "Один промокод можно использовать только 1 раз.\n\n"
            "Нажмите /start чтобы вернуться в меню."
        )
        await state.clear()
        return
    
    # Специальные промокоды (Сигна, Дерево) - отправляем админам
    if promo["type"] == "special":
        create_promo_request(user_id, code, promo_code)
        mark_promo_used(user_id, promo_code)
        
        admins = get_admins()
        for admin_id in admins:
            try:
                await bot.send_message(
                    admin_id,
                    f"🎁 Специальный промокод!\n\n"
                    f"👤 Пользователь @{message.from_user.username}\n"
                    f"🔑 Код: {code}\n"
                    f"📌 Промокод: {promo['name']}\n"
                    f"Нужно выдать ссылку.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="✅ Выдать ссылку", callback_data=f"forever_{user_id}")]
                    ])
                )
            except:
                pass
        
        await state.clear()
        await message.answer(
            f"✅ Промокод {promo['name']} активирован!\n"
            f"Ожидайте — администратор выдаст вам ссылку.",
            reply_markup=back_to_main_keyboard()
        )
        return
    
    # Batek (навсегда)
    if promo["type"] == "forever":
        create_promo_request(user_id, code, promo_code)
        mark_promo_used(user_id, promo_code)
        
        admins = get_admins()
        for admin_id in admins:
            try:
                await bot.send_message(
                    admin_id,
                    f"🎁 Промокод BATEK!\n\n"
                    f"👤 Пользователь @{message.from_user.username}\n"
                    f"🔑 Код: {code}\n"
                    f"📌 Ввел промокод на НАВСЕГДА!\n"
                    f"Нужно выдать ссылку.",
                    reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="✅ Выдать ссылку (Batek)", callback_data=f"forever_{user_id}")]
                    ])
                )
            except:
                pass
        
        await state.clear()
        await message.answer(
            "✅ Промокод Batek активирован!\n"
            "Подписка НАВСЕГДА!\n\n"
            "Ожидайте — администратор выдаст вам ссылку.",
            reply_markup=back_to_main_keyboard()
        )
        return
    
    # Обычные промокоды со скидкой
    user_promo_cache[user_id] = {
        "code": promo_code,
        "discount": promo["discount"],
        "name": promo["name"]
    }
    
    await state.clear()
    await message.answer(
        f"✅ Промокод активирован!\n"
        f"Скидка: {promo['discount']}%\n\n"
        f"Теперь выберите тариф — скидка применится автоматически:",
        reply_markup=tariff_keyboard()
    )

# ==================== ВЫБОР ТАРИФА ====================
@router.callback_query(F.data == "select_tariff")
async def select_tariff(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("📋 Выберите тариф:", reply_markup=tariff_keyboard())

@router.callback_query(F.data.startswith("tariff_"))
async def tariff_selected(callback: CallbackQuery):
    tariff_key = callback.data.replace("tariff_", "")
    tariff = TARIFFS.get(tariff_key)
    if not tariff:
        await callback.answer("Тариф не найден!", show_alert=True)
        return

    user_id = callback.from_user.id
    user = get_user(user_id)
    code = user[3]
    
    promo_data = user_promo_cache.get(user_id)
    discount = 0
    promo_code = None
    promo_name = None
    
    if promo_data:
        discount = promo_data["discount"]
        promo_code = promo_data["code"]
        promo_name = promo_data["name"]
        mark_promo_used(user_id, promo_code)
        del user_promo_cache[user_id]
    
    final_price = create_payment(user_id, code, tariff["name"], tariff["price"], tariff["days"], discount, promo_code)
    
    msg = f"📅 Тариф: {tariff['name']}\n"
    if discount > 0:
        msg += f"💰 Цена без скидки: {tariff['price']}₽\n"
        msg += f"🎁 Скидка по промокоду: {discount}%\n"
        msg += f"💳 Итого к оплате: {final_price}₽\n\n"
    else:
        msg += f"💰 Сумма: {final_price}₽\n\n"
    
    msg += f"🏦 Банк: {PAYMENT_BANK}\n"
    msg += f"💳 Карта: {PAYMENT_CARD}\n\n"
    msg += f"📝 В переводе укажите код: {code}\n\n"
    msg += f"После оплаты нажмите «Я оплатил»"

    await callback.answer()
    await callback.message.answer(msg, reply_markup=i_paid_keyboard())

# ==================== Я ОПЛАТИЛ ====================
@router.callback_query(F.data == "i_paid")
async def i_paid(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    code = user[3]

    payment = get_user_pending_payment(user_id)
    if not payment:
        await callback.answer("Сначала выберите тариф!", show_alert=True)
        return

    confirm_payment(user_id)

    admins = get_admins()
    for admin_id in admins:
        try:
            msg = f"💳 Новая оплата!\n\n"
            msg += f"👤 Ник: @{callback.from_user.username}\n"
            msg += f"🔑 Код: {code}\n"
            msg += f"📅 Тариф: {payment[3]}\n"
            
            if payment[6] and payment[6] > 0:
                msg += f"🎁 Промокод: {payment[7]} (-{payment[6]}%)\n"
                msg += f"💰 Итого: {payment[4]}₽\n"
            else:
                msg += f"💰 Сумма: {payment[4]}₽\n"
            
            msg += f"⏳ Дней: {payment[5]}"
            
            await bot.send_message(admin_id, msg, reply_markup=admin_decision_keyboard(user_id))
        except:
            pass

    await callback.answer("✅ Платёж отправлен на модерацию!", show_alert=True)
    await callback.message.answer("⏳ Ожидайте подтверждения...", reply_markup=back_to_main_keyboard())

# ==================== РЕФЕРАЛЬНАЯ ССЫЛКА ====================
@router.callback_query(F.data == "ref_info")
async def ref_info(callback: CallbackQuery):
    user_id = callback.from_user.id
    user = get_user(user_id)
    ref_code = user[8]
    ref_link = f"https://t.me/{BOT_USERNAME}?start={ref_code}"
    await callback.answer()
    await callback.message.answer(
        f"👥 Ваша реферальная ссылка:\n\n{ref_link}\n\n🎁 +1 день за друга!",
        reply_markup=back_to_main_keyboard()
    )

@router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: CallbackQuery):
    await callback.answer()
    await callback.message.answer("🏠 Главное меню:", reply_markup=main_menu_keyboard(callback.from_user.id))

# ==================== АДМИН ПАНЕЛЬ ====================
@router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    
    if is_admin(user_id):
        await callback.answer()
        await callback.message.answer("🔐 Админ-панель:", reply_markup=admin_panel_keyboard())
        return
    
    await callback.answer()
    await callback.message.answer("👤 Введите никнейм админа:")
    await state.set_state(AdminAuth.waiting_for_username)

@router.message(AdminAuth.waiting_for_username)
async def check_username(message: Message, state: FSMContext):
    if message.text in ADMIN_USERNAMES:
        await state.update_data(username=message.text)
        await message.answer("🔑 Введите пароль:")
        await state.set_state(AdminAuth.waiting_for_password)
    else:
        await message.answer("❌ Неверный никнейм! Попробуйте ещё раз.")

@router.message(AdminAuth.waiting_for_password)
async def check_password(message: Message, state: FSMContext):
    if message.text in ADMIN_PASSWORDS:
        user_id = message.from_user.id
        set_admin(user_id)
        await message.answer("✅ Вы стали администратором! Доступ сохранён навсегда.", reply_markup=admin_panel_keyboard())
        await state.clear()
    else:
        await message.answer("❌ Неверный пароль! Попробуйте ещё раз.")

# ==================== АДМИН: СПИСКИ ====================
@router.callback_query(F.data == "admin_list_subs")
async def admin_list_subs(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    await callback.answer()
    subs = get_all_active_subscriptions()
    
    if not subs:
        await callback.message.answer("📭 Нет активных подписок.")
        return
    
    for user_id, code, username, end_date, link in subs:
        await callback.message.answer(
            f"📋 Активная подписка:\n\n"
            f"🔑 Код: {code}\n"
            f"👤 Ник: @{username}\n"
            f"🔗 Ссылка: {link}\n"
            f"⏰ Истекает: {end_date}",
            reply_markup=subscription_action_keyboard(user_id)
        )

@router.callback_query(F.data == "admin_list_pending")
async def admin_list_pending(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("❌ Нет доступа!", show_alert=True)
        return
    
    await callback.answer()
    pending = get_pending_payments()
    promo_requests = get_pending_promo_requests()
    
    if not pending and not promo_requests:
        await callback.message.answer("📭 Нет ожидающих модерации.")
        return
    
    for user_id, code, username, promo_code in promo_requests:
        promo = PROMOCODES.get(promo_code, {})
        promo_name = promo.get("name", promo_code)
        await callback.message.answer(
            f"🎁 Специальный промокод!\n\n"
            f"👤 Ник: @{username}\n"
            f"🔑 Код: {code}\n"
            f"📌 Промокод: {promo_name}\n"
            f"Нужно выдать ссылку.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="✅ Выдать ссылку", callback_data=f"forever_{user_id}")]
            ])
        )
    
    for user_id, code, username, tariff, price, days, discount, promo in pending:
        msg = f"📝 Ожидает модерации:\n\n"
        msg += f"👤 Ник: @{username}\n"
        msg += f"🔑 Код: {code}\n"
        msg += f"📅 Тариф: {tariff}\n"
        if discount and discount > 0:
            msg += f"🎁 Промокод: {promo} (-{discount}%)\n"
        msg += f"💰 Сумма: {price}₽\n"
        msg += f"⏳ Дней: {days}"
        
        await callback.message.answer(msg, reply_markup=admin_decision_keyboard(user_id))

# ==================== АДМИН: ВЫДАТЬ ССЫЛКУ ====================
@router.callback_query(F.data.startswith("approve_"))
async def approve_payment(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[1])
    admin_temp_data[callback.from_user.id] = {"user_id": user_id, "type": "normal"}
    await callback.answer()
    await callback.message.answer("🔗 Отправьте ссылку:")
    await state.set_state(AdminSendLink.waiting_for_link)

@router.callback_query(F.data.startswith("forever_"))
async def forever_approve(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[1])
    admin_temp_data[callback.from_user.id] = {"user_id": user_id, "type": "forever"}
    await callback.answer()
    await callback.message.answer("🔗 Отправьте ссылку:")
    await state.set_state(AdminSendLink.waiting_for_link)

@router.message(AdminSendLink.waiting_for_link)
async def get_link(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    data = admin_temp_data.get(admin_id, {})
    data["link"] = message.text
    admin_temp_data[admin_id] = data
    
    if data.get("type") == "forever":
        user_id = data.get("user_id")
        if user_id:
            activate_forever_subscription(user_id, message.text)
            try:
                await bot.send_message(user_id, f"✅ Подписка активирована НАВСЕГДА!\n\n{message.text}")
                await message.answer("✅ Вечная подписка выдана!")
            except:
                await message.answer("❌ Ошибка отправки.")
        await state.clear()
        return
    
    now = datetime.datetime.now()
    await message.answer(
        f"📅 Дата истечения (ДД:ММ:ГГГГ ЧЧ:ММ):\nПример: {now.strftime('%d:%m:%Y %H:%M')}"
    )
    await state.set_state(AdminSendLink.waiting_for_date)

@router.message(AdminSendLink.waiting_for_date)
async def get_date_and_send(message: Message, state: FSMContext):
    admin_id = message.from_user.id
    data = admin_temp_data.get(admin_id, {})
    user_id = data.get("user_id")
    link = data.get("link")
    
    if not re.match(r"^\d{2}:\d{2}:\d{4} \d{2}:\d{2}$", message.text):
        await message.answer("❌ Неверный формат! ДД:ММ:ГГГГ ЧЧ:ММ")
        return
    
    try:
        end_date = datetime.datetime.strptime(message.text, "%d:%m:%Y %H:%M")
        end_date_str = end_date.strftime("%d:%m:%Y %H:%M")
    except:
        await message.answer("❌ Некорректная дата!")
        return
    
    if user_id:
        conn = sqlite3.connect("vpn_bot.db")
        cur = conn.cursor()
        cur.execute("SELECT days FROM payments WHERE user_id = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1", (user_id,))
        payment = cur.fetchone()
        conn.close()
        days = payment[0] if payment else 3
        
        activate_subscription(user_id, link, end_date_str, days)
        
        try:
            await bot.send_message(user_id, f"✅ Подписка активирована!\n\n{link}\n\n⏰ До: {end_date_str}")
            await message.answer(f"✅ Готово! До {end_date_str}")
        except:
            await message.answer("❌ Ошибка отправки.")
    
    await state.clear()

# ==================== АДМИН: ОТКАЗ ====================
@router.callback_query(F.data.startswith("reject_"))
async def reject_payment(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[1])
    await state.update_data(user_id=user_id)
    await callback.answer()
    await callback.message.answer("📝 Причина отказа:")
    await state.set_state(AdminRejectReason.waiting_for_reason)

@router.message(AdminRejectReason.waiting_for_reason)
async def send_reject(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("user_id")
    if user_id:
        reject_payment_db(user_id)
        reject_promo_request(user_id)
        try:
            await bot.send_message(user_id, f"❌ Отклонено.\nПричина: {message.text}")
            await message.answer("✅ Уведомление отправлено!")
        except:
            await message.answer("❌ Ошибка.")
    await state.clear()

# ==================== АДМИН: ЗАБРАТЬ ПОДПИСКУ ====================
@router.callback_query(F.data.startswith("take_"))
async def take_subscription_start(callback: CallbackQuery, state: FSMContext):
    user_id = int(callback.data.split("_")[1])
    await state.update_data(user_id=user_id)
    await callback.answer()
    await callback.message.answer("📝 Причина:")
    await state.set_state(AdminTakeReason.waiting_for_reason)

@router.message(AdminTakeReason.waiting_for_reason)
async def take_subscription_finish(message: Message, state: FSMContext):
    data = await state.get_data()
    user_id = data.get("user_id")
    if user_id:
        cancel_subscription(user_id)
        try:
            await bot.send_message(user_id, f"⏰ Подписка закончилась.\nПричина: {message.text}\n\nВыберите тариф для продления.", reply_markup=back_to_main_keyboard())
            await message.answer("✅ Подписка забрана.")
        except:
            await message.answer("❌ Ошибка.")
    await state.clear()

# ==================== АДМИН: ПРОДЛИТЬ ====================
@router.callback_query(F.data.startswith("keep_"))
async def keep_subscription(callback: CallbackQuery):
    user_id = int(callback.data.split("_")[1])
    extend_subscription(user_id, 1)
    try:
        await bot.send_message(user_id, "🎁 +1 день!")
        await callback.answer("✅ Продлено!", show_alert=True)
    except:
        await callback.answer("❌ Ошибка.", show_alert=True)

# ==================== ЗАПУСК ====================
async def main():
    print("=== БОТ ЗАПУЩЕН ===")
    init_db()
    dp.include_router(router)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
