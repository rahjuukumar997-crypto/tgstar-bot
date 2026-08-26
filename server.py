"""
Combined Telegram bot + Web App backend.

Run modes:
  - Polling (simplest, good for testing):  python server.py --polling
  - Webhook (for production behind HTTPS):  python server.py

Architecture:
  Web App (webapp/index.html) --fetch()--> REST API (/api/*) --sqlite--> wallet.db
  Telegram user               --messages-->  Bot handlers (aiogram)

Fragment fulfillment note:
  Fragment.com has no official public API for buying Stars/Premium.
  This starter treats every Stars/Premium purchase as a pending Order that
  an admin fulfills manually (buy on fragment.com yourself, then run
  /fulfill <order_id>). That is the same workflow most real resale bots
  use today. If Telegram or Fragment later ships an official API, swap
  the stub in `fulfill_order_stub()` for a real call.
"""
import argparse
import json
import logging

from aiohttp import web
import aiohttp
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command, CommandObject
from aiogram.types import Message, WebAppInfo, InlineKeyboardMarkup, InlineKeyboardButton

import config
import database as db
from webapp_auth import validate_init_data

logging.basicConfig(level=logging.INFO)
log = logging.getLogger("tgstars_bot")

bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher()

db.init_db()


# ---------------------------------------------------------------------------
# Bot handlers
# ---------------------------------------------------------------------------
@dp.message(Command("myid"))
async def cmd_myid(message: Message):
    await message.answer(
        f"Your ID: {message.from_user.id}\n"
        f"ADMIN_IDS in config: {config.ADMIN_IDS}"
    )
@dp.message(Command("rawenv")) 
async def cmd_rawenv(message: Message):
    import os
    raw = os.getenv("ADMIN_IDS")
    await message.answer(
        f"Raw env value: {repr(raw)}\n"
        f"Type: {type(raw)}"
    )
@dp.message(Command("start"))
async def cmd_start(message: Message):
    db.get_or_create_user(message.from_user.id, message.from_user.username)
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="⭐ Stars / Premium Shop ဖွင့်ရန်", web_app=WebAppInfo(url=config.WEBAPP_URL))
    ]])
    await message.answer(
        "မင်္ဂလာပါ! Star နဲ့ Premium ကို MMK Wallet နဲ့ အချိန်မရွေး ဝယ်ယူနိုင်ပါပြီ။\n\n"
        "👇 အောက်က ခလုတ်ကနေ Shop ကို ဖွင့်ပါ။",
        reply_markup=kb,
    )


@dp.message(Command("balance"))
async def cmd_balance(message: Message):
    bal = db.get_balance(message.from_user.id)
    await message.answer(f"💰 သင့် Wallet လက်ကျန်: {bal:,} Ks")


@dp.message(F.photo)
async def handle_payment_screenshot(message: Message):
    """
    User sends a KBZPay/WavePay screenshot after tapping "ငွေလွှဲပြီးပါပြီ" in the
    Web App. We attach it to their most recent pending topup and notify admins.
    """
    pending = [t for t in db.list_pending_topups() if t["telegram_id"] == message.from_user.id]
    if not pending:
        await message.answer("လက်ရှိ ငွေဖြည့်ခွင့်တောင်းထားခြင်း မရှိသေးပါ။ Shop ထဲက 'ငွေဖြည့်ရန်' ကို အရင်နှိပ်ပါ။")
        return

    topup = pending[-1]
    file_id = message.photo[-1].file_id
    db.attach_topup_proof(topup["id"], file_id)

    await message.answer("✅ ပြေစာ ရရှိပါပြီ။ Admin စစ်ဆေးပြီးရင် Wallet ထဲ ငွေဝင်ပါမယ်။")

    for admin_id in config.ADMIN_IDS:
        try:
            kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Approve", callback_data=f"topup_approve:{topup['id']}"),
                InlineKeyboardButton(text="❌ Reject", callback_data=f"topup_reject:{topup['id']}"),
            ]])
            await bot.send_photo(
                admin_id,
                file_id,
                caption=(
                    f"🧾 Top-up #{topup['id']}\n"
                    f"User: {message.from_user.id} (@{message.from_user.username})\n"
                    f"Amount: {topup['amount_mmk']:,} Ks\n"
                    f"Method: {topup['method']}"
                ),
                reply_markup=kb,
            )
        except Exception as e:
            log.warning(f"Could not notify admin {admin_id}: {e}")


