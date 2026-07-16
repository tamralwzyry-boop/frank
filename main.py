import asyncio, json, os, random, re, logging
from pathlib import Path
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    BufferedInputFile
)
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

# ================== الإعدادات ==================
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
TARGET_URL = "https://www.fasah.sa"
HEADLESS_MODE = os.getenv("HEADLESS", "true").lower() == "true"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15",
]
VIEWPORT = {"width": 1366, "height": 768}

ACCOUNTS_FILE = Path("accounts.json")
if not ACCOUNTS_FILE.exists():
    ACCOUNTS_FILE.write_text("{}", encoding="utf-8")

def load_accounts():
    with open(ACCOUNTS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_accounts(data):
    with open(ACCOUNTS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

# ================== إدارة المتصفح ==================
user_browsers = {}
user_pages = {}

async def get_browser_context(user_id: str):
    if user_id not in user_browsers:
        p = await async_playwright().start()
        try:
            browser = await p.chromium.launch(
                headless=HEADLESS_MODE,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"]
            )
        except Exception as e:
            logger.error(f"فشل تشغيل المتصفح: {e}")
            raise
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

# ================== تفاعلات بشرية ==================
async def human_delay(min_ms=80, max_ms=300):
    await asyncio.sleep(random.uniform(min_ms/1000, max_ms/1000))

async def human_click(page, selector):
    try:
        element = await page.wait_for_selector(selector, state="visible", timeout=8000)
        await element.scroll_into_view_if_needed()
        box = await element.bounding_box()
        if box:
            await page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height']/2)
        else:
            await element.click()
        await element.click()
    except PlaywrightTimeout:
        raise Exception(f"العنصر '{selector}' لم يظهر")

# ================== حالات المحادثة ==================
class States(StatesGroup):
    choosing_mode = State()       # اختيار الوضع
    # الوضع التلقائي القديم
    new_email = State()
    new_password = State()
    purpose = State()
    extra_options = State()
    waiting_for_date = State()
    waiting_for_time = State()
    confirm_start = State()
    monitoring = State()
    # الوضع التفاعلي
    interactive = State()
    choose_element = State()      # اختيار عنصر من قائمة

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================== أدوات ذكية ==================
async def get_clickable_elements(page):
    """يجلب جميع الأزرار والروابط الظاهرة في الصفحة مع نصوصها."""
    return await page.evaluate('''() => {
        const elements = document.querySelectorAll('a, button, [role="button"], input[type="submit"], input[type="button"]');
        const visible = [];
        elements.forEach((el, index) => {
            const rect = el.getBoundingClientRect();
            if (rect.width > 0 && rect.height > 0 && rect.top < window.innerHeight) {
                const text = el.innerText || el.value || el.getAttribute('aria-label') || '';
                if (text.trim().length > 0) {
                    visible.push({index, tag: el.tagName, text: text.trim().substring(0, 80)});
                }
            }
        });
        return visible;
    }''')

async def find_and_click_by_text(page, text):
    """يبحث عن عناصر تحتوي النص (مطابقة جزئية). إذا وجد أكثر من واحد، يعرضهم للمستخدم عبر البوت."""
    # نبحث عن العناصر التي تحتوي النص
    elements = await page.query_selector_all(f"text='{text}'")
    clickable = []
    for el in elements:
        tag = await el.evaluate("e => e.tagName")
        if tag in ["A", "BUTTON", "INPUT"]:
            clickable.append(el)
    if not clickable:
        # نجرب البحث باستخدام محدد يحتوي النص
        try:
            el = await page.wait_for_selector(f"*:has-text('{text}')", state="visible", timeout=2000)
            if el:
                await el.click()
                return True, None
        except:
            return False, "لم أجد عنصرًا يحتوي هذا النص"
    if len(clickable) == 1:
        await clickable[0].click()
        return True, None
    else:
        # تخزين العناصر لاختيار المستخدم لاحقاً
        choices = []
        for i, el in enumerate(clickable):
            txt = await el.inner_text()
            choices.append((i, txt.strip()[:50]))
        return "multiple", choices

# ================== البداية ==================
@dp.message(F.text == "/start")
async def start(message: types.Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 تلقائي (حجز سريع)", callback_data="auto")],
        [InlineKeyboardButton(text="🖱️ تفاعلي (أنا أتحكم)", callback_data="manual")],
    ])
    await message.answer("اختر وضع العمل:", reply_markup=kb)
    await state.set_state(States.choosing_mode)

@dp.callback_query(F.data == "auto", States.choosing_mode)
async def auto_mode(cb: types.CallbackQuery, state: FSMContext):
    # ننتقل مباشرة لطلب الإيميل (اختصار)
    user_id = str(cb.from_user.id)
    accounts = load_accounts().get(user_id, [])
    if accounts:
        buttons = [[InlineKeyboardButton(text=acc["email"], callback_data=f"login_{acc['email']}")] for acc in accounts]
        buttons.append([InlineKeyboardButton(text="➕ تسجيل جديد", callback_data="new_login")])
        await cb.message.answer("اختر حسابًا:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))
        await state.set_state(States.choosing_mode)
    else:
        await cb.message.answer("أرسل البريد الإلكتروني:")
        await state.set_state(States.new_email)
    await cb.answer()

@dp.callback_query(F.data == "manual", States.choosing_mode)
async def manual_mode(cb: types.CallbackQuery, state: FSMContext):
    user_id = str(cb.from_user.id)
    page = await get_page(user_id)
    await page.goto(TARGET_URL, wait_until="domcontentloaded")
    await human_delay(1000)
    screenshot = await page.screenshot()
    await cb.message.answer_photo(
        BufferedInputFile(screenshot, filename="page.png"),
        caption="الصفحة الرئيسية. أرسل لي أوامر:\n- `انقر على <النص>`\n- `اكتب <قيمة> في <وصف>`\n- `لقطة`\n- `اضغط Enter`"
    )
    await state.set_state(States.interactive)
    await cb.answer()

# ================== الوضع التفاعلي ==================
@dp.message(States.interactive)
async def interactive_handler(message: types.Message, state: FSMContext):
    text = message.text.strip()
    user_id = str(message.from_user.id)
    page = await get_page(user_id)

    # ---- تحليل الأمر ----
    cmd_click = re.match(r"انقر على (.+)", text)
    cmd_type = re.match(r"اكتب (.+?) في (.+)", text)
    cmd_screenshot = re.match(r"لقطة|صورة", text)
    cmd_enter = re.match(r"اضغط Enter|Enter", text)

    if cmd_click:
        target = cmd_click.group(1).strip()
        result, choices = await find_and_click_by_text(page, target)
        if result == True:
            await human_delay(500, 1000)
            screenshot = await page.screenshot()
            await message.answer_photo(BufferedInputFile(screenshot, filename="after_click.png"), caption=f"تم النقر على '{target}'")
        elif isinstance(result, str) and result == "multiple":
            # عرض الخيارات
            opts = "\n".join([f"{i+1}. {txt}" for i, txt in choices])
            await state.update_data(click_choices=choices)
            await message.answer(f"وجدت عدة عناصر:\n{opts}\nأرسل الرقم المطلوب.")
            await state.set_state(States.choose_element)
        else:
            await message.answer(f"❌ {choices}")

    elif cmd_type:
        value = cmd_type.group(1).strip()
        field_desc = cmd_type.group(2).strip()
        # محاولة إيجاد حقل بناءً على الوصف
        locators = [
            f"input[placeholder*='{field_desc}']",
            f"input[aria-label*='{field_desc}']",
            f"label:has-text('{field_desc}') + input",
            f"label:has-text('{field_desc}') ~ input",
        ]
        found = False
        for loc in locators:
            try:
                field = await page.query_selector(loc)
                if field:
                    await field.click()
                    await field.fill(value)
                    found = True
                    break
            except:
                continue
        if not found:
            await message.answer(f"❌ لم أجد حقلًا يطابق '{field_desc}'")
        else:
            await human_delay(200)
            screenshot = await page.screenshot()
            await message.answer_photo(BufferedInputFile(screenshot, filename="after_type.png"), caption="تمت الكتابة")
    elif cmd_screenshot:
        screenshot = await page.screenshot()
        await message.answer_photo(BufferedInputFile(screenshot, filename="screen.png"), caption="لقطة الشاشة الحالية")
    elif cmd_enter:
        await page.keyboard.press("Enter")
        await human_delay(500)
        screenshot = await page.screenshot()
        await message.answer_photo(BufferedInputFile(screenshot, filename="after_enter.png"), caption="تم الضغط Enter")
    else:
        await message.answer("لم أفهم. استخدم: `انقر على ...`، `اكتب ... في ...`، `لقطة`، `اضغط Enter`")

# ================== اختيار عنصر من قائمة (بعد تعدد الخيارات) ==================
@dp.message(States.choose_element)
async def choose_element_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    choices = data.get("click_choices", [])
    try:
        idx = int(message.text.strip()) - 1
        if 0 <= idx < len(choices):
            # نقر على العنصر المختار
            page = await get_page(str(message.from_user.id))
            # نعيد البحث عن العنصر بالنص المختار
            target_text = choices[idx][1]
            el = await page.query_selector(f"text='{target_text}'")
            if el:
                await el.click()
                await human_delay(500)
                screenshot = await page.screenshot()
                await message.answer_photo(BufferedInputFile(screenshot, filename="chosen.png"), caption=f"تم النقر على '{target_text}'")
                await state.set_state(States.interactive)
            else:
                await message.answer("العنصر اختفى.")
        else:
            await message.answer("رقم غير صحيح.")
    except ValueError:
        await message.answer("أرسل رقمًا صحيحًا.")

# ================== الوضع التلقائي (بعد أن يصل المستخدم لصفحة المواعيد) ==================
# يمكن للمستخدم في الوضع التفاعلي أن يكتب "بدء المراقبة" بعد أن يصل لصفحة المواعيد.
@dp.message(States.interactive, F.text.lower() == "بدء المراقبة")
async def start_auto_from_interactive(message: types.Message, state: FSMContext):
    await message.answer("أدخل التاريخ المطلوب (YYYY-MM-DD):")
    await state.set_state(States.waiting_for_date)

@dp.message(States.waiting_for_date)
async def date_entered(message: types.Message, state: FSMContext):
    if not re.match(r"\d{4}-\d{2}-\d{2}", message.text):
        await message.answer("صيغة خاطئة. استخدم YYYY-MM-DD:")
        return
    await state.update_data(date=message.text.strip())
    await message.answer("أدخل الوقت (HH:MM):")
    await state.set_state(States.waiting_for_time)

@dp.message(States.waiting_for_time)
async def time_entered(message: types.Message, state: FSMContext):
    if not re.match(r"\d{2}:\d{2}", message.text):
        await message.answer("صيغة خاطئة. استخدم HH:MM:")
        return
    await state.update_data(time=message.text.strip())
    data = await state.get_data()
    summary = f"التاريخ: {data['date']}\nالوقت: {data['time']}\nبدء المراقبة؟"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 ابدأ المراقبة", callback_data="start_monitor_btn")]
    ])
    await message.answer(summary, reply_markup=kb)

