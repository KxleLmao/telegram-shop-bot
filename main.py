import sqlite3
import os
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

# ===== CONFIG =====
TOKEN = os.getenv("BOT_TOKEN")

if not TOKEN:
    raise ValueError("BOT_TOKEN is missing in Railway Variables")

ADMIN_ID = 5907942510  # your Telegram ID
WALLET = "YOUR_USDT_ADDRESS"

# ===== DATABASE =====
conn = sqlite3.connect("database.db", check_same_thread=False)
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS products (
    id TEXT PRIMARY KEY,
    name TEXT,
    price INTEGER,
    stock INTEGER
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    items TEXT,
    total INTEGER,
    status TEXT
)
""")

conn.commit()

# Default products
cursor.execute("SELECT * FROM products")
if not cursor.fetchall():
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
        "Shop is Online 🛍",
        reply_markup=main_menu()
    )

# ===== BROWSE =====
async def browse(update, context):
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

    keyboard.append([InlineKeyboardButton("Back", callback_data="menu")])

    await query.edit_message_text(
        "Products:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ===== PRODUCT =====
async def product_page(update, context):
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

# ===== ADD CART =====
async def add_to_cart(update, context):
    query = update.callback_query
    user = query.from_user.id
    pid = query.data.split("_")[1]

    baskets.setdefault(user, {})
    baskets[user][pid] = baskets[user].get(pid, 0) + 1

    await query.answer("Added ✔")

# ===== CART =====
async def view_cart(update, context):
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
        if not row:
            continue

        name, price = row
        text += f"{name} x{qty} = £{price * qty}\n"
        total += price * qty

    text += f"\nTotal: £{total}"

    keyboard = [
        [InlineKeyboardButton("Checkout", callback_data="checkout")],
        [InlineKeyboardButton("Back", callback_data="menu")]
    ]

    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# ===== CHECKOUT =====
async def checkout(update, context):
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
        name, price = cursor.fetchone()
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

# ===== HANDLER =====
async def handler(update, context):
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

# ===== RUN =====
app = ApplicationBuilder().token(TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CallbackQueryHandler(handler))

print("Bot running...")
app.run_polling()
