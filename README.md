<div align="center">
  <h1>🚀 Telegram Message Forwarder</h1>
  <p><i>A powerful, real-time Telegram message router with interactive bot controls, database persistence, and dual-state architecture.</i></p>
  

  [![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
  [![Python](https://img.shields.io/badge/Python-3.12%2B-blueviolet)](https://www.python.org/)
  [![Telethon](https://img.shields.io/badge/Powered%20By-Telethon-orange)](https://github.com/LonamiWebs/Telethon)
</div>

---

## ✨ Key Features
- **Instant Forwarding**: Listens to source chats and forwards messages to targets with zero delay.
- **Topics Support**: Fully supports Telegram forum topics routing natively.
- **Dual Architecture**: Use a **Bot Access Token** for stability, and a **User Account Profile** to fetch historical missed messages!
- **Interactive UI**: Change configurations, reboot, and pull logs using inline Telegram Bot menus.
- **Cloud Configurations**: Upload `.env` or `rules.txt` straight to the bot, parsing directly to your MongoDB securely.
- **In-App Login**: Generate User String Sessions without ever touching the console via `/sessiongen`.

---

## ⚡ Quick Start

### 1. Get your Telegram API Credentials
| Requirement | Where to get it |
|-------------|-----------------|
| **`API_ID` & `API_HASH`** | [my.telegram.org](https://my.telegram.org/) → **API development tools** |
| **`BOT_TOKEN`** *(optional)* | [@BotFather](https://t.me/BotFather) on Telegram |
| **Chat IDs** | [@userinfobot](https://t.me/userinfobot) or [@get_id_bot](https://t.me/get_id_bot) |

### 2. Clone & Install
```bash
git clone https://github.com/Zan-getsu/TGForwarder.git
cd TGForwarder
pip install -r requirements.txt
cp .env.example .env
```

### 3. Configure your `.env`
Edit `.env` with your values (or upload a `.env` straight to the bot later if using MongoDB!):
```env
API_ID=12345678
API_HASH=abcdef1234567890abcdef1234567890
BOT_TOKEN=123456:ABC-DEF

SOURCE_1=-1001111111111
TARGET_1=-1002222222222
```

### 4. Run the Script
```bash
python telegram_forwarder.py
```
*Your forwarder is now live and routing messages!*

---

## ⚙️ Interactive Bot & MongoDB Panel

By adding a **`DATABASE_URL`** (MongoDB Connection String) to your `.env` file, the bot unlocks powerful, interactive features allowing you to manage the script directly from Telegram!

- **Interactive Settings (`/bsetting`)**: Send `/bsetting` to the bot to open an inline keyboard menu. Toggle `Dual Mode`, `Catch-up Sync`, and `Signatures` directly from your chat!
- **Dynamic File Uploads**: Upload a **`rules.txt`** file listing your `SOURCE_N=...` and `TARGET_N=...` routing rules privately to the bot. It will securely parse it, wipe old routing rules, and ingest the new ones straight into MongoDB! You can also upload `.env` files to override the `API_ID`.
- **In-App Authentication (`/sessiongen`)**: Securely exchange your Phone Number, OTP, and 2FA password over an interactive Telegram conversation to instantly store a highly secure "User Session" directly into your database.
- **Remote Process Control**: Use `/restart` to safely restart the python application remotely, or `/log` to receive the bot's `telegram_forwarder.log` file.

---

## 🔀 Configuring Forwarding Rules

### The `rules.txt` or `.env` Format (Recommended)
Set `SOURCE_N` and `TARGET_N` pairs. You can define these in your `.env` file or write them in a `rules.txt` file and upload it to the bot over Telegram!

```env
# Basic one-to-one mapping
SOURCE_1=-1001111111111
TARGET_1=-1002222222222

# Forum Topics (Source Topic 5 → Target Topic 10)
SOURCE_2=-1001111111111/5
TARGET_2=-1003333333333/10

# One-to-Many Routing
SOURCE_3=-1004444444444
TARGET_3=-1005555555555,-1006666666666
```

### Inline Commands
You can also update rules instantly using the bot via:
`/setrules -100111:-100222, -100333:-100444`

---

## 🤖 Account Execution Modes

| Feature | User Mode | Bot Mode | Dual Mode |
|---|-----------|----------|----------|
| **Setup** | Leave `BOT_TOKEN` empty | Set `BOT_TOKEN` | Set `BOT_TOKEN` + User Session + `DUAL_MODE=true` |
| **Authentication** | `/sessiongen` or Terminal | Instant API Token | API Token + User Session |
| **Live Forwarding** | ✅ User account | ✅ Bot | ✅ Bot |
| **History Catch-up Sync** | ✅ Supported | ❌ API Denied | ✅ User account fetches missing history |
| **Monitored Chats** | Any chat you're in | Chats bot is invited to | Bot chats (Live) + User chats (Sync) |

### 🔄 Catch-up Sync Details
*(Only supported in User and Dual modes)*
If the script goes offline, User accounts can catch up on missed messages. 
1. Set `SYNC_MISSED_MESSAGES=true` in `.env` (or via `/bsetting`).
2. The bot tracks the last forwarded message ID.
3. On startup, it fetches **all messages newer than that ID** and forwards them chronologically *before* it begins listening live!

---

## 🐳 Docker Deployment

The cleanest way to run the forwarder 24/7 is via Docker Compose:

```bash
docker compose up -d        # build & run in background
docker compose logs -f      # view live terminal logs
docker compose down         # shutdown
```

**Authenticating User Sessions in Docker:**
1. Text your bot **`/sessiongen`** on Telegram to authorize. (*Easiest*)
2. Or use the terminal script: `docker compose run forwarder python3 generate_session.py`
3. Or supply a raw `SESSION_STRING` in your `.env`.

---

## 📌 Finding Chat and Topic IDs

- **Private Users**: Positive number (`123456789`)
- **Groups/Channels**: Starts with `-100` (`-1001234567890`)
- **Find IDs**: Forward a message to [@userinfobot](https://t.me/userinfobot) or [@RawDataBot](https://t.me/RawDataBot).
- **Topic IDs**: Right-click a message in a topic -> Copy Link -> The middle number is the Topic ID (`t.me/c/CHANNEL_ID/TOPIC_ID/MSG_ID`). General topics are always ID `1`.

---

## 💬 BotFather Menu Settings Template

To easily configure your bot's command menu layout, go to [@BotFather](https://t.me/BotFather), send `/setcommands`, select your bot, and copy/paste this block:

```text
status - To check Bot Status and Uptime. [ADMIN]
log - To get the bot's log file. [ADMIN]
restart - To restart the bot process safely. [ADMIN]
bsetting - To open the bot settings menu. [ADMIN]
setrules - To update live forwarding rules. [ADMIN]
sessiongen - To interactively generate a user session. [ADMIN]
```

---

## ⚠️ Troubleshooting & Notes

- **`Missing API_ID`**: Double check your `.env` file or MongoDB database parameters.
- **`Rate Limited`**: The script handles Telegram flood waits automatically. Do not panic if the script pauses briefly.
- **No Forward Header**: Messages sent directly to a *specific topic* cannot use Telegram's native `forward_messages` API, so they are cleanly cloned instead, omitting the "Forwarded from..." header.
- **`Error getting entity info`**: Ensure your bot (or user account) is actually a member of the chat ID configured!

<br>

<div align="center">
  <i>This tool is for educational and personal use. Please respect Telegram's Terms of Service regarding user privacy.</i><br>
  <a href="./LICENSE">GNU General Public License v3.0</a>
</div>
