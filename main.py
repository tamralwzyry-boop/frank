import asyncio, json, os, random, re, logging
from pathlib import Path
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# ================== الإعدادات ==================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = "8661589595:AAEh22n0-Od7pMJxsLT7GORHOyAWX4PFWsU"          # استبدله بتوكن بوت تيليجرام
TARGET_URL = "https://www.fasah.sa"    # رابط الموقع الرسمي

# يفضل ترك headless=False لتجربة المتصفح، وللموبايل اجعلها True
HEADLESS_MODE = False

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]
VIEWPORT = {"width": 1366, "height": 768}

# ================== تخزين الحسابات (إيميلات فقط) ==================
ACCOUNTS_FILE = Path("accounts.json")
if not ACCOUNTS_FILE.exists():
    ACCOUNTS_FILE.write_text("{}", encoding="utf-8")

def load_accounts():
    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_accounts(data):
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ================== إدارة جلسات Playwright ==================
user_browsers = {}   # {user_id: (browser, context)}
user_pages = {}      # {user_id: page}

async def get_browser_context(user_id: str):
    if user_id not in user_browsers:
        p = await async_playwright().start()
        browser = await p.chromium.launch(
            headless=HEADLESS_MODE,
            args=["--disable-blink-features=AutomationControlled"]
        )
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport=VIEWPORT,
            locale="ar-SA"
        )
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        user_browsers[user_id] = (browser, context)
    else:
        browser, context = user_browsers[user_id]
    return browser, context

async def get_page(user_id: str):
    if user_id not in user_pages:
        _, context = await get_browser_context(user_id)
        page = await context.new_page()
        user_pages[user_id] = page
    else:
        page = user_pages[user_id]
    return page

async def close_user_browser(user_id: str):
    if user_id in user_browsers:
        browser, context = user_browsers.pop(user_id)
        await context.close()
        await browser.close()
    if user_id in user_pages:
        user_pages.pop(user_id)

# ================== محاكاة حركات بشرية ==================
async def human_delay(min_ms=80, max_ms=300):
    await asyncio.sleep(random.uniform(min_ms/1000, max_ms/1000))

async def human_click(page, selector):
    try:
        element = await page.wait_for_selector(selector, state="visible", timeout=8000)
        await element.scroll_into_view_if_needed()
        box = await element.bounding_box()
        if box:
            # حركة ماوس عشوائية
            start_x = box['x'] + box['width'] * random.uniform(0.2, 0.8)
            start_y = box['y'] + box['height'] * random.uniform(0.2, 0.8)
            await page.mouse.move(start_x, start_y)
            await human_delay(30, 80)
            target_x = box['x'] + box['width'] * 0.5
            target_y = box['y'] + box['height'] * 0.5
            await page.mouse.move(target_x, target_y)
            await human_delay(10, 30)
            await page.mouse.click(target_x, target_y)
        else:
            await element.click()
    except PlaywrightTimeout:
        raise Exception(f"العنصر '{selector}' لم يظهر")

# ================== حالات FSM ==================
class BookingStates(StatesGroup):
    choosing_account = State()
    new_email = State()
    new_password = State()
    purpose = State()
    extra_options = State()
    waiting_for_date = State()
    waiting_for_time = State()
    confirm_start = State()
    monitoring = State()

