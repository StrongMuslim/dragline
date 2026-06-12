import os
import json
import logging
import requests
import gspread
import cloudinary
import cloudinary.uploader
from google.oauth2.service_account import Credentials
from aiohttp import web
from dotenv import load_dotenv
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, KeyboardButton, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, filters, ContextTypes
)

load_dotenv()

BOT_TOKEN    = os.getenv('BOT_TOKEN')
ADMIN_ID     = int(os.getenv('ADMIN_ID', '0'))
ADMIN_SECRET = os.getenv('ADMIN_SECRET', 'dragline2025')
SHEET_ID     = os.getenv('SHEET_ID', '')
SHEET_NAME   = os.getenv('SHEET_NAME', 'Sheet1')
SITE_URL     = 'https://strongmuslim.github.io/dragline/'

GVIZ_URL = f'https://docs.google.com/spreadsheets/d/{SHEET_ID}/gviz/tq?tqx=out:json&sheet={SHEET_NAME}'

# Must match Google Sheet column order exactly
COLUMNS = [
    'id', 'category', 'brand', 'model', 'year', 'hours', 'condition',
    'compatible_models', 'price_krw', 'location_kr', 'status',
    'name_kr', 'name_uz', 'name_ru', 'name_en',
    'desc_kr', 'desc_uz', 'desc_ru', 'desc_en',
    'photos'
]

cloudinary.config(
    cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
    api_key=os.getenv('CLOUDINARY_API_KEY'),
    api_secret=os.getenv('CLOUDINARY_API_SECRET')
)

BRAND_SUGGESTIONS = [
    'Hyundai', 'Doosan', 'Yanmar', 'Kobelco',
    'Volvo', 'Caterpillar', 'Komatsu', 'Daewoo', 'Hitachi', 'Samsung'
]

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# ─── States ──────────────────────────────────────────────────────────────────
SECRET_WAIT = 10
(ADD_CAT, ADD_BRAND, ADD_MODEL, ADD_YEAR, ADD_HOURS,
 ADD_COND, ADD_PRICE, ADD_LOC, ADD_COMPAT, ADD_PHOTOS_URL,
 ADD_NAME_RU, ADD_NAME_KR, ADD_NAME_UZ, ADD_NAME_EN,
 ADD_DESC_RU, ADD_DESC_KR, ADD_DESC_UZ, ADD_DESC_EN) = range(20, 38)
EDIT_CHOOSE, EDIT_FIELD, EDIT_VALUE = range(40, 43)
DEL_CHOOSE = 50
STATUS_CHOOSE, STATUS_VALUE = 60, 61

# ─── Google Sheets (gspread) ─────────────────────────────────────────────────

def _get_sheet():
    creds_json = os.getenv('GOOGLE_CREDS_JSON')
    if not creds_json:
        logger.error("GOOGLE_CREDS_JSON не задан")
        return None
    try:
        creds_dict = json.loads(creds_json)
        scopes = ['https://www.googleapis.com/auth/spreadsheets']
        creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
        client = gspread.authorize(creds)
        return client.open_by_key(SHEET_ID).worksheet(SHEET_NAME)
    except Exception as e:
        logger.error(f"gspread init: {e}")
        return None

def _find_row(sheet, pid: str):
    try:
        all_rows = sheet.get_all_values()
        for i, row in enumerate(all_rows):
            if i == 0:
                continue
            if row and str(row[0]).strip() == str(pid).strip():
                return i + 1  # 1-indexed
        return None
    except Exception as e:
        logger.error(f"_find_row: {e}")
        return None

# ─── Read (gviz — free, no limits) ───────────────────────────────────────────

