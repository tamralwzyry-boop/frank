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

BOT_TOKEN = os.getenv("BOT_TOKEN", "8661589595:AAEh22n0-Od7pMJxsLT7GORHOyAWX4PFWsU")
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

async def human_delay(min_ms=80, max_ms=300):
    await asyncio.sleep(random.uniform(min_ms/1000, max_ms/1000))

async def human_click(page, selector):
    try:
        element = await page.wait_for_selector(selector, state="visible", timeout=8000)
        await element.scroll_into_view_if_needed()
        box = await element.bounding_box()
        if box:
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

# ================== حالات البوت ==================
class States(StatesGroup):
    choosing_mode = State()      # تلقائي أم يدوي؟
    # الأتمتة السابقة
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

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================== البداية: اختيار الوضع ==================
@dp.message(F.text == "/start")
async def start(message: types.Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🤖 تلقائي (حجز سريع)", callback_data="auto")],
        [InlineKeyboardButton(text="🖱️ تفاعلي (أنا أتحكم)", callback_data="manual")],
    ])
    await message.answer("اختر طريقة العمل:", reply_markup=kb)
    await state.set_state(States.choosing_mode)

@dp.callback_query(F.data == "auto", States.choosing_mode)
async def choose_auto(cb: types.CallbackQuery, state: FSMContext):
    # نفس منطق الأتمتة السابقة (باختصار: إدخال الإيميل...)
    await cb.message.answer("وضع التلقائي قيد الصيانة حاليًا. استخدم التفاعلي.")
    await cb.answer()

@dp.callback_query(F.data == "manual", States.choosing_mode)
async def choose_manual(cb: types.CallbackQuery, state: FSMContext):
    user_id = str(cb.from_user.id)
    page = await get_page(user_id)
    await page.goto(TARGET_URL, wait_until="domcontentloaded")
    await human_delay(1000, 1500)
    screenshot = await page.screenshot()
    await cb.message.answer_photo(
        BufferedInputFile(screenshot, filename="page.png"),
        caption="الصفحة الرئيسية. أرسل لي أوامرك:\n- `انقر على ...`\n- `اكتب ... في ...`\n- `لقطة`"
    )
    await state.set_state(States.interactive)
    await cb.answer()

# ================== محلل الأوامر الذكي (بدون API) ==================
def parse_command(text: str):
    text = text.strip()
    # 1. أمر النقر: "انقر على <نص>" أو "اضغط على <نص>" أو "click <نص>"
    click_match = re.match(r"(?:انقر|اضغط|click)\s+على\s+(.+)", text, re.IGNORECASE)
    if click_match:
        return {"action": "click", "target": click_match.group(1).strip()}

    # 2. أمر الكتابة: "اكتب <قيمة> في <وصف الحقل>"
    write_match = re.match(r"(?:اكتب|write)\s+(.+?)\s+في\s+(.+)", text, re.IGNORECASE)
    if write_match:
        return {"action": "type", "value": write_match.group(1).strip(), "field_desc": write_match.group(2).strip()}

    # 3. مجرد كتابة في الحقل النشط (إذا لم يذكر حقل)
    just_write = re.match(r"(?:اكتب|write)\s+(.+)", text, re.IGNORECASE)
    if just_write:
        return {"action": "type_active", "value": just_write.group(1).strip()}

    # 4. لقطة
    if re.match(r"(?:لقطة|صورة|screenshot)", text, re.IGNORECASE):
        return {"action": "screenshot"}

    # 5. انتظار
    wait_match = re.match(r"(?:انتظر|wait)\s+(\d+)", text, re.IGNORECASE)
    if wait_match:
        return {"action": "wait", "seconds": int(wait_match.group(1))}

    # 6. ضغط مفتاح: "اضغط Enter" أو "اضغط على Enter"
    key_match = re.match(r"(?:اضغط|press)\s+(?:على\s+)?(.+)", text, re.IGNORECASE)
    if key_match:
        return {"action": "press_key", "key": key_match.group(1).strip()}

    # 7. تحديث الصفحة
    if re.match(r"(?:تحديث|refresh|ريلود)", text, re.IGNORECASE):
        return {"action": "refresh"}

    # 8. بدء المراقبة الآلية (لاحقًا)
    if re.match(r"(?:بدء المراقبة|start\s*monitoring)", text, re.IGNORECASE):
        return {"action": "start_monitor"}

    return {"action": "unknown"}

