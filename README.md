# Telegram Stars & Premium Wallet Bot — Starter Kit

MMK Wallet အခြေခံ Bot + Web App။ User က ငွေဖြည့်ထားပြီး Stars/Premium ကို အချိန်မရွေး ဝယ်ယူနိုင်ပါတယ်။

## ဖွဲ့စည်းပုံ (Architecture)

```
User (Telegram)
   │
   ├─ /start → Bot က Web App button ပို့
   │
   ▼
Web App (webapp/index.html)
   │  fetch() + initData (Telegram ကထုတ်ပေးတဲ့ signed data)
   ▼
REST API (server.py: /api/me, /api/history, /api/topup/request, /api/buy)
   │
   ▼
SQLite (wallet.db) — users, topups, orders
   │
   ▼
Admin (Telegram chat) → /pending, /fulfill <id>, Approve/Reject buttons
```

## လိုအပ်သော ဖိုင်များ

- `config.py` — Bot token, admin ID list, ငွေလွှဲရမည့် account, Star/Premium စျေးနှုန်း
- `database.py` — SQLite wrapper (users, topups, orders)
- `webapp_auth.py` — Telegram WebApp `initData` ကို HMAC နဲ့ စစ်ဆေးခြင်း (security အတွက် အရေးကြီးဆုံးအပိုင်း)
- `server.py` — Bot handlers + REST API (aiohttp)
- `webapp/index.html` — Wallet UI (Stars/Premium ဝယ်ရန်၊ ငွေဖြည့်ရန်၊ history)

## စတင်ရန် (Setup)

1. **Bot Token ရယူပါ**: [@BotFather](https://t.me/BotFather) မှာ `/newbot` → Token ကို `config.py` ထဲ (သို့) `BOT_TOKEN` env var ထဲ ထည့်ပါ

2. **Dependencies ထည့်ပါ**:
   ```bash
   pip install -r requirements.txt
   ```

3. **`config.py` ကို ပြင်ဆင်ပါ**:
   - `ADMIN_IDS` — သင့် Telegram user ID (Admin bot ကနေ ID သိနိုင်ပါတယ်၊ e.g. @userinfobot)
   - `PAYMENT_ACCOUNTS` — KBZPay/WavePay/AYAPay account နံပါတ်များ
   - `WEBAPP_URL` — Web App ကို host လုပ်ထားတဲ့ HTTPS URL (Telegram က HTTPS ကိုသာ လက်ခံပါတယ်)

4. **Web App ကို host လုပ်ပါ**: `webapp/index.html` ကို HTTPS static hosting (Cloudflare Pages, Netlify, Vercel, VPS+nginx) မှာ တင်ပါ။ `server.py` ကလည်း `/webapp/` ကနေ serve ပေးနိုင်ပါတယ် (webhook mode မှာ) — domain တစ်ခုတည်းသုံးရင် ပိုလွယ်ပါတယ်။

5. **BotFather မှာ Menu Button သတ်မှတ်ပါ**:
   `/mybots` → Bot ရွေး → Bot Settings → Menu Button → Web App URL ထည့်ပါ

6. **Bot ကို run ပါ**:
   ```bash
   # Testing (polling — HTTPS domain မလိုအပ်ဘူး)
   python server.py --polling

   # Production (webhook — HTTPS domain လိုအပ်တယ်)
   python server.py
   ```

## Fragment Fulfillment — အရေးကြီးအချက်

Fragment.com မှာ Stars/Premium ကို programmatically ဝယ်ဖို့ **official public API မရှိသေးပါ**။ ဒီ starter kit က အဲဒီအတွက် manual-approval workflow တစ်ခု ထည့်ပေးထားပါတယ် (Stars-resell bot အများစု အလုပ်လုပ်နည်းနဲ့ တူတူပါပဲ):

1. User က wallet ကနေ Stars/Premium order တင်တယ် → balance ချက်ချင်း နုတ်ယူတယ်
2. Admin group/chat ကို order အသစ် notification ရောက်တယ်
3. Admin က fragment.com ကို ကိုယ်တိုင်ဝင်ပြီး Stars/Premium ကို target username ကို လက်ရှိနည်းအတိုင်း ဝယ်ပေးတယ်
4. Admin က `/fulfill <order_id>` ခေါ်တယ် → User ကို "ပို့ပြီးပါပြီ" notification ရောက်တယ်

**Scale တက်လာရင်**: order အရေအတွက်များလာရင် admin တစ်ယောက်တည်း manual လုပ်ရတာ မလုံလောက်တော့ရင် — (a) Fragment ကနေ officially ထုတ်ပေးမယ့် API ကို စောင့်ကြည့်ဖို့၊ (b) Fragment ရဲ့ TON-based marketplace ကို reseller partner အဖြစ် တရားဝင်ချိတ်ဆက်ထားတဲ့ 3rd-party payment/reseller service တွေနဲ့ စကားပြောဖို့ လိုအပ်ပါလိမ့်မယ်။ Fragment ကိုယ်တိုင်ရဲ့ web session ကို scrape/automate လုပ်တာက ToS ချိုးဖောက်မှု ဖြစ်နိုင်ခြေရှိလို့ ဒီ starter kit ထဲ မထည့်ထားပါ။

## Security မှတ်ချက်များ

- `webapp_auth.py` ထဲက HMAC validation ကို **ဖယ်ရှားလို့ မရပါ** — Web App ကနေ ပို့တဲ့ telegram_id ကို တိုက်ရိုက် မယုံဘဲ၊ Telegram ထုတ်ပေးတဲ့ signed `initData` ကနေသာ user ကို အတည်ပြုပါ။
- Production မှာ SQLite အစား PostgreSQL သုံးဖို့ စဉ်းစားပါ (concurrent write များလာရင်)
- Admin command တွေ (`/fulfill`, `/pending`) ကို `ADMIN_IDS` list ထဲက user တွေသာ ခေါ်လို့ရအောင် စစ်ထားပါတယ်
- Payment screenshot များကို manual review မလုပ်ခင် balance မတိုးပါစေနဲ့ (ဒီ kit မှာ admin approve မှသာ balance တိုးအောင် ရေးထားပါတယ်)

## Testing လုပ်နည်း

```bash
python server.py --polling
```
ပြီးရင် bot ကို Telegram ထဲ `/start` ခေါ်ပြီး Web App button ကို tap လိုက်ပါ (Telegram Desktop/Mobile app ထဲကနေမှ Web App ပွင့်ပါလိမ့်မယ် — browser ထဲကနေ တိုက်ရိုက်ဖွင့်လို့ `initData` empty ဖြစ်နေပါလိမ့်မယ်)။