def fetch_listings() -> list:
    try:
        r = requests.get(GVIZ_URL, timeout=10)
        r.raise_for_status()
        text = r.text
        data = json.loads(text[text.index('{'):text.rindex('}') + 1])
        rows = data['table']['rows']
        result = []
        for row in rows:
            c = row.get('c', [])

            def v(i, default=''):
                try:
                    cell = c[i]
                    return cell['v'] if cell and cell.get('v') is not None else default
                except Exception:
                    return default

            raw_id = v(0)
            if raw_id is None or raw_id == '':
                continue

            def ts(val):
                if val is None:
                    return ''
                if isinstance(val, float) and val == int(val):
                    return str(int(val))
                return str(val).strip()

            result.append({
                'id':                str(int(raw_id)) if isinstance(raw_id, float) else str(raw_id).strip(),
                'category':          ts(v(1)),
                'brand':             ts(v(2)),
                'model':             ts(v(3)),
                'year':              ts(v(4)),
                'hours':             ts(v(5)),
                'condition':         ts(v(6)),
                'compatible_models': ts(v(7)),
                'price_krw':         ts(v(8)),
                'location_kr':       ts(v(9)),
                'status':            ts(v(10)) or 'available',
                'name_kr':           ts(v(11)),
                'name_uz':           ts(v(12)),
                'name_ru':           ts(v(13)),
                'name_en':           ts(v(14)),
                'desc_kr':           ts(v(15)),
                'desc_uz':           ts(v(16)),
                'desc_ru':           ts(v(17)),
                'desc_en':           ts(v(18)),
                'photos':            ts(v(19)),
            })
        return result
    except Exception as e:
        logger.error(f"fetch_listings: {e}")
        return []

# ─── Write (gspread) ─────────────────────────────────────────────────────────

def add_listing(data: dict) -> bool:
    sheet = _get_sheet()
    if not sheet:
        return False
    try:
        row = [str(data.get(col, '')) for col in COLUMNS]
        sheet.append_row(row, value_input_option='USER_ENTERED')
        return True
    except Exception as e:
        logger.error(f"add_listing: {e}")
        return False

def update_listing_field(pid: str, field: str, value: str) -> bool:
    sheet = _get_sheet()
    if not sheet:
        return False
    row_num = _find_row(sheet, pid)
    if not row_num:
        return False
    try:
        col_idx = COLUMNS.index(field) + 1
        sheet.update_cell(row_num, col_idx, value)
        return True
    except Exception as e:
        logger.error(f"update_listing_field: {e}")
        return False

def delete_listing(pid: str) -> bool:
    sheet = _get_sheet()
    if not sheet:
        return False
    row_num = _find_row(sheet, pid)
    if not row_num:
        return False
    try:
        sheet.delete_rows(row_num)
        return True
    except Exception as e:
        logger.error(f"delete_listing: {e}")
        return False

def next_id() -> int:
    ids = []
    for l in fetch_listings():
        try:
            ids.append(int(l['id']))
        except (ValueError, KeyError):
            pass
    return max(ids, default=0) + 1

# ─── UI helpers ──────────────────────────────────────────────────────────────

CAT_LABELS = {'excavator': 'Экскаватор', 'parts': 'Запчасть', 'other_machinery': 'Техника'}
STATUS_LABELS = {'available': '✅ Доступен', 'reserved': '🟡 Резерв', 'sold': '❌ Продан'}
STATUS_ICONS  = {'available': '✅', 'reserved': '🟡', 'sold': '❌'}

def listing_card(l: dict) -> str:
    price = l.get('price_krw', '—')
    try:
        price = f"{int(price):,}".replace(',', ' ')
    except Exception:
        pass
    cat    = CAT_LABELS.get(l.get('category', ''), l.get('category', '—'))
    status = STATUS_LABELS.get(l.get('status', ''), l.get('status', '—'))
    return (
        f"🆔 {l.get('id','—')}  |  {l.get('brand','—')} {l.get('model','—')}\n"
        f"📂 {cat}  |  💰 {price} ₩\n"
        f"{status}"
    )

def main_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[KeyboardButton("🌐 Открыть каталог", web_app=WebAppInfo(url=SITE_URL))]],
        resize_keyboard=True
    )

def admin_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            ["➕ Добавить лот", "✏️ Редактировать"],
            ["🗑 Удалить", "📊 Статус"],
            ["📋 Все лоты", "🆔 Показать ID"],
            ["🔙 Выйти"]
        ],
        resize_keyboard=True
    )

def cancel_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["Отмена"]], resize_keyboard=True)

