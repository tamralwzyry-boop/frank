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
from playwright_stealth import stealth_async  # <-- الجديد

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
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            )
        except Exception as e:
            logger.error(f"فشل تشغيل المتصفح: {e}")
            raise
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport=VIEWPORT,
            locale="ar-SA",
            timezone_id="Asia/Riyadh",       # توقيت السعودية
        )
        # تطبيق stealth على السياق (يخفي كل شيء)
        await stealth_async(context)
        # إضافة init script للتأكيد
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
        # تطبيق stealth على الصفحة كذلك (بعض الحالات)
        await stealth_async(page)
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
            await human_delay(20, 60)
            await page.mouse.move(box['x'] + box['width']/2, box['y'] + box['height']/2)
            await human_delay(10, 30)
            await page.mouse.click(box['x'] + box['width']/2, box['y'] + box['height']/2)
        else:
            await element.click()
    except PlaywrightTimeout:
        # إرسال لقطة تلقائياً عند الفشل
        raise Exception(f"العنصر '{selector}' لم يظهر")

async def human_type(page, element, text):
    await element.click()
    await human_delay(100, 200)
    await element.fill("")
    await human_delay(50, 100)
    for char in text:
        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(0.05, 0.15))

class States(StatesGroup):
    choosing_mode = State()
    interactive = State()
    choose_element = State()
    waiting_for_date = State()
    waiting_for_time = State()
    monitoring = State()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

async def find_and_click_by_text(page, text):
    candidates = []
    all_buttons = await page.query_selector_all("a, button, [role='button'], input[type='submit'], input[type='button']")
    for btn in all_buttons:
        txt = await btn.inner_text()
        if text.lower() in txt.lower().strip():
            candidates.append(btn)
    if not candidates:
        return False, "لم أجد عنصرًا يحتوي هذا النص"
    if len(candidates) == 1:
        await human_click(page, candidates[0])
        return True, None
    else:
        choices = [(i, (await btn.inner_text()).strip()[:60]) for i, btn in enumerate(candidates)]
        return "multiple", choices

@dp.message(F.text == "/start")
async def start(message: types.Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖱️ تفاعلي (أنا أتحكم)", callback_data="manual")],
    ])
    await message.answer("مرحبًا! سأفتح موقع فسح ويمكنك توجيهي.\nاختر الوضع:", reply_markup=kb)
    await state.set_state(States.choosing_mode)

@dp.callback_query(F.data == "manual", States.choosing_mode)
async def manual_mode(cb: types.CallbackQuery, state: FSMContext):
    user_id = str(cb.from_user.id)
    page = await get_page(user_id)
    await page.goto(TARGET_URL, wait_until="domcontentloaded")
    await human_delay(1000)
    screenshot = await page.screenshot()
    await cb.message.answer_photo(
        BufferedInputFile(screenshot, filename="start.png"),
        caption="الصفحة الرئيسية. أرسل الأوامر."
    )
    await state.set_state(States.interactive)
    await cb.answer()

