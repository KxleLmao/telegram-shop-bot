import sqlite3
import os
import logging
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ============== LOGGING ==============
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============== CONFIG ==============
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("🚨 BOT_TOKEN is missing!")

WALLET = "YOUR_USDT_ADDRESS"

# ============== DATABASE ==============
DB_PATH = Path("/data/database.db")
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
cursor = conn.cursor()

cursor.executescript("""
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT,
    price INTEGER,
    stock INTEGER
);
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    items TEXT,
    total INTEGER,
    status TEXT
);
""")
conn.commit()

if cursor.execute("SELECT COUNT(*) FROM products").fetchone()[0] == 0:
    cursor.executemany("INSERT INTO products VALUES (?, ?, ?, ?)", [
        ("g1", "Gummies Pack", 10, 20),
        ("g2", "Big Gummies Pack", 18, 10),
    ])
    conn.commit()

baskets = {}

def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛍 Browse Products", callback_data="browse")],
        [InlineKeyboardButton("🛒 View Cart", callback_data="cart")]
    ])

# ============== HANDLERS ==============
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    baskets[update.effective_user.id] = {}
    await update.message.reply_text("Shop is Online 🛍", reply_markup=main_menu())

async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return
    data = query.data

    try:
        if data == "browse":
            await browse(update, context)
        elif data.startswith("product_"):
            await product_page(update, context)
        elif data.startswith("add_"):
            await add_to_cart(update, context)
        elif data == "cart":
            await view_cart(update, context)
        elif data == "checkout":
            await checkout(update, context)
        elif data == "menu":
            await query.edit_message_text("Menu", reply_markup=main_menu())
    except Exception as e:
        logger.error(f"Error in handler: {e}", exc_info=True)

# ============== OTHER HANDLERS (add the rest here - browse, product_page, etc.) ==============
# Paste all your previous browse, product_page, add_to_cart, view_cart, checkout functions here
# (I'm keeping this short so you can just drop them in)

async def main():
    logger.info("=== HORNY BOT STARTING ===")
    logger.info(f"DB path: {DB_PATH} (exists: {DB_PATH.exists()})")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("Bot is running like a horny little slut... 🔥 Ready for commands")

    await app.initialize()
    await app.start()
    await app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        asyncio.run(main())   # Wait — we still need asyncio
    except RuntimeError as e:
        if "event loop is already running" in str(e).lower():
            logger.warning("Event loop already running — using nest_asyncio fix...")
            import nest_asyncio
            nest_asyncio.apply()
            asyncio.run(main())
        else:
            logger.critical(f"Bot crashed: {e}", exc_info=True)
    except Exception as e:
        logger.critical(f"Bot crashed hard: {e}", exc_info=True)