@dp.callback_query(F.data == "start_monitor_btn")
async def start_monitor_btn(cb: types.CallbackQuery, state: FSMContext):
    user_id = str(cb.from_user.id)
    data = await state.get_data()
    page = await get_page(user_id)
    await cb.message.answer("المراقبة بدأت... سأخبرك فور ظهور موعد.")
    asyncio.create_task(monitor_and_book(page, data, cb.message.chat.id))
    await state.set_state(States.monitoring)
    await cb.answer()

# ================== المراقبة الخاطفة (بدون تحديث متكرر) ==================
async def monitor_and_book(page, data, chat_id):
    target_date = data["date"]
    target_time = data["time"]
    max_minutes = 60
    start = datetime.now()
    logger.info("بدء مراقبة DOM...")

    check_js = """() => {
        const available = document.querySelectorAll('button.time-slot:not([disabled]), .available-slot, td.available');
        if (available.length > 0) return true;
        const noSlots = document.querySelector('.alert-warning, .no-slots');
        if (noSlots) return false;
        const table = document.querySelector('table.table-bordered, .slots-table');
        if (table) {
            const cells = table.querySelectorAll('td');
            for (const cell of cells) {
                if (cell.innerText && !cell.classList.contains('disabled') && cell.offsetParent !== null) return true;
            }
        }
        return false;
    }"""

    while (datetime.now() - start) < timedelta(minutes=max_minutes):
        try:
            available = await page.evaluate(check_js)
        except:
            available = False
        if available:
            logger.info("تم اكتشاف موعد!")
            try:
                # اختيار التاريخ إذا لزم
                date_input = await page.query_selector("input[type='date'], input.datepicker")
                if date_input:
                    await date_input.fill(target_date)
                # اختيار الوقت
                time_btn = await page.query_selector(f"button:has-text('{target_time}'), td:has-text('{target_time}')")
                if time_btn:
                    await time_btn.click()
                else:
                    # أول موعد متاح
                    first_avail = await page.query_selector("button.time-slot:not([disabled])")
                    if first_avail:
                        await first_avail.click()
                await human_delay(200, 400)
                await human_click(page, "button:has-text('التالي')")
                await human_delay(200, 400)
                await human_click(page, "button:has-text('تقديم الطلب')")
                await human_delay(1500, 2500)
                success = await page.query_selector("text=تم الحجز بنجاح") or await page.query_selector(".alert-success")
                if success:
                    text = await success.inner_text()
                    await bot.send_message(chat_id, f"✅ {text}\nالتاريخ: {target_date}\nالوقت: {target_time}")
                else:
                    body = await page.inner_text("body")
                    await bot.send_message(chat_id, f"❌ لم يتم الحجز:\n{body[:300]}")
                return
            except Exception as e:
                await bot.send_message(chat_id, f"⚠️ خطأ أثناء الحجز: {e}")
                return
        await asyncio.sleep(random.uniform(1.0, 2.0))
    await bot.send_message(chat_id, "⏳ انتهت المراقبة (ساعة) دون مواعيد.")

# ================== تشغيل البوت ==================
async def main():
    logger.info("البوت الشامل قيد التشغيل...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