@dp.message(States.interactive)
async def handle_interactive(message: types.Message, state: FSMContext):
    text = message.text.strip()
    user_id = str(message.from_user.id)
    page = await get_page(user_id)

    async def send_error(selector):
        screenshot = await page.screenshot()
        await message.answer_photo(
            BufferedInputFile(screenshot, filename="error.png"),
            caption=f"❌ فشل في إيجاد العنصر: {selector}\nتحقق من اللقطة وأعد المحاولة."
        )

    try:
        if match := re.match(r"انقر على (.+)", text):
            target = match.group(1).strip()
            res, extra = await find_and_click_by_text(page, target)
            if res == True:
                await human_delay(500, 1000)
                screenshot = await page.screenshot()
                await message.answer_photo(BufferedInputFile(screenshot, filename="clicked.png"), caption=f"تم النقر على '{target}'")
            elif res == "multiple":
                opts = "\n".join([f"{i+1}. {t}" for i, t in extra])
                await state.update_data(click_choices=extra)
                await message.answer(f"وجدت عدة عناصر:\n{opts}\nأرسل الرقم.")
                await state.set_state(States.choose_element)
            else:
                await send_error(target)
        elif match := re.match(r"اكتب (.+?) في (.+)", text):
            value = match.group(1).strip()
            field_desc = match.group(2).strip()
            locators = [
                f"input[placeholder*='{field_desc}']",
                f"input[aria-label*='{field_desc}']",
                f"label:has-text('{field_desc}') + input",
                f"label:has-text('{field_desc}') ~ input",
            ]
            field = None
            for loc in locators:
                try:
                    field = await page.query_selector(loc)
                    if field:
                        break
                except:
                    continue
            if not field:
                await send_error(f"حقل: {field_desc}")
                return
            await human_type(page, field, value)
            await human_delay(200)
            screenshot = await page.screenshot()
            await message.answer_photo(BufferedInputFile(screenshot, filename="typed.png"), caption=f"تمت كتابة '{value}'")
        elif re.match(r"لقطة|صورة", text):
            screenshot = await page.screenshot()
            await message.answer_photo(BufferedInputFile(screenshot, filename="screenshot.png"))
        elif re.match(r"اضغط Enter|Enter", text):
            await page.keyboard.press("Enter")
            await human_delay(500)
            screenshot = await page.screenshot()
            await message.answer_photo(BufferedInputFile(screenshot, filename="enter.png"), caption="Enter")
        elif re.match(r"اضغط Tab|Tab", text):
            await page.keyboard.press("Tab")
            await human_delay(200)
            screenshot = await page.screenshot()
            await message.answer_photo(BufferedInputFile(screenshot, filename="tab.png"))
        elif text == "بدء المراقبة":
            await message.answer("أدخل التاريخ (YYYY-MM-DD):")
            await state.set_state(States.waiting_for_date)
        else:
            await message.answer("الأوامر: `انقر على ...`، `اكتب ... في ...`، `اضغط Enter`، `لقطة`")
    except Exception as e:
        logger.error(f"Error: {e}")
        screenshot = await page.screenshot()
        await message.answer_photo(BufferedInputFile(screenshot, filename="error.png"), caption=f"⚠️ حدث خطأ: {e}")

@dp.message(States.choose_element)
async def choose_element_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    choices = data.get("click_choices", [])
    try:
        idx = int(message.text.strip()) - 1
        if 0 <= idx < len(choices):
            target_text = choices[idx][1]
            page = await get_page(str(message.from_user.id))
            res, _ = await find_and_click_by_text(page, target_text)
            if res == True:
                await human_delay(500)
                screenshot = await page.screenshot()
                await message.answer_photo(BufferedInputFile(screenshot, filename="chosen.png"), caption=f"تم النقر على '{target_text}'")
            else:
                await message.answer("فشل النقر.")
            await state.set_state(States.interactive)
        else:
            await message.answer("رقم غير صحيح.")
    except ValueError:
        await message.answer("أرسل رقمًا.")

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
    summary = f"التاريخ: {data['date']}\nالوقت: {data['time']}\nابدأ المراقبة؟"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 ابدأ المراقبة", callback_data="start_monitor_btn")]
    ])
    await message.answer(summary, reply_markup=kb)

@dp.callback_query(F.data == "start_monitor_btn")
async def start_monitor_btn(cb: types.CallbackQuery, state: FSMContext):
    user_id = str(cb.from_user.id)
    data = await state.get_data()
    page = await get_page(user_id)
    await cb.message.answer("المراقبة الذكية تعمل الآن... سأخبرك فور ظهور موعد.")
    asyncio.create_task(monitor_and_book(page, data, cb.message.chat.id))
    await state.set_state(States.monitoring)
    await cb.answer()

async def monitor_and_book(page, data, chat_id):
    target_date = data["date"]
    target_time = data["time"]
    max_minutes = 60
    start = datetime.now()
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
            try:
                date_input = await page.query_selector("input[type='date'], input.datepicker")
                if date_input:
                    await date_input.fill(target_date)
                time_btn = await page.query_selector(f"button:has-text('{target_time}'), td:has-text('{target_time}')")
                if time_btn:
                    await time_btn.click()
                else:
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

async def main():
    logger.info("البوت التفاعلي المتطور يعمل...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
