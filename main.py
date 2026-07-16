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

# سيتم استخدام وضع headless فقط لمتصفح السيرفر. الوضع المحلي يتطلب متصفحك الحقيقي.
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

# ================== إدارة الجلسات ==================
# سنخزن جلسة لكل مستخدم: نوعها (local_server / remote_user)، ومتصفحها
user_sessions = {}  # {user_id: {"type": ..., "browser", "context", "page"}}

async def get_session(user_id: str, mode: str):
    """
    إنشاء أو استرداد جلسة حسب النمط:
    mode = "remote": يتصل بمتصفح المستخدم المحلي على localhost:9222
    mode = "local": يشغل متصفح كروميوم على السيرفر
    """
    if user_id in user_sessions:
        return user_sessions[user_id]

    p = await async_playwright().start()
    if mode == "remote":
        try:
            browser = await p.chromium.connect_over_cdp("http://localhost:9222")
            # استخدام السياق الأول أو إنشاء واحد جديد
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            page = await context.new_page()
            session = {"type": "remote", "browser": browser, "context": context, "page": page}
            user_sessions[user_id] = session
            return session
        except Exception as e:
            raise Exception(f"❌ تعذر الاتصال بمتصفحك المحلي. تأكد أن Chrome يعمل على منفذ 9222.\nالخطأ: {e}")

    else:  # local server browser
        try:
            browser = await p.chromium.launch(
                headless=HEADLESS_MODE,
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox", "--disable-dev-shm-usage"]
            )
        except Exception as e:
            raise Exception(f"فشل تشغيل المتصفح: {e}")
        context = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport=VIEWPORT,
            locale="ar-SA",
            timezone_id="Asia/Riyadh"
        )
        # تطبيق stealth إذا كانت المكتبة موجودة
        try:
            from playwright_stealth import stealth_async
            await stealth_async(context)
        except ImportError:
            logger.warning("playwright-stealth غير مثبتة، قد يكون الكشف سهلاً")
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        page = await context.new_page()
        session = {"type": "local", "browser": browser, "context": context, "page": page}
        user_sessions[user_id] = session
        return session

async def close_session(user_id: str):
    if user_id in user_sessions:
        session = user_sessions.pop(user_id)
        try:
            await session["page"].close()
            await session["context"].close()
            if session["type"] == "local":
                await session["browser"].close()
            else:
                # لا نغلق متصفح المستخدم
                pass
        except:
            pass

# ================== تفاعلات بشرية ==================
async def human_delay(min_ms=80, max_ms=300):
    await asyncio.sleep(random.uniform(min_ms/1000, max_ms/1000))

async def human_click(page, selector):
    try:
        element = await page.wait_for_selector(selector, state="visible", timeout=8000)
        await element.scroll_into_view_if_needed()
        box = await element.bounding_box()
        if box:
            # حركة ماوس عشوائية تدريجية
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
        raise Exception(f"العنصر '{selector}' لم يظهر")

async def human_type(page, element, text):
    """يكتب النص حرفاً حرفاً مع تأخيرات طبيعية"""
    await element.click()
    await human_delay(100, 250)
    await element.fill("")  # مسح المحتوى
    await human_delay(50, 100)
    for char in text:
        await page.keyboard.type(char)
        await asyncio.sleep(random.uniform(0.05, 0.15))
    await human_delay(50, 100)

# ================== حالات FSM ==================
class States(StatesGroup):
    choosing_mode = State()
    interactive = State()
    choose_element = State()
    waiting_for_date = State()
    waiting_for_time = State()
    monitoring = State()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# ================== أدوات البحث عن العناصر ==================
async def find_and_click_by_text(page, text):
    """يبحث عن زر/رابط يحتوي النص. إذا تعدد، يعرض قائمة."""
    candidates = []
    all_buttons = await page.query_selector_all("a, button, [role='button'], input[type='submit'], input[type='button']")
    for btn in all_buttons:
        txt = await btn.inner_text()
        if text.lower() in txt.lower().strip():
            candidates.append(btn)
    if not candidates:
        return False, "لم أجد عنصرًا يحتوي هذا النص بين الأزرار والروابط"
    if len(candidates) == 1:
        # استخدام human_click مع النص للراحة
        await human_click(page, f"text='{text}'")
        return True, None
    else:
        choices = [(i, (await btn.inner_text()).strip()[:60]) for i, btn in enumerate(candidates)]
        return "multiple", choices