@dp.callback_query(F.data.startswith("topup_approve:"))
async def cb_topup_approve(callback):
    if callback.from_user.id not in config.ADMIN_IDS:
        return await callback.answer("Admin only.", show_alert=True)
    topup_id = int(callback.data.split(":")[1])
    topup = db.get_topup(topup_id)
    if not topup or topup["status"] != "pending":
        return await callback.answer("Already handled.", show_alert=True)

    db.set_topup_status(topup_id, "approved", callback.from_user.id)
    db.adjust_balance(topup["telegram_id"], topup["amount_mmk"])

    await callback.message.edit_caption(caption=callback.message.caption + "\n\n✅ APPROVED")
    await bot.send_message(topup["telegram_id"], f"✅ ငွေဖြည့်ခြင်း အတည်ပြုပြီးပါပြီ: +{topup['amount_mmk']:,} Ks")
    await callback.answer("Approved")


@dp.callback_query(F.data.startswith("topup_reject:"))
async def cb_topup_reject(callback):
    if callback.from_user.id not in config.ADMIN_IDS:
        return await callback.answer("Admin only.", show_alert=True)
    topup_id = int(callback.data.split(":")[1])
    topup = db.get_topup(topup_id)
    if not topup or topup["status"] != "pending":
        return await callback.answer("Already handled.", show_alert=True)

    db.set_topup_status(topup_id, "rejected", callback.from_user.id)
    await callback.message.edit_caption(caption=callback.message.caption + "\n\n❌ REJECTED")
    await bot.send_message(topup["telegram_id"], "❌ ငွေဖြည့်ခြင်း အတည်မပြုနိုင်ပါ။ ပြေစာကို ပြန်စစ်ပြီး Admin ကို ဆက်သွယ်ပါ။")
    await callback.answer("Rejected")



import re
import asyncio

async def deliver_via_fragment_api(order: dict):
    """
    Delivers Stars/Premium via fragment-api.space (no API key — uses wallet seed).
    Docs: https://fragment-api.space
    """
    if not config.FRAGMENT_WALLET_SEED:
        return False, "FRAGMENT_WALLET_SEED ကို Render Environment Variables ထဲ ထားပါ"

    match = re.search(r"\d+", order["detail"])
    if not match:
        return False, "Order detail ထဲက ဂဏန်း မတွေ့ပါ"
    number = int(match.group())

    username = order["target_username"].lstrip("@")

    async with aiohttp.ClientSession() as session:
        if order["order_type"] == "stars":
            payload = {
                "username": f"@{username}",
                "amount": number,
                "seed": config.FRAGMENT_WALLET_SEED,
                "payment_method": "ton",
            }
            async with session.post(f"{config.FRAGMENT_API_BASE}/api/v1/stars/buy", json=payload, timeout=30) as resp:
                data = await resp.json()
                if resp.status not in (200, 202):
                    return False, data.get("error", f"Request failed (status {resp.status})")
                request_id = data.get("request_id")

            for _ in range(20):
                await asyncio.sleep(3)
                async with session.get(f"{config.FRAGMENT_API_BASE}/api/v1/queue/{request_id}") as poll_resp:
                    poll_data = await poll_resp.json()
                    status = poll_data.get("status")
                    if status == "success":
                        return True, "delivered"
                    if status == "failed":
                        return False, poll_data.get("error", "Delivery failed")
            return False, "Timeout — queue ထဲမှာ ကြာနေပါသေးတယ်၊ /pending ကနေ ပြန်စစ်ပါ"

        else:
            payload = {
                "username": f"@{username}",
                "duration": number,
                "seed": config.FRAGMENT_WALLET_SEED,
                "payment_method": "ton",
            }
            async with session.post(f"{config.FRAGMENT_API_BASE}/api/v1/premium/buy", json=payload, timeout=60) as resp:
                data = await resp.json()
                if resp.status == 200 and data.get("success"):
                    return True, "delivered"
                return False, data.get("error", f"Request failed (status {resp.status})")