def skip_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["Пропустить"], ["Отмена"]], resize_keyboard=True)

def same_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["Такое же"], ["Отмена"]], resize_keyboard=True)

def same_skip_kb() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup([["Такое же"], ["Пропустить"], ["Отмена"]], resize_keyboard=True)

# ─── /start ───────────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "⚙️ <b>Dragline</b> — б/у спецтехника из Кореи\n\n"
        "Экскаваторы, запчасти, спецтехника с прямой поставкой.\n"
        "Откройте каталог 👇",
        parse_mode='HTML',
        reply_markup=main_kb()
    )
    return ConversationHandler.END

# ─── Admin: secret ───────────────────────────────────────────────────────────

async def admin_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Нет доступа.")
        return ConversationHandler.END
    await update.message.reply_text("🔐 Введите секретный код:", reply_markup=ReplyKeyboardRemove())
    return SECRET_WAIT

async def check_secret(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.text.strip() == ADMIN_SECRET and update.effective_user.id == ADMIN_ID:
        context.user_data['is_admin'] = True
        await update.message.reply_text("✅ Добро пожаловать в админ-панель!", reply_markup=admin_kb())
    else:
        await update.message.reply_text("❌ Неверный код. /start — главное меню.")
    return ConversationHandler.END

async def admin_exit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('is_admin', None)
    await update.message.reply_text("Вышли из панели.", reply_markup=main_kb())

# ─── Admin: list / ID view ────────────────────────────────────────────────────

async def admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('is_admin'):
        return
    listings = fetch_listings()
    if not listings:
        await update.message.reply_text("📭 Лотов нет.")
        return

    by_cat = {}
    for l in listings:
        by_cat.setdefault(l.get('category', 'other'), []).append(l)

    cat_headers = {'excavator': '🦾 Экскаваторы', 'parts': '🔩 Запчасти', 'other_machinery': '🚛 Техника'}
    messages = []
    for cat, items in by_cat.items():
        block = f"<b>{cat_headers.get(cat, cat.upper())}</b>\n{'─'*20}\n"
        for l in items:
            price = l.get('price_krw', '—')
            try:
                price = f"{int(price):,}".replace(',', ' ')
            except Exception:
                pass
            st = STATUS_ICONS.get(l.get('status', ''), '❓')
            block += f"{st} <b>{l['id']}</b>  {l.get('brand','—')} {l.get('model','—')}  💰{price}₩\n"
        messages.append(block)

    chunk = ""
    for block in messages:
        if len(chunk) + len(block) > 3500:
            await update.message.reply_text(chunk, parse_mode='HTML')
            chunk = ""
        chunk += block + "\n"
    if chunk:
        await update.message.reply_text(chunk, parse_mode='HTML')

async def admin_id_view(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('is_admin'):
        return
    listings = fetch_listings()
    if not listings:
        await update.message.reply_text("📭 Лотов нет.")
        return
    lines = [f"🆔 <b>{l['id']}</b> — {l.get('brand','—')} {l.get('model','—')}" for l in listings]
    text = "\n".join(lines)
    if len(text) > 3800:
        for i in range(0, len(lines), 30):
            await update.message.reply_text("\n".join(lines[i:i+30]), parse_mode='HTML')
    else:
        await update.message.reply_text(text, parse_mode='HTML')

# ─── Admin: ADD ───────────────────────────────────────────────────────────────

async def add_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.pop('new_listing', None)
    await update.message.reply_text("Отменено.", reply_markup=admin_kb())
    return ConversationHandler.END

async def admin_add_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('is_admin'):
        return ConversationHandler.END
    context.user_data['new_listing'] = {}
    await update.message.reply_text(
        "Добавление лота.\n\n📂 Выберите категорию:",
        reply_markup=ReplyKeyboardMarkup(
            [["Экскаватор", "Запчасть"], ["Другая техника"], ["Отмена"]],
            resize_keyboard=True
        )
    )
    return ADD_CAT

async def add_cat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        return await add_cancel(update, context)
    cat_map = {"Экскаватор": "excavator", "Запчасть": "parts", "Другая техника": "other_machinery"}
    cat = cat_map.get(text)
    if not cat:
        await update.message.reply_text("Выберите из кнопок ниже.")
        return ADD_CAT
    context.user_data['new_listing']['category'] = cat
    brand_rows = [[b] for b in BRAND_SUGGESTIONS] + [["Другая марка"], ["Отмена"]]
    await update.message.reply_text(
        "🏭 Выберите марку (или 'Другая марка'):",
        reply_markup=ReplyKeyboardMarkup(brand_rows, resize_keyboard=True)
    )
    return ADD_BRAND

async def add_brand(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        return await add_cancel(update, context)
    if text == "Другая марка":
        await update.message.reply_text("Введите название марки:", reply_markup=cancel_kb())
        return ADD_BRAND
    context.user_data['new_listing']['brand'] = text
    await update.message.reply_text("🔧 Введите модель (например: R210LC-9):", reply_markup=cancel_kb())
    return ADD_MODEL

async def add_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        return await add_cancel(update, context)
    context.user_data['new_listing']['model'] = text
    await update.message.reply_text("📅 Год выпуска:", reply_markup=cancel_kb())
    return ADD_YEAR

async def add_year(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        return await add_cancel(update, context)
    try:
        year = int(text)
        if not (1980 <= year <= 2030):
            raise ValueError
        context.user_data['new_listing']['year'] = str(year)
    except ValueError:
        await update.message.reply_text("❌ Введите корректный год (1980–2030).")
        return ADD_YEAR
    await update.message.reply_text("⏱ Моточасы (или 'Пропустить'):", reply_markup=skip_kb())
    return ADD_HOURS

async def add_hours(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        return await add_cancel(update, context)
    if text == "Пропустить":
        context.user_data['new_listing']['hours'] = ''
    else:
        try:
            hours = int(text.replace(' ', '').replace(',', ''))
            context.user_data['new_listing']['hours'] = str(hours)
        except ValueError:
            await update.message.reply_text("❌ Введите число.")
            return ADD_HOURS
    await update.message.reply_text(
        "🔍 Состояние техники:",
        reply_markup=ReplyKeyboardMarkup(
            [["Отличное", "Хорошее", "Среднее"], ["Отмена"]],
            resize_keyboard=True
        )
    )
    return ADD_COND

async def add_cond(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        return await add_cancel(update, context)
    context.user_data['new_listing']['condition'] = text
    await update.message.reply_text("💰 Цена в вонах (₩):\nНапример: 15000000", reply_markup=cancel_kb())
    return ADD_PRICE

async def add_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        return await add_cancel(update, context)
    try:
        price = int(text.replace(' ', '').replace(',', ''))
        context.user_data['new_listing']['price_krw'] = str(price)
    except ValueError:
        await update.message.reply_text("❌ Только цифры (например: 15000000).")
        return ADD_PRICE
    await update.message.reply_text("📍 Локация в Корее (город или регион):", reply_markup=cancel_kb())
    return ADD_LOC

async def add_loc(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        return await add_cancel(update, context)
    context.user_data['new_listing']['location_kr'] = text
    await update.message.reply_text(
        "🔗 Совместимые модели (для запчастей)\nИли 'Пропустить':",
        reply_markup=skip_kb()
    )
    return ADD_COMPAT

async def add_compat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        return await add_cancel(update, context)
    context.user_data['new_listing']['compatible_models'] = '' if text == "Пропустить" else text
    context.user_data['new_listing']['photos_list'] = []
    await update.message.reply_text(
        "📸 Отправьте фото (можно несколько).\n"
        "Когда все загрузите — нажмите <b>Готово</b>.",
        parse_mode='HTML',
        reply_markup=ReplyKeyboardMarkup([["Готово"], ["Отмена"]], resize_keyboard=True)
    )
    return ADD_PHOTOS_URL

async def add_photos_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Photo received — upload to Cloudinary
    if update.message.photo:
        photo = update.message.photo[-1]
        file = await photo.get_file()
        file_bytes = await file.download_as_bytearray()
        try:
            result = cloudinary.uploader.upload(
                bytes(file_bytes),
                folder="dragline",
                transformation=[{"width": 1200, "height": 900, "crop": "limit", "quality": "auto"}]
            )
            url = result['secure_url']
            context.user_data['new_listing']['photos_list'].append(url)
            count = len(context.user_data['new_listing']['photos_list'])
            await update.message.reply_text(
                f"✅ Фото {count} загружено.\nОтправьте ещё или нажмите <b>Готово</b>.",
                parse_mode='HTML'
            )
        except Exception as e:
            await update.message.reply_text(f"❌ Ошибка загрузки: {e}")
        return ADD_PHOTOS_URL

    text = update.message.text.strip() if update.message.text else ''
    if text == "Отмена":
        return await add_cancel(update, context)
    if text == "Готово":
        photos_list = context.user_data['new_listing'].get('photos_list', [])
        if not photos_list:
            await update.message.reply_text("❌ Отправьте хотя бы одно фото.")
            return ADD_PHOTOS_URL
        context.user_data['new_listing']['photos'] = ','.join(photos_list)
        await update.message.reply_text(
            "🇷🇺 Название лота на <b>русском</b>:",
            parse_mode='HTML',
            reply_markup=cancel_kb()
        )
        return ADD_NAME_RU

    await update.message.reply_text("Отправьте фото или нажмите Готово.")
    return ADD_PHOTOS_URL

async def add_name_ru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        return await add_cancel(update, context)
    context.user_data['new_listing']['name_ru'] = text
    await update.message.reply_text(
        "🇰🇷 Название на <b>корейском</b> (или 'Такое же'):",
        parse_mode='HTML',
        reply_markup=same_kb()
    )
    return ADD_NAME_KR

async def add_name_kr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        return await add_cancel(update, context)
    nl = context.user_data['new_listing']
    nl['name_kr'] = nl['name_ru'] if text == "Такое же" else text
    await update.message.reply_text(
        "🇺🇿 Название на <b>узбекском</b> (или 'Такое же'):",
        parse_mode='HTML',
        reply_markup=same_kb()
    )
    return ADD_NAME_UZ

async def add_name_uz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        return await add_cancel(update, context)
    nl = context.user_data['new_listing']
    nl['name_uz'] = nl['name_ru'] if text == "Такое же" else text
    await update.message.reply_text(
        "🇬🇧 Название на <b>английском</b> (или 'Такое же'):",
        parse_mode='HTML',
        reply_markup=same_kb()
    )
    return ADD_NAME_EN

async def add_name_en(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        return await add_cancel(update, context)
    nl = context.user_data['new_listing']
    nl['name_en'] = nl['name_ru'] if text == "Такое же" else text
    await update.message.reply_text(
        "📝 Описание на <b>русском</b> (или 'Пропустить'):",
        parse_mode='HTML',
        reply_markup=skip_kb()
    )
    return ADD_DESC_RU

async def add_desc_ru(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        return await add_cancel(update, context)
    nl = context.user_data['new_listing']
    nl['desc_ru'] = '' if text == "Пропустить" else text
    if not nl['desc_ru']:
        nl['desc_kr'] = nl['desc_uz'] = nl['desc_en'] = ''
        return await _save_listing(update, context)
    await update.message.reply_text(
        "🇰🇷 Описание на <b>корейском</b> ('Такое же' / 'Пропустить'):",
        parse_mode='HTML',
        reply_markup=same_skip_kb()
    )
    return ADD_DESC_KR

async def add_desc_kr(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        return await add_cancel(update, context)
    nl = context.user_data['new_listing']
    nl['desc_kr'] = nl['desc_ru'] if text == "Такое же" else ('' if text == "Пропустить" else text)
    await update.message.reply_text(
        "🇺🇿 Описание на <b>узбекском</b> ('Такое же' / 'Пропустить'):",
        parse_mode='HTML',
        reply_markup=same_skip_kb()
    )
    return ADD_DESC_UZ

async def add_desc_uz(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        return await add_cancel(update, context)
    nl = context.user_data['new_listing']
    nl['desc_uz'] = nl['desc_ru'] if text == "Такое же" else ('' if text == "Пропустить" else text)
    await update.message.reply_text(
        "🇬🇧 Описание на <b>английском</b> ('Такое же' / 'Пропустить'):",
        parse_mode='HTML',
        reply_markup=same_skip_kb()
    )
    return ADD_DESC_EN

async def add_desc_en(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        return await add_cancel(update, context)
    nl = context.user_data['new_listing']
    nl['desc_en'] = nl['desc_ru'] if text == "Такое же" else ('' if text == "Пропустить" else text)
    return await _save_listing(update, context)

async def _save_listing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nl = context.user_data['new_listing']
    nl['id'] = str(next_id())
    nl['status'] = 'available'
    for col in COLUMNS:
        nl.setdefault(col, '')
    await update.message.reply_text("⏳ Сохраняю в таблицу...")
    if add_listing(nl):
        await update.message.reply_text(
            f"✅ Лот добавлен!\n\n{listing_card(nl)}",
            reply_markup=admin_kb()
        )
    else:
        await update.message.reply_text("❌ Ошибка при сохранении.", reply_markup=admin_kb())
    context.user_data.pop('new_listing', None)
    return ConversationHandler.END

# ─── Admin: DELETE ────────────────────────────────────────────────────────────

async def admin_del_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('is_admin'):
        return ConversationHandler.END
    await update.message.reply_text("🗑 Введите ID лота для удаления:", reply_markup=cancel_kb())
    return DEL_CHOOSE

async def admin_del_do(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        await update.message.reply_text("Отменено.", reply_markup=admin_kb())
        return ConversationHandler.END
    listings = fetch_listings()
    l = next((x for x in listings if x['id'] == text), None)
    if not l:
        await update.message.reply_text("❌ Лот не найден. Проверьте ID.")
        return DEL_CHOOSE
    if delete_listing(text):
        await update.message.reply_text(
            f"✅ Лот <b>{l.get('brand','?')} {l.get('model','?')}</b> (ID {text}) удалён.",
            parse_mode='HTML', reply_markup=admin_kb()
        )
    else:
        await update.message.reply_text("❌ Ошибка при удалении.", reply_markup=admin_kb())
    return ConversationHandler.END

# ─── Admin: STATUS ────────────────────────────────────────────────────────────

async def admin_status_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('is_admin'):
        return ConversationHandler.END
    await update.message.reply_text("📊 Введите ID лота:", reply_markup=cancel_kb())
    return STATUS_CHOOSE

async def admin_status_choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        await update.message.reply_text("Отменено.", reply_markup=admin_kb())
        return ConversationHandler.END
    listings = fetch_listings()
    l = next((x for x in listings if x['id'] == text), None)
    if not l:
        await update.message.reply_text("❌ Лот не найден.")
        return STATUS_CHOOSE
    context.user_data['status_id'] = text
    cur = STATUS_LABELS.get(l.get('status', ''), '—')
    await update.message.reply_text(
        f"Текущий статус: <b>{cur}</b>\n\nВыберите новый:",
        parse_mode='HTML',
        reply_markup=ReplyKeyboardMarkup(
            [["✅ Доступен", "🟡 Резерв", "❌ Продан"], ["Отмена"]],
            resize_keyboard=True
        )
    )
    return STATUS_VALUE

async def admin_status_set(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        await update.message.reply_text("Отменено.", reply_markup=admin_kb())
        return ConversationHandler.END
    status_map = {"✅ Доступен": "available", "🟡 Резерв": "reserved", "❌ Продан": "sold"}
    status = status_map.get(text)
    if not status:
        await update.message.reply_text("Выберите из кнопок.")
        return STATUS_VALUE
    pid = context.user_data.pop('status_id', None)
    if update_listing_field(pid, 'status', status):
        await update.message.reply_text(
            f"✅ Статус лота {pid}: <b>{text}</b>",
            parse_mode='HTML', reply_markup=admin_kb()
        )
    else:
        await update.message.reply_text("❌ Ошибка.", reply_markup=admin_kb())
    return ConversationHandler.END

# ─── Admin: EDIT ─────────────────────────────────────────────────────────────

EDIT_FIELDS = {
    'brand':             'Марка',
    'model':             'Модель',
    'year':              'Год',
    'hours':             'Моточасы',
    'condition':         'Состояние',
    'price_krw':         'Цена (₩)',
    'location_kr':       'Локация',
    'compatible_models': 'Совм. модели',
    'photos':            'Фото (URL через ,)',
    'name_ru':           'Название RU',
    'name_kr':           'Название KR',
    'name_uz':           'Название UZ',
    'name_en':           'Название EN',
    'desc_ru':           'Описание RU',
    'desc_kr':           'Описание KR',
    'desc_uz':           'Описание UZ',
    'desc_en':           'Описание EN',
}

async def admin_edit_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('is_admin'):
        return ConversationHandler.END
    await update.message.reply_text("✏️ Введите ID лота:", reply_markup=cancel_kb())
    return EDIT_CHOOSE

async def admin_edit_choose_field(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        await update.message.reply_text("Отменено.", reply_markup=admin_kb())
        return ConversationHandler.END
    listings = fetch_listings()
    l = next((x for x in listings if x['id'] == text), None)
    if not l:
        await update.message.reply_text("❌ Лот не найден.")
        return EDIT_CHOOSE
    context.user_data['edit_id'] = text
    rows = [[v] for v in EDIT_FIELDS.values()] + [["Отмена"]]
    await update.message.reply_text(
        f"Лот: <b>{l.get('brand','?')} {l.get('model','?')}</b>\n\nЧто редактировать?",
        parse_mode='HTML',
        reply_markup=ReplyKeyboardMarkup(rows, resize_keyboard=True)
    )
    return EDIT_FIELD

async def admin_edit_get_value(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        await update.message.reply_text("Отменено.", reply_markup=admin_kb())
        return ConversationHandler.END
    key = next((k for k, v in EDIT_FIELDS.items() if v == text), None)
    if not key:
        await update.message.reply_text("❌ Выберите поле из списка.")
        return EDIT_FIELD
    context.user_data['edit_field'] = key
    await update.message.reply_text(
        f"<b>{text}</b> — введите новое значение:",
        parse_mode='HTML',
        reply_markup=cancel_kb()
    )
    return EDIT_VALUE

async def admin_edit_save(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    if text == "Отмена":
        await update.message.reply_text("Отменено.", reply_markup=admin_kb())
        return ConversationHandler.END
    pid   = context.user_data.pop('edit_id', None)
    field = context.user_data.pop('edit_field', None)
    if update_listing_field(pid, field, text):
        await update.message.reply_text(
            f"✅ <b>{EDIT_FIELDS.get(field, field)}</b> обновлено!",
            parse_mode='HTML', reply_markup=admin_kb()
        )
    else:
        await update.message.reply_text("❌ Ошибка при обновлении.", reply_markup=admin_kb())
    return ConversationHandler.END

# ─── Admin menu ───────────────────────────────────────────────────────────────

async def admin_menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('is_admin'):
        return
    t = update.message.text
    if t == "📋 Все лоты":
        await admin_list(update, context)
    elif t == "🆔 Показать ID":
        await admin_id_view(update, context)
    elif t == "🔙 Выйти":
        await admin_exit(update, context)

# ─── Fallback ─────────────────────────────────────────────────────────────────

async def unknown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get('is_admin'):
        await update.message.reply_text("Используйте кнопки 👆", reply_markup=admin_kb())
    else:
        await update.message.reply_text("Используйте кнопку для открытия каталога 👇", reply_markup=main_kb())

# ─── Error handler ────────────────────────────────────────────────────────────

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    from telegram.error import Conflict, NetworkError
    err = context.error
    if isinstance(err, Conflict):
        logger.warning("Conflict: другой инстанс запущен.")
        return
    if isinstance(err, NetworkError):
        logger.warning(f"Network error: {err}")
        return
    logger.error(f"Ошибка: {err}", exc_info=err)

# ─── Main ─────────────────────────────────────────────────────────────────────

async def start_web_server(application) -> None:
    web_app = web.Application()
    web_app.router.add_get('/health', lambda r: web.Response(text='ok'))
    port = int(os.getenv('PORT', 8080))
    runner = web.AppRunner(web_app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', port).start()
    logger.info(f"Health server started on port {port}")

def main():
    app = Application.builder().token(BOT_TOKEN).post_init(start_web_server).build()
    app.add_error_handler(error_handler)

    secret_conv = ConversationHandler(
        entry_points=[CommandHandler('admin', admin_entry)],
        states={SECRET_WAIT: [MessageHandler(filters.TEXT & ~filters.COMMAND, check_secret)]},
        fallbacks=[CommandHandler('start', start)],
        allow_reentry=True
    )

    add_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r'^➕ Добавить лот$'), admin_add_start)],
        states={
            ADD_CAT:        [MessageHandler(filters.TEXT & ~filters.COMMAND, add_cat)],
            ADD_BRAND:      [MessageHandler(filters.TEXT & ~filters.COMMAND, add_brand)],
            ADD_MODEL:      [MessageHandler(filters.TEXT & ~filters.COMMAND, add_model)],
            ADD_YEAR:       [MessageHandler(filters.TEXT & ~filters.COMMAND, add_year)],
            ADD_HOURS:      [MessageHandler(filters.TEXT & ~filters.COMMAND, add_hours)],
            ADD_COND:       [MessageHandler(filters.TEXT & ~filters.COMMAND, add_cond)],
            ADD_PRICE:      [MessageHandler(filters.TEXT & ~filters.COMMAND, add_price)],
            ADD_LOC:        [MessageHandler(filters.TEXT & ~filters.COMMAND, add_loc)],
            ADD_COMPAT:     [MessageHandler(filters.TEXT & ~filters.COMMAND, add_compat)],
            ADD_PHOTOS_URL: [
                MessageHandler(filters.PHOTO, add_photos_url),
                MessageHandler(filters.TEXT & ~filters.COMMAND, add_photos_url),
            ],
            ADD_NAME_RU:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name_ru)],
            ADD_NAME_KR:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name_kr)],
            ADD_NAME_UZ:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name_uz)],
            ADD_NAME_EN:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_name_en)],
            ADD_DESC_RU:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_desc_ru)],
            ADD_DESC_KR:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_desc_kr)],
            ADD_DESC_UZ:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_desc_uz)],
            ADD_DESC_EN:    [MessageHandler(filters.TEXT & ~filters.COMMAND, add_desc_en)],
        },
        fallbacks=[MessageHandler(filters.Regex(r'^Отмена$'), add_cancel)],
        allow_reentry=True
    )

    del_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r'^🗑 Удалить$'), admin_del_start)],
        states={DEL_CHOOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_del_do)]},
        fallbacks=[MessageHandler(filters.Regex(r'^Отмена$'), add_cancel)],
        allow_reentry=True
    )

    status_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r'^📊 Статус$'), admin_status_start)],
        states={
            STATUS_CHOOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_status_choose)],
            STATUS_VALUE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_status_set)],
        },
        fallbacks=[MessageHandler(filters.Regex(r'^Отмена$'), add_cancel)],
        allow_reentry=True
    )

    edit_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(r'^✏️ Редактировать$'), admin_edit_start)],
        states={
            EDIT_CHOOSE: [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_choose_field)],
            EDIT_FIELD:  [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_get_value)],
            EDIT_VALUE:  [MessageHandler(filters.TEXT & ~filters.COMMAND, admin_edit_save)],
        },
        fallbacks=[MessageHandler(filters.Regex(r'^Отмена$'), add_cancel)],
        allow_reentry=True
    )

    app.add_handler(secret_conv)
    app.add_handler(add_conv)
    app.add_handler(del_conv)
    app.add_handler(status_conv)
    app.add_handler(edit_conv)

    app.add_handler(CommandHandler('start', start))
    app.add_handler(MessageHandler(
        filters.Regex(r'^(📋 Все лоты|🆔 Показать ID|🔙 Выйти)$'),
        admin_menu_handler
    ))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, unknown))

    logger.info("Dragline bot started ⚙️")
    app.run_polling(drop_pending_updates=True)


if __name__ == '__main__':
    main()
