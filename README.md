# Telegram Forwarder

Real-time Telegram message forwarder — listens to source chats and instantly forwards to one or more targets. Supports forum topics, mirror mode with auto-topic creation, and both bot & user accounts.

---

## ⚡ Quick Start (5 minutes)

### 1. Get your credentials

| What | Where |
|------|-------|
| `API_ID` + `API_HASH` | [my.telegram.org](https://my.telegram.org) → API development tools |
| `BOT_TOKEN` *(optional)* | [@BotFather](https://t.me/BotFather) on Telegram |
| Chat IDs | [@userinfobot](https://t.me/userinfobot) or [@get_id_bot](https://t.me/get_id_bot) |

### 2. Clone & install

```bash
git clone https://github.com/Zan-getsu/TGForwarder.git
cd TGForwarder
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
API_ID=12345678
API_HASH=abcdef1234567890abcdef1234567890
BOT_TOKEN=

SOURCE_1=-1001111111111
TARGET_1=-1002222222222
```

### 4. Run

```bash
python telegram_forwarder.py
```

That's it. The forwarder is now listening and will forward every new message from source → target.

> **First run (user mode only):** You'll be prompted for your phone number, verification code, and 2FA password if enabled. A session file is saved so you won't need to re-authenticate.

---

## 🐳 Docker Deployment

### Using Docker Compose (recommended)

```bash
cp .env.example .env
# edit .env with your values

docker compose up -d        # build & run
docker compose logs -f      # view logs
docker compose down          # stop
```

Session files are persisted in the `./sessions/` directory.

### Using Docker directly

```bash
docker build -t tg-forwarder .
docker run -d \
  --name tg-forwarder \
  --restart unless-stopped \
  --env-file .env \
  -v ./sessions:/app/sessions \
  tg-forwarder
```

### User Mode Authentication (for Docker)

**Option 1: Generate a session string (recommended)**

Run locally once to generate a session string:

```bash
python telegram_forwarder.py --generate-session
```

Follow the prompts (phone → code → 2FA), then copy the output string to your `.env`:

```env
SESSION_STRING=1BVtsOKwL... (paste the full string here)
```

Now Docker can start without interactive input!

**Option 2: Interactive container (first run only)**

```bash
docker compose run forwarder
# Complete the phone/code/2FA prompts
# Then restart normally: docker compose up -d
```

---

## 📋 Environment Variables

| Variable | Required | Description |
|----------|:--------:|-------------|
| `API_ID` | ✅ | Telegram API ID |
| `API_HASH` | ✅ | Telegram API Hash |
| `BOT_TOKEN` | ❌ | Bot token (leave empty for user mode) |
| `SESSION_STRING` | ❌ | Session string for user mode (alternative to interactive auth) |
| `REMOVE_FORWARD_SIGNATURE` | ❌ | `true` = send clean copies without "Forwarded from..." header |
| `DISABLE_CONSOLE_LOG` | ❌ | `true` = log only to file, no console output |
| `SYNC_MISSED_MESSAGES` | ❌ | `true` = catch up on messages missed while bot was offline |


> CLI flags `-r` and `-q` still work and override the env vars.

---

## 🔀 Forwarding Rules

### Numbered Pairs (recommended)

The simplest way to configure forwarding. Set `SOURCE_N` and `TARGET_N` pairs:

```env
# Rule 1: one-to-one
SOURCE_1=-1001111111111
TARGET_1=-1002222222222

# Rule 2: with forum topics (source topic 5 → target topic 10)
SOURCE_2=-1001111111111/5
TARGET_2=-1003333333333/10

# Rule 3: one-to-many (comma-separated targets)
SOURCE_3=-1004444444444
TARGET_3=-1005555555555,-1006666666666

# Rule 4: topic to multiple target topics
SOURCE_4=-1001111111111/5
TARGET_4=-1002222222222/10,-1003333333333/15
```

### Compact Format (still supported)

```env
FORWARDING_RULES=-1001111111111:-1002222222222,-1003333333333:-1004444444444
```

Format: `source[/topic]:target1[/topic]:target2[/topic],...`

### Legacy Format (still supported)

```env
SOURCE_ID=-1001111111111
TARGET_ID=-1002222222222
```

---



## 🔄 Catch-up Sync (Missed Messages)

> ⚠️ **IMPORTANT:** This feature is **ONLY supported in User Mode**. Telegram strictly prevents Bot accounts from fetching chat history.

If the script goes offline, User accounts can catch up on missed messages:
1. Set `SYNC_MISSED_MESSAGES=true` in `.env`
2. The bot will save the ID of the last forwarded message to `sessions/sync_state.json`
3. On startup, it will fetch all messages newer than that ID and forward them chronologically *before* it begins listening live.

*Note: On its very first run, it will sync the entire history of the chat from the very beginning. Be aware that this may take time for large groups.*

---

## 🔍 Finding IDs

### Chat IDs

| Chat Type | Format | Example |
|-----------|--------|---------|
| Private user | Positive number | `123456789` |
| Group / Channel | `-100` + ID | `-1001234567890` |

**Tools:** [@userinfobot](https://t.me/userinfobot), [@get_id_bot](https://t.me/get_id_bot), [@RawDataBot](https://t.me/RawDataBot)

### Topic IDs

- **Message link:** Right-click message → Copy Link → `https://t.me/c/CHANNEL_ID/TOPIC_ID/MESSAGE_ID`
- **General topic:** Always ID `1`
- **Bot:** [@raw_info_bot](https://t.me/raw_info_bot)

---

## 🤖 Bot Mode vs User Mode

| Feature | User Mode | Bot Mode |
|---|-----------|----------|
| **Setup** | Leave `BOT_TOKEN` empty | Set `BOT_TOKEN` |
| **Auth** | Phone + code + optional 2FA (or use `SESSION_STRING`) | Instant |
| **History Sync** | ✅ Supported (`SYNC_MISSED_MESSAGES`) | ❌ Unusable (Telegram API refuses) |
| **Access** | Any chat you're in | Only chats where bot is added |
| **Session** | `sessions/user_session.session` or `SESSION_STRING` env | `sessions/bot_session.session` |

---

## 📝 Logging

| Mode | Console | File |
|------|:-------:|:----:|
| Default | ✅ | ✅ |
| `DISABLE_CONSOLE_LOG=true` | ❌ | ✅ |

---

## ⚠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| `Missing API_ID or API_HASH` | Check `.env` file |
| `No forwarding rules configured` | Set `SOURCE_N`/`TARGET_N` or `FORWARDING_RULES` |
| `Error getting entity info` | Account/bot doesn't have access to that chat |

| Rate limited | Script handles automatically; reduce volume if frequent |
| Messages not in topic | Verify topic ID (copy message link to check) |

---

## 📌 Important Notes

- **Rate limits** handled automatically
- **Session files** in `sessions/` — don't delete unless you want to re-login
- **Topic forwarding caveat:** Messages sent to a specific topic use `send_message` (not `forward_messages`), so the "Forwarded from..." header won't appear


---

## License

[GNU General Public License v3.0](./LICENSE)

## Disclaimer

This tool is for educational and personal use. Please respect Telegram's Terms of Service and applicable laws regarding message forwarding and privacy.