@dp.callback_query(F.data.startswith("order_approve:"))
async def cb_order_approve(callback):
    if callback.from_user.id not in config.ADMIN_IDS:
        return await callback.answer("Admin only.", show_alert=True)
    order_id = int(callback.data.split(":")[1])
    order = db.get_order(order_id)
    if not order or order["status"] != "pending":
        return await callback.answer("Already handled.", show_alert=True)

    await callback.answer("Processing...")
    success, message = await deliver_via_fragment_api(order)

    if success:
        db.set_order_status(order_id, "fulfilled", callback.from_user.id)
        await callback.message.edit_text(callback.message.text + "\n\n✅ APPROVED & DELIVERED")
        await bot.send_message(
            order["telegram_id"],
            f"🎉 Order #{order_id} ({order['detail']}) ပို့ပေးပြီးပါပြီ! Telegram ကို စစ်ကြည့်ပါ။",
        )
    else:
        await callback.answer(f"API failed: {message}", show_alert=True)
        await bot.send_message(
            callback.from_user.id,
            f"⚠️ Order #{order_id} auto-deliver မအောင်မြင်ပါ: {message}\n"
            f"Manual fulfill: fragment.com ကနေ ကိုယ်တိုင်ဝယ်ပြီး /fulfill {order_id} ခေါ်ပါ",
        )


@dp.callback_query(F.data.startswith("order_reject:"))
async def cb_order_reject(callback):
    if callback.from_user.id not in config.ADMIN_IDS:
        return await callback.answer("Admin only.", show_alert=True)
    order_id = int(callback.data.split(":")[1])
    order = db.get_order(order_id)
    if not order or order["status"] != "pending":
        return await callback.answer("Already handled.", show_alert=True)

    db.adjust_balance(order["telegram_id"], order["price_mmk"])
    db.set_order_status(order_id, "rejected", callback.from_user.id)
    await callback.message.edit_text(callback.message.text + "\n\n❌ REJECTED (refunded)")
    await bot.send_message(
        order["telegram_id"],
        f"❌ Order #{order_id} ({order['detail']}) ကို Admin မှ လက်မခံနိုင်ပါ — "
        f"{order['price_mmk']:,} Ks ကို Wallet ထဲ ပြန်ထည့်ပေးလိုက်ပါပြီ။",
    )
    await callback.answer("Rejected & refunded")
@dp.message(Command("fulfill"))
async def cmd_fulfill(message: Message, command: CommandObject):
    """Admin marks a Stars/Premium order as delivered after buying it manually on fragment.com"""
    if message.from_user.id not in config.ADMIN_IDS:
        return
    if not command.args:
        return await message.answer("Usage: /fulfill <order_id>")
    order = db.get_order(int(command.args.strip()))
    if not order:
        return await message.answer("Order not found.")
    if order["status"] != "pending":
        return await message.answer(f"Order already {order['status']}.")

    db.set_order_status(order["id"], "fulfilled", message.from_user.id)
    await bot.send_message(
        order["telegram_id"],
        f"🎉 Order #{order['id']} ({order['detail']}) ပို့ပေးပြီးပါပြီ! Telegram ကို စစ်ကြည့်ပါ။",
    )
    await message.answer(f"Order #{order['id']} marked fulfilled.")


@dp.message(Command("pending"))
async def cmd_pending(message: Message):
    if message.from_user.id not in config.ADMIN_IDS:
        return
    topups = db.list_pending_topups()
    orders = db.list_pending_orders()

    topup_lines = [
        f"  #{t['id']} — {t['telegram_id']} — {t['amount_mmk']:,} Ks ({t['method']})" for t in topups
    ] or ["  (none)"]
    order_lines = [
        f"  #{o['id']} — {o['telegram_id']} — {o['detail']} — {o['price_mmk']:,} Ks" for o in orders
    ] or ["  (none)"]

    lines = ["📋 Pending topups:"] + topup_lines + ["", "📦 Pending orders:"] + order_lines
    await message.answer("\n".join(lines))


# ---------------------------------------------------------------------------
# REST API for the Web App (validated via initData, not a plain user id)
# ---------------------------------------------------------------------------

def _auth_or_none(request: web.Request):
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    return validate_init_data(init_data)


async def api_me(request: web.Request):
    user = _auth_or_none(request)
    if not user:
        return web.json_response({"error": "invalid init data"}, status=401)
    db.get_or_create_user(user["id"], user.get("username"))
    balance = db.get_balance(user["id"])
    return web.json_response({"telegram_id": user["id"], "username": user.get("username"), "balance_mmk": balance})


async def api_history(request: web.Request):
    user = _auth_or_none(request)
    if not user:
        return web.json_response({"error": "invalid init data"}, status=401)
    return web.json_response(db.list_user_history(user["id"]))


