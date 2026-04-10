import sqlite3
import os
import logging
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ===== LOGGING =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ===== CONFIG =====
TOKEN = os.getenv("TOKEN")  # Railway variable
ADMIN_ID = 5907942510  # CHANGE THIS
WALLET = "YOUR_USDT_ADDRESS"  # CHANGE THIS

if not TOKEN:
    raise ValueError("TOKEN missing")

# ===== DATABASE =====
DB_PATH = Path("database.db")

conn = sqlite3.connect(DB_PATH, check_same_thread=False)
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

# ===== MEMORY =====
baskets = {}

# ===== MENU =====
def main_menu():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🛍 Browse Products", callback_data="browse")],
        [InlineKeyboardButton("🛒 View Cart", callback_data="cart")]
    ])

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    baskets[update.effective_user.id] = {}
    await update.message.reply_text(
        "🛍 Shop is Online!",
        reply_markup=main_menu()
    )

# ===== BROWSE =====
async def browse(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    cursor.execute("SELECT * FROM products")
    products = cursor.fetchall()

    keyboard = []
    for p in products:
        keyboard.append([
            InlineKeyboardButton(
                f"{p[1]} | £{p[2]} | Stock: {p[3]}",
                callback_data=f"product_{p[0]}"
            )
        ])

    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="menu")])

    await query.edit_message_text(
        "🛍 Products:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ===== PRODUCT PAGE =====
async def product_page(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    pid = query.data.split("_")[1]

    cursor.execute("SELECT * FROM products WHERE id=?", (pid,))
    p = cursor.fetchone()

    if not p:
        await query.edit_message_text("Product not found")
        return

    keyboard = [
        [InlineKeyboardButton("➕ Add to Cart", callback_data=f"add_{pid}")],
        [InlineKeyboardButton("🔙 Back", callback_data="browse")]
    ]

    await query.edit_message_text(
        f"{p[1]}\nPrice: £{p[2]}\nStock: {p[3]}",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ===== ADD TO CART =====
async def add_to_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user.id
    pid = query.data.split("_")[1]

    baskets.setdefault(user, {})
    baskets[user][pid] = baskets[user].get(pid, 0) + 1

    await query.answer("Added to cart ✅")

# ===== CART =====
async def view_cart(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = query.from_user.id
    basket = baskets.get(user, {})

    if not basket:
        await query.edit_message_text("Cart is empty")
        return

    text = "🛒 Your Cart:\n\n"
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
        [InlineKeyboardButton("💳 Checkout", callback_data="checkout")],
        [InlineKeyboardButton("🔙 Back", callback_data="menu")]
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ===== CHECKOUT =====
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
        f"💰 Send {total} USDT to:\n{WALLET}\n\nOrder ID: {order_id}"
    )

# ===== CALLBACK ROUTER =====
async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    if not query:
        return

    data = query.data

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

# ===== ADMIN COMMANDS =====
async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    order_id = context.args[0]

    cursor.execute("UPDATE orders SET status='paid' WHERE id=?", (order_id,))
    conn.commit()

    cursor.execute("SELECT user_id FROM orders WHERE id=?", (order_id,))
    user_id = cursor.fetchone()[0]

    await context.bot.send_message(user_id, "✅ Payment confirmed!")

async def ship(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    order_id = context.args[0]
    tracking = context.args[1]

    cursor.execute("SELECT user_id FROM orders WHERE id=?", (order_id,))
    user_id = cursor.fetchone()[0]

    await context.bot.send_message(
        user_id,
        f"📦 Shipped!\nTracking: {tracking}"
    )

# ===== RUN =====
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(callback_handler))
    app.add_handler(CommandHandler("confirm", confirm))
    app.add_handler(CommandHandler("ship", ship))

    logger.info("Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