# ================== تنفيذ الأوامر التفاعلية ==================
async def execute_command(page, cmd, user_id, chat_id):
    action = cmd["action"]
    if action == "click":
        target_text = cmd["target"]
        # البحث عن عنصر يحتوي على النص (مرن)
        try:
            element = await page.query_selector(f"text='{target_text}'")
            if element:
                await element.click()
                await human_delay(500, 1000)
                return True, None
            else:
                return False, f"لم أجد زرًا أو رابطًا بالنص '{target_text}'"
        except Exception as e:
            return False, str(e)

    elif action == "type":
        value = cmd["value"]
        field_desc = cmd["field_desc"]
        # نحاول إيجاد حقل بناءً على الوصف (بالبحث عن placeholder أو label)
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
            return False, f"لم أجد حقلًا يطابق '{field_desc}'"
        await human_delay(200, 400)
        return True, None

    elif action == "type_active":
        value = cmd["value"]
        # كتابة في الحقل النشط حاليًا
        await page.keyboard.type(value)
        return True, None

    elif action == "screenshot":
        screenshot = await page.screenshot()
        await bot.send_photo(chat_id, BufferedInputFile(screenshot, filename="screen.png"))
        return True, None

    elif action == "wait":
        seconds = cmd["seconds"]
        await asyncio.sleep(seconds)
        return True, None

    elif action == "press_key":
        key = cmd["key"].lower()
        # تحويل الاسم العربي لإنجليزي شائع
        key_map = {"انتر": "Enter", "دخول": "Enter", "مسافة": "Space", "تاب": "Tab", "حذف": "Backspace"}
        mapped = key_map.get(key, key.capitalize())
        await page.keyboard.press(mapped)
        return True, None

    elif action == "refresh":
        await page.reload()
        await human_delay(1000, 1500)
        return True, None

    elif action == "start_monitor":
        return "start_monitoring", None

    else:
        return False, "أمر غير مفهوم. جرب:\n- `انقر على تسجيل الدخول`\n- `اكتب user@mail.com في البريد الإلكتروني`\n- `لقطة`"

# ================== حلقة التفاعل ==================
@dp.message(States.interactive)
async def handle_interactive(message: types.Message, state: FSMContext):
    user_id = str(message.from_user.id)
    page = await get_page(user_id)
    cmd = parse_command(message.text)

    if cmd["action"] == "unknown":
        await message.answer("لم أفهم الأمر. اكتب `انقر على ...` أو `اكتب ... في ...` أو `لقطة`.")
        return

    if cmd["action"] == "start_monitor":
        data = await state.get_data()
        # نتوقع أن المستخدم قد ملأ البيانات مسبقًا؟ أو نطلبها منه الآن
        await message.answer("الرجاء إدخال البيانات المطلوبة للمراقبة:\nالتاريخ (YYYY-MM-DD):")
        await state.set_state(States.waiting_for_date)
        return

    # تنفيذ الأمر
    success, error = await execute_command(page, cmd, user_id, message.chat.id)

    if error:
        await message.answer(f"❌ {error}")
    elif success and cmd["action"] != "screenshot":
        # بعد التنفيذ الناجح (عدا اللقطة التي تم إرسالها مسبقاً)، نرسل لقطة جديدة ليرى النتيجة
        screenshot = await page.screenshot()
        await message.answer_photo(
            BufferedInputFile(screenshot, filename="result.png"),
            caption="تم. ماذا بعد؟"
        )
    elif not success:
        await message.answer("حدث خطأ غير معروف.")

# ================== المراقبة الآلية (عندما يصل المستخدم لصفحة المواعيد) ==================
@dp.message(States.waiting_for_date)
async def date_for_auto(message: types.Message, state: FSMContext):
    if not re.match(r"\d{4}-\d{2}-\d{2}", message.text):
        await message.answer("صيغة خاطئة. استخدم YYYY-MM-DD:")
        return
    await state.update_data(date=message.text.strip())
    await message.answer("أدخل الوقت (HH:MM):")
    await state.set_state(States.waiting_for_time)

@dp.message(States.waiting_for_time)
async def time_for_auto(message: types.Message, state: FSMContext):
    if not re.match(r"\d{2}:\d{2}", message.text):
        await message.answer("صيغة خاطئة. استخدم HH:MM:")
        return
    await state.update_data(time=message.text.strip())
    data = await state.get_data()
    # نقرأ البريد من state إذا كان موجودًا (يمكن أن تكون أضفته يدويًا من قبل)
    summary = f"التاريخ: {data['date']}\nالوقت: {data['time']}\nبدء المراقبة الآن؟"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 ابدأ المراقبة", callback_data="start_monitor_auto")]
    ])
    await message.answer(summary, reply_markup=kb)

@dp.callback_query(F.data == "start_monitor_auto")
async def start_auto_monitor(cb: types.CallbackQuery, state: FSMContext):
    user_id = str(cb.from_user.id)
    data = await state.get_data()
    page = await get_page(user_id)
    await cb.message.answer("المراقبة بدأت...")
    asyncio.create_task(monitor_and_book(page, data, cb.message.chat.id))
    await cb.answer()

async def monitor_and_book(page, data, chat_id):
    target_date = data["date"]
    target_time = data["time"]
    max_minutes = 60
    start = datetime.now()
    check_js = """() => {
        const availableButtons = document.querySelectorAll('button.btn-success, .time-slot:not([disabled]), td.available');
        if (availableButtons.length > 0) return true;
        return false;
    }"""
    while (datetime.now() - start) < timedelta(minutes=max_minutes):
        try:
            if await page.evaluate(check_js):
                # ... منطق الحجز الآلي ...
                pass
        except:
            pass
        await asyncio.sleep(random.uniform(1, 2))
    await bot.send_message(chat_id, "⏳ انتهت المراقبة دون حجز.")

# ================== تشغيل البوت ==================
async def main():
    logger.info("البوت التفاعلي قيد التشغيل...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
