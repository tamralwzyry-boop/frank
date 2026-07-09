import os
import sys
import subprocess 

# ================================================================
# تثبيت المكتبات الناقصة تلقائياً
# ================================================================
REQUIRED = {
    'aiogram':  'aiogram==2.25.2',
    'aiohttp':  'aiohttp',
}

def install_if_missing():
    for module, package in REQUIRED.items():
        try:
            __import__(module)
        except ImportError:
            print(f"[+] تثبيت {package}...")
            subprocess.check_call(
                [sys.executable, '-m', 'pip', 'install', package,
                 '--break-system-packages', '-q'],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
            print(f"[✓] تم تثبيت {package}")

install_if_missing()

import sqlite3
import logging
import asyncio
import random
import string
import aiohttp
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import LabeledPrice, ContentType

# ================================================================
# الإعدادات
# ================================================================
def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f"متغير البيئة {name} غير موجود. حدده قبل تشغيل البوت، مثال:\n"
            f"  export {name}=\"...\""
        )
    return value

API_TOKEN         = _require_env('BOT_API_TOKEN')
SMM_KEY           = _require_env('SMM_API_KEY')

ADMIN_ID          = 7450173654
BOT_USERNAME      = 'naqaqbot'
SUB_ADMIN_IDS     = []
SUPPORT_USERNAME  = 'Q_D_OS'
CODES_CHANNEL     = '@xx3vz'
SUBSCRIBE_CHANNELS = ['@N_A_NQ', '@xx3vz']

# ── DarkFollow API ──────────────────────────────────────────────
SMM_URL = 'https://darkfollow.shop/api/v2'

# سعر النقاط: كل عضو/متابع = X نقطة
POINTS_PER_UNIT = 2
MIN_ORDER       = 100   # أقل طلب

BASE_DIR     = os.path.dirname(os.path.abspath(__file__))
DB_PATH      = os.path.join(BASE_DIR, 'points_bot.db')
SESSIONS_DIR = os.path.join(BASE_DIR, 'sessions')
os.makedirs(SESSIONS_DIR, exist_ok=True)