# ================== /start ==================
@dp.message(F.text == "/start")
async def start(message: types.Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🖥️ اتصال بمتصفحي المحلي (أقوى حماية)", callback_data="remote")],
        [InlineKeyboardButton(text="☁️ تشغيل على السيرفر (متصفح مخفي)", callback_data="local")],
    ])
    await message.answer(
        "اختر طريقة تشغيل المتصفح:\n\n"
        "1️⃣ <b>متصفحي المحلي</b>: تحتاج تشغيل Chrome مع <code>--remote-debugging-port=9222</code> على جهازك.\n"
        "2️⃣ <b>السيرفر</b>: المتصفح يعمل على Railway (قد تكتشفه بعض المواقع).",
        reply_markup=kb, parse_mode="HTML"
    )
    await state.set_state(States.choosing_mode)

@dp.callback_query(F.data == "remote", States.choosing_mode)
async def choose_remote(cb: types.CallbackQuery, state: FSMContext):
    user_id = str(cb.from_user.id)
    try:
        session = await get_session(user_id, "remote")
        page = session["page"]
        await page.goto(TARGET_URL, wait_until="domcontentloaded")
        await human_delay(1000)
        screenshot = await page.screenshot()
        await cb.message.answer_photo(
            BufferedInputFile(screenshot, filename="remote_start.png"),
            caption="✅ تم الاتصال بمتصفحك المحلي. أرسل الأوامر الآن:\n- `انقر على ...`\n- `اكتب ... في ...`\n- `لقطة`\n- `اضغط Enter`"
        )
        await state.set_state(States.interactive)
    except Exception as e:
        await cb.message.answer(f"❌ {e}")
    await cb.answer()

@dp.callback_query(F.data == "local", States.choosing_mode)
async def choose_local(cb: types.CallbackQuery, state: FSMContext):
    user_id = str(cb.from_user.id)
    try:
        session = await get_session(user_id, "local")
        page = session["page"]
        await page.goto(TARGET_URL, wait_until="domcontentloaded")
        await human_delay(1000)
        screenshot = await page.screenshot()
        await cb.message.answer_photo(
            BufferedInputFile(screenshot, filename="local_start.png"),
            caption="✅ تم تشغيل المتصفح على السيرفر. أرسل الأوامر:\n- `انقر على ...`\n- `اكتب ... في ...`\n- `لقطة`\n- `اضغط Enter`"
        )
        await state.set_state(States.interactive)
    except Exception as e:
        await cb.message.answer(f"❌ {e}")
    await cb.answer()