# ================== البوت الأساسي ==================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ---------- /start ----------
@dp.message(F.text == "/start")
async def cmd_start(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    accounts = load_accounts().get(user_id, [])

    if accounts:
        buttons = [
            [InlineKeyboardButton(text=acc["email"], callback_data=f"login_{acc['email']}")]
            for acc in accounts
        ]
        buttons.append([InlineKeyboardButton(text="➕ تسجيل دخول جديد", callback_data="new_login")])
        await message.answer("اختر حسابًا مسجلًا أو أضف جديدًا:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        await state.set_state(BookingStates.choosing_account)
    else:
        await message.answer("لا توجد حسابات محفوظة. أرسل البريد الإلكتروني:")
        await state.set_state(BookingStates.new_email)

# ---------- اختيار حساب قديم ----------
@dp.callback_query(F.data == "new_login")
async def new_login(cb: types.CallbackQuery, state: FSMContext):
    await cb.message.answer("أرسل البريد الإلكتروني:")
    await state.set_state(BookingStates.new_email)
    await cb.answer()

@dp.callback_query(F.data.startswith("login_"))
async def existing_login(cb: types.CallbackQuery, state: FSMContext):
    email = cb.data[len("login_"):]
    user_id = str(cb.from_user.id)
    await cb.answer()
    try:
        page = await get_page(user_id)
        await page.goto(TARGET_URL, wait_until="domcontentloaded")
        # التحقق إذا كنا مسجلين (قد يظهر رابط "حسابي" أو "تسجيل خروج")
        if await page.query_selector("text=تسجيل الخروج") or await page.query_selector("text=حسابي"):
            await cb.message.answer(f"تم استعادة جلسة {email}.")
            await state.update_data(email=email, logged_in=True)
            await ask_purpose(cb.message, state)
        else:
            await cb.message.answer("انتهت الجلسة، أرسل كلمة المرور:")
            await state.update_data(email=email)
            await state.set_state(BookingStates.new_password)
    except Exception as e:
        await cb.message.answer(f"خطأ في استعادة الحساب: {e}")

# ---------- إدخال بيانات حساب جديد ----------
@dp.message(BookingStates.new_email)
async def process_new_email(message: types.Message, state: FSMContext):
    await state.update_data(email=message.text.strip())
    await message.answer("أرسل كلمة المرور:")
    await state.set_state(BookingStates.new_password)

@dp.message(BookingStates.new_password)
async def process_new_password(message: types.Message, state: FSMContext):
    password = message.text.strip()
    data = await state.get_data()
    email = data["email"]
    user_id = str(message.from_user.id)

    page = await get_page(user_id)
    await page.goto(TARGET_URL, wait_until="domcontentloaded")
    try:
        # ابحث عن حقول الإدخال (قد تكون من نوع email/ password)
        await page.fill("input[type='email'], input[name='email'], input#email", email)
        await page.fill("input[type='password'], input[name='password'], input#password", password)
        await human_click(page, "button:has-text('دخول'), button:has-text('تسجيل الدخول')")
        await page.wait_for_load_state("networkidle")
        await human_delay(1000, 2000)

        if await page.query_selector("text=تسجيل الخروج") or await page.query_selector("text=حسابي"):
            # حفظ الحساب
            accounts = load_accounts()
            if user_id not in accounts:
                accounts[user_id] = []
            if not any(a["email"] == email for a in accounts[user_id]):
                accounts[user_id].append({"email": email})
                save_accounts(accounts)
            await state.update_data(logged_in=True, email=email)
            await message.answer("تم تسجيل الدخول بنجاح!")
            await ask_purpose(message, state)
        else:
            await message.answer("فشل الدخول، تحقق من البيانات.")
            await state.clear()
    except Exception as e:
        await message.answer(f"خطأ أثناء الدخول: {e}")
        await state.clear()

# ---------- سؤال الغرض ----------
async def ask_purpose(message, state):
    kb = [[KeyboardButton(text="شاحنة فارغة"), KeyboardButton(text="عبور")]]
    await message.answer("اختر الغرض من الرحلة:", reply_markup=ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True, one_time_keyboard=True))
    await state.set_state(BookingStates.purpose)

@dp.message(BookingStates.purpose, F.text.in_(["شاحنة فارغة", "عبور"]))
async def purpose_chosen(message: types.Message, state: FSMContext):
    purpose = message.text
    await state.update_data(purpose=purpose)
    await message.answer("جاري تحضير الخيارات الإضافية...")
    user_id = str(message.from_user.id)
    page = await get_page(user_id)
    try:
        # سنكرر التنقل حتى الوصول لصفحة الخيارات بعد الغرض
        await go_until_extra_options(page, purpose)
        # استخراج القوائم أو الخيارات (قد تكون select أو راديو)
        options_raw = await page.evaluate('''() => {
            const selects = document.querySelectorAll('select');
            if (selects.length > 0) {
                return Array.from(selects).map(s => ({
                    id: s.id,
                    name: s.name || s.id,
                    options: Array.from(s.options).map(o => ({text: o.text, value: o.value}))
                }));
            }
            // إن لم تكن select، نبحث عن مجموعة أزرار راديو
            const radioGroups = document.querySelectorAll('.form-group, .radio-group');
            return Array.from(radioGroups).map(g => ({
                name: g.querySelector('label')?.innerText || 'خيار',
                options: Array.from(g.querySelectorAll('input[type="radio"]')).map(r => ({
                    text: r.labels?.[0]?.innerText || r.value,
                    value: r.value
                }))
            }));
        }''')

        if options_raw and len(options_raw) > 0:
            await state.update_data(extra_options_raw=options_raw)
            # عرض الخيار الأول (لتبسيط التفاعل؛ يمكن تطويره لاحقًا)
            first = options_raw[0]
            opts_text = "\n".join([f"{i+1}. {o['text']}" for i, o in enumerate(first['options'])])
            await message.answer(f"اختر قيمة لـ \"{first['name']}\":\n{opts_text}\n(أرسل الرقم أو النص)")
            await state.set_state(BookingStates.extra_options)
        else:
            await message.answer("لا توجد خيارات إضافية. أدخل التاريخ (YYYY-MM-DD):")
            await state.set_state(BookingStates.waiting_for_date)
    except Exception as e:
        await message.answer(f"خطأ أثناء جلب الخيارات: {e}")
        await state.clear()

async def go_until_extra_options(page, purpose):
    """ينتقل من الصفحة الرئيسية إلى ما بعد اختيار الغرض (قبل المواعيد)"""
    await page.goto(TARGET_URL, wait_until="domcontentloaded")
    await human_delay(500, 800)
    # الدخول إلى مواعيد الشاحنات (قد يكون رابط أو زر)
    await human_click(page, "a:has-text('مواعيد الشاحنات'), button:has-text('مواعيد الشاحنات')")
    await human_delay(600, 900)
    # حجز جديد
    await human_click(page, "a:has-text('حجز جديد'), button:has-text('حجز جديد')")
    await human_delay(600, 900)
    # اختيار الغرض (فارغة أو عبور) - قد يكونان أزرارًا أو روابط
    if purpose == "شاحنة فارغة":
        await human_click(page, "text=شاحنة فارغة")
    else:
        await human_click(page, "text=عبور")
    await human_delay(700, 1000)
    # بعد ذلك يجب أن تظهر الخيارات الإضافية أو زر المواعيد

# ---------- استقبال الخيار الإضافي ----------
@dp.message(BookingStates.extra_options)
async def extra_option_input(message: types.Message, state: FSMContext):
    data = await state.get_data()
    raw = data.get("extra_options_raw", [])
    if not raw:
        await message.answer("لا خيارات متاحة، انتقل للتاريخ:")
        await state.set_state(BookingStates.waiting_for_date)
        return

    user_choice = message.text.strip()
    # نحاول مطابقة النص أو الرقم (تبسيط)
    first_options = raw[0]['options']
    selected = None
    if user_choice.isdigit():
        idx = int(user_choice) - 1
        if 0 <= idx < len(first_options):
            selected = first_options[idx]
    else:
        for opt in first_options:
            if opt['text'].strip() == user_choice:
                selected = opt
                break
    if not selected:
        await message.answer("اختيار غير صحيح، حاول مجددًا:")
        return

    # حفظ الاختيار (القيمة أو النص)
    await state.update_data(extra_selections=[selected['value'] if selected.get('value') else selected['text']])
    await message.answer("تم استلام الاختيار. أدخل التاريخ (YYYY-MM-DD):")
    await state.set_state(BookingStates.waiting_for_date)

# ---------- التاريخ والوقت ----------
@dp.message(BookingStates.waiting_for_date)
async def date_entered(message: types.Message, state: FSMContext):
    if not re.match(r"\d{4}-\d{2}-\d{2}", message.text):
        await message.answer("صيغة خاطئة، استخدم YYYY-MM-DD:")
        return
    await state.update_data(date=message.text.strip())
    await message.answer("أدخل الوقت المفضل (HH:MM):")
    await state.set_state(BookingStates.waiting_for_time)

@dp.message(BookingStates.waiting_for_time)
async def time_entered(message: types.Message, state: FSMContext):
    if not re.match(r"\d{2}:\d{2}", message.text):
        await message.answer("صيغة خاطئة، استخدم HH:MM:")
        return
    await state.update_data(time=message.text.strip())
    data = await state.get_data()
    summary = (
        f"📋 ملخص الحجز:\n"
        f"البريد: {data.get('email')}\n"
        f"الغرض: {data.get('purpose')}\n"
        f"التاريخ: {data['date']}\n"
        f"الوقت: {data['time']}\n\n"
        f"هل تبدأ مراقبة المواعيد الآن؟"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 ابدأ المراقبة", callback_data="start_monitor")]
    ])
    await message.answer(summary, reply_markup=kb)
    await state.set_state(BookingStates.confirm_start)