logging.basicConfig(level=logging.INFO)
bot     = Bot(token=API_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp      = Dispatcher(bot, storage=storage)

# كاش الخدمات من API
smm_services_cache: list = []

# ================================================================
# قاعدة البيانات
# ================================================================
conn   = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
cursor.execute("PRAGMA journal_mode=WAL;")
cursor.execute("PRAGMA synchronous=FULL;")

def init_db():
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY,
            username TEXT,
            points INTEGER DEFAULT 0,
            verified INTEGER DEFAULT 0,
            last_game_time TIMESTAMP DEFAULT NULL,
            referred_by INTEGER DEFAULT NULL
        );
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            service TEXT,
            members INTEGER,
            points_spent INTEGER,
            status TEXT DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS smm_orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            platform TEXT,
            service_id INTEGER,
            service_name TEXT,
            link TEXT,
            quantity INTEGER,
            points_spent INTEGER,
            smm_order_id TEXT,
            order_code TEXT UNIQUE,
            status TEXT DEFAULT 'pending',
            start_count INTEGER DEFAULT 0,
            remains INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS gift_codes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT UNIQUE,
            points INTEGER,
            max_uses INTEGER,
            used_count INTEGER DEFAULT 0,
            created_by INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE IF NOT EXISTS config (
            key TEXT PRIMARY KEY,
            value TEXT
        );
    ''')
    conn.commit()
    cursor.execute("INSERT OR IGNORE INTO config (key, value) VALUES ('total_orders', '0')")
    conn.commit()

init_db()

# ================================================================
# دوال قاعدة البيانات
# ================================================================
def get_user_points(uid):
    cursor.execute("SELECT points FROM users WHERE id=?", (uid,))
    r = cursor.fetchone()
    return r[0] if r else 0

def add_user_if_not_exists(uid, username, referrer=None):
    cursor.execute("SELECT id FROM users WHERE id=?", (uid,))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (id, username, points, verified, referred_by) VALUES (?,?,0,0,?)",
            (uid, username, referrer)
        )
        if referrer and referrer != uid:
            cursor.execute("UPDATE users SET points = points + 30 WHERE id=?", (referrer,))
        cursor.execute("UPDATE users SET points = points + 5 WHERE id=?", (uid,))
        conn.commit()

def set_user_verified(uid):
    cursor.execute("UPDATE users SET verified=1 WHERE id=?", (uid,))
    conn.commit()

def is_user_verified(uid):
    cursor.execute("SELECT verified FROM users WHERE id=?", (uid,))
    r = cursor.fetchone()
    return r and r[0] == 1

def is_admin(uid):
    return uid == ADMIN_ID or uid in SUB_ADMIN_IDS

def get_total_orders():
    cursor.execute("SELECT value FROM config WHERE key='total_orders'")
    r = cursor.fetchone()
    return int(r[0]) if r else 0

def increment_total_orders():
    cursor.execute("UPDATE config SET value = value + 1 WHERE key='total_orders'")
    conn.commit()

def generate_order_code():
    while True:
        code = 'DF-' + ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        cursor.execute("SELECT id FROM smm_orders WHERE order_code=?", (code,))
        if not cursor.fetchone():
            return code

# ================================================================
# DarkFollow API
# ================================================================
async def smm_get_services() -> list:
    """جلب قائمة الخدمات من API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                SMM_URL,
                params={'key': SMM_KEY, 'action': 'services'},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as r:
                data = await r.json(content_type=None)
                return data if isinstance(data, list) else []
    except Exception as e:
        logging.error(f"smm_get_services error: {e}")
        return []

async def smm_add_order(service_id: int, link: str, quantity: int) -> dict:
    """إرسال طلب جديد للـ API"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                SMM_URL,
                data={'key': SMM_KEY, 'action': 'add',
                      'service': service_id, 'link': link, 'quantity': quantity},
                timeout=aiohttp.ClientTimeout(total=20)
            ) as r:
                return await r.json(content_type=None)
    except Exception as e:
        logging.error(f"smm_add_order error: {e}")
        return {'error': str(e)}

async def smm_check_status(order_id) -> dict:
    """فحص حالة طلب"""
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                SMM_URL,
                params={'key': SMM_KEY, 'action': 'status', 'order': order_id},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as r:
                return await r.json(content_type=None)
    except Exception as e:
        logging.error(f"smm_check_status error: {e}")
        return {'error': str(e)}

def filter_services(platform: str) -> list:
    """فلترة الخدمات حسب المنصة"""
    platform = platform.lower()
    keywords = {
        'instagram': ['instagram', 'انستا', 'insta'],
        'tiktok':    ['tiktok', 'tik tok', 'تيك توك'],
        'telegram':  ['telegram', 'تليجرام', 'تلغرام'],
    }
    kws = keywords.get(platform, [platform])
    result = []
    for s in smm_services_cache:
        cat  = str(s.get('category', '')).lower()
        name = str(s.get('name', '')).lower()
        if any(k in cat or k in name for k in kws):
            result.append(s)
    return result

def get_followers_service(platform: str) -> dict | None:
    """الحصول على أول خدمة متابعين/أعضاء للمنصة"""
    follow_keywords = ['follow', 'member', 'subscriber', 'متابع', 'عضو', 'مشترك']
    services = filter_services(platform)
    for s in services:
        name = str(s.get('name', '')).lower()
        if any(k in name for k in follow_keywords):
            return s
    return services[0] if services else None

# ================================================================
# نظام الأزرار الملونة (Bot API 9.4)
# ================================================================
def colored_button(text, callback_data, color="primary"):
    btn = {"text": text, "callback_data": callback_data}
    if color in ("primary", "success", "danger"):
        btn["style"] = color
    return btn

def colored_url_button(text, url, color="primary"):
    btn = {"text": text, "url": url}
    if color in ("primary", "success", "danger"):
        btn["style"] = color
    return btn

def colored_inline_keyboard(*rows):
    keyboard = []
    for row in rows:
        kb_row = [btn for btn in row if btn]
        if kb_row:
            keyboard.append(kb_row)
    return {"inline_keyboard": keyboard}

def cancel_markup():
    return colored_inline_keyboard(
        [colored_button("❌ إلغاء", "main_menu", "danger")]
    )

# ================================================================
# القائمة الرئيسية
# ================================================================
def get_main_markup(user_id):
    buttons = [
        [colored_button("📸 رشق أنستا",   "service_instagram", "primary"),
         colored_button("🎵 رشق تيك توك", "service_tiktok",   "primary")],
        [colored_button("✈️ رشق تليجرام",  "service_telegram", "primary"),
         colored_button("🎁 الكود الهدية","redeem_gift",      "success")],
        [colored_button("💸 تحويل نقاط",  "transfer_points",  "primary"),
         colored_button("💳 شراء نقاط",   "buy_points",       "success")],
        [colored_button("🎲 تجميع نقاط",  "collect_points",   "primary"),
         colored_button("📦 طلباتي",      "my_orders",        "primary")],
        [colored_button("🔍 تتبع طلب",    "track_order",      "primary"),
         colored_button("📊 إحصائياتي",   "my_stats",         "success")],
        [colored_button("🔗 رابط الدعوة", "referral_link",    "primary"),
         colored_button("📞 الدعم الفني", "support",          "danger")],
        [colored_url_button("📢 قناة الأكواد",
                            f"https://t.me/{CODES_CHANNEL.lstrip('@')}", "primary")],
    ]
    if is_admin(user_id):
        buttons.append([colored_button("⚙️ لوحة المطور", "admin_panel", "danger")])
    return colored_inline_keyboard(*buttons)

def get_admin_markup():
    return colored_inline_keyboard(
        [colored_button("➕ إضافة كود هدية",  "admin_add_gift",    "success")],
        [colored_button("📊 إحصائيات البوت", "admin_stats",       "primary")],
        [colored_button("📋 الطلبات النشطة", "admin_active_orders","primary")],
        [colored_button("🔙 رجوع للقائمة",   "main_menu",         "danger")]
    )

# ================================================================
# دوال مشتركة
# ================================================================
async def guard(call) -> bool:
    if not await is_subscribed(call.from_user.id):
        await call.answer("⚠️ اشترك في القناة أولاً", show_alert=True)
        return False
    if not is_user_verified(call.from_user.id):
        await call.answer("⚠️ أكمل التحقق البشري أولاً", show_alert=True)
        return False
    return True

async def show_main_menu(target, user_id):
    points       = get_user_points(user_id)
    total_orders = get_total_orders()
    text = (
        f"👋 أهلاً بك في بوت النقاط!\n\n"
        f"🆔 ايديك: <code>{user_id}</code>\n"
        f"⭐ نقاطك: <b>{points}</b>\n"
        f"📦 الطلبات المكتملة: {total_orders}"
    )
    markup = get_main_markup(user_id)
    if hasattr(target, 'edit_text') and hasattr(target, 'message_id'):
        try:
            await target.edit_text(text, reply_markup=markup)
        except Exception:
            await target.answer(text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)

# ================================================================
# التحقق من الاشتراك
# ================================================================
async def is_subscribed(user_id) -> bool:
    if not SUBSCRIBE_CHANNELS:
        return True
    try:
        for ch in SUBSCRIBE_CHANNELS:
            member = await bot.get_chat_member(ch, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        return True
    except:
        return False

async def send_subscribe_message(chat_id, user_id):
    rows = []
    for i, ch in enumerate(SUBSCRIBE_CHANNELS):
        rows.append([colored_url_button(
            f"📢 اشترك في القناة {i+1}",
            f"https://t.me/{ch.lstrip('@')}",
            "success" if i % 2 == 0 else "primary"
        )])
    rows.append([colored_button("🔄 تحقق من الاشتراك", "check_sub", "danger")])
    await bot.send_message(
        chat_id,
        "⚠️ يجب الاشتراك في القناة أولاً لاستخدام البوت.",
        reply_markup=colored_inline_keyboard(*rows)
    )

# ================================================================
# الكابتشا
# ================================================================
CAPTCHA_QUESTIONS = [
    {"q": "ما ناتج 5 + 3 ؟",            "correct": "8",     "wrong": ["6","7","9"]},
    {"q": "ما ناتج 12 - 4 ؟",           "correct": "8",     "wrong": ["7","9","6"]},
    {"q": "ما ناتج 3 × 4 ؟",            "correct": "12",    "wrong": ["10","14","9"]},
    {"q": "ما ناتج 15 ÷ 5 ؟",           "correct": "3",     "wrong": ["2","4","5"]},
    {"q": "لون السماء في النهار؟",        "correct": "أزرق",  "wrong": ["أخضر","أحمر","أصفر"]},
    {"q": "كم عدد الأيام في الأسبوع؟",  "correct": "7",     "wrong": ["5","6","8"]},
]

def generate_captcha():
    item    = random.choice(CAPTCHA_QUESTIONS)
    options = item["wrong"] + [item["correct"]]
    random.shuffle(options)
    return item["q"], item["correct"], options

def build_captcha_markup(options):
    colors = ["primary", "success", "primary", "success"]
    rows   = [[colored_button(opt, f"captcha_{opt}", colors[i % 4])]
              for i, opt in enumerate(options)]
    return colored_inline_keyboard(*rows)

# ================================================================
# FSM
# ================================================================
class CaptchaStates(StatesGroup):
    waiting_for_answer = State()

class ServiceStates(StatesGroup):
    choosing_service    = State()
    waiting_for_link    = State()
    waiting_for_quantity = State()

class TrackStates(StatesGroup):
    waiting_for_code = State()

class TransferStates(StatesGroup):
    waiting_for_target = State()
    waiting_for_amount = State()

class GiftStates(StatesGroup):
    waiting_for_code = State()

class BuyPointsStates(StatesGroup):
    waiting_for_amount = State()

class GameStates(StatesGroup):
    choosing_game = State()

class AdminStates(StatesGroup):
    waiting_for_gift_code     = State()
    waiting_for_gift_points   = State()
    waiting_for_gift_max_uses = State()

pending_referrers = {}

PLATFORM_NAMES = {
    'instagram': '📸 إنستاغرام',
    'tiktok':    '🎵 تيك توك',
    'telegram':  '✈️ تيليجرام',
}

# ================================================================
# /start
# ================================================================
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    referrer = None
    args = message.get_args()
    if args and args.startswith('ref'):
        try:
            referrer = int(args[3:])
            if referrer == message.from_user.id:
                referrer = None
        except:
            pass

    if not await is_subscribed(message.from_user.id):
        if referrer:
            pending_referrers[message.from_user.id] = referrer
        await send_subscribe_message(message.chat.id, message.from_user.id)
        return

    add_user_if_not_exists(message.from_user.id, message.from_user.username, referrer)

    if is_user_verified(message.from_user.id):
        await show_main_menu(message, message.from_user.id)
        return

    question, correct, options = generate_captcha()
    await state.update_data(captcha_correct=correct)
    await message.answer(
        f"🤖 <b>تأكيد أنك إنسان</b>\n\n{question}",
        reply_markup=build_captcha_markup(options)
    )
    await CaptchaStates.waiting_for_answer.set()

# ================================================================
# الكابتشا
# ================================================================
@dp.callback_query_handler(lambda c: c.data.startswith('captcha_'), state=CaptchaStates.waiting_for_answer)
async def captcha_answer(call: types.CallbackQuery, state: FSMContext):
    answer  = call.data.split('_', 1)[1]
    data    = await state.get_data()
    correct = data.get('captcha_correct', '')
    if answer == correct:
        set_user_verified(call.from_user.id)
        await state.finish()
        await call.answer("✅ صحيح!")
        await show_main_menu(call.message, call.from_user.id)
    else:
        await call.answer("❌ إجابة خاطئة، حاول مرة أخرى.", show_alert=True)

@dp.callback_query_handler(text="check_sub")
async def check_subscription(call: types.CallbackQuery):
    if not await is_subscribed(call.from_user.id):
        await call.answer("❌ لم تشترك بعد.", show_alert=True)
        return
    referrer = pending_referrers.pop(call.from_user.id, None)
    add_user_if_not_exists(call.from_user.id, call.from_user.username, referrer)
    if not is_user_verified(call.from_user.id):
        question, correct, options = generate_captcha()
        st = dp.current_state(chat=call.message.chat.id, user=call.from_user.id)
        await st.update_data(captcha_correct=correct)
        await call.message.edit_text(
            f"🤖 <b>تأكيد أنك إنسان</b>\n\n{question}",
            reply_markup=build_captcha_markup(options)
        )
        await CaptchaStates.waiting_for_answer.set()
        return
    await show_main_menu(call.message, call.from_user.id)

@dp.callback_query_handler(text="main_menu", state="*")
async def back_to_main(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    if not await guard(call):
        return
    await show_main_menu(call.message, call.from_user.id)

# ================================================================
# خدمة الرشق (Instagram / TikTok / Telegram)
# ================================================================
@dp.callback_query_handler(lambda c: c.data.startswith('service_'))
async def service_start(call: types.CallbackQuery, state: FSMContext):
    if not await guard(call):
        return
    platform = call.data.split('_', 1)[1]
    await state.update_data(platform=platform)

    # جلب الخدمات المتاحة
    services = filter_services(platform)
    if not services:
        await call.answer("⚠️ لا توجد خدمات متاحة حالياً، حاول لاحقاً.", show_alert=True)
        return

    platform_name = PLATFORM_NAMES.get(platform, platform)

    # عرض الخدمات المتاحة (أول 6 خدمات متابعين/أعضاء)
    follow_kws = ['follow', 'member', 'subscriber', 'متابع', 'عضو', 'مشترك']
    follow_services = [s for s in services
                       if any(k in s.get('name','').lower() for k in follow_kws)]
    show_services = follow_services[:6] if follow_services else services[:6]

    rows = []
    for s in show_services:
        name = s.get('name', 'خدمة')
        sid  = s.get('service', s.get('id', 0))
        rows.append([colored_button(f"👥 {name}", f"pick_service_{sid}", "primary")])
    rows.append([colored_button("🔙 رجوع", "main_menu", "danger")])

    await call.message.edit_text(
        f"🛒 <b>خدمات {platform_name}</b>\n\n"
        f"اختر الخدمة المطلوبة:\n"
        f"💡 كل وحدة = {POINTS_PER_UNIT} نقاط | الحد الأدنى: {MIN_ORDER}",
        reply_markup=colored_inline_keyboard(*rows)
    )
    await ServiceStates.choosing_service.set()

@dp.callback_query_handler(lambda c: c.data.startswith('pick_service_'), state=ServiceStates.choosing_service)
async def pick_service(call: types.CallbackQuery, state: FSMContext):
    sid = int(call.data.split('_')[-1])
    # البحث عن الخدمة في الكاش
    service = next((s for s in smm_services_cache
                    if s.get('service', s.get('id')) == sid), None)
    if not service:
        await call.answer("⚠️ خدمة غير موجودة.", show_alert=True)
        return

    data     = await state.get_data()
    platform = data.get('platform', '')
    await state.update_data(service_id=sid, service_name=service.get('name',''))

    smin = service.get('min', MIN_ORDER)
    smax = service.get('max', 100000)

    # تنبيه خاص للتيليجرام
    telegram_note = ""
    if platform == 'telegram':
        telegram_note = "\n\n⚠️ <b>تأكد أن الرابط عام (Public)</b> وليس خاصاً!"

    await call.message.edit_text(
        f"✅ اخترت: <b>{service.get('name')}</b>\n"
        f"📊 الحد الأدنى: {smin} | الأقصى: {smax}{telegram_note}\n\n"
        f"🔗 أرسل رابط الحساب أو القناة:",
        reply_markup=cancel_markup()
    )
    await ServiceStates.waiting_for_link.set()

@dp.message_handler(state=ServiceStates.waiting_for_link)
async def service_link(message: types.Message, state: FSMContext):
    link = message.text.strip()
    if not (link.startswith('http') or link.startswith('@') or link.startswith('t.me')):
        return await message.answer(
            "❌ الرابط غير صحيح.\nأرسل رابطاً صحيحاً مثل:\n"
            "<code>https://t.me/channel</code>\n<code>@username</code>",
            reply_markup=cancel_markup()
        )
    # تحويل @username لرابط كامل
    if link.startswith('@'):
        link = f"https://t.me/{link[1:]}"
    elif link.startswith('t.me'):
        link = f"https://{link}"

    await state.update_data(link=link)
    data = await state.get_data()
    points = get_user_points(message.from_user.id)

    await message.answer(
        f"🔗 الرابط: <code>{link}</code>\n"
        f"⭐ رصيدك: <b>{points}</b> نقطة\n"
        f"💡 كل وحدة = {POINTS_PER_UNIT} نقاط\n\n"
        f"📊 أرسل الكمية المطلوبة (الحد الأدنى {MIN_ORDER}):",
        reply_markup=cancel_markup()
    )
    await ServiceStates.waiting_for_quantity.set()

@dp.message_handler(state=ServiceStates.waiting_for_quantity)
async def service_quantity(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ أرسل عدداً صحيحاً.", reply_markup=cancel_markup())

    quantity = int(message.text)
    if quantity < MIN_ORDER:
        return await message.answer(
            f"❌ الحد الأدنى {MIN_ORDER}.", reply_markup=cancel_markup()
        )

    data          = await state.get_data()
    platform      = data.get('platform', '')
    service_id    = data.get('service_id')
    service_name  = data.get('service_name', '')
    link          = data.get('link', '')
    points_needed = quantity * POINTS_PER_UNIT
    user_points   = get_user_points(message.from_user.id)

    if user_points < points_needed:
        return await message.answer(
            f"❌ <b>رصيدك غير كافٍ</b>\n"
            f"المطلوب: <b>{points_needed}</b> نقطة\n"
            f"رصيدك: <b>{user_points}</b> نقطة",
            reply_markup=colored_inline_keyboard(
                [colored_button("💳 شراء نقاط", "buy_points", "success")],
                [colored_button("🔙 رجوع",      "main_menu",  "danger")]
            )
        )

    # إرسال رسالة "جاري المعالجة"
    processing_msg = await message.answer("⏳ جاري إرسال طلبك...")

    # إرسال الطلب للـ API
    result = await smm_add_order(service_id, link, quantity)

    if 'error' in result or 'order' not in result:
        error_msg = result.get('error', 'خطأ غير معروف')
        await processing_msg.edit_text(
            f"❌ <b>فشل الطلب</b>\n\n"
            f"السبب: {error_msg}\n\n"
            f"لم يتم خصم أي نقاط. حاول مرة أخرى أو تواصل مع الدعم.",
            reply_markup=colored_inline_keyboard(
                [colored_url_button("📞 الدعم", f"https://t.me/{SUPPORT_USERNAME}", "danger")],
                [colored_button("🔙 رجوع", "main_menu", "danger")]
            )
        )
        await state.finish()
        return

    # نجح الطلب — خصم النقاط وحفظ الطلب
    smm_order_id = str(result.get('order', ''))
    order_code   = generate_order_code()
    new_balance  = user_points - points_needed

    cursor.execute("UPDATE users SET points=? WHERE id=?", (new_balance, message.from_user.id))
    cursor.execute(
        "INSERT INTO smm_orders (user_id, platform, service_id, service_name, link, quantity, "
        "points_spent, smm_order_id, order_code, status) VALUES (?,?,?,?,?,?,?,?,?,'pending')",
        (message.from_user.id, platform, service_id, service_name,
         link, quantity, points_needed, smm_order_id, order_code)
    )
    conn.commit()
    increment_total_orders()

    platform_name = PLATFORM_NAMES.get(platform, platform)
    await processing_msg.edit_text(
        f"✅ <b>تم إرسال طلبك بنجاح!</b>\n\n"
        f"🔖 كود الطلب: <code>{order_code}</code>\n"
        f"📌 الخدمة: {service_name}\n"
        f"🌐 المنصة: {platform_name}\n"
        f"🔗 الرابط: <code>{link}</code>\n"
        f"👥 الكمية: {quantity:,}\n"
        f"⭐ النقاط المستخدمة: {points_needed}\n"
        f"💰 رصيدك المتبقي: <b>{new_balance}</b> نقطة\n\n"
        f"⏳ طلبك قيد التنفيذ، سنخبرك عند الانتهاء.",
        reply_markup=colored_inline_keyboard(
            [colored_button("🔍 تتبع الطلب", f"track_{order_code}", "primary")],
            [colored_button("🏠 القائمة الرئيسية", "main_menu", "danger")]
        )
    )
    await state.finish()

# ================================================================
# تتبع الطلب
# ================================================================
@dp.callback_query_handler(text="track_order")
async def track_order_start(call: types.CallbackQuery, state: FSMContext):
    if not await guard(call):
        return
    await call.message.edit_text(
        "🔍 <b>تتبع طلب</b>\n\nأرسل كود الطلب الخاص بك:\nمثال: <code>DF-ABC123</code>",
        reply_markup=cancel_markup()
    )
    await TrackStates.waiting_for_code.set()

@dp.callback_query_handler(lambda c: c.data.startswith('track_'), state="*")
async def track_by_code_button(call: types.CallbackQuery, state: FSMContext):
    code = call.data.split('track_', 1)[1]
    await show_order_status(call.message, call.from_user.id, code, edit=True)

@dp.message_handler(state=TrackStates.waiting_for_code)
async def track_order_code(message: types.Message, state: FSMContext):
    code = message.text.strip().upper()
    await state.finish()
    await show_order_status(message, message.from_user.id, code, edit=False)

async def show_order_status(target, user_id, code, edit=False):
    cursor.execute(
        "SELECT platform, service_name, link, quantity, points_spent, smm_order_id, "
        "status, start_count, remains, created_at FROM smm_orders "
        "WHERE order_code=? AND user_id=?",
        (code, user_id)
    )
    row = cursor.fetchone()
    if not row:
        text = f"❌ لا يوجد طلب بالكود: <code>{code}</code>"
        markup = colored_inline_keyboard([colored_button("🔙 رجوع", "main_menu", "danger")])
        if edit:
            try:
                await target.edit_text(text, reply_markup=markup)
            except:
                await target.answer(text, reply_markup=markup)
        else:
            await target.answer(text, reply_markup=markup)
        return

    platform, svc_name, link, qty, pts, smm_id, status, start_count, remains, created = row

    # تحديث الحالة من API
    if status not in ('completed', 'canceled', 'Completed', 'Canceled'):
        api_status = await smm_check_status(smm_id)
        if 'status' in api_status:
            status      = api_status.get('status', status)
            start_count = api_status.get('start_count', start_count) or 0
            remains     = api_status.get('remains', remains) or 0
            cursor.execute(
                "UPDATE smm_orders SET status=?, start_count=?, remains=?, updated_at=? WHERE order_code=?",
                (status, start_count, remains, datetime.now().isoformat(), code)
            )
            conn.commit()

    STATUS_MAP = {
        'pending':    '⏳ في الانتظار',
        'in progress': '🔄 قيد التنفيذ',
        'processing': '🔄 قيد التنفيذ',
        'completed':  '✅ مكتمل',
        'Completed':  '✅ مكتمل',
        'partial':    '⚠️ مكتمل جزئياً',
        'Partial':    '⚠️ مكتمل جزئياً',
        'canceled':   '❌ ملغي',
        'Canceled':   '❌ ملغي',
    }
    status_text   = STATUS_MAP.get(status, f"📌 {status}")
    platform_name = PLATFORM_NAMES.get(platform, platform)
    done          = max(0, int(qty) - int(remains or 0))

    text = (
        f"🔖 <b>تفاصيل الطلب</b>\n\n"
        f"الكود: <code>{code}</code>\n"
        f"الحالة: {status_text}\n"
        f"المنصة: {platform_name}\n"
        f"الخدمة: {svc_name}\n"
        f"الرابط: <code>{link}</code>\n"
        f"الكمية: {int(qty):,}\n"
        f"المنجز: {done:,}\n"
        f"المتبقي: {int(remains or 0):,}\n"
        f"النقاط المستخدمة: {pts}\n"
        f"تاريخ الطلب: {str(created)[:16]}"
    )
    markup = colored_inline_keyboard(
        [colored_button("🔄 تحديث الحالة", f"track_{code}", "primary")],
        [colored_button("🔙 رجوع", "main_menu", "danger")]
    )
    if edit:
        try:
            await target.edit_text(text, reply_markup=markup)
        except:
            await target.answer(text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)

# ================================================================
# رابط الدعوة
# ================================================================
@dp.callback_query_handler(text="referral_link")
async def referral_link(call: types.CallbackQuery):
    if not await guard(call):
        return
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref{call.from_user.id}"
    cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (call.from_user.id,))
    ref_count = cursor.fetchone()[0]
    await call.message.edit_text(
        f"🔗 <b>رابط الدعوة الخاص بك</b>\n\n"
        f"<code>{ref_link}</code>\n\n"
        f"👥 عدد من دعوتهم: <b>{ref_count}</b>\n"
        f"🎁 لكل شخص جديد: +30 نقطة لك، +5 نقاط له.",
        reply_markup=colored_inline_keyboard(
            [colored_button("🔙 رجوع", "main_menu", "danger")]
        )
    )

# ================================================================
# الكود الهدية
# ================================================================
@dp.callback_query_handler(text="redeem_gift")
async def redeem_gift_start(call: types.CallbackQuery, state: FSMContext):
    if not await guard(call):
        return
    await call.message.edit_text(
        "🎁 <b>الكود الهدية</b>\n\nأرسل الكود:",
        reply_markup=cancel_markup()
    )
    await GiftStates.waiting_for_code.set()

@dp.message_handler(state=GiftStates.waiting_for_code)
async def redeem_gift_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    cursor.execute("SELECT points, max_uses, used_count FROM gift_codes WHERE code=?", (code,))
    row = cursor.fetchone()
    await state.finish()
    if not row:
        return await message.answer("❌ الكود غير صحيح.", reply_markup=get_main_markup(message.from_user.id))
    points, max_uses, used = row
    if used >= max_uses:
        return await message.answer("❌ تم استنفاذ استخدامات هذا الكود.", reply_markup=get_main_markup(message.from_user.id))
    cursor.execute("UPDATE gift_codes SET used_count = used_count + 1 WHERE code=?", (code,))
    cursor.execute("UPDATE users SET points = points + ? WHERE id=?", (points, message.from_user.id))
    conn.commit()
    new_points = get_user_points(message.from_user.id)
    await message.answer(
        f"✅ <b>تم تفعيل الكود!</b>\n"
        f"أضيف <b>{points}</b> نقطة.\n"
        f"⭐ رصيدك الحالي: <b>{new_points}</b> نقطة",
        reply_markup=get_main_markup(message.from_user.id)
    )

# ================================================================
# تحويل نقاط
# ================================================================
@dp.callback_query_handler(text="transfer_points")
async def transfer_start(call: types.CallbackQuery, state: FSMContext):
    if not await guard(call):
        return
    await call.message.edit_text(
        "💸 <b>تحويل نقاط</b>\n\n"
        "أرسل معرف المستلم (username أو ID):",
        reply_markup=cancel_markup()
    )
    await TransferStates.waiting_for_target.set()

@dp.message_handler(state=TransferStates.waiting_for_target)
async def transfer_target(message: types.Message, state: FSMContext):
    target    = message.text.strip()
    target_id = None
    if target.startswith('@'):
        try:
            chat      = await bot.get_chat(target)
            target_id = chat.id
        except:
            return await message.answer("❌ لم أجد هذا المستخدم.", reply_markup=cancel_markup())
    elif target.lstrip('-').isdigit():
        target_id = int(target)
    else:
        return await message.answer("❌ صيغة غير صحيحة.", reply_markup=cancel_markup())

    if target_id == message.from_user.id:
        return await message.answer("❌ لا يمكنك التحويل لنفسك.", reply_markup=cancel_markup())
    cursor.execute("SELECT id FROM users WHERE id=?", (target_id,))
    if not cursor.fetchone():
        return await message.answer("❌ هذا المستخدم غير موجود.", reply_markup=cancel_markup())

    await state.update_data(target_id=target_id)
    await message.answer(
        f"✅ المستلم: <code>{target_id}</code>\n"
        f"💡 رسوم الخدمة: 8%\n"
        f"⭐ رصيدك: <b>{get_user_points(message.from_user.id)}</b>\n\n"
        f"أدخل عدد النقاط:",
        reply_markup=cancel_markup()
    )
    await TransferStates.waiting_for_amount.set()

@dp.message_handler(state=TransferStates.waiting_for_amount)
async def transfer_amount(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ أرسل عدداً صحيحاً.", reply_markup=cancel_markup())
    amount        = int(message.text)
    sender_points = get_user_points(message.from_user.id)
    if amount <= 0:
        return await message.answer("❌ المبلغ يجب أن يكون أكبر من صفر.", reply_markup=cancel_markup())
    if sender_points < amount:
        return await message.answer(f"❌ رصيدك {sender_points} نقطة فقط.", reply_markup=cancel_markup())

    fee              = max(1, int(amount * 0.08))
    recipient_amount = amount - fee
    if recipient_amount <= 0:
        return await message.answer("❌ المبلغ صغير جداً بعد خصم الرسوم.", reply_markup=cancel_markup())

    data      = await state.get_data()
    target_id = data['target_id']
    cursor.execute("UPDATE users SET points = points - ? WHERE id=?", (amount, message.from_user.id))
    cursor.execute("UPDATE users SET points = points + ? WHERE id=?", (recipient_amount, target_id))
    conn.commit()

    new_sender = get_user_points(message.from_user.id)
    await message.answer(
        f"✅ <b>تم التحويل!</b>\n\n"
        f"إلى: <code>{target_id}</code>\n"
        f"المحوّل: {recipient_amount} نقطة\n"
        f"الرسوم: {fee} نقطة\n"
        f"⭐ رصيدك: <b>{new_sender}</b> نقطة",
        reply_markup=get_main_markup(message.from_user.id)
    )
    try:
        await bot.send_message(
            target_id,
            f"📩 استلمت <b>{recipient_amount}</b> نقطة من <code>{message.from_user.id}</code>."
        )
    except:
        pass
    await state.finish()

# ================================================================
# شراء نقاط
# ================================================================
@dp.callback_query_handler(text="buy_points")
async def buy_points_start(call: types.CallbackQuery, state: FSMContext):
    if not await guard(call):
        return
    await call.message.edit_text(
        "💳 <b>شراء نقاط</b>\n\nكل نجمة = 1 نقطة.\nأدخل عدد النقاط (1 - 10000):",
        reply_markup=cancel_markup()
    )
    await BuyPointsStates.waiting_for_amount.set()

@dp.message_handler(state=BuyPointsStates.waiting_for_amount)
async def buy_points_amount(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        return await message.answer("❌ أدخل عدداً صحيحاً.", reply_markup=cancel_markup())
    amount = int(message.text)
    if not (1 <= amount <= 10000):
        return await message.answer("❌ العدد بين 1 و 10000.", reply_markup=cancel_markup())
    await state.finish()
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="شراء نقاط",
        description=f"شراء {amount} نقطة",
        payload="buy_points_payload",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="نجوم", amount=amount)]
    )

@dp.pre_checkout_query_handler(lambda q: True)
async def process_pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message_handler(content_types=ContentType.SUCCESSFUL_PAYMENT)
async def process_successful_payment(message: types.Message):
    stars = message.successful_payment.total_amount
    cursor.execute("UPDATE users SET points = points + ? WHERE id=?", (stars, message.from_user.id))
    conn.commit()
    new_points = get_user_points(message.from_user.id)
    await message.answer(
        f"💳 <b>تم الشحن بنجاح!</b>\n"
        f"أضيف <b>{stars}</b> نقطة.\n"
        f"⭐ رصيدك الجديد: <b>{new_points}</b> نقطة",
        reply_markup=get_main_markup(message.from_user.id)
    )

# ================================================================
# تجميع نقاط
# ================================================================
GAME_NAMES = [
    ("🍀 لعبة الحظ",    "luck"),
    ("🧠 لعبة الذكاء",  "smart"),
    ("⚡ لعبة السرعة",  "speed"),
    ("🏆 لعبة التحدي", "challenge"),
]

@dp.callback_query_handler(text="collect_points")
async def collect_points_start(call: types.CallbackQuery, state: FSMContext):
    if not await guard(call):
        return
    cursor.execute("SELECT last_game_time FROM users WHERE id=?", (call.from_user.id,))
    row = cursor.fetchone()
    if row and row[0]:
        last_time = datetime.fromisoformat(row[0])
        remaining = timedelta(hours=24) - (datetime.now() - last_time)
        if remaining.total_seconds() > 0:
            h = int(remaining.total_seconds() // 3600)
            m = int((remaining.total_seconds() % 3600) // 60)
            await call.answer(f"⏳ العب مرة أخرى بعد {h}س و{m}د", show_alert=True)
            return

    rows = [[colored_button(name, f"game_play_{key}", "primary")] for name, key in GAME_NAMES]
    rows.append([colored_button("🔙 رجوع", "main_menu", "danger")])
    await call.message.edit_text(
        "🎲 <b>تجميع نقاط</b>\n\nاختر لعبة — ستحصل على 1-50 نقطة عشوائية.\n⏳ مرة كل 24 ساعة.",
        reply_markup=colored_inline_keyboard(*rows)
    )
    await GameStates.choosing_game.set()

@dp.callback_query_handler(lambda c: c.data.startswith('game_play_'), state=GameStates.choosing_game)
async def game_play(call: types.CallbackQuery, state: FSMContext):
    now    = datetime.now().isoformat()
    points = random.randint(1, 50)
    cursor.execute(
        "UPDATE users SET last_game_time=?, points = points + ? WHERE id=?",
        (now, points, call.from_user.id)
    )
    conn.commit()
    new_points = get_user_points(call.from_user.id)
    await call.message.edit_text(
        f"🎉 <b>حصلت على {points} نقطة!</b>\n"
        f"⭐ رصيدك الحالي: <b>{new_points}</b> نقطة\n"
        f"⏳ العب مرة أخرى بعد 24 ساعة.",
        reply_markup=get_main_markup(call.from_user.id)
    )
    await state.finish()

# ================================================================
# طلباتي
# ================================================================
@dp.callback_query_handler(text="my_orders")
async def my_orders(call: types.CallbackQuery):
    if not await guard(call):
        return
    cursor.execute(
        "SELECT order_code, platform, quantity, status, created_at "
        "FROM smm_orders WHERE user_id=? ORDER BY created_at DESC LIMIT 10",
        (call.from_user.id,)
    )
    orders = cursor.fetchall()
    if not orders:
        await call.answer("📭 ليس لديك طلبات.", show_alert=True)
        return

    STATUS_ICONS = {
        'pending': '⏳', 'in progress': '🔄', 'processing': '🔄',
        'completed': '✅', 'Completed': '✅',
        'partial': '⚠️', 'Partial': '⚠️',
        'canceled': '❌', 'Canceled': '❌',
    }
    text  = "📦 <b>طلباتي الأخيرة</b>\n\n"
    rows  = []
    for o in orders:
        code, platform, qty, status, created = o
        icon  = STATUS_ICONS.get(status, '📌')
        pname = PLATFORM_NAMES.get(platform, platform)
        text += f"{icon} <code>{code}</code> | {pname} | {int(qty):,} | {str(created)[:10]}\n"
        rows.append([colored_button(f"🔍 {code}", f"track_{code}", "primary")])

    rows.append([colored_button("🔙 رجوع", "main_menu", "danger")])
    await call.message.edit_text(text, reply_markup=colored_inline_keyboard(*rows))

# ================================================================
# إحصائياتي
# ================================================================
@dp.callback_query_handler(text="my_stats")
async def my_stats(call: types.CallbackQuery):
    if not await guard(call):
        return
    uid    = call.from_user.id
    points = get_user_points(uid)
    cursor.execute("SELECT COUNT(*) FROM smm_orders WHERE user_id=?", (uid,))
    orders_count = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(points_spent) FROM smm_orders WHERE user_id=?", (uid,))
    spent = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (uid,))
    ref_count = cursor.fetchone()[0]
    cursor.execute(
        "SELECT COUNT(*) FROM smm_orders WHERE user_id=? AND status IN ('completed','Completed')",
        (uid,)
    )
    done_count = cursor.fetchone()[0]
    await call.message.edit_text(
        f"📊 <b>إحصائياتي</b>\n\n"
        f"🆔 الايدي: <code>{uid}</code>\n"
        f"⭐ رصيد النقاط: <b>{points}</b>\n"
        f"📦 إجمالي الطلبات: {orders_count}\n"
        f"✅ الطلبات المكتملة: {done_count}\n"
        f"💸 النقاط المستهلكة: {spent}\n"
        f"👥 عدد الإحالات: {ref_count}",
        reply_markup=colored_inline_keyboard(
            [colored_button("🔙 رجوع", "main_menu", "danger")]
        )
    )

# ================================================================
# الدعم الفني
# ================================================================
@dp.callback_query_handler(text="support")
async def support(call: types.CallbackQuery):
    await call.message.edit_text(
        "📞 <b>الدعم الفني</b>\n\nاضغط الزر أدناه للتواصل مع فريق الدعم.",
        reply_markup=colored_inline_keyboard(
            [colored_url_button("💬 تواصل مع الدعم", f"https://t.me/{SUPPORT_USERNAME}", "success")],
            [colored_button("🔙 رجوع", "main_menu", "danger")]
        )
    )

# ================================================================
# لوحة المطور
# ================================================================
@dp.callback_query_handler(text="admin_panel")
async def admin_panel(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ غير مصرح.", show_alert=True)
        return
    await call.message.edit_text("⚙️ <b>لوحة المطور</b>", reply_markup=get_admin_markup())

@dp.callback_query_handler(text="admin_stats")
async def admin_stats(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ غير مصرح.", show_alert=True)
        return
    cursor.execute("SELECT COUNT(*) FROM users")
    users = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(points) FROM users")
    total_points = cursor.fetchone()[0] or 0
    cursor.execute("SELECT COUNT(*) FROM smm_orders")
    total_orders = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM smm_orders WHERE status IN ('pending','in progress','processing')")
    active_orders = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM gift_codes")
    total_codes = cursor.fetchone()[0]
    await call.message.edit_text(
        f"📊 <b>إحصائيات البوت</b>\n\n"
        f"👥 المستخدمون: {users}\n"
        f"⭐ إجمالي النقاط: {total_points}\n"
        f"📦 إجمالي الطلبات: {total_orders}\n"
        f"🔄 الطلبات النشطة: {active_orders}\n"
        f"🎁 الأكواد الهدية: {total_codes}",
        reply_markup=get_admin_markup()
    )

@dp.callback_query_handler(text="admin_active_orders")
async def admin_active_orders(call: types.CallbackQuery):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ غير مصرح.", show_alert=True)
        return
    cursor.execute(
        "SELECT order_code, user_id, platform, quantity, status, created_at "
        "FROM smm_orders WHERE status IN ('pending','in progress','processing') "
        "ORDER BY created_at DESC LIMIT 15"
    )
    orders = cursor.fetchall()
    if not orders:
        await call.answer("✅ لا توجد طلبات نشطة.", show_alert=True)
        return
    text = "🔄 <b>الطلبات النشطة</b>\n\n"
    for o in orders:
        code, uid, platform, qty, status, created = o
        pname = PLATFORM_NAMES.get(platform, platform)
        text += f"<code>{code}</code> | {uid} | {pname} | {int(qty):,} | {status}\n"
    await call.message.edit_text(text, reply_markup=get_admin_markup())

# ================================================================
# إضافة كود هدية
# ================================================================
@dp.callback_query_handler(text="admin_add_gift")
async def admin_add_gift_start(call: types.CallbackQuery, state: FSMContext):
    if not is_admin(call.from_user.id):
        await call.answer("⛔ غير مصرح.", show_alert=True)
        return
    await call.message.edit_text("🎁 <b>إضافة كود هدية</b>\n\nأدخل الكود:", reply_markup=cancel_markup())
    await AdminStates.waiting_for_gift_code.set()

@dp.message_handler(state=AdminStates.waiting_for_gift_code)
async def admin_gift_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    if not code:
        return await message.answer("❌ الكود لا يمكن أن يكون فارغاً.")
    await state.update_data(code=code)
    await message.answer("أدخل عدد النقاط:", reply_markup=cancel_markup())
    await AdminStates.waiting_for_gift_points.set()

@dp.message_handler(state=AdminStates.waiting_for_gift_points)
async def admin_gift_points(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) <= 0:
        return await message.answer("❌ أدخل عدداً صحيحاً أكبر من صفر.")
    await state.update_data(points=int(message.text))
    await message.answer("أدخل الحد الأقصى للاستخدام:", reply_markup=cancel_markup())
    await AdminStates.waiting_for_gift_max_uses.set()

@dp.message_handler(state=AdminStates.waiting_for_gift_max_uses)
async def admin_gift_max_uses(message: types.Message, state: FSMContext):
    if not message.text.isdigit() or int(message.text) <= 0:
        return await message.answer("❌ أدخل عدداً صحيحاً أكبر من صفر.")
    max_uses = int(message.text)
    data     = await state.get_data()
    try:
        cursor.execute(
            "INSERT INTO gift_codes (code, points, max_uses, created_by) VALUES (?,?,?,?)",
            (data['code'], data['points'], max_uses, message.from_user.id)
        )
        conn.commit()
        await message.answer(
            f"✅ <b>تم إضافة الكود!</b>\n\n"
            f"الكود: <code>{data['code']}</code>\n"
            f"النقاط: {data['points']}\n"
            f"الحد الأقصى: {max_uses}",
            reply_markup=get_admin_markup()
        )
    except sqlite3.IntegrityError:
        await message.answer("❌ هذا الكود موجود مسبقاً.", reply_markup=get_admin_markup())
    await state.finish()

# ================================================================
# مهمة خلفية: فحص الطلبات وإشعار العملاء
# ================================================================
async def check_pending_orders():
    """تفحص الطلبات كل 5 دقائق وتُشعر العميل عند الانتهاء"""
    while True:
        try:
            cursor.execute(
                "SELECT id, user_id, order_code, smm_order_id, quantity "
                "FROM smm_orders WHERE status IN ('pending','in progress','processing')"
            )
            pending = cursor.fetchall()
            for row in pending:
                oid, uid, code, smm_id, qty = row
                try:
                    result = await smm_check_status(smm_id)
                    status = result.get('status', '')
                    if not status:
                        continue
                    start_count = result.get('start_count', 0) or 0
                    remains     = result.get('remains', 0) or 0
                    cursor.execute(
                        "UPDATE smm_orders SET status=?, start_count=?, remains=?, updated_at=? WHERE id=?",
                        (status, start_count, remains, datetime.now().isoformat(), oid)
                    )
                    conn.commit()

                    # إشعار العميل عند الاكتمال أو الإلغاء
                    if status.lower() in ('completed', 'partial', 'canceled'):
                        icons = {'completed': '✅', 'partial': '⚠️', 'canceled': '❌'}
                        texts = {
                            'completed': 'تم تنفيذ طلبك بالكامل! ✅',
                            'partial':   'تم تنفيذ طلبك جزئياً ⚠️',
                            'canceled':  'تم إلغاء طلبك ❌',
                        }
                        icon    = icons.get(status.lower(), '📌')
                        msg_txt = texts.get(status.lower(), f'تحديث طلبك: {status}')
                        try:
                            await bot.send_message(
                                uid,
                                f"{icon} <b>{msg_txt}</b>\n\n"
                                f"🔖 كود الطلب: <code>{code}</code>\n"
                                f"👥 الكمية: {int(qty):,}\n"
                                f"المتبقي: {int(remains):,}",
                                reply_markup=colored_inline_keyboard(
                                    [colored_button("🔍 تفاصيل الطلب", f"track_{code}", "primary")],
                                    [colored_button("🏠 القائمة", "main_menu", "danger")]
                                )
                            )
                        except:
                            pass
                    await asyncio.sleep(0.3)  # تجنب rate limit
                except Exception as e:
                    logging.error(f"check order {oid} error: {e}")
        except Exception as e:
            logging.error(f"check_pending_orders error: {e}")
        await asyncio.sleep(300)  # كل 5 دقائق

# ================================================================
# تحميل الخدمات عند البدء
# ================================================================
async def on_startup(dp):
    global smm_services_cache
    logging.info("جاري تحميل خدمات DarkFollow API...")
    smm_services_cache = await smm_get_services()
    logging.info(f"تم تحميل {len(smm_services_cache)} خدمة من DarkFollow API")
    # تشغيل مهمة فحص الطلبات
    asyncio.create_task(check_pending_orders())

# ================================================================
if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
