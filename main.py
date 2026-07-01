import os
import re
import sqlite3
import logging
import asyncio
import random
from datetime import datetime
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import InlineKeyboardButton, LabeledPrice, ContentType
from telethon import TelegramClient, errors

# الإعدادات
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_USERNAME    = 'DYD55'
SUB_ADMIN_USERNAMES = []
BOT_USERNAME      = 'Kaido_TG_KINGbot'
TELETHON_API_ID = int(os.getenv('TELETHON_API_ID'))
TELETHON_API_HASH = os.getenv('TELETHON_API_HASH')
ACTIVATIONS_CHANNEL = ''
SUBSCRIBE_CHANNELS  = ['@TGNUMERS', '@TGFRANK1']

ADMIN_ID = None

user_languages: dict = {}  # {user_id: 'ar' or 'en'}

def get_lang(uid) -> str:
    return user_languages.get(uid, 'ar')

TEXTS = {
    'ar': {
        'welcome': (
            "أهلاً بك في - FRANK TG NUMBERS 👋\n\n"
            "الوجهة الأولى لبيع وشراء حسابات تيليجرام الفورية، جديدة ومُفعّلة، تشمل كل الدول العربية والأجنبية📞\n\n"
            "🆔 ايديك: <code>{user_id}</code>\n"
            "💵 رصيدك: <code>{bal:.2f}$</code>\n\n"
            "👍 ابدأ باستخدام البوت الآن واستمتع بجميع الخدمات المتاحة عبر الأزرار بالأسفل ⬇️."
        ),
        'verified_ok': "✅ <b>تم التحقق بنجاح!</b>\n\n",
        'sub_verified': "✅ <b>تم التحقق من الاشتراك.</b>\n\n",
        'captcha_title': "🤖 <b>تأكيد أنك إنسان</b>\n\n",
        'captcha_wrong': "❌ إجابة خاطئة، حاول مرة أخرى.",
        'sub_required': "⚠️ <b>يجب الاشتراك في القناتين أولاً لاستخدام البوت.</b>\n\nبعد الاشتراك، اضغط على زر التحقق.",
        'sub_check_btn': "🔄 تحقق من الاشتراك",
        'sub_not_done': "❌ لم تشترك في القناتين بعد. يرجى الاشتراك ثم الضغط على التحقق.",
        'sub_first': "⚠️ اشترك أولاً",
        'human_check': "يرجى إكمال التحقق البشري أولاً.",
        'balance': "💰 رصيدك: ${bal:.2f}",
        'ref_text': (
            "🔗 <b>رابط الإحالة الخاص بك:</b>\n\n"
            "<code>{link}</code>\n\n"
            "👥 عند دخول شخص جديد لأول مرة عبر رابطك، ستكسب <b>$0.01</b> تلقائياً."
        ),
        'back': "🔙 رجوع",
        'back_main': "🔙 رجوع للقائمة",
        'main_menu_title': "أهلاً بك في - FRANK TG NUMBERS 👋\n\nالوجهة الأولى لبيع وشراء حسابات تيليجرام الفورية📞\n\n🆔 ايديك: <code>{user_id}</code>\n💵 رصيدك: <code>{bal:.2f}$</code>",
        # أزرار القائمة الرئيسية
        'btn_buy': "🛒 شراء حساب",
        'btn_support': "📞 الدعم الفني",
        'btn_agents': "👥 الوكلاء",
        'btn_channel': "📢 قناة التفعيلات",
        'btn_ref': "🔗 إحالة",
        'btn_purchases': "📦 مشترياتي",
        'btn_balance': "💰 رصيدي",
        'btn_dev': "👨‍💻 المطور",
        'btn_admin': "⚙️ لوحة التحكم للمطور",
        'btn_topup': "💳 شحن رصيد",
        'btn_laws': "📜 القواعد | LAWS",
        'btn_lang': "🌐 English",
        # القواعد
        'laws_menu_title': "📜 <b>القواعد والشروط</b>\n\nاختر الصفحة:",
        'law1_title': "📋 القاعدة الأولى",
        'law1_text': (
            "📋 <b>القاعدة الأولى — الضمان</b>\n\n"
            "❌ ماكو أي ضمان بعد الشراء."
        ),
        'law2_title': "📋 القاعدة الثانية",
        'law2_text': (
            "📋 <b>القاعدة الثانية — نقل الملكية</b>\n\n"
            "أول شي: من يطلع الرقم من عدنا ويستلمه للمشتري، إحنا نفقد السيطرة على الرقم نهائياً~\n\n"
            "وما عدنا أي طريقة نرجعه أو نتحكم بالرقم.\n\n"
            "ويصير ملك الشخص اللي اشتراه فقط."
        ),
        'law3_title': "📋 القاعدة الثالثة",
        'law3_text': (
            "📋 <b>القاعدة الثالثة — الاستخدام الخاطئ</b>\n\n"
            "هواي ناس تخربط الرقم لو تحذفه أو تجرب عليها ثغرات أو يستخدموه غلط ويرجع يطالب بحقه.\n\n"
            "⚠️ في هاي الحالة ماكو أي ضمان.\n\n"
            "في حال المستخدم ايتعمل الرقم غلط وتجمد ويرجع يطالب بتعويض — هاي الحالة التعويض مرفوض ✓"
        ),
        'law4_title': "📋 القاعدة الرابعة",
        'law4_text': (
            "📋 <b>القاعدة الرابعة — الموافقة على الشروط</b>\n\n"
            "⚠️ <b>كلام مهم:</b>\n\n"
            "من تضغط على زر الشراء = الموافقة على الشروط.\n\n"
            "ومابيها أي مجال للتراجع."
        ),
        'law_page': "الصفحة {cur} من {total}",
        'prev': "◀️ السابق",
        'next': "التالي ▶️",
        'laws_menu_btn': "📜 القائمة",
        'agents_text': (
            "مرحباً بك في قسم الوكلاء، هنا قائمة بوكلاء البوت الذين تم اعتمادهم من الإدارة شخصياً.\n\n"
            "✅ يمكنك شحن البوت عبرهم بكل ثقة وأمان وبضمان من الإدارة رسميًا\n\n"
            "⚠️ في حال لاحظت من أحدهم أي تصرف غير لائق، يرجى إبلاغنا فورًا."
        ),
        'agent_btn': "👤 الوكيل | @DYD55",
        'buy_title': "🌏 <b>قائمة الدول المتاحة:</b>\n\naختر الدولة التي تريد شراء حساب منها:",
        'no_cats': "❌ لا تتوفر أقسام.",
        'go_back': "🔙 العودة",
        'bought': "🎉 <b>تم الشراء!</b>\n📞 <code>{phone}</code>\n💰 رصيدك: ${bal:.2f}",
        'get_otp': "📥 جلب كود التحقق (OTP)",
        'get_2fa': "🔐 جلب كلمة السر (2FA)",
        'confirm_login': "✅ تم تسجيل الدخول",
        'topup_choose': "💳 <b>اختر طريقة الشحن:</b>",
        'stars_btn': "⭐ شحن بالنجوم (Telegram Stars)",
        'asia_btn': "🌏 شحن عبر آسيا",
        'purchases_empty': "❌ لم تقم بأي عملية شراء أو شحن بعد.",
        'purchases_title': "📦 <b>سجل حسابك:</b>\n\n",
        'purchase_count': "🛒 <b>عدد مرات الشراء:</b> {n}\n",
        'recharge_count': "💳 <b>عدد مرات الشحن:</b> {n}\n\n",
        'purchase_details': "📋 <b>تفاصيل المشتريات:</b>\n",
    },
    'en': {
        'welcome': (
            "Welcome to - FRANK TG NUMBERS 👋\n\n"
            "The #1 destination for buying & selling instant Telegram accounts, new & activated, covering all Arab & international countries 📞\n\n"
            "🆔 Your ID: <code>{user_id}</code>\n"
            "💵 Balance: <code>{bal:.2f}$</code>\n\n"
            "👍 Start using the bot now and enjoy all available services via the buttons below ⬇️."
        ),
        'verified_ok': "✅ <b>Verified successfully!</b>\n\n",
        'sub_verified': "✅ <b>Subscription verified.</b>\n\n",
        'captcha_title': "🤖 <b>Human Verification</b>\n\n",
        'captcha_wrong': "❌ Wrong answer, try again.",
        'sub_required': "⚠️ <b>You must subscribe to both channels first to use the bot.</b>\n\nAfter subscribing, press the verify button.",
        'sub_check_btn': "🔄 Verify Subscription",
        'sub_not_done': "❌ You haven't subscribed to both channels yet. Please subscribe then press verify.",
        'sub_first': "⚠️ Subscribe first",
        'human_check': "Please complete human verification first.",
        'balance': "💰 Your balance: ${bal:.2f}",
        'ref_text': (
            "🔗 <b>Your referral link:</b>\n\n"
            "<code>{link}</code>\n\n"
            "👥 When a new user joins via your link, you earn <b>$0.01</b> automatically."
        ),
        'back': "🔙 Back",
        'back_main': "🔙 Back to Menu",
        'main_menu_title': "Welcome to - FRANK TG NUMBERS 👋\n\nThe #1 destination for buying & selling Telegram accounts 📞\n\n🆔 Your ID: <code>{user_id}</code>\n💵 Balance: <code>{bal:.2f}$</code>",
        # Main menu buttons
        'btn_buy': "🛒 Buy Account",
        'btn_support': "📞 Support",
        'btn_agents': "👥 Agents",
        'btn_channel': "📢 Activations Channel",
        'btn_ref': "🔗 Referral",
        'btn_purchases': "📦 My Purchases",
        'btn_balance': "💰 My Balance",
        'btn_dev': "👨‍💻 Developer",
        'btn_admin': "⚙️ Admin Panel",
        'btn_topup': "💳 Top Up",
        'btn_laws': "📜 القواعد | LAWS",
        'btn_lang': "🌐 العربية",
        # Laws
        'laws_menu_title': "📜 <b>Rules & Terms</b>\n\nChoose a page:",
        'law1_title': "📋 Rule 1",
        'law1_text': (
            "📋 <b>Rule 1 — No Warranty</b>\n\n"
            "❌ There is NO warranty after purchase."
        ),
        'law2_title': "📋 Rule 2",
        'law2_text': (
            "📋 <b>Rule 2 — Ownership Transfer</b>\n\n"
            "Once the number leaves our hands and is delivered to the buyer, we lose all control over it permanently.\n\n"
            "We have no way to retrieve or control the number after delivery.\n\n"
            "It becomes the sole property of the buyer."
        ),
        'law3_title': "📋 Rule 3",
        'law3_text': (
            "📋 <b>Rule 3 — Misuse</b>\n\n"
            "Many users damage the account by deleting it, exploiting vulnerabilities, or misusing it — then demand compensation.\n\n"
            "⚠️ In this case there is NO warranty.\n\n"
            "If the account is misused and gets frozen, any compensation request will be rejected ✓"
        ),
        'law4_title': "📋 Rule 4",
        'law4_text': (
            "📋 <b>Rule 4 — Agreement to Terms</b>\n\n"
            "⚠️ <b>Important:</b>\n\n"
            "Pressing the Buy button = agreeing to all terms.\n\n"
            "There is no room for reversal."
        ),
        'law_page': "Page {cur} of {total}",
        'prev': "◀️ Previous",
        'next': "Next ▶️",
        'laws_menu_btn': "📜 Menu",
        'agents_text': (
            "Welcome to the Agents section. Here is a list of agents officially approved by the administration.\n\n"
            "✅ You can top up via them with full trust and a guarantee from the administration.\n\n"
            "⚠️ If you notice any inappropriate behavior from any of them, please report it immediately."
        ),
        'agent_btn': "👤 Agent | @DYD55",
        'buy_title': "🌏 <b>Available Countries:</b>\n\nChoose the country you want to buy an account from:",
        'no_cats': "❌ No sections available.",
        'go_back': "🔙 Back",
        'bought': "🎉 <b>Purchase successful!</b>\n📞 <code>{phone}</code>\n💰 Balance: ${bal:.2f}",
        'get_otp': "📥 Get OTP Code",
        'get_2fa': "🔐 Get 2FA Password",
        'confirm_login': "✅ Login Completed",
        'topup_choose': "💳 <b>Choose top-up method:</b>",
        'stars_btn': "⭐ Top up with Stars (Telegram Stars)",
        'asia_btn': "🌏 Top up via Asia",
        'purchases_empty': "❌ You haven't made any purchases or top-ups yet.",
        'purchases_title': "📦 <b>Your Account History:</b>\n\n",
        'purchase_count': "🛒 <b>Purchase count:</b> {n}\n",
        'recharge_count': "💳 <b>Top-up count:</b> {n}\n\n",
        'purchase_details': "📋 <b>Purchase details:</b>\n",
    }
}