# ---------- بدء المراقبة والحجز ----------
@dp.callback_query(F.data == "start_monitor")
async def start_monitor(cb: types.CallbackQuery, state: FSMContext):
    user_id = str(cb.from_user.id)
    data = await state.get_data()
    await cb.message.answer("عيناي على المواعيد الآن... سأخبرك فور ظهورها.")
    await state.set_state(BookingStates.monitoring)

    page = await get_page(user_id)
    try:
        # الانتقال إلى صفحة المواعيد النهائية
        await go_to_appointments_page(page, data)
        # بدء مهمة المراقبة في الخلفية
        asyncio.create_task(monitor_and_book(page, data, cb.message.chat.id, cb.from_user.id))
    except Exception as e:
        await bot.send_message(cb.message.chat.id, f"خطأ في التحضير: {e}")
        await state.clear()
    await cb.answer()

async def go_to_appointments_page(page, data):
    """ينتقل إلى صفحة المواعيد مباشرة (قد تحتاج لضغط زر 'المواعيد')"""
    # نعيد استخدام go_until_extra_options ثم نضغط على زر المواعيد
    await go_until_extra_options(page, data['purpose'])
    # تطبيق الاختيار الإضافي إن وجد
    extra = data.get("extra_selections", [])
    if extra:
        # نضغط على العنصر المناسب (قد يكون select option أو راديو)
        # نحاول اختيار القيمة
        try:
            await page.select_option("select", extra[0])  # إذا كان select
        except:
            # وإلا نحاول الضغط على label يحتوي النص
            await human_click(page, f"text={extra[0]}")
        await human_delay(500, 800)
    # اضغط زر "المواعيد"
    await human_click(page, "button:has-text('المواعيد'), a:has-text('المواعيد')")
    await human_delay(1000, 1500)

