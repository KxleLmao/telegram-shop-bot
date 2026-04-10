import sqlite3
import os
import logging
import nest_asyncio
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# Fix for "event loop is already running" on Railway
nest_asyncio.apply()

# ============== LOGGING ==============
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ============== CONFIG ==============
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("🚨 BOT_TOKEN is missing! Check Railway Variables.")

WALLET = "YOUR_USDT_ADDRESS"   # ← CHANGE THIS TO YOUR REAL WALLET

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

# Default products
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

async def browse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    keyboard = []
    for p in products:
        keyboard.append([InlineKeyboardButton(
            f"{p[1]} | £{p[2]} | Stock: {p[3]}", callback_data=f"product_{p[0]}"
        )])
    keyboard.append([InlineKeyboardButton("Back", callback_data="menu")])

    await query.edit_message_text("Products:", reply_markup=InlineKeyboardMarkup(keyboard))

async def product_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    pid = query.data.split("_")[1]

    cursor.execute("SELECT * FROM products WHERE id=?", (pid,))
    p = cursor.fetchone()
    if not p:
        await query.edit_message_text("Not found")
        return

    keyboard = [
        [InlineKeyboardButton("Add to Cart", callback_data=f"add_{pid}")],
        [InlineKeyboardButton("Back", callback_data="browse")]
    ]

    await query.edit_message_text(
        f"{p[1]}\nPrice: £{p[2]}\nStock: {p[3]}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user.id
    pid = query.data.split("_")[1]

    baskets.setdefault(user, {})
    baskets[user][pid] = baskets[user].get(pid, 0) + 1
    await query.answer("Added ✔")

async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user.id
    basket = baskets.get(user, {})

    if not basket:
        await query.edit_message_text("Cart empty")
        return

    text = "Your Cart:\n\n"
    total = 0
    for pid, qty in basket.items():
        cursor.execute("SELECT name, price FROM products WHERE id=?", (pid,))
        row = cursor.fetchone()
        if row:
            name, price = row
            text += f"{name} x{qty} = £{price * qty}\n"
            total += price * qty

    text += f"\nTotal: £{total}"

    keyboard = [
        [InlineKeyboardButton("Checkout", callback_data="checkout")],
        [InlineKeyboardButton("Back", callback_data="menu")]
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def checkout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user.id
    basket = baskets.get(user, {})

    if not basket:
        await query.edit_message_text("Cart empty")
        return

    total = 0
    items = ""
    for pid, qty in basket.items():
        cursor.execute("SELECT name, price FROM products WHERE id=?", (pid,))
        row = cursor.fetchone()
        if row:
            name, price = row
            total += price * qty
            items += f"{name} x{qty}, "

    cursor.execute(
        "INSERT INTO orders (user_id, items, total, status) VALUES (?, ?, ?, ?)",
        (user, items, total, "pending")
    )
    conn.commit()

    order_id = cursor.lastrowid
    baskets[user] = {}

    await query.edit_message_text(
        f"Send {total} USDT to:\n{WALLET}\n\nOrder ID: {order_id}"
    )

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
        logger.error(f"Handler error: {e}", exc_info=True)
        await query.answer("Something went wrong 😈")

# ============== RUN BOT ==============
def run_bot():
    logger.info("=== HORNY BOT STARTING ===")
    logger.info(f"Database ready at {DB_PATH}")

    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("Bot is running like a horny little slut... 🔥 Go test /start now!")

    app.run_polling(allowed_updates=Update.ALL_TYPES, stop_signals=None)

if __name__ == "__main__":
    run_bot()