def t(uid, key, **kwargs):
    lang = get_lang(uid)
    text = TEXTS[lang].get(key, TEXTS['ar'].get(key, key))
    if kwargs:
        try:
            text = text.format(**kwargs)
        except:
            pass
    return text

# مسارات ثابتة ومطلقة (مهم جداً)
# بدون هذا، أي إعادة تشغيل (restart) من مسار عمل (working directory) مختلف
# كانت تخلق قاعدة بيانات جديدة فاضية ويبدو الأمر كأن الأرقام والأرصدة "اختفت"
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
DB_PATH       = os.path.join(BASE_DIR, 'levi_bot.db')
SESSIONS_DIR  = os.path.join(BASE_DIR, 'sessions')

for folder in ['sessions', 'sessions_good', 'sessions_spam', 'sessions_old', 'uploaded_files']:
    os.makedirs(os.path.join(BASE_DIR, folder), exist_ok=True)

logging.basicConfig(level=logging.INFO)
bot     = Bot(token=API_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp      = Dispatcher(bot, storage=storage)

active_clients: dict = {}

channel_msg_queue: asyncio.Queue = asyncio.Queue()

async def _channel_worker():

    while True:
        item = await channel_msg_queue.get()
        chat_id  = item['chat_id']
        text     = item['text']
        markup   = item.get('markup')
        parse_md = item.get('parse_mode')
        max_retries = 5
        for attempt in range(max_retries):
            try:
                await bot.send_message(chat_id, text, reply_markup=markup, parse_mode=parse_md)
                logging.info(f"✅ Channel message sent successfully (attempt {attempt+1})")
                break
            except Exception as e:
                err_name = type(e).__name__
                # FloodWait: تيليجرام يطلب انتظار محدد
                if 'FloodWait' in err_name or 'flood' in str(e).lower():
                    import re as _re
                    wait_match = _re.search(r'(\d+)', str(e))
                    wait_sec   = int(wait_match.group(1)) + 5 if wait_match else 60
                    logging.warning(f"⏳ FloodWait {wait_sec}s قبل إعادة إرسال القناة")
                    await asyncio.sleep(wait_sec)
                    continue
                # البوت مش أدمن أو ممنوع من النشر
                elif any(x in err_name for x in ['Forbidden', 'ChatWriteForbidden', 'ChatAdminRequired']):
                    logging.error(f"🚫 البوت لا يملك صلاحية النشر في {chat_id}: {e}")
                    # أبلغ الأدمن مرة واحدة بس
                    try:
                        await bot.send_message(
                            ADMIN_USERNAME,
                            f"🚫 <b>خطأ حرج:</b> البوت لا يملك صلاحية النشر في القناة <b>{chat_id}</b>\n"
                            f"يرجى إضافة البوت كأدمن بصلاحية <b>Post Messages</b>."
                        )
                    except:
                        pass
                    break  # لا فائدة من إعادة المحاولة
                else:
                    wait = 2 ** attempt  # 1, 2, 4, 8, 16 ثانية
                    logging.warning(f"⚠️ فشل الإرسال (محاولة {attempt+1}/{max_retries}): {e} — إعادة بعد {wait}s")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(wait)
                    else:
                        logging.error(f"❌ فشل نهائي بعد {max_retries} محاولات: {e}")
                        try:
                            await bot.send_message(
                                ADMIN_USERNAME,
                                f"❌ <b>فشل إرسال رسالة القناة بعد {max_retries} محاولات</b>\n"
                                f"الخطأ: <code>{type(e).__name__}: {e}</code>\n\n"
                                f"الرسالة:\n<code>{text[:300]}</code>"
                            )
                        except:
                            pass
        channel_msg_queue.task_done()

async def send_to_channel(text: str, markup=None, parse_mode=None):
    """
    أضف رسالة إلى queue القناة بدلاً من الإرسال المباشر.
    هذا يضمن عدم ضياع أي رسالة حتى لو كان هناك FloodWait.
    """
    await channel_msg_queue.put({
        'chat_id':    ACTIVATIONS_CHANNEL,
        'text':       text,
        'markup':     markup,
        'parse_mode': parse_mode,
    })


# قاعدة البيانات
conn   = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()
# WAL: يحافظ على البيانات سليمة وغير قابلة للتلف حتى لو حصل إيقاف غير متوقع للبوت
cursor.execute("PRAGMA journal_mode=WAL;")
cursor.execute("PRAGMA synchronous=FULL;")

def init_db():
    cursor.executescript('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY, username TEXT, balance REAL DEFAULT 0.0,
            referred_by INTEGER DEFAULT NULL,
            verified INTEGER DEFAULT 0
        );
        CREATE TABLE IF NOT EXISTS categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, prefix TEXT, price REAL
        );
        CREATE TABLE IF NOT EXISTS accounts (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            phone        TEXT,
            session_name TEXT,
            country_id   INTEGER,
            password_2fa TEXT,
            status       TEXT DEFAULT 'available',
            buyer_id     INTEGER,
            otp          TEXT
        );
    ''')
    conn.commit()
    _migrate()

def _migrate():
    cols   = [r[1] for r in cursor.execute("PRAGMA table_info(users)").fetchall()]
    if 'referred_by' not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN referred_by INTEGER DEFAULT NULL")
        conn.commit()
    if 'verified' not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN verified INTEGER DEFAULT 0")
        conn.commit()
    if 'recharge_count' not in cols:
        cursor.execute("ALTER TABLE users ADD COLUMN recharge_count INTEGER DEFAULT 0")
        conn.commit()

    cols   = [r[1] for r in cursor.execute("PRAGMA table_info(accounts)").fetchall()]
    needed = {
        'phone':        'ALTER TABLE accounts ADD COLUMN phone TEXT',
        'session_name': 'ALTER TABLE accounts ADD COLUMN session_name TEXT',
        'country_id':   'ALTER TABLE accounts ADD COLUMN country_id INTEGER',
        'password_2fa': 'ALTER TABLE accounts ADD COLUMN password_2fa TEXT',
        'status':       "ALTER TABLE accounts ADD COLUMN status TEXT DEFAULT 'available'",
        'buyer_id':     'ALTER TABLE accounts ADD COLUMN buyer_id INTEGER',
        'otp':          'ALTER TABLE accounts ADD COLUMN otp TEXT',
    }
    for col, sql in needed.items():
        if col not in cols:
            try:
                cursor.execute(sql); conn.commit()
            except Exception as e:
                logging.warning(f"Migration: {e}")

init_db()

# تخزين مؤقت لمعرفات المُحيلين لحين اكتمال اشتراك المستخدم الجديد
pending_referrers: dict = {}

# FSM

class AdminStates(StatesGroup):
    waiting_for_cat_name      = State()
    waiting_for_cat_prefix    = State()
    waiting_for_cat_price     = State()
    waiting_for_session_file  = State()
    waiting_for_session_phone = State()
    waiting_for_session_2fa   = State()
    checker_phone             = State()
    checker_code              = State()
    checker_2fa               = State()
    checker_cat               = State()
    waiting_for_numbers_file  = State()
    add_to_cat_session_file   = State()
    add_to_cat_phone          = State()
    add_to_cat_code           = State()
    add_to_cat_2fa            = State()
    gift_user_id              = State()
    gift_amount               = State()
    asia_approve_amount       = State()
    asia_reject_reason        = State()
    bulk_select_cat           = State()
    bulk_code                 = State()
    bulk_2fa                  = State()

class PaymentStates(StatesGroup):
    waiting_for_stars = State()

class AsiaTopUpStates(StatesGroup):
    waiting_for_amount = State()
    waiting_for_screenshot = State()

class CaptchaStates(StatesGroup):
    waiting_for_answer = State()


# دوال مساعدة
def get_user_balance(uid):
    cursor.execute("SELECT balance FROM users WHERE id=?", (uid,))
    r = cursor.fetchone()
    return r[0] if r else 0.0

def add_user_if_not_exists(uid, username, referrer=None):
    cursor.execute("SELECT id, verified FROM users WHERE id=?", (uid,))
    row = cursor.fetchone()
    if row is None:
        cursor.execute("INSERT INTO users (id, username, balance, referred_by, verified) VALUES (?,?,0.0,?,0)",
                       (uid, username, referrer))
        conn.commit()
        if referrer:
            cursor.execute("UPDATE users SET balance = balance + 0.01 WHERE id=?", (referrer,))
            conn.commit()
    else:
        cursor.execute("UPDATE users SET username=? WHERE id=?", (username, uid))
        conn.commit()

def is_user_verified(uid):
    cursor.execute("SELECT verified FROM users WHERE id=?", (uid,))
    r = cursor.fetchone()
    return r and r[0] == 1

def set_user_verified(uid):
    cursor.execute("UPDATE users SET verified=1 WHERE id=?", (uid,))
    conn.commit()

def get_accounts_count(cat_id):
    cursor.execute("SELECT COUNT(*) FROM accounts WHERE country_id=? AND status='available'", (cat_id,))
    return cursor.fetchone()[0]

def mask_phone(phone: str) -> str:
    if phone.startswith('+'):
        phone = phone[1:]
    if len(phone) >= 7:
        return phone[:7] + '*' * (len(phone) - 7)
    return phone

def mask_user_id(uid: int) -> str:
    s = str(uid)
    if len(s) >= 5:
        return s[:5] + '*' * (len(s) - 5)
    return s

def is_full_admin(username) -> bool:
    return username == ADMIN_USERNAME

def is_admin(username) -> bool:
    return username == ADMIN_USERNAME or username in SUB_ADMIN_USERNAMES

# دوال بناء الأزرار الملونة
def colored_button(text, callback_data, color):
    return {"text": text, "callback_data": callback_data, "style": color}

def colored_url_button(text, url, color):
    return {"text": text, "url": url, "style": color}

def colored_inline_keyboard(*rows):
    keyboard = []
    for row in rows:
        kb_row = []
        for btn in row:
            if isinstance(btn, dict):
                kb_row.append(btn)
            else:
                d = {"text": btn.text}
                if btn.callback_data:
                    d["callback_data"] = btn.callback_data
                if btn.url:
                    d["url"] = btn.url
                kb_row.append(d)
        keyboard.append(kb_row)
    return {"inline_keyboard": keyboard}

def cancel_markup():
    return colored_inline_keyboard([
        colored_button("❌ إلغاء", "admin_panel", "danger")
    ])

# التحقق من الاشتراك الإجباري في القناتين
async def is_subscribed(user_id) -> bool:
    try:
        for ch in SUBSCRIBE_CHANNELS:
            member = await bot.get_chat_member(ch, user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        return True
    except:
        return False

async def send_subscribe_message(chat_id, user_id):
    lang = get_lang(user_id)
    T = TEXTS[lang]
    kb = colored_inline_keyboard(
        [colored_url_button("📢 اشترك في FRANK TG NUMBERS", f"https://t.me/{SUBSCRIBE_CHANNELS[0].lstrip('@')}", "success")],
        [colored_url_button("📢 اشترك في قناة التفعيلات", f"https://t.me/{SUBSCRIBE_CHANNELS[1].lstrip('@')}", "danger")],
        [colored_button(T['sub_check_btn'], "check_sub", "danger")]
    )
    await bot.send_message(chat_id, T['sub_required'], reply_markup=kb)

# أسئلة التحقق العشوائية (كابتشا)
CAPTCHA_QUESTIONS = [
    {"q": "ما ناتج 5 + 3 ؟", "correct": "8", "wrong": ["6", "7", "9"]},
    {"q": "ما ناتج 12 - 4 ؟", "correct": "8", "wrong": ["7", "9", "6"]},
    {"q": "ما ناتج 3 × 4 ؟", "correct": "12", "wrong": ["10", "14", "9"]},
    {"q": "ما ناتج 15 ÷ 5 ؟", "correct": "3", "wrong": ["2", "4", "5"]},
    {"q": "أي لون هو لون السماء في النهار الصافي؟", "correct": "أزرق", "wrong": ["أخضر", "أحمر", "أصفر"]},
    {"q": "كم عدد الأيام في الأسبوع؟", "correct": "7", "wrong": ["5", "6", "8"]},
    {"q": "ما هو الحيوان الذي يُلقب بسفينة الصحراء؟", "correct": "الجمل", "wrong": ["الحصان", "الفيل", "الأسد"]},
]

def generate_captcha():
    item = random.choice(CAPTCHA_QUESTIONS)
    question = item["q"]
    correct = item["correct"]
    options = item["wrong"] + [correct]
    random.shuffle(options)
    return question, correct, options

def build_captcha_markup(options):
    colors = ["primary", "success", "danger", "primary"]
    buttons = []
    for i, opt in enumerate(options):
        buttons.append([colored_button(opt, f"captcha_{opt}", colors[i % len(colors)])])
    return colored_inline_keyboard(*buttons)

# القائمة الرئيسية
def get_main_markup(username, uid=0):
    lang = get_lang(uid)
    T = TEXTS[lang]
    buttons = [
        [colored_button(T['btn_buy'], "buy_account", "success"),
         colored_url_button(T['btn_support'], "https://t.me/DYD55", "danger")],
        [colored_button(T['btn_agents'], "agents_menu", "success"),
         colored_url_button(T['btn_channel'], "https://t.me/az_cxz", "danger")],
        [colored_button(T['btn_ref'], "referral_link", "success"),
         colored_button(T['btn_purchases'], "my_purchases", "danger")],
        [colored_button(T['btn_balance'], "my_balance", "success"),
         colored_url_button(T['btn_dev'], f"https://t.me/{ADMIN_USERNAME}", "danger")],
        [colored_button(T['btn_laws'], "laws_menu", "primary"),
         colored_button(T['btn_lang'], "toggle_lang", "primary")],
    ]
    if is_admin(username):
        buttons.append([colored_button(T['btn_admin'], "admin_panel", "danger")])
    buttons.append([colored_button(T['btn_topup'], "add_balance", "primary")])
    return colored_inline_keyboard(*buttons)

def get_admin_markup():
    return colored_inline_keyboard(
        [colored_button("➕ إضافة قسم/دولة", "admin_add_cat", "danger")],
        [colored_button("📋 إدارة الأقسام", "admin_manage_cats", "success")],
        [colored_button("📂 رفع ملف جلسة (.session)", "admin_add_session", "danger")],
        [colored_button("🔢 فحص رقم واحد + تسجيل دخول", "admin_check_single", "success")],
        [colored_button("📄 رفع ملف أرقام (numbers.txt)", "admin_upload_numbers", "danger")],
        [colored_button("🎁 منح رصيد لمستخدم", "admin_gift_balance", "success")],
        [colored_button("📊 إحصائيات", "admin_stats", "danger")],
        [colored_button("🔙 رجوع للقائمة", "main_menu", "success")]
    )

# لوحة أدمن مساعد بصلاحيات محدودة: إضافة أرقام/جلسات إلى الأقسام فقط
def get_sub_admin_markup():
    return colored_inline_keyboard(
        [colored_button("📋 إدارة الأقسام (إضافة أرقام)", "admin_manage_cats", "success")],
        [colored_button("📂 رفع ملف جلسة (.session)", "admin_add_session", "danger")],
        [colored_button("🔢 فحص رقم واحد + تسجيل دخول", "admin_check_single", "success")],
        [colored_button("🔙 رجوع للقائمة", "main_menu", "danger")]
    )

def admin_markup_for(username):
    return get_admin_markup() if username == ADMIN_USERNAME else get_sub_admin_markup()

# SpamBot و الفحص
async def check_spambot(client: TelegramClient) -> str:
    try:
        await client.send_message('spambot', '/start')
        await asyncio.sleep(3)
        msgs = await client.get_messages('spambot', limit=1)
        if msgs:
            t = msgs[0].message or ''
            return 'good' if ('Good news' in t or 'لا توجد قيود' in t) else 'spam'
        return 'unknown'
    except Exception:
        return 'error'

async def run_full_check(client: TelegramClient, phone: str, password_2fa: str = None):
    me = await client.get_me()
    is_premium = getattr(me, 'premium', False)
    spam_status = await check_spambot(client)
    groups = channels = 0
    try:
        from telethon.tl.functions.messages import GetDialogsRequest
        from telethon.tl.types import InputPeerEmpty, Channel, Chat as TLChat
        result = await client(GetDialogsRequest(
            offset_date=None, offset_id=0,
            offset_peer=InputPeerEmpty(), limit=500, hash=0
        ))
        for chat in result.chats:
            if isinstance(chat, Channel):
                channels += 1 if chat.broadcast else 0
                groups   += 0 if chat.broadcast else 1
            elif isinstance(chat, TLChat):
                groups += 1
    except Exception as ex:
        logging.warning(f"Dialogs: {ex}")
    is_old = me.id < 6_500_000_000
    spam_text = {
        'good':    '✅ سليم بدون قيود',
        'spam':    '🚫 عليه قيود سبام',
        'unknown': '❓ غير معروف',
        'error':   '⚠️ خطأ في الفحص',
    }.get(spam_status, '❓')
    result_text = (
        f"📊 <b>نتيجة الفحص</b>\n\n"
        f"📞 الرقم      : <code>{phone}</code>\n"
        f"👤 الاسم      : <b>{me.first_name or ''} {me.last_name or ''}</b>\n"
        f"🆔 ID         : <code>{me.id}</code>\n"
        f"⭐ Premium    : {'نعم ✅' if is_premium else 'لا ❌'}\n"
        f"🔎 SpamBot    : {spam_text}\n"
        f"👥 مجموعات   : <b>{groups}</b>\n"
        f"📢 قنوات      : <b>{channels}</b>\n"
        f"📅 العمر      : {'🕰️ قديم (قبل 2024)' if is_old else '🆕 جديد'}\n"
        f"🔐 2FA        : <code>{password_2fa or 'لا يوجد'}</code>\n\n"
    )
    return {
        'me': me,
        'is_premium': is_premium,
        'spam_status': spam_status,
        'groups': groups,
        'channels': channels,
        'is_old': is_old,
        'result_text': result_text,
    }

# /start مع الاشتراك الإجباري والتحقق البشري

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message, state: FSMContext):
    global ADMIN_ID
    if message.from_user.username == ADMIN_USERNAME:
        ADMIN_ID = message.chat.id

    referrer = None
    args = message.get_args()
    if args and args.startswith('ref'):
        try:
            referrer = int(args[3:])
        except:
            pass
    if not await is_subscribed(message.from_user.id):
        if referrer:
            pending_referrers[message.from_user.id] = referrer
        await send_subscribe_message(message.chat.id, message.from_user.id)
        return
    add_user_if_not_exists(message.from_user.id, message.from_user.username, referrer or pending_referrers.pop(message.from_user.id, None))

    uid = message.from_user.id
    if is_user_verified(uid):
        bal = get_user_balance(uid)
        await message.answer(
            t(uid, 'welcome', user_id=uid, bal=bal),
            reply_markup=get_main_markup(message.from_user.username, uid)
        )
        return

    question, correct, options = generate_captcha()
    await state.update_data(captcha_correct=correct)
    await message.answer(
        f"{t(uid, 'captcha_title')}{question}",
        reply_markup=build_captcha_markup(options)
    )
    await CaptchaStates.waiting_for_answer.set()

@dp.callback_query_handler(lambda c: c.data.startswith('captcha_'), state=CaptchaStates.waiting_for_answer)
async def captcha_answer(call: types.CallbackQuery, state: FSMContext):
    answer = call.data.split('_', 1)[1]
    data = await state.get_data()
    correct = data.get('captcha_correct', '')
    uid = call.from_user.id
    if answer == correct:
        set_user_verified(uid)
        await state.finish()
        bal = get_user_balance(uid)
        await call.message.edit_text(
            t(uid, 'verified_ok') + t(uid, 'welcome', user_id=uid, bal=bal),
            reply_markup=get_main_markup(call.from_user.username, uid)
        )
    else:
        await call.answer(t(uid, 'captcha_wrong'), show_alert=True)

@dp.callback_query_handler(text="check_sub")
async def check_subscription(call: types.CallbackQuery):
    uid = call.from_user.id
    if await is_subscribed(uid):
        referrer = pending_referrers.pop(uid, None)
        add_user_if_not_exists(uid, call.from_user.username, referrer)
        if not is_user_verified(uid):
            question, correct, options = generate_captcha()
            state = dp.current_state(chat=call.message.chat.id, user=uid)
            await state.update_data(captcha_correct=correct)
            await call.message.edit_text(
                f"{t(uid, 'captcha_title')}{question}",
                reply_markup=build_captcha_markup(options)
            )
            await CaptchaStates.waiting_for_answer.set()
            return
        bal = get_user_balance(uid)
        await call.message.edit_text(
            t(uid, 'sub_verified') + t(uid, 'welcome', user_id=uid, bal=bal),
            reply_markup=get_main_markup(call.from_user.username, uid)
        )
    else:
        await call.answer(t(uid, 'sub_not_done'), show_alert=True)

@dp.callback_query_handler(text="main_menu", state="*")
async def back_to_main(call: types.CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    if not await is_subscribed(uid):
        await send_subscribe_message(call.message.chat.id, uid)
        await state.finish()
        return
    if not is_user_verified(uid):
        await call.answer(t(uid, 'human_check'), show_alert=True)
        return
    await state.finish()
    client = active_clients.pop(uid, None)
    if client and client.is_connected():
        await client.disconnect()
    bal = get_user_balance(uid)
    await call.message.edit_text(
        t(uid, 'main_menu_title', user_id=uid, bal=bal),
        reply_markup=get_main_markup(call.from_user.username, uid)
    )

# دوال القائمة الرئيسية
@dp.callback_query_handler(text="my_balance")
async def my_balance(call: types.CallbackQuery):
    uid = call.from_user.id
    if not await is_subscribed(uid): return await call.answer(t(uid,'sub_first'), show_alert=True)
    if not is_user_verified(uid): return await call.answer(t(uid,'human_check'), show_alert=True)
    bal = get_user_balance(uid)
    await call.answer(t(uid,'balance',bal=bal), show_alert=True)

@dp.callback_query_handler(text="referral_link")
async def referral_link(call: types.CallbackQuery):
    uid = call.from_user.id
    if not await is_subscribed(uid): return await call.answer(t(uid,'sub_first'), show_alert=True)
    if not is_user_verified(uid): return await call.answer(t(uid,'human_check'), show_alert=True)
    ref_link = f"https://t.me/{BOT_USERNAME}?start=ref{uid}"
    await call.message.edit_text(
        t(uid, 'ref_text', link=ref_link),
        reply_markup=colored_inline_keyboard([colored_button(t(uid,'back'), "main_menu", "danger")])
    )

@dp.callback_query_handler(text="my_purchases")
async def my_purchases(call: types.CallbackQuery):
    uid = call.from_user.id
    if not await is_subscribed(uid): return await call.answer(t(uid,'sub_first'), show_alert=True)
    if not is_user_verified(uid): return await call.answer(t(uid,'human_check'), show_alert=True)
    cursor.execute(
        "SELECT a.phone, c.name, c.price FROM accounts a LEFT JOIN categories c ON a.country_id = c.id WHERE a.buyer_id=? AND a.status='sold'",
        (uid,)
    )
    purchases = cursor.fetchall()
    recharge_row = cursor.execute("SELECT recharge_count FROM users WHERE id=?", (uid,)).fetchone()
    recharge_count = recharge_row[0] if recharge_row else 0
    if not purchases and recharge_count == 0:
        await call.answer(t(uid,'purchases_empty'), show_alert=True)
        return
    text = t(uid,'purchases_title')
    text += t(uid,'purchase_count',n=len(purchases))
    text += t(uid,'recharge_count',n=recharge_count)
    if purchases:
        text += t(uid,'purchase_details')
        for p in purchases:
            phone = mask_phone(p[0]) if p[0] else "غير معروف"
            text += f"🌍 {p[1]} | 📞 {phone} | 💵 ${p[2]:.2f}\n"
    await call.message.edit_text(
        text,
        reply_markup=colored_inline_keyboard([colored_button(t(uid,'back'), "main_menu", "danger")])
    )

# قسم الوكلاء
@dp.callback_query_handler(text="agents_menu")
async def agents_menu(call: types.CallbackQuery):
    uid = call.from_user.id
    if not await is_subscribed(uid): return await call.answer(t(uid,'sub_first'), show_alert=True)
    if not is_user_verified(uid): return await call.answer(t(uid,'human_check'), show_alert=True)
    kb = colored_inline_keyboard(
        [colored_url_button(t(uid,'agent_btn'), "https://t.me/DYD55", "primary")],
        [colored_button(t(uid,'back'), "main_menu", "danger")]
    )
    await call.message.edit_text(t(uid,'agents_text'), reply_markup=kb)

# تغيير اللغة
@dp.callback_query_handler(text="toggle_lang")
async def toggle_language(call: types.CallbackQuery):
    uid = call.from_user.id
    current = get_lang(uid)
    user_languages[uid] = 'en' if current == 'ar' else 'ar'
    bal = get_user_balance(uid)
    await call.message.edit_text(
        t(uid, 'main_menu_title', user_id=uid, bal=bal),
        reply_markup=get_main_markup(call.from_user.username, uid)
    )

# القواعد
LAWS_COUNT = 4

def get_laws_keyboard(uid, page):
    lang = get_lang(uid)
    T = TEXTS[lang]
    buttons = []
    nav = []
    if page > 1:
        nav.append(colored_button(T['prev'], f"laws_page_{page-1}", "primary"))
    if page < LAWS_COUNT:
        nav.append(colored_button(T['next'], f"laws_page_{page+1}", "success"))
    if nav:
        buttons.append(nav)
    buttons.append([colored_button(T['laws_menu_btn'], "laws_menu", "danger")])
    buttons.append([colored_button(T['back'], "main_menu", "primary")])
    return colored_inline_keyboard(*buttons)

@dp.callback_query_handler(text="laws_menu")
async def laws_menu(call: types.CallbackQuery):
    uid = call.from_user.id
    lang = get_lang(uid)
    T = TEXTS[lang]
    kb = colored_inline_keyboard(
        [colored_button(T['law1_title'], "laws_page_1", "success")],
        [colored_button(T['law2_title'], "laws_page_2", "danger")],
        [colored_button(T['law3_title'], "laws_page_3", "success")],
        [colored_button(T['law4_title'], "laws_page_4", "danger")],
        [colored_button(T['back'], "main_menu", "primary")]
    )
    await call.message.edit_text(T['laws_menu_title'], reply_markup=kb)

@dp.callback_query_handler(lambda c: c.data.startswith('laws_page_'))
async def laws_page(call: types.CallbackQuery):
    uid = call.from_user.id
    lang = get_lang(uid)
    T = TEXTS[lang]
    try:
        page = int(call.data.split('_')[2])
    except:
        page = 1
    page = max(1, min(page, LAWS_COUNT))
    law_key = f'law{page}_text'
    page_label = T['law_page'].format(cur=page, total=LAWS_COUNT)
    text = T.get(law_key, '') + f"\n\n<i>{page_label}</i>"
    await call.message.edit_text(text, reply_markup=get_laws_keyboard(uid, page))

@dp.callback_query_handler(text="admin_panel", state="*")
async def admin_panel(call: types.CallbackQuery, state: FSMContext):
    uid = call.from_user.id
    if not await is_subscribed(uid): return await call.answer(t(uid,'sub_first'), show_alert=True)
    if not is_user_verified(uid): return await call.answer(t(uid,'human_check'), show_alert=True)
    if not is_admin(call.from_user.username): return await call.answer("⛔ للمطور فقط.", show_alert=True)
    await state.finish()
    if call.from_user.username == ADMIN_USERNAME:
        await call.message.edit_text("⚙️ <b>لوحة تحكم المطور</b>", reply_markup=get_admin_markup())
    else:
        await call.message.edit_text(
            "⚙️ <b>لوحة تحكم المطور</b>\n"
            "🔐 صلاحياتك محدودة: إضافة أرقام/جلسات إلى الأقسام فقط.",
            reply_markup=get_sub_admin_markup()
        )

@dp.callback_query_handler(text="admin_stats")
async def admin_stats(call: types.CallbackQuery):
    if not await is_subscribed(call.from_user.id): return await call.answer("⚠️ اشترك أولاً", show_alert=True)
    if not is_user_verified(call.from_user.id): return await call.answer("يرجى إكمال التحقق البشري أولاً.", show_alert=True)
    if call.from_user.username != ADMIN_USERNAME: return await call.answer("⛔", show_alert=True)
    cursor.execute("SELECT COUNT(*) FROM users"); u = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM accounts WHERE status='available'"); av = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM accounts WHERE status='sold'"); so = cursor.fetchone()[0]
    cursor.execute("SELECT COUNT(*) FROM categories"); ca = cursor.fetchone()[0]
    cursor.execute("SELECT SUM(balance) FROM users"); bal = cursor.fetchone()[0] or 0
    m = colored_inline_keyboard([colored_button("🔙 رجوع", "admin_panel", "danger")])
    await call.message.edit_text(
        f"📊 <b>إحصائيات</b>\n\n"
        f"👥 مستخدمون: <b>{u}</b>\n"
        f"🟢 حسابات متاحة: <b>{av}</b>\n"
        f"✅ مباعة: <b>{so}</b>\n"
        f"🌍 أقسام: <b>{ca}</b>\n"
        f"💵 إجمالي الأرصدة: <b>${bal:.2f}</b>",
        reply_markup=m
    )

@dp.callback_query_handler(text="admin_gift_balance")
async def gift_balance_start(call: types.CallbackQuery):
    if not await is_subscribed(call.from_user.id): return await call.answer("⚠️ اشترك أولاً", show_alert=True)
    if not is_user_verified(call.from_user.id): return await call.answer("يرجى إكمال التحقق البشري أولاً.", show_alert=True)
    if call.from_user.username != ADMIN_USERNAME: return await call.answer("⛔", show_alert=True)
    await call.message.edit_text("🎁 <b>منح رصيد لمستخدم</b>\n\nأرسل آيدي المستخدم الرقمي:", reply_markup=cancel_markup())
    await AdminStates.gift_user_id.set()

@dp.message_handler(state=AdminStates.gift_user_id)
async def gift_balance_get_id(message: types.Message, state: FSMContext):
    if not message.text.isdigit(): return await message.answer("❌ أرسل آيدي رقمي صحيح.")
    uid = int(message.text)
    await state.update_data(gift_uid=uid)
    await message.answer(f"💰 كم المبلغ الذي تريد منحه للمستخدم <code>{uid}</code>؟\nمثال: <code>10.5</code>")
    await AdminStates.gift_amount.set()

@dp.message_handler(state=AdminStates.gift_amount)
async def gift_balance_get_amount(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0: raise ValueError
    except ValueError: return await message.answer("❌ أرسل رقماً موجباً صحيحاً.")
    data = await state.get_data()
    uid = data['gift_uid']
    add_user_if_not_exists(uid, None)
    current = get_user_balance(uid)
    new_bal = current + amount
    cursor.execute("UPDATE users SET balance=? WHERE id=?", (new_bal, uid))
    conn.commit()
    await message.answer(
        f"✅ <b>تم منح الرصيد بنجاح!</b>\n"
        f"👤 المستخدم: <code>{uid}</code>\n"
        f"💵 المبلغ المضاف: ${amount:.2f}\n"
        f"💰 رصيده الحالي: ${new_bal:.2f}",
        reply_markup=get_admin_markup()
    )
    await state.finish()

# إدارة الأقسام (مع خيار الحذف)
@dp.callback_query_handler(text="admin_manage_cats")
async def admin_manage_cats(call: types.CallbackQuery):
    if not await is_subscribed(call.from_user.id): return await call.answer("⚠️ اشترك أولاً", show_alert=True)
    if not is_user_verified(call.from_user.id): return await call.answer("يرجى إكمال التحقق البشري أولاً.", show_alert=True)
    if not is_admin(call.from_user.username): return await call.answer("⛔", show_alert=True)
    cursor.execute("SELECT id, name, prefix, price FROM categories")
    cats = cursor.fetchall()
    if not cats:
        m = colored_inline_keyboard([colored_button("🔙 رجوع", "admin_panel", "danger")])
        return await call.message.edit_text("❌ لا توجد أقسام بعد.", reply_markup=m)
    rows = []
    for cat in cats:
        count = get_accounts_count(cat[0])
        rows.append([colored_button(
            f"📁 {cat[1]} ({cat[2]}) | متاح: {count} | ${cat[3]:.2f}",
            f"cat_manage_{cat[0]}", "danger"
        )])
    rows.append([colored_button("🔙 رجوع", "admin_panel", "success")])
    m = colored_inline_keyboard(*rows)
    await call.message.edit_text("📋 <b>اختر قسماً لإدارته:</b>", reply_markup=m)

@dp.callback_query_handler(lambda c: c.data.startswith('cat_manage_'))
async def cat_manage(call: types.CallbackQuery):
    if not is_user_verified(call.from_user.id): return await call.answer("يرجى إكمال التحقق البشري أولاً.", show_alert=True)
    if not is_admin(call.from_user.username): return await call.answer("⛔", show_alert=True)
    cat_id = int(call.data.split('_')[2])
    cursor.execute("SELECT name, prefix, price FROM categories WHERE id=?", (cat_id,))
    cat = cursor.fetchone()
    if not cat: return await call.answer("❌ القسم غير موجود.", show_alert=True)
    count = get_accounts_count(cat_id)
    rows = [
        [colored_button("📲 إضافة رقم (تسجيل دخول + فحص)", f"addcat_phone_{cat_id}", "danger")],
        [colored_button("📂 إضافة .session (فحص)", f"addcat_session_{cat_id}", "success")],
    ]
    if call.from_user.username == ADMIN_USERNAME:
        rows.append([colored_button("🗑️ حذف القسم", f"delete_cat_{cat_id}", "primary")])
    rows.append([colored_button("🔙 رجوع للأقسام", "admin_manage_cats", "danger")])
    m = colored_inline_keyboard(*rows)
    await call.message.edit_text(
        f"📁 <b>قسم:</b> {cat[0]}\n"
        f"🔢 البادئة: <code>{cat[1]}</code> | 💵 السعر: <code>${cat[2]:.2f}</code>\n"
        f"🟢 الحسابات المتاحة: <b>{count}</b>\n\n"
        f"اختر العملية:", reply_markup=m
    )

@dp.callback_query_handler(lambda c: c.data.startswith('delete_cat_'))
async def delete_cat_confirm(call: types.CallbackQuery):
    if not is_user_verified(call.from_user.id): return await call.answer("يرجى إكمال التحقق البشري أولاً.", show_alert=True)
    if call.from_user.username != ADMIN_USERNAME: return await call.answer("⛔", show_alert=True)
    cat_id = int(call.data.split('_')[2])
    cursor.execute("SELECT name FROM categories WHERE id=?", (cat_id,))
    cat = cursor.fetchone()
    if not cat: return await call.answer("❌ القسم غير موجود.", show_alert=True)
    kb = colored_inline_keyboard([
        colored_button("✅ نعم، احذف", f"confirm_delete_cat_{cat_id}", "danger"),
        colored_button("❌ إلغاء", f"cat_manage_{cat_id}", "success")
    ])
    await call.message.edit_text(
        f"⚠️ <b>هل أنت متأكد من حذف قسم \"{cat[0]}\"؟</b>\n"
        f"سيتم حذف جميع الحسابات المرتبطة به نهائياً.",
        reply_markup=kb
    )

@dp.callback_query_handler(lambda c: c.data.startswith('confirm_delete_cat_'))
async def confirm_delete_cat(call: types.CallbackQuery):
    if not is_user_verified(call.from_user.id): return await call.answer("يرجى إكمال التحقق البشري أولاً.", show_alert=True)
    if call.from_user.username != ADMIN_USERNAME: return await call.answer("⛔", show_alert=True)
    try:
        cat_id = int(call.data.split('_')[-1])   # [-1] دايماً رقم القسم
    except (ValueError, IndexError):
        return await call.answer("❌ بيانات غير صحيحة.", show_alert=True)
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _do_delete_cat, cat_id)
    await call.message.edit_text("✅ <b>تم حذف القسم وجميع حساباته بنجاح.</b>",
                                 reply_markup=colored_inline_keyboard([colored_button("🔙 رجوع", "admin_manage_cats", "success")]))

def _do_delete_cat(cat_id: int):
    cursor.execute("DELETE FROM accounts WHERE country_id=?", (cat_id,))
    cursor.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    conn.commit()

# إضافة رقم لقسم (فحص تلقائي)
@dp.callback_query_handler(lambda c: c.data.startswith('addcat_phone_'))
async def addcat_phone_start(call: types.CallbackQuery, state: FSMContext):
    if not is_user_verified(call.from_user.id): return await call.answer("يرجى إكمال التحقق البشري أولاً.", show_alert=True)
    if not is_admin(call.from_user.username): return await call.answer("⛔", show_alert=True)
    cat_id = int(call.data.split('_')[2])
    await state.update_data(target_cat_id=cat_id)
    await call.message.edit_text("📲 أرسل الرقم مع كود الدولة:", reply_markup=cancel_markup())
    await AdminStates.add_to_cat_phone.set()

@dp.message_handler(state=AdminStates.add_to_cat_phone)
async def addcat_got_phone(message: types.Message, state: FSMContext):
    number = message.text.strip()
    if not re.match(r'^\+\d{7,15}$', number):
        return await message.answer("❌ صيغة غير صحيحة.", reply_markup=cancel_markup())
    session_path = os.path.join(SESSIONS_DIR, number.replace('+', ''))
    client = TelegramClient(session_path, TELETHON_API_ID, TELETHON_API_HASH)
    try:
        await client.connect()
        sent = await client.send_code_request(number)
        active_clients[message.from_user.id] = client
        await state.update_data(phone=number, phone_code_hash=sent.phone_code_hash, session_path=session_path)
        await message.answer(f"📲 تم إرسال الكود. أرسل الكود:", reply_markup=cancel_markup())
        await AdminStates.add_to_cat_code.set()
    except Exception as e:
        await client.disconnect()
        await message.answer(f"❌ خطأ: {e}")
        await state.finish()

@dp.message_handler(state=AdminStates.add_to_cat_code)
async def addcat_got_code(message: types.Message, state: FSMContext):
    code = message.text.strip().replace(' ', '')
    data = await state.get_data()
    client = active_clients.get(message.from_user.id)
    if not client: await state.finish(); return await message.answer("❌ انتهت الجلسة.")
    try:
        await client.sign_in(data['phone'], code, phone_code_hash=data['phone_code_hash'])
        await _addcat_do_check(message, state, client)
    except errors.SessionPasswordNeededError:
        await message.answer("🔐 أرسل 2FA:", reply_markup=cancel_markup())
        await AdminStates.add_to_cat_2fa.set()
    except Exception as e:
        active_clients.pop(message.from_user.id, None); await client.disconnect()
        await message.answer(f"❌ خطأ: {e}"); await state.finish()

@dp.message_handler(state=AdminStates.add_to_cat_2fa)
async def addcat_got_2fa(message: types.Message, state: FSMContext):
    password = message.text.strip()
    client = active_clients.get(message.from_user.id)
    if not client: await state.finish(); return await message.answer("❌ انتهت الجلسة.")
    try:
        await client.sign_in(password=password)
        await state.update_data(password_2fa=password)
        await _addcat_do_check(message, state, client)
    except Exception as e:
        active_clients.pop(message.from_user.id, None); await client.disconnect()
        await message.answer(f"❌ خطأ: {e}"); await state.finish()

async def _addcat_do_check(message, state, client):
    data = await state.get_data()
    phone = data['phone']; cat_id = data['target_cat_id']; password_2fa = data.get('password_2fa', 'لا يوجد')
    try:
        check = await run_full_check(client, phone, password_2fa)
        await client.disconnect(); active_clients.pop(message.from_user.id, None)
        session_name = phone.replace('+', '') + '.session'
        cursor.execute("INSERT INTO accounts (phone, session_name, country_id, password_2fa, status) VALUES (?,?,?,?,?)",
                       (phone, session_name, cat_id, password_2fa, 'available'))
        conn.commit()
        cat_name = cursor.execute("SELECT name FROM categories WHERE id=?", (cat_id,)).fetchone()[0]
        count = get_accounts_count(cat_id)
        m = colored_inline_keyboard(
            [colored_button("➕ إضافة رقم آخر", f"addcat_phone_{cat_id}", "danger")],
            [colored_button("📋 إدارة الأقسام", "admin_manage_cats", "success")],
            [colored_button("⚙️ لوحة التحكم", "admin_panel", "danger")]
        )
        await message.answer(check['result_text'] + f"✅ تم الحفظ في {cat_name}\n🟢 المتاح: {count}", reply_markup=m)
        await state.finish()
    except Exception as e:
        logging.error(f"_addcat_do_check: {e}")
        if client.is_connected(): await client.disconnect()
        active_clients.pop(message.from_user.id, None)
        await message.answer(f"❌ خطأ: {e}"); await state.finish()

# دوال .session للقسم (فحص تلقائي) - اختصار
@dp.callback_query_handler(lambda c: c.data.startswith('addcat_session_'))
async def addcat_session_start(call: types.CallbackQuery, state: FSMContext):
    if not is_user_verified(call.from_user.id): return await call.answer("يرجى إكمال التحقق البشري أولاً.", show_alert=True)
    if not is_admin(call.from_user.username): return await call.answer("⛔", show_alert=True)
    cat_id = int(call.data.split('_')[2])
    await state.update_data(target_cat_id=cat_id)
    await call.message.edit_text("📂 أرسل ملف .session:", reply_markup=cancel_markup())
    await AdminStates.add_to_cat_session_file.set()

@dp.message_handler(content_types=['document'], state=AdminStates.add_to_cat_session_file)
async def addcat_got_session_file(message: types.Message, state: FSMContext):
    if not message.document.file_name.endswith('.session'): return await message.answer("❌ أرسل ملف .session فقط.")
    data = await state.get_data(); cat_id = data['target_cat_id']
    fname = message.document.file_name; session_name = fname
    session_path_full = os.path.join(SESSIONS_DIR, fname)
    await message.document.download(destination_file=session_path_full)
    raw = fname.replace('.session', ''); phone = f"+{raw}" if raw.isdigit() else None
    session_path_noext = os.path.join(SESSIONS_DIR, raw)
    client = TelegramClient(session_path_noext, TELETHON_API_ID, TELETHON_API_HASH)
    try:
        await client.connect()
        if not await client.is_user_authorized():
            await client.disconnect(); await message.answer("❌ الجلسة غير مصرحة.", reply_markup=admin_markup_for(message.from_user.username)); await state.finish(); return
        me = await client.get_me()
        if not phone: phone = f"+{me.phone}" if me.phone else str(me.id)
        check = await run_full_check(client, phone)
        await client.disconnect()
        cursor.execute("INSERT INTO accounts (phone, session_name, country_id, password_2fa, status) VALUES (?,?,?,?,?)",
                       (phone, session_name, cat_id, 'لا يوجد', 'available'))
        conn.commit()
        cat_name = cursor.execute("SELECT name FROM categories WHERE id=?", (cat_id,)).fetchone()[0]
        count = get_accounts_count(cat_id)
        m = colored_inline_keyboard(
            [colored_button("➕ رفع جلسة أخرى", f"addcat_session_{cat_id}", "danger")],
            [colored_button("📋 إدارة الأقسام", "admin_manage_cats", "success")],
            [colored_button("⚙️ لوحة التحكم", "admin_panel", "danger")]
        )
        await message.answer(check['result_text'] + f"✅ تم الحفظ في {cat_name}\n🟢 المتاح: {count}", reply_markup=m)
        await state.finish()
    except Exception as e:
        logging.error(f"addcat_session: {e}")
        if client.is_connected(): await client.disconnect()
        await message.answer(f"❌ خطأ: {e}", reply_markup=admin_markup_for(message.from_user.username)); await state.finish()

# فحص رقم واحد
@dp.callback_query_handler(text="admin_check_single")
async def checker_start(call: types.CallbackQuery):
    if not is_user_verified(call.from_user.id): return await call.answer("يرجى إكمال التحقق البشري أولاً.", show_alert=True)
    if not is_admin(call.from_user.username): return await call.answer("⛔", show_alert=True)
    await call.message.edit_text("🔢 أرسل الرقم مع كود الدولة:", reply_markup=cancel_markup())
    await AdminStates.checker_phone.set()

@dp.message_handler(state=AdminStates.checker_phone)
async def checker_got_phone(message: types.Message, state: FSMContext):
    number = message.text.strip()
    if not re.match(r'^\+\d{7,15}$', number): return await message.answer("❌ صيغة غير صحيحة.")
    session_path = os.path.join(SESSIONS_DIR, number.replace('+', ''))
    client = TelegramClient(session_path, TELETHON_API_ID, TELETHON_API_HASH)
    try:
        await client.connect(); sent = await client.send_code_request(number)
        active_clients[message.from_user.id] = client
        await state.update_data(phone=number, phone_code_hash=sent.phone_code_hash, session_path=session_path)
        await message.answer(f"📲 تم إرسال الكود. أرسله هنا:", reply_markup=cancel_markup())
        await AdminStates.checker_code.set()
    except Exception as e: await client.disconnect(); await message.answer(f"❌ خطأ: {e}"); await state.finish()

@dp.message_handler(state=AdminStates.checker_code)
async def checker_got_code(message: types.Message, state: FSMContext):
    code = message.text.strip().replace(' ', '')
    data = await state.get_data(); client = active_clients.get(message.from_user.id)
    if not client: await state.finish(); return await message.answer("❌ انتهت الجلسة.")
    try:
        await client.sign_in(data['phone'], code, phone_code_hash=data['phone_code_hash'])
        await _checker_finish(message, state, client, data['phone'])
    except errors.SessionPasswordNeededError:
        await message.answer("🔐 أرسل 2FA:", reply_markup=cancel_markup())
        await AdminStates.checker_2fa.set()
    except Exception as e: active_clients.pop(message.from_user.id, None); await client.disconnect(); await message.answer(f"❌ خطأ: {e}"); await state.finish()

@dp.message_handler(state=AdminStates.checker_2fa)
async def checker_got_2fa(message: types.Message, state: FSMContext):
    password = message.text.strip(); client = active_clients.get(message.from_user.id)
    data = await state.get_data()
    if not client: await state.finish(); return await message.answer("❌ انتهت الجلسة.")
    try:
        await client.sign_in(password=password); await state.update_data(password_2fa=password)
        await _checker_finish(message, state, client, data['phone'])
    except Exception as e: active_clients.pop(message.from_user.id, None); await client.disconnect(); await message.answer(f"❌ خطأ: {e}"); await state.finish()

async def _checker_finish(message, state, client, phone):
    try:
        data = await state.get_data(); password_2fa = data.get('password_2fa', 'لا يوجد')
        check = await run_full_check(client, phone, password_2fa)
        await client.disconnect(); active_clients.pop(message.from_user.id, None)
        cursor.execute("SELECT id, name FROM categories"); cats = cursor.fetchall()
        if not cats:
            session_name = phone.replace('+', '') + '.session'
            cursor.execute("INSERT INTO accounts (phone,session_name,password_2fa,status) VALUES (?,?,?,?)",
                           (phone, session_name, password_2fa, 'available')); conn.commit()
            await message.answer(check['result_text'] + "⚠️ لا توجد أقسام.", reply_markup=admin_markup_for(message.from_user.username)); await state.finish(); return
        await state.update_data(spam_status=check['spam_status'], is_old=check['is_old'], is_premium=check['is_premium'],
                                groups=check['groups'], channels=check['channels'], password_2fa=password_2fa, result_text=check['result_text'])
        rows = [[colored_button(c[1], f"checker_cat_{c[0]}", "danger")] for c in cats]
        rows.append([colored_button("🔙 إلغاء الحفظ", "checker_skip", "success")])
        markup = colored_inline_keyboard(*rows)
        await message.answer(check['result_text'] + "🌍 اختر القسم:", reply_markup=markup)
        await AdminStates.checker_cat.set()
    except Exception as e: logging.error(f"checker_finish: {e}"); await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith('checker_cat_'), state=AdminStates.checker_cat)
async def checker_save_account(call: types.CallbackQuery, state: FSMContext):
    cat_id = int(call.data.split('_')[2]); data = await state.get_data(); phone = data['phone']
    session_name = phone.replace('+', '') + '.session'
    cursor.execute("INSERT INTO accounts (phone,session_name,country_id,password_2fa,status) VALUES (?,?,?,?,?)",
                   (phone, session_name, cat_id, data.get('password_2fa','لا يوجد'), 'available')); conn.commit()
    await call.message.edit_text(f"✅ تم حفظ الحساب!\n📞 <code>{phone}</code>", reply_markup=admin_markup_for(call.from_user.username)); await state.finish()

@dp.callback_query_handler(text="checker_skip", state=AdminStates.checker_cat)
async def checker_skip_save(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("⚠️ تم إلغاء الحفظ."); await state.finish()

# رفع ملف أرقام / إضافة قسم / رفع جلسة (بدون فحص)
@dp.callback_query_handler(text="admin_upload_numbers")
async def admin_upload_numbers(call: types.CallbackQuery):
    if not is_user_verified(call.from_user.id): return await call.answer("يرجى إكمال التحقق البشري أولاً.", show_alert=True)
    if not is_admin(call.from_user.username): return await call.answer("⛔", show_alert=True)
    await call.message.edit_text(
        "📄 <b>رفع ملف أرقام للمعالجة التلقائية</b>\n\n"
        "أرسل ملف <code>.txt</code> يحتوي على الأرقام (رقم واحد في كل سطر مع كود الدولة).\n"
        "مثال:\n<code>+201234567890\n+9665xxxxxxxx</code>",
        reply_markup=cancel_markup()
    )
    await AdminStates.waiting_for_numbers_file.set()

@dp.message_handler(content_types=['document'], state=AdminStates.waiting_for_numbers_file)
async def process_numbers_file(message: types.Message, state: FSMContext):
    if not message.document.file_name.endswith('.txt'):
        return await message.answer("❌ أرسل ملف .txt فقط.")

    file_path = os.path.join(BASE_DIR, 'uploaded_files', 'bulk_numbers.txt')
    await message.document.download(destination_file=file_path)

    with open(file_path, 'r', encoding='utf-8') as f:
        phones = [line.strip() for line in f if line.strip() and re.match(r'^\+\d{7,15}$', line.strip())]

    if not phones:
        await state.finish()
        return await message.answer("❌ لم يتم العثور على أرقام صحيحة في الملف.\nتأكد أن كل رقم في سطر مستقل مع كود الدولة.", reply_markup=admin_markup_for(message.from_user.username))

    cursor.execute("SELECT id, name FROM categories")
    cats = cursor.fetchall()
    if not cats:
        await state.finish()
        return await message.answer("❌ لا توجد أقسام. أنشئ قسماً أولاً.", reply_markup=admin_markup_for(message.from_user.username))

    await state.update_data(bulk_phones=phones, bulk_index=0, bulk_done=0, bulk_failed=0)

    rows = [[colored_button(f"📁 {c[1]}", f"bulk_cat_{c[0]}", "danger")] for c in cats]
    rows.append([colored_button("❌ إلغاء", "admin_panel", "danger")])

    await message.answer(
        f"✅ تم قراءة <b>{len(phones)}</b> رقم من الملف.\n\n"
        f"📌 اختر القسم الذي ستُضاف إليه الأرقام:",
        reply_markup=colored_inline_keyboard(*rows)
    )
    await AdminStates.bulk_select_cat.set()


@dp.callback_query_handler(lambda c: c.data.startswith('bulk_cat_'), state=AdminStates.bulk_select_cat)
async def bulk_cat_selected(call: types.CallbackQuery, state: FSMContext):
    cat_id = int(call.data.split('_')[2])
    cat = cursor.execute("SELECT name FROM categories WHERE id=?", (cat_id,)).fetchone()
    if not cat:
        return await call.answer("❌ القسم غير موجود.", show_alert=True)
    await state.update_data(bulk_cat_id=cat_id)
    data = await state.get_data()
    total = len(data['bulk_phones'])
    await call.message.edit_text(
        f"📁 القسم: <b>{cat[0]}</b>\n"
        f"📋 إجمالي الأرقام: <b>{total}</b>\n\n"
        f"🚀 جاري بدء المعالجة التلقائية..."
    )
    await _bulk_start_next(call.message, state, call.from_user.id)


async def _bulk_start_next(message, state, admin_id):
    data = await state.get_data()
    phones = data['bulk_phones']
    idx = data['bulk_index']
    total = len(phones)

    if idx >= total:
        done = data.get('bulk_done', 0)
        failed = data.get('bulk_failed', 0)
        await state.finish()
        cat_name = cursor.execute("SELECT name FROM categories WHERE id=?", (data['bulk_cat_id'],)).fetchone()
        cat_name = cat_name[0] if cat_name else "القسم"
        return await message.answer(
            f"🎉 <b>انتهت المعالجة!</b>\n\n"
            f"📁 القسم: <b>{cat_name}</b>\n"
            f"✅ تم إضافتهم: <b>{done}</b>\n"
            f"❌ فشل: <b>{failed}</b>\n"
            f"📋 المجموع: <b>{total}</b>",
            reply_markup=admin_markup_for(None)
        )

    phone = phones[idx]
    cat_id = data['bulk_cat_id']
    session_path = os.path.join(SESSIONS_DIR, phone.replace('+', ''))

    await message.answer(
        f"📲 <b>[{idx+1}/{total}]</b> جاري تسجيل الدخول لـ:\n<code>{phone}</code>"
    )

    client = TelegramClient(session_path, TELETHON_API_ID, TELETHON_API_HASH)
    try:
        await client.connect()
        sent = await client.send_code_request(phone)
        active_clients[admin_id] = client
        await state.update_data(
            bulk_current_phone=phone,
            bulk_phone_code_hash=sent.phone_code_hash,
            bulk_password_2fa='لا يوجد'
        )
        await message.answer(
            f"📩 <b>[{idx+1}/{total}]</b> تم إرسال الكود إلى <code>{phone}</code>\n"
            f"أرسل الكود الآن:",
            reply_markup=cancel_markup()
        )
        await AdminStates.bulk_code.set()
    except Exception as e:
        if client.is_connected():
            await client.disconnect()
        failed = data.get('bulk_failed', 0) + 1
        await state.update_data(bulk_index=idx + 1, bulk_failed=failed)
        await message.answer(f"⚠️ <b>[{idx+1}/{total}]</b> فشل إرسال الكود لـ <code>{phone}</code>\nالخطأ: {e}\n\nالانتقال للرقم التالي...")
        await _bulk_start_next(message, state, admin_id)


@dp.message_handler(state=AdminStates.bulk_code)
async def bulk_got_code(message: types.Message, state: FSMContext):
    code = message.text.strip().replace(' ', '')
    data = await state.get_data()
    client = active_clients.get(message.from_user.id)
    if not client:
        await state.finish()
        return await message.answer("❌ انتهت الجلسة.")
    phone = data['bulk_current_phone']
    idx = data['bulk_index']
    total = len(data['bulk_phones'])
    try:
        await client.sign_in(phone, code, phone_code_hash=data['bulk_phone_code_hash'])
        await _bulk_do_check_and_save(message, state, client)
    except errors.SessionPasswordNeededError:
        await message.answer(
            f"🔐 <b>[{idx+1}/{total}]</b> الحساب <code>{phone}</code> يحتاج 2FA.\n"
            f"أرسل كلمة المرور:",
            reply_markup=cancel_markup()
        )
        await AdminStates.bulk_2fa.set()
    except Exception as e:
        active_clients.pop(message.from_user.id, None)
        if client.is_connected(): await client.disconnect()
        failed = data.get('bulk_failed', 0) + 1
        await state.update_data(bulk_index=idx + 1, bulk_failed=failed)
        await message.answer(f"❌ <b>[{idx+1}/{total}]</b> خطأ في الكود لـ <code>{phone}</code>: {e}\n\nالانتقال للتالي...")
        await _bulk_start_next(message, state, message.from_user.id)


@dp.message_handler(state=AdminStates.bulk_2fa)
async def bulk_got_2fa(message: types.Message, state: FSMContext):
    password = message.text.strip()
    client = active_clients.get(message.from_user.id)
    data = await state.get_data()
    if not client:
        await state.finish()
        return await message.answer("❌ انتهت الجلسة.")
    phone = data['bulk_current_phone']
    idx = data['bulk_index']
    total = len(data['bulk_phones'])
    try:
        await client.sign_in(password=password)
        await state.update_data(bulk_password_2fa=password)
        await _bulk_do_check_and_save(message, state, client)
    except Exception as e:
        active_clients.pop(message.from_user.id, None)
        if client.is_connected(): await client.disconnect()
        failed = data.get('bulk_failed', 0) + 1
        await state.update_data(bulk_index=idx + 1, bulk_failed=failed)
        await message.answer(f"❌ <b>[{idx+1}/{total}]</b> خطأ في 2FA لـ <code>{phone}</code>: {e}\n\nالانتقال للتالي...")
        await _bulk_start_next(message, state, message.from_user.id)


async def _bulk_do_check_and_save(message, state, client):
    data = await state.get_data()
    phone = data['bulk_current_phone']
    cat_id = data['bulk_cat_id']
    idx = data['bulk_index']
    total = len(data['bulk_phones'])
    password_2fa = data.get('bulk_password_2fa', 'لا يوجد')

    try:
        check = await run_full_check(client, phone, password_2fa)
        await client.disconnect()
        active_clients.pop(message.from_user.id, None)

        session_name = phone.replace('+', '') + '.session'
        cursor.execute(
            "INSERT INTO accounts (phone, session_name, country_id, password_2fa, status) VALUES (?,?,?,?,?)",
            (phone, session_name, cat_id, password_2fa, 'available')
        )
        conn.commit()

        done = data.get('bulk_done', 0) + 1
        await state.update_data(bulk_index=idx + 1, bulk_done=done, bulk_password_2fa='لا يوجد')

        cat_name = cursor.execute("SELECT name FROM categories WHERE id=?", (cat_id,)).fetchone()[0]
        await message.answer(
            f"✅ <b>[{idx+1}/{total}]</b> تم حفظ <code>{phone}</code> في <b>{cat_name}</b>\n\n"
            + check['result_text']
        )
    except Exception as e:
        if client.is_connected(): await client.disconnect()
        active_clients.pop(message.from_user.id, None)
        failed = data.get('bulk_failed', 0) + 1
        await state.update_data(bulk_index=idx + 1, bulk_failed=failed, bulk_password_2fa='لا يوجد')
        await message.answer(f"⚠️ <b>[{idx+1}/{total}]</b> فشل حفظ <code>{phone}</code>: {e}")

    await _bulk_start_next(message, state, message.from_user.id)

@dp.callback_query_handler(text="admin_add_cat")
async def admin_add_cat(call: types.CallbackQuery):
    if not is_user_verified(call.from_user.id): return await call.answer("يرجى إكمال التحقق البشري أولاً.", show_alert=True)
    if call.from_user.username != ADMIN_USERNAME: return await call.answer("⛔", show_alert=True)
    await call.message.edit_text("📝 أرسل اسم الدولة:", reply_markup=cancel_markup())
    await AdminStates.waiting_for_cat_name.set()

@dp.message_handler(state=AdminStates.waiting_for_cat_name)
async def process_cat_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text); await message.answer("🔢 أرسل رمز الدولة:"); await AdminStates.waiting_for_cat_prefix.set()

@dp.message_handler(state=AdminStates.waiting_for_cat_prefix)
async def process_cat_prefix(message: types.Message, state: FSMContext):
    await state.update_data(prefix=message.text); await message.answer("💵 أرسل السعر:"); await AdminStates.waiting_for_cat_price.set()

@dp.message_handler(state=AdminStates.waiting_for_cat_price)
async def process_cat_price(message: types.Message, state: FSMContext):
    try: price = float(message.text)
    except ValueError: return await message.answer("❌ أرسل رقم صحيح.")
    data = await state.get_data()
    cursor.execute("INSERT INTO categories (name,prefix,price) VALUES (?,?,?)", (data['name'], data['prefix'], price))
    conn.commit(); new_cat_id = cursor.lastrowid
    m = colored_inline_keyboard(
        [colored_button("📲 إضافة رقم للقسم", f"addcat_phone_{new_cat_id}", "danger")],
        [colored_button("📂 إضافة .session للقسم", f"addcat_session_{new_cat_id}", "success")],
        [colored_button("⚙️ لوحة التحكم", "admin_panel", "danger")]
    )
    await message.answer(f"✅ تم إضافة القسم!\n🌍 {data['name']} | 💵 ${price:.2f}", reply_markup=m); await state.finish()

@dp.callback_query_handler(text="admin_add_session")
async def admin_add_session(call: types.CallbackQuery):
    if not is_user_verified(call.from_user.id): return await call.answer("يرجى إكمال التحقق البشري أولاً.", show_alert=True)
    if not is_admin(call.from_user.username): return await call.answer("⛔", show_alert=True)
    await call.message.edit_text("📂 أرسل ملف .session:", reply_markup=cancel_markup())
    await AdminStates.waiting_for_session_file.set()

@dp.message_handler(content_types=['document'], state=AdminStates.waiting_for_session_file)
async def process_session_file(message: types.Message, state: FSMContext):
    if not message.document.file_name.endswith('.session'): return await message.answer("❌ أرسل ملف .session فقط.")
    file_path = os.path.join(SESSIONS_DIR, message.document.file_name); await message.document.download(destination_file=file_path)
    await state.update_data(session_name=message.document.file_name); await message.answer("📞 أرسل رقم الهاتف:"); await AdminStates.waiting_for_session_phone.set()

@dp.message_handler(state=AdminStates.waiting_for_session_phone)
async def process_session_phone(message: types.Message, state: FSMContext):
    await state.update_data(phone=message.text.strip()); await message.answer("🔐 أرسل 2FA أو اكتب: لا يوجد"); await AdminStates.waiting_for_session_2fa.set()

@dp.message_handler(state=AdminStates.waiting_for_session_2fa)
async def process_session_2fa(message: types.Message, state: FSMContext):
    await state.update_data(password_2fa=message.text.strip())
    cursor.execute("SELECT id, name FROM categories"); cats = cursor.fetchall()
    if not cats: await state.finish(); return await message.answer("❌ لا توجد أقسام.", reply_markup=admin_markup_for(message.from_user.username))
    rows = [[colored_button(c[1], f"set_cat_{c[0]}", "danger")] for c in cats]
    await message.answer("🌍 اختر الدولة:", reply_markup=colored_inline_keyboard(*rows))
    await state.set_state("waiting_for_category_selection")

@dp.callback_query_handler(lambda c: c.data.startswith('set_cat_'), state="waiting_for_category_selection")
async def save_account_final(call: types.CallbackQuery, state: FSMContext):
    cat_id = int(call.data.split('_')[2]); data = await state.get_data()
    cursor.execute("INSERT INTO accounts (phone,session_name,country_id,password_2fa,status) VALUES (?,?,?,?,?)",
                   (data['phone'], data['session_name'], cat_id, data['password_2fa'], 'available')); conn.commit()
    await call.message.edit_text("✅ تم حفظ الجلسة!", reply_markup=admin_markup_for(call.from_user.username)); await state.finish()

# شراء الحسابات
@dp.callback_query_handler(text="buy_account")
async def user_buy_account(call: types.CallbackQuery):
    uid = call.from_user.id
    if not await is_subscribed(uid): return await call.answer(t(uid,'sub_first'), show_alert=True)
    if not is_user_verified(uid): return await call.answer(t(uid,'human_check'), show_alert=True)
    cursor.execute("SELECT id, name, prefix, price FROM categories"); cats = cursor.fetchall()
    if not cats: return await call.answer(t(uid,'no_cats'), show_alert=True)
    rows = []
    pair = []
    for cat in cats:
        count = get_accounts_count(cat[0])
        emoji = "🟢" if count > 0 else "🔴"
        pair.append(colored_button(
            f"{emoji} {cat[1]} ({cat[2]}) | ${cat[3]:.2f} | {count}",
            f"buy_cat_{cat[0]}", "primary"
        ))
        if len(pair) == 2:
            rows.append(pair)
            pair = []
    if pair:
        rows.append(pair)
    rows.append([colored_button(t(uid,'go_back'), "main_menu", "success")])
    await call.message.edit_text(t(uid,'buy_title'), reply_markup=colored_inline_keyboard(*rows))

@dp.callback_query_handler(lambda c: c.data.startswith('buy_cat_'))
async def process_purchase(call: types.CallbackQuery):
    uid = call.from_user.id
    if not await is_subscribed(uid): return await call.answer(t(uid,'sub_first'), show_alert=True)
    if not is_user_verified(uid): return await call.answer(t(uid,'human_check'), show_alert=True)
    cat_id = int(call.data.split('_')[2])
    cat_info = cursor.execute("SELECT name, price FROM categories WHERE id=?", (cat_id,)).fetchone()
    if not cat_info: return await call.answer("❌ القسم غير موجود.", show_alert=True)
    account = cursor.execute("SELECT id, phone, session_name, password_2fa FROM accounts WHERE country_id=? AND status='available' LIMIT 1", (cat_id,)).fetchone()
    if not account: return await call.answer("❌ نفذت الأرقام.", show_alert=True)
    bal = get_user_balance(uid)
    if bal < cat_info[1]: return await call.answer(f"❌ رصيدك غير كاف. السعر: ${cat_info[1]:.2f}", show_alert=True)
    new_bal = bal - cat_info[1]
    cursor.execute("UPDATE users SET balance=? WHERE id=?", (new_bal, uid))
    cursor.execute("UPDATE accounts SET status='pending', buyer_id=? WHERE id=?", (uid, account[0]))
    conn.commit()
    m = colored_inline_keyboard(
        [colored_button(t(uid,'get_otp'), f"get_otp_{account[0]}", "danger")],
        [colored_button(t(uid,'get_2fa'), f"get_2fa_{account[0]}", "success")],
        [colored_button(t(uid,'confirm_login'), f"confirm_login_{account[0]}", "danger")]
    )
    await call.message.edit_text(t(uid,'bought',phone=account[1],bal=new_bal), reply_markup=m)

@dp.callback_query_handler(lambda c: c.data.startswith('get_otp_'))
async def get_otp_callback(call: types.CallbackQuery):
    if not is_user_verified(call.from_user.id): return await call.answer("يرجى إكمال التحقق البشري أولاً.", show_alert=True)
    acc_id = int(call.data.split('_')[2])
    acc = cursor.execute("SELECT session_name, buyer_id FROM accounts WHERE id=?", (acc_id,)).fetchone()
    if not acc or acc[1] != call.from_user.id: return await call.answer("❌ غير مسموح.", show_alert=True)
    session_path = os.path.join(SESSIONS_DIR, acc[0])
    try:
        client = TelegramClient(session_path, TELETHON_API_ID, TELETHON_API_HASH); await client.connect()
        if not await client.is_user_authorized(): await client.disconnect(); return await call.message.answer("❌ الجلسة منتهية.")
        otp = None
        async for msg in client.iter_messages(777000, limit=5):
            if msg.text:
                match = re.search(r'\b(\d{5,6})\b', msg.text)
                if match: otp = match.group(1); break
        await client.disconnect()
        if otp:
            cursor.execute("UPDATE accounts SET otp=? WHERE id=?", (otp, acc_id)); conn.commit()
            await call.message.answer(f"📩 <b>كود التحقق:</b> <code>{otp}</code>")
        else: await call.message.answer("⏳ الكود لم يصل بعد.")
    except Exception as e: await call.message.answer(f"❌ خطأ: {e}")

@dp.callback_query_handler(lambda c: c.data.startswith('get_2fa_'))
async def get_2fa_callback(call: types.CallbackQuery):
    if not is_user_verified(call.from_user.id): return await call.answer("يرجى إكمال التحقق البشري أولاً.", show_alert=True)
    acc_id = int(call.data.split('_')[2])
    acc = cursor.execute("SELECT password_2fa, buyer_id FROM accounts WHERE id=?", (acc_id,)).fetchone()
    if not acc or acc[1] != call.from_user.id: return await call.answer("❌ غير مسموح.", show_alert=True)
    await call.message.answer(f"🔐 <b>كلمة السر (2FA):</b> <code>{acc[0]}</code>")

@dp.callback_query_handler(lambda c: c.data.startswith('confirm_login_'))
async def confirm_login_callback(call: types.CallbackQuery):
    if not is_user_verified(call.from_user.id): return await call.answer("يرجى إكمال التحقق البشري أولاً.", show_alert=True)
    acc_id = int(call.data.split('_')[2])
    acc = cursor.execute("SELECT session_name, buyer_id, phone, country_id, otp FROM accounts WHERE id=?", (acc_id,)).fetchone()
    if not acc or acc[1] != call.from_user.id: return await call.answer("❌ غير مسموح.", show_alert=True)
    session_path = os.path.join(SESSIONS_DIR, acc[0])
    try:
        client = TelegramClient(session_path, TELETHON_API_ID, TELETHON_API_HASH); await client.connect()
        if await client.is_user_authorized(): await client.log_out()
        await client.disconnect()
    except Exception as e: logging.error(f"confirm_login: {e}")
    finally:
        if os.path.exists(session_path):
            try: os.remove(session_path)
            except: pass
        cursor.execute("UPDATE accounts SET status='sold' WHERE id=?", (acc_id,)); conn.commit()
        cat_name, price = "", 0.0
        if acc[3]:
            cat_info = cursor.execute("SELECT name, price FROM categories WHERE id=?", (acc[3],)).fetchone()
            if cat_info: cat_name, price = cat_info
        phone_masked = mask_phone(acc[2]) if acc[2] else "غير معروف"
        buyer_masked = mask_user_id(call.from_user.id)
        otp_code = acc[4] if acc[4] else "----"
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        msg_text = (
            "✅ تم شراء حساب جديد من البوت\n\n"
            f"🌍 الدولة: {cat_name}\n"
            f"📱 المنصة: تليجرام\n"
            f"📞 الرقم: {phone_masked}\n"
            f"💰 السعر: $ {price:.2f}\n"
            f"👤 العميل: {buyer_masked}\n"
            f"🔑 كود التفعيل: {otp_code}\n"
            f"✅ الحالة: تم التفعيل\n\n"
            f"📅 التاريخ والوقت: {now}"
        )
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
        kb_channel = InlineKeyboardMarkup().add(
            InlineKeyboardButton("🤖 الدخول إلى البوت", url=f"https://t.me/{BOT_USERNAME}")
        )
        # إرسال عبر queue موثوق بدلاً من الإرسال المباشر
        await send_to_channel(msg_text, markup=kb_channel, parse_mode=None)
        await call.message.edit_text("✨ <b>تم تفعيل الحساب بنجاح. شكراً! 🎉</b>")

# شحن الرصيد (النجوم + آسيا)
@dp.callback_query_handler(text="add_balance")
async def add_balance_choose(call: types.CallbackQuery):
    uid = call.from_user.id
    if not await is_subscribed(uid): return await call.answer(t(uid,'sub_first'), show_alert=True)
    if not is_user_verified(uid): return await call.answer(t(uid,'human_check'), show_alert=True)
    m = colored_inline_keyboard(
        [colored_button(t(uid,'stars_btn'), "pay_stars", "danger")],
        [colored_button(t(uid,'asia_btn'), "pay_asia", "success")],
        [colored_button(t(uid,'back'), "main_menu", "danger")]
    )
    await call.message.edit_text(t(uid,'topup_choose'), reply_markup=m)

@dp.callback_query_handler(text="pay_stars")
async def ask_stars(call: types.CallbackQuery):
    uid = call.from_user.id
    if not await is_subscribed(uid): return await call.answer(t(uid,'sub_first'), show_alert=True)
    if not is_user_verified(uid): return await call.answer(t(uid,'human_check'), show_alert=True)
    m = colored_inline_keyboard([colored_button(t(uid,'back'), "add_balance", "danger")])
    await call.message.edit_text(
        "⭐ <b>شحن بالنجوم</b>\n\n"
        "أدخل عدد النجوم (1 — 10000):\n"
        "<i>كل نجمة = $0.01  (10 نجوم = $0.10)</i>",
        reply_markup=m
    )
    await PaymentStates.waiting_for_stars.set()

@dp.message_handler(state=PaymentStates.waiting_for_stars)
async def process_stars(message: types.Message, state: FSMContext):
    if not await is_subscribed(message.from_user.id): return await message.answer("⚠️ اشترك أولاً")
    if not is_user_verified(message.from_user.id): return await message.answer("يرجى إكمال التحقق البشري أولاً.")
    if not message.text.isdigit() or not (1 <= int(message.text) <= 10000):
        return await message.answer("❌ أدخل رقم بين 1 و 10000.")
    amount = int(message.text)
    added_dollars = amount * 0.01
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="شحن رصيد ZZ",
        description=f"شحن {amount} نجمة (= ${added_dollars:.2f})",
        payload="add_balance_payload",
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label="النجوم", amount=amount)]
    )
    await state.finish()

@dp.pre_checkout_query_handler(lambda q: True)
async def process_pre_checkout(pre_checkout_query: types.PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message_handler(content_types=types.ContentType.SUCCESSFUL_PAYMENT)
async def process_successful_payment(message: types.Message):
    stars = message.successful_payment.total_amount
    added = stars * 0.01
    new_bal = get_user_balance(message.from_user.id) + added
    cursor.execute("UPDATE users SET balance=?, recharge_count = recharge_count + 1 WHERE id=?", (new_bal, message.from_user.id))
    conn.commit()
    await message.answer(
        f"💳 <b>تم الشحن بنجاح!</b>\n"
        f"✨ النجوم: {stars} | 💵 المضاف: ${added:.2f}\n"
        f"💰 رصيدك الجديد: ${new_bal:.2f}"
    )

# شحن عبر آسيا (بدون كلمة "اسيا" في السؤال، مع دينار)
@dp.callback_query_handler(text="pay_asia")
async def pay_asia_start(call: types.CallbackQuery):
    uid = call.from_user.id
    if not await is_subscribed(uid): return await call.answer(t(uid,'sub_first'), show_alert=True)
    if not is_user_verified(uid): return await call.answer(t(uid,'human_check'), show_alert=True)
    
    text = (
        "شحن الرصيد عبر آسيا سيل:\n"
        "حوّل إلى الرقم: 07719383439\n"
        "الحد الأدنى: 1000 دينار.\n"
        "اضغط على الزر أدناه لتأكيد البيانات."
    )
    kb = colored_inline_keyboard([
        colored_button("✅ تأكيد البيانات", "confirm_asia_data", "success"),
        colored_button("🔙 رجوع", "add_balance", "danger")
    ])
    await call.message.edit_text(text, reply_markup=kb)


@dp.callback_query_handler(text="confirm_asia_data")
async def confirm_asia_data(call: types.CallbackQuery):
    # انتقل إلى إدخال المبلغ
    await call.message.edit_text(
        "أدخل المبلغ الذي تريد شحنه (بالدينار):\nمثال: <code>1000</code>",
        reply_markup=colored_inline_keyboard([colored_button("🔙 رجوع", "add_balance", "danger")])
    )
    await AsiaTopUpStates.waiting_for_amount.set()


# دالة استقبال المبلغ (تبقى كما هي، لكن مع السماح من 1 إلى 500000)
@dp.message_handler(state=AsiaTopUpStates.waiting_for_amount)
async def asia_amount_entered(message: types.Message, state: FSMContext):
    if not is_user_verified(message.from_user.id): return await message.answer("يرجى إكمال التحقق البشري أولاً.")
    try:
        amount = float(message.text)
        if amount <= 0 or amount > 500000:  # الحد الأقصى اختياري، يمكن إزالته
            raise ValueError
    except ValueError:
        return await message.answer("❌ أرسل مبلغاً صحيحاً (1 - 500000 دينار).")
    
    await state.update_data(amount=amount)
    await message.answer(
        f"💵 <b>المبلغ المطلوب:</b> {amount:.2f} دينار\n\n"
        f"📱 <b>يرجى تحويل المبلغ إلى الرقم التالي:</b>\n"
        f"<code>07719383439</code>\n\n"
        f"بعد التحويل، اضغط على <b>تم التحويل</b> وأرسل سكرين شوت.",
        reply_markup=colored_inline_keyboard([
            colored_button("✅ تم التحويل", "asia_done", "danger"),
            colored_button("❌ إلغاء", "main_menu", "success")
        ])
    )
    await AsiaTopUpStates.waiting_for_screenshot.set()

@dp.callback_query_handler(text="asia_done", state=AsiaTopUpStates.waiting_for_screenshot)
async def asia_request_screenshot(call: types.CallbackQuery, state: FSMContext):
    await call.message.edit_text("📸 <b>أرسل الآن سكرين شوت لعملية التحويل.</b>",
                                 reply_markup=colored_inline_keyboard([colored_button("❌ إلغاء", "main_menu", "danger")]))

@dp.message_handler(content_types=ContentType.PHOTO, state=AsiaTopUpStates.waiting_for_screenshot)
async def asia_screenshot_received(message: types.Message, state: FSMContext):
    global ADMIN_ID
    data = await state.get_data()
    amount = data['amount']
    user_id = message.from_user.id
    username = message.from_user.username or "بدون معرف"
    photo = message.photo[-1].file_id
    text = (
        f"🔄 <b>طلب شحن رصيد جديد (آسيا)</b>\n\n"
        f"👤 المستخدم: <a href='tg://user?id={user_id}'>{username}</a>\n"
        f"🆔 الآيدي: <code>{user_id}</code>\n"
        f"💰 المبلغ المطلوب: <b>{amount:.2f} دينار</b>\n\n"
        f"📎 الصورة أدناه:"
    )
    kb = colored_inline_keyboard([
        colored_button("✅ موافقة", f"asia_approve_{user_id}", "danger"),
        colored_button("❌ رفض", f"asia_reject_{user_id}", "success")
    ])
    try:
        if ADMIN_ID:
            await bot.send_photo(ADMIN_ID, photo, caption=text, reply_markup=kb)
        else:
            await bot.send_photo(ADMIN_USERNAME, photo, caption=text, reply_markup=kb)
    except Exception as e:
        if "Chat not found" in str(e):
            await message.answer("⚠️ المطور لم يبدأ البوت بعد. يرجى إبلاغه.")
        else:
            await message.answer(f"❌ خطأ: {e}")
        await state.finish()
        return
    await message.answer("✅ <b>تم إرسال طلبك إلى المطور. سنعلمك بالقرار قريباً.</b>",
                         reply_markup=get_main_markup(message.from_user.username, message.from_user.id))
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith('asia_approve_'))
async def asia_approve(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.username != ADMIN_USERNAME: return await call.answer("⛔ للمطور فقط.", show_alert=True)
    uid = int(call.data.split('_')[2])
    await state.update_data(approve_uid=uid)
    await call.message.edit_caption(call.message.caption + "\n\n✏️ <b>أدخل الآن المبلغ الذي ستضيفه لهذا المستخدم:</b>", reply_markup=None)
    await AdminStates.asia_approve_amount.set()

@dp.message_handler(state=AdminStates.asia_approve_amount)
async def asia_approve_amount_entered(message: types.Message, state: FSMContext):
    try:
        amount = float(message.text)
        if amount <= 0: raise ValueError
    except ValueError: return await message.answer("❌ أرسل مبلغاً صحيحاً موجباً.")
    data = await state.get_data(); uid = data['approve_uid']
    add_user_if_not_exists(uid, None)
    new_bal = get_user_balance(uid) + amount
    cursor.execute("UPDATE users SET balance=?, recharge_count = recharge_count + 1 WHERE id=?", (new_bal, uid)); conn.commit()
    await message.answer(f"✅ تمت إضافة <b>${amount:.2f}</b> إلى رصيد المستخدم <code>{uid}</code>.")
    try:
        await bot.send_message(uid, f"🎉 <b>تمت الموافقة على طلب الشحن الخاص بك!</b>\nتم إضافة <b>${amount:.2f}</b> إلى رصيدك.\nرصيدك الحالي: <b>${new_bal:.2f}$</b>")
    except Exception as e: logging.error(f"Failed to notify user {uid}: {e}")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data.startswith('asia_reject_'))
async def asia_reject(call: types.CallbackQuery, state: FSMContext):
    if call.from_user.username != ADMIN_USERNAME: return await call.answer("⛔ للمطور فقط.", show_alert=True)
    uid = int(call.data.split('_')[2])
    await state.update_data(reject_uid=uid)
    await call.message.edit_caption(call.message.caption + "\n\n✏️ <b>اكتب سبب الرفض:</b>", reply_markup=None)
    await AdminStates.asia_reject_reason.set()

@dp.message_handler(state=AdminStates.asia_reject_reason)
async def asia_reject_reason_entered(message: types.Message, state: FSMContext):
    reason = message.text.strip()
    data = await state.get_data(); uid = data['reject_uid']
    try:
        await bot.send_message(uid, f"❌ <b>تم رفض طلب الشحن الخاص بك.</b>\nالسبب: {reason}")
    except Exception as e: logging.error(f"Failed to notify user {uid}: {e}")
    await message.answer(f"✅ تم إرسال سبب الرفض للمستخدم <code>{uid}</code>.")
    await state.finish()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    # شغّل worker القناة في الخلفية قبل بدء البوت
    loop.create_task(_channel_worker())
    executor.start_polling(dp, skip_updates=True)