# ---------- المراقبة الذكية (بدون تحديث متكرر للصفحة) ----------
async def monitor_and_book(page, data, chat_id, user_id):
    target_date = data["date"]
    target_time = data["time"]
    max_minutes = 60
    start = datetime.now()
    logger.info(f"بدء المراقبة للمستخدم {user_id} - التاريخ {target_date} الوقت {target_time}")

    # كود JavaScript لفحص ظهور المواعيد (قد تختلف المحددات)
    check_js = """() => {
        // أزرار المواعيد المتاحة (مثل btn-success أو غير معطلة)
        const availableButtons = document.querySelectorAll('button.btn-success, .time-slot:not([disabled]), td.available');
        if (availableButtons.length > 0) return true;

        // اختفاء رسالة "لا توجد مواعيد متاحة"
        const noSlots = document.querySelector('.alert.alert-warning, .no-slots, :contains("لا توجد")');
        if (noSlots && noSlots.offsetParent !== null) return false;

        // إذا كان هناك جدول مواعيد بدون رسالة "لا يوجد"، اعتبر أن المواعيد متاحة
        const table = document.querySelector('table.table-bordered');
        if (table && !noSlots) return true;

        return false;
    }"""

    while (datetime.now() - start) < timedelta(minutes=max_minutes):
        try:
            slots_available = await page.evaluate(check_js)
        except Exception as e:
            logger.warning(f"خطأ في فحص DOM: {e}")
            slots_available = False

        if slots_available:
            logger.info("تم اكتشاف مواعيد متاحة!")
            try:
                # اختيار التاريخ (إذا كان هناك حقل تاريخ)
                date_input = await page.query_selector("input[type='date'], input.datepicker")
                if date_input:
                    await date_input.fill(target_date)
                    await human_delay(100, 200)

                # اختيار الوقت: نضغط على زر يحمل الوقت المطلوب
                time_selector = f"button:has-text('{target_time}'), td:has-text('{target_time}')"
                time_elem = await page.query_selector(time_selector)
                if time_elem:
                    await human_click(page, time_selector)
                else:
                    # إن لم يجد الوقت المحدد، نضغط على أول موعد متاح
                    first_available = await page.query_selector("button.btn-success, .time-slot:not([disabled])")
                    if first_available:
                        await first_available.click()
                        logger.info("تم اختيار أول موعد متاح (الوقت المحدد غير موجود)")

                await human_delay(200, 400)
                await human_click(page, "button:has-text('التالي')")
                await human_delay(200, 400)
                await human_click(page, "button:has-text('تقديم الطلب')")
                await human_delay(1500, 2500)

                # قراءة النتيجة
                success = await page.query_selector("text=تم الحجز بنجاح") or await page.query_selector(".alert-success")
                if success:
                    text = await success.inner_text()
                    await bot.send_message(chat_id, f"✅ {text}\nالتاريخ: {target_date}\nالوقت: {target_time}")
                else:
                    error_text = await page.inner_text("body")
                    await bot.send_message(chat_id, f"❌ لم يتم الحجز:\n{error_text[:500]}")
                return
            except Exception as e:
                await bot.send_message(chat_id, f"⚠️ خطأ أثناء الحجز: {e}")
                return

        # انتظر قبل الفحص التالي (1-2 ثانية) لتجنب الحظر
        await asyncio.sleep(random.uniform(1.0, 2.0))

    await bot.send_message(chat_id, "⏳ انتهت مدة المراقبة (ساعة) دون ظهور مواعيد. يمكنك المحاولة لاحقًا.")

# ================== بدء البوت ==================
async def main():
    logger.info("بدء تشغيل البوت...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
