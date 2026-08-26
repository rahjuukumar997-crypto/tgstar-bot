import os

# --- Bot ---
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x.strip()]  # e.g. "123456,789012"
# --- Fragment Stars API (fragment-api.space, no signup needed) ---
FRAGMENT_API_BASE = "https://api.fragment-api.space"
FRAGMENT_WALLET_SEED = os.getenv("FRAGMENT_WALLET_SEED", "")
# --- Web App ---
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://axsu-stars-bot.onrender.com/webapp/index.html")  # must be HTTPS
WEBHOOK_HOST = os.getenv("WEBHOOK_HOST", "https://axsu-stars-bot.onrender.com")
WEBHOOK_PATH = "/webhook"
WEB_SERVER_HOST = "0.0.0.0"
WEB_SERVER_PORT = int(os.getenv("PORT", 8080))

# --- Database ---
DB_PATH = os.getenv("DB_PATH", "wallet.db")

# --- Manual top-up payment accounts (edit to your real accounts) ---
PAYMENT_ACCOUNTS = {
    "kbzpay": {"label": "KBZ Pay", "number": "09681109228", "name": "Aye Myo Naing"},
    "wavepay": {"label": "Wave Pay", "number": "09942001929", "name": "Moe Moe Aung"},
    "ayapay": {"label": "AYA Pay", "number": "09680154618", "name": "Aye Myo Naing"},
}

# --- Star packages: (stars, price_mmk) ---
STAR_PACKAGES = [
    {"amount": 50, "price": 3400},
    {"amount": 100, "price": 6800},
    {"amount": 150, "price": 10200},
    {"amount": 200, "price": 13600},
    {"amount": 250, "price": 17000},
    {"amount": 500, "price": 34000},
    {"amount": 1000, "price": 68000},
    {"amount": 2500, "price": 170000},
]

# --- Premium plans: (key, label, months, price_mmk) ---
PREMIUM_PLANS = [
    {"key": "3m", "label": "Premium — 3 လ", "months": 3, "price": 53500},
    {"key": "6m", "label": "Premium — 6 လ", "months": 6, "price": 71000},
    {"key": "12m", "label": "Premium — 12 လ", "months": 12, "price": 129000},
]