async def api_topup_request(request: web.Request):
    user = _auth_or_none(request)
    if not user:
        return web.json_response({"error": "invalid init data"}, status=401)
    body = await request.json()
    amount = int(body.get("amount_mmk", 0))
    method = body.get("method", "")
    if amount <= 0 or method not in config.PAYMENT_ACCOUNTS:
        return web.json_response({"error": "invalid request"}, status=400)

    db.get_or_create_user(user["id"], user.get("username"))
    topup_id = db.create_topup(user["id"], amount, method)

    account = config.PAYMENT_ACCOUNTS[method]
    await bot.send_message(
        user["id"],
        f"🧾 Top-up #{topup_id} — {amount:,} Ks ({account['label']})\n\n"
        f"👉 {account['label']} — {account['number']} ({account['name']}) ကို ငွေလွှဲပါ။\n"
        f"လွှဲပြီးရင် ပြေစာ Screenshot ကို ဒီ chat ထဲ ပို့ပေးပါ — Admin အတည်ပြုပြီးရင် Wallet ထဲ ငွေဝင်ပါမယ်။",
    )
    return web.json_response({"topup_id": topup_id, "status": "awaiting_proof"})


async def api_buy(request: web.Request):
    user = _auth_or_none(request)
    if not user:
        return web.json_response({"error": "invalid init data"}, status=401)
    body = await request.json()
    order_type = body.get("type")  # 'stars' or 'premium'
    target_username = (body.get("target_username") or "").lstrip("@").strip()

    if order_type == "stars":
        idx = int(body.get("index", -1))
        if not (0 <= idx < len(config.STAR_PACKAGES)):
            return web.json_response({"error": "invalid package"}, status=400)
        pkg = config.STAR_PACKAGES[idx]
        detail, price = f"{pkg['amount']} Stars", pkg["price"]
    elif order_type == "premium":
        idx = int(body.get("index", -1))
        if not (0 <= idx < len(config.PREMIUM_PLANS)):
            return web.json_response({"error": "invalid plan"}, status=400)
        plan = config.PREMIUM_PLANS[idx]
        detail, price = plan["label"], plan["price"]
    else:
        return web.json_response({"error": "invalid type"}, status=400)

    if not target_username:
        return web.json_response({"error": "target_username required"}, status=400)

    balance = db.get_balance(user["id"])
    if balance < price:
        return web.json_response({"error": "insufficient_balance", "balance_mmk": balance}, status=402)

    db.adjust_balance(user["id"], -price)
    order_id = db.create_order(user["id"], order_type, detail, price, target_username)

    order_kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Approve & Deliver", callback_data=f"order_approve:{order_id}"),
        InlineKeyboardButton(text="❌ Reject & Refund", callback_data=f"order_reject:{order_id}"),
    ]])
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🆕 Order #{order_id}\n{detail} → @{target_username}\n"
                f"Buyer: {user['id']} (@{user.get('username')})\n"
                f"Price: {price:,} Ks",
                reply_markup=order_kb,
            )
        except Exception as e:
            log.warning(f"Could not notify admin {admin_id}: {e}")

    return web.json_response({"order_id": order_id, "status": "pending", "new_balance_mmk": balance - price})


# ---------------------------------------------------------------------------
# App wiring
# ---------------------------------------------------------------------------

async def on_webhook(request: web.Request):
    from aiogram.types import Update
    data = await request.json()
    await dp.feed_update(bot, Update(**data))
    return web.Response()


def create_app():
    app = web.Application()
    app.router.add_get("/api/me", api_me)
    app.router.add_get("/api/history", api_history)
    app.router.add_post("/api/topup/request", api_topup_request)
    app.router.add_post("/api/buy", api_buy)
    app.router.add_post(config.WEBHOOK_PATH, on_webhook)
    app.router.add_static("/webapp/", path="webapp", name="webapp")
    return app


async def run_polling():
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--polling", action="store_true", help="Run bot with polling instead of webhook")
    args = parser.parse_args()

    if args.polling:
        import asyncio
        asyncio.run(run_polling())
    else:
        app = create_app()

        async def set_webhook(app):
            await bot.set_webhook(config.WEBHOOK_HOST + config.WEBHOOK_PATH)

        app.on_startup.append(set_webhook)
        web.run_app(app, host=config.WEB_SERVER_HOST, port=config.WEB_SERVER_PORT)