# ================== الوضع التفاعلي ==================
@dp.message(States.interactive)
async def interactive_handler(message: types.Message, state: FSMContext):
    text = message.text.strip()
    user_id = str(message.from_user.id)
    session = user_sessions.get(user_id)
    if not session:
        await message.answer("لا توجد جلسة نشطة. أرسل /start.")
        return
    page = session["page"]

    # تحليل الأوامر
    cmd_click = re.match(r"انقر على (.+)", text)
    cmd_type = re.match(r"اكتب (.+?) في (.+)", text)
    cmd_screenshot = re.match(r"لقطة|صورة", text)
    cmd_enter = re.match(r"اضغط Enter|Enter", text)
    cmd_tab = re.match(r"اضغط Tab|Tab", text)

    try:
        if cmd_click:
            target = cmd_click.group(1).strip()
            res, extra = await find_and_click_by_text(page, target)
            if res == True:
                await human_delay(500, 1000)
                screenshot = await page.screenshot()
                await message.answer_photo(BufferedInputFile(screenshot, filename="clicked.png"), caption=f"تم النقر على '{target}'")
            elif res == "multiple":
                opts = "\n".join([f"{i+1}. {t}" for i, t in extra])
                await state.update_data(click_choices=extra)
                await message.answer(f"وجدت عدة عناصر:\n{opts}\nأرسل الرقم المطلوب.")
                await state.set_state(States.choose_element)
            else:
                await message.answer(f"❌ {extra}")

        elif cmd_type:
            value = cmd_type.group(1).strip()
            field_desc = cmd_type.group(2).strip()
            # البحث عن الحقل المناسب
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
                # محاولة مطابقة النص القريب
                all_inputs = await page.query_selector_all("input:visible")
                for inp in all_inputs:
                    near = await inp.evaluate("el => (el.labels?.[0]?.innerText || el.placeholder || '')")
                    if field_desc.lower() in near.lower():
                        field = inp
                        break
            if not field:
                await message.answer(f"❌ لم أجد حقلًا يطابق '{field_desc}'")
            else:
                # استخدام الكتابة البشرية في وضع السيرفر، والعادية في المحلي
                if session["type"] == "local":
                    await human_type(page, field, value)
                else:
                    # في المتصفح المحلي نستخدم fill عادية (لكن يمكن استخدام human_type أيضاً)
                    await field.click()
                    await field.fill(value)
                await human_delay(200)
                screenshot = await page.screenshot()
                await message.answer_photo(BufferedInputFile(screenshot, filename="typed.png"), caption=f"تمت كتابة '{value}'")

        elif cmd_screenshot:
            screenshot = await page.screenshot()
            await message.answer_photo(BufferedInputFile(screenshot, filename="screen.png"), caption="لقطة الشاشة الحالية")

        elif cmd_enter:
            await page.keyboard.press("Enter")
            await human_delay(500)
            screenshot = await page.screenshot()
            await message.answer_photo(BufferedInputFile(screenshot, filename="enter.png"), caption="تم الضغط Enter")

        elif cmd_tab:
            await page.keyboard.press("Tab")
            await human_delay(200)
            screenshot = await page.screenshot()
            await message.answer_photo(BufferedInputFile(screenshot, filename="tab.png"), caption="تم الانتقال للحقل التالي")

        elif text == "بدء المراقبة":
            await message.answer("أدخل التاريخ المطلوب (YYYY-MM-DD):")
            await state.set_state(States.waiting_for_date)

        else:
            await message.answer("أوامر غير معروفة. جرّب:\n- `انقر على ...`\n- `اكتب ... في ...`\n- `اضغط Enter`\n- `اضغط Tab`\n- `لقطة`\n- `بدء المراقبة`")

    except Exception as e:
        logger.error(f"خطأ في التفاعل: {e}")
        screenshot = await page.screenshot()
        await message.answer_photo(BufferedInputFile(screenshot, filename="error.png"), caption=f"⚠️ حدث خطأ: {e}")

# ================== اختيار عنصر من قائمة ==================
@dp.message(States.choose_element)
async def choose_element_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    choices = data.get("click_choices", [])
    try:
        idx = int(message.text.strip()) - 1
        if 0 <= idx < len(choices):
            target_text = choices[idx][1]
            session = user_sessions.get(str(message.from_user.id))
            if not session:
                await message.answer("لا توجد جلسة نشطة.")
                return
            page = session["page"]
            # نجرب النقر باستخدام النص المختار
            try:
                await human_click(page, f"text='{target_text}'")
            except:
                await message.answer("فشل النقر على العنصر.")
                await state.set_state(States.interactive)
                return
            await human_delay(500)
            screenshot = await page.screenshot()
            await message.answer_photo(BufferedInputFile(screenshot, filename="chosen.png"), caption=f"تم النقر على '{target_text}'")
            await state.set_state(States.interactive)
        else:
            await message.answer("رقم غير صحيح.")
    except ValueError:
        await message.answer("أرسل رقمًا صحيحًا.")

# ================== إعدادات المراقبة ==================
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
    summary = f"التاريخ: {data['date']}\nالوقت: {data['time']}\nابدأ المراقبة الآن؟"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 ابدأ المراقبة", callback_data="start_monitor_btn")]
    ])
    await message.answer(summary, reply_markup=kb)

@dp.callback_query(F.data == "start_monitor_btn")
async def start_monitor_btn(cb: types.CallbackQuery, state: FSMContext):
    user_id = str(cb.from_user.id)
    session = user_sessions.get(user_id)
    if not session:
        await cb.message.answer("لا توجد جلسة نشطة. أرسل /start.")
        return
    data = await state.get_data()
    page = session["page"]
    await cb.message.answer("🔍 بدأت المراقبة الذكية... ستصلك رسالة فور ظهور موعد.")
    asyncio.create_task(monitor_and_book(page, data, cb.message.chat.id))
    await state.set_state(States.monitoring)
    await cb.answer()

# ================== المراقبة الخاطفة (بدون تحديث) ==================
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
    await bot.send_message(chat_id, "⏳ انتهت المراقبة (ساعة) دون ظهور مواعيد.")

# ================== تشغيل البوت ==================
async def main():
    logger.info("البوت الذكي مع خيار المتصفح المحلي قيد التشغيل...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
