# Telegram Forwarder

Real-time Telegram message forwarder — listens to source chats and instantly forwards to one or more targets. Supports forum topics, multiple routing patterns, and both bot & user accounts.

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
BOT_TOKEN=                # leave empty for user-account mode
FORWARDING_RULES=-1001111111111:-1002222222222
```

### 4. Run

```bash
python telegram_forwarder.py
```

That's it. The forwarder is now listening and will forward every new message from source → target.

> **First run (user mode only):** You'll be prompted for your phone number, verification code, and 2FA password if enabled. A session file is saved so you won't need to re-authenticate.

---

## � Docker Deployment

### Using Docker Compose (recommended)

```bash
# 1. Configure your .env file
cp .env.example .env
# edit .env with your values

# 2. Build and run
docker compose up -d

# View logs
docker compose logs -f

# Stop
docker compose down
```

Session files are persisted in the `./sessions/` directory so authentication survives container restarts.

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

### CLI options with Docker

```bash
# Remove forward signature
docker compose run --rm forwarder -r

# Quiet mode
docker compose run --rm forwarder -q
```

> **First run (user mode):** You must run interactively the first time to authenticate: `docker compose run forwarder`. After the session is saved, restart with `docker compose up -d`.

---

## �📋 Environment Variables

| Variable | Required | Description |
|----------|:--------:|-------------|
| `API_ID` | ✅ | Telegram API ID from [my.telegram.org](https://my.telegram.org) |
| `API_HASH` | ✅ | Telegram API Hash from [my.telegram.org](https://my.telegram.org) |
| `BOT_TOKEN` | ❌ | Bot token from [@BotFather](https://t.me/BotFather). Leave empty for user-account mode |
| `FORWARDING_RULES` | ✅* | Forwarding rules (see syntax below) |
| `SOURCE_ID` | ✅* | Legacy: single source chat ID |
| `TARGET_ID` | ✅* | Legacy: single target chat ID |

> *\* Provide either `FORWARDING_RULES` **or** `SOURCE_ID`+`TARGET_ID`*

---

## 🔀 Forwarding Rules

### Syntax

```
source_id[/topic] : target_id[/topic] : target_id[/topic] , next_rule...
```

- **`:`** separates source from targets (first part = source, rest = targets)
- **`,`** separates independent rules
- **`/topic_id`** optional — targets a specific forum topic

### Examples

```env
# ┌─────────────────────── One-to-one ───────────────────────┐
FORWARDING_RULES=-1001111111111:-1002222222222

# ┌─────────────────────── One-to-many ──────────────────────┐
# Source broadcasts to 3 targets
FORWARDING_RULES=-1001111111111:-1002222222222:-1003333333333:-1004444444444

# ┌─────────────────────── Many-to-one ──────────────────────┐
# 3 sources aggregate into 1 target
FORWARDING_RULES=-1001111111111:-1004444444444,-1002222222222:-1004444444444,-1003333333333:-1004444444444

# ┌─────────────────────── Complex mix ──────────────────────┐
FORWARDING_RULES=-1001111111111:-1002222222222,-1003333333333:-1004444444444:-1005555555555
```

### Forum Topic Forwarding

Append `/topic_id` to any chat ID to forward from/to a specific topic:

```env
# Topic 5 in source → Topic 10 in target
FORWARDING_RULES=-1001111111111/5:-1002222222222/10

# Topic 5 → multiple target topics
FORWARDING_RULES=-1001111111111/5:-1002222222222/10:-1003333333333/15

# All topics (wildcard) → one specific target topic
FORWARDING_RULES=-1001111111111:-1002222222222/10

# Specific source topic → target General chat (no /topic)
FORWARDING_RULES=-1001111111111/5:-1002222222222
```

> **Priority:** If both a specific topic rule **and** a wildcard rule exist for the same source chat, the specific topic rule wins.

#### Finding Topic IDs

- **From a message link:** Right-click any message in a topic → Copy Link → URL format: `https://t.me/c/CHANNEL_ID/TOPIC_ID/MESSAGE_ID`
- **General topic:** Always ID `1`
- **Bot inspector:** Forward a message to [@raw_info_bot](https://t.me/raw_info_bot)

---

## 🔧 Command Line Options

```bash
python telegram_forwarder.py [OPTIONS]
```

| Flag | Short | What it does |
|------|:-----:|--------------|
| `--remove-forward-signature` | `-r` | Sends as a new message instead of forwarding (removes "Forwarded from..." header) |
| `--disable-console-log` | `-q` | Suppresses console output, logs only to `telegram_forwarder.log` |

```bash
# Examples
python telegram_forwarder.py              # default: forward with signature + console logs
python telegram_forwarder.py -r           # clean copy, no "Forwarded from..."
python telegram_forwarder.py -q           # silent console, file-only logging
python telegram_forwarder.py -r -q        # both options combined
```

---

## 🤖 Bot Mode vs User Mode

| | User Mode | Bot Mode |
|---|-----------|----------|
| **Setup** | Leave `BOT_TOKEN` empty | Set `BOT_TOKEN` in `.env` |
| **Auth** | Phone + code + optional 2FA | Instant (token-based) |
| **Access** | Any chat you're a member of | Only chats where the bot is added |
| **Permissions** | Your account's permissions | Bot must have read + send permissions |
| **Session file** | `user_session.session` | `bot_session.session` |

---

## 🔍 Finding Chat IDs

| Chat Type | ID Format | Example |
|-----------|-----------|---------|
| Private user | Positive number | `123456789` |
| Group / Supergroup | `-100` + ID | `-1001234567890` |
| Channel | `-100` + ID | `-1001234567890` |

**Tools to get IDs:**
- Forward any message to [@userinfobot](https://t.me/userinfobot) or [@get_id_bot](https://t.me/get_id_bot)
- For groups: add [@RawDataBot](https://t.me/RawDataBot) temporarily and check the chat ID it reports

---

## 📝 Logging

| Mode | Console | File (`telegram_forwarder.log`) |
|------|:-------:|:-------------------------------:|
| Default | ✅ | ✅ |
| Quiet (`-q`) | ❌ | ✅ |

Logs include: connection status, forwarding events, sender/source/target details, errors, and rate-limit waits.

---

## ⚠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| `Missing API_ID or API_HASH` | Check `.env` file has valid credentials |
| `No forwarding rules configured` | Set either `FORWARDING_RULES` or `SOURCE_ID`+`TARGET_ID` |
| `Error getting entity info` | Account/bot doesn't have access to that chat |
| Rate limited frequently | Reduce the number of high-volume sources |
| Bot not receiving messages | Ensure bot is added to BOTH source and target chats with permissions |
| Messages not arriving in topic | Verify topic ID is correct (copy message link to check) |

---

## 📌 Important Notes

- **Rate limits** are handled automatically — the script waits and retries
- **Session files** are stored in `sessions/` directory — don't delete them unless you want to re-login
- **Topic forwarding caveat:** When forwarding to a specific topic, messages are sent as new messages (not forwarded) because Telegram's API doesn't support placing forwarded messages into topics. The "Forwarded from..." header won't appear in this case
- **Privacy:** Be mindful of Telegram's Terms of Service and privacy laws

---

## License

[GNU General Public License v3.0](./LICENSE)

## Disclaimer

This tool is for educational and personal use. Please respect Telegram's Terms of Service and applicable laws regarding message forwarding and privacy.
