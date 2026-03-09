import asyncio
import logging
import os
import re
import json
import argparse
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.errors import SessionPasswordNeededError, FloodWaitError
from telethon.tl.types import PeerUser, PeerChat, PeerChannel

# Load environment variables
load_dotenv()

def setup_logging(disable_console=False):
    """Configure logging based on console preference."""
    if disable_console:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[logging.FileHandler('telegram_forwarder.log')]
        )
    else:
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('telegram_forwarder.log')
            ]
        )

logger = logging.getLogger(__name__)


def _env_bool(key, default=False):
    """Read a boolean from environment variables."""
    val = os.getenv(key, '').strip().lower()
    if val in ('true', '1', 'yes'):
        return True
    if val in ('false', '0', 'no', ''):
        return default
    return default


class TelegramForwarder:
    def __init__(self, remove_forward_signature=None, disable_console_log=None):
        """Initialize the Telegram forwarder with environment variables."""
        self.api_id = os.getenv('API_ID')
        self.api_hash = os.getenv('API_HASH')
        self.bot_token = os.getenv('BOT_TOKEN', '').strip() or None
        self.session_string = os.getenv('SESSION_STRING', '').strip() or None

        # Options: env vars as defaults, CLI args override
        env_remove_sig = _env_bool('REMOVE_FORWARD_SIGNATURE')
        self.remove_forward_signature = remove_forward_signature if remove_forward_signature is not None else env_remove_sig


        # Sync settings
        self.sync_enabled = _env_bool('SYNC_MISSED_MESSAGES')
        self.state_file = 'sessions/sync_state.json'
        # State: {chat_id: last_message_id} -> global message ID per chat
        self.sync_state = {}

        # Validate required environment variables
        if not all([self.api_id, self.api_hash]):
            raise ValueError("Missing API_ID or API_HASH. Check your .env file.")

        # Parse forwarding configuration
        # forwarding_map: {(source_chat_id, source_topic_id|None): [(target_chat_id, target_topic_id|None), ...]}
        self.forwarding_map = {}

        self._parse_all_rules()

        if not self.forwarding_map:
            raise ValueError(
                "No forwarding rules configured. "
                "Set SOURCE_N/TARGET_N, FORWARDING_RULES, or SOURCE_ID/TARGET_ID."
            )

        # Extract unique source chat IDs for event registration
        source_from_rules = {src_chat for src_chat, _ in self.forwarding_map.keys()}
        self.source_chat_ids = list(source_from_rules)

        # Ensure session directory exists
        os.makedirs('sessions', exist_ok=True)

        # Load sync state if enabled
        if self.sync_enabled:
            self._load_state()

        # Initialize Telegram client
        if self.bot_token:
            self.client = TelegramClient('sessions/bot_session', self.api_id, self.api_hash)
            logger.info("Initialized in bot mode")
        elif self.session_string:
            self.client = TelegramClient('sessions/user_session', self.api_id, self.api_hash)
            logger.info("Initialized in user mode (session string)")
        else:
            self.client = TelegramClient('sessions/user_session', self.api_id, self.api_hash)
            logger.info("Initialized in user mode (interactive auth required)")

    # ─── Parsing helpers ───────────────────────────────────────

    @staticmethod
    def _parse_id_topic(part):
        """Parse 'chat_id/topic_id' or 'chat_id' into (chat_id, topic_id|None)."""
        part = part.strip()
        if '/' in part:
            chat_str, topic_str = part.split('/', 1)
            return (int(chat_str), int(topic_str))
        return (int(part), None)

    def _parse_all_rules(self):
        """Parse all forwarding configurations in priority order."""
        # 1. SOURCE_N / TARGET_N numbered pairs (highest priority)
        self._parse_numbered_pairs()

        # 3. FORWARDING_RULES compact format
        self._parse_forwarding_rules_compact()
        # 4. Legacy SOURCE_ID / TARGET_ID
        self._parse_legacy_single()

    def _parse_numbered_pairs(self):
        """Parse SOURCE_N / TARGET_N environment variable pairs."""
        n = 1
        while True:
            source_env = os.getenv(f'SOURCE_{n}')
            target_env = os.getenv(f'TARGET_{n}')
            if source_env is None and target_env is None:
                break
            if source_env and target_env:
                try:
                    source_key = self._parse_id_topic(source_env)
                    # TARGET_N can be comma-separated for one-to-many
                    target_list = [self._parse_id_topic(t) for t in target_env.split(',')]
                    if source_key in self.forwarding_map:
                        self.forwarding_map[source_key].extend(target_list)
                    else:
                        self.forwarding_map[source_key] = target_list
                    logger.info(f"Parsed SOURCE_{n}/TARGET_{n} rule")
                except ValueError as e:
                    raise ValueError(f"Error parsing SOURCE_{n}/TARGET_{n}: {e}")
            elif source_env or target_env:
                raise ValueError(f"SOURCE_{n} and TARGET_{n} must both be set (found only one).")
            n += 1


    def _parse_forwarding_rules_compact(self):
        """Parse FORWARDING_RULES compact format."""
        forwarding_rules = os.getenv('FORWARDING_RULES')
        if not forwarding_rules:
            return
        try:
            rules = forwarding_rules.split(',')
            for rule in rules:
                rule = rule.strip()
                if not rule:
                    continue
                parts = rule.split(':')
                if len(parts) < 2:
                    raise ValueError(f"Invalid forwarding rule format: {rule}")
                source_key = self._parse_id_topic(parts[0])
                target_list = [self._parse_id_topic(t) for t in parts[1:]]
                if source_key in self.forwarding_map:
                    self.forwarding_map[source_key].extend(target_list)
                else:
                    self.forwarding_map[source_key] = target_list
            logger.info(f"Parsed {len(self.forwarding_map)} FORWARDING_RULES")
        except ValueError as e:
            raise ValueError(f"Error parsing FORWARDING_RULES: {e}")

    def _parse_legacy_single(self):
        """Parse legacy SOURCE_ID / TARGET_ID single pair."""
        source_id = os.getenv('SOURCE_ID')
        target_id = os.getenv('TARGET_ID')
        if not source_id or not target_id:
            return
        # Only use legacy if no other rules were found
        if self.forwarding_map:
            return
        try:
            source_key = (int(source_id), None)
            target_val = (int(target_id), None)
            self.forwarding_map[source_key] = [target_val]
            logger.info("Using legacy single source/target configuration")
        except ValueError:
            raise ValueError("SOURCE_ID and TARGET_ID must be valid integers.")

    # ─── State Management (Sync Feature) ───────────────────────

    def _load_state(self):
        """Load the sync state from JSON file."""
        if not os.path.exists(self.state_file):
            self.sync_state = {}
            logger.info("No existing sync state found. Starting fresh.")
            return

        try:
            with open(self.state_file, 'r') as f:
                raw_state = json.load(f)
            
            self.sync_state = {}
            for key_str, last_id in raw_state.items():
                # Handle old format ("chat_id:topic_id") migration
                if ':' in key_str:
                    chat_str = key_str.split(':')[0]
                else:
                    chat_str = key_str
                
                chat_id = int(chat_str)
                # Keep the absolute highest message ID for this chat
                self.sync_state[chat_id] = max(self.sync_state.get(chat_id, 0), last_id)
                
            logger.info(f"Loaded sync state for {len(self.sync_state)} source chats")
        except Exception as e:
            logger.error(f"Error loading sync state: {e}")
            self.sync_state = {}

    def _save_state(self):
        """Save the sync state to JSON file."""
        if not self.sync_enabled:
            return
            
        try:
            # Convert tuple keys to strings: chat_id -> "chat_id"
            raw_state = {str(chat_id): last_id for chat_id, last_id in self.sync_state.items()}
            with open(self.state_file, 'w') as f:
                json.dump(raw_state, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving sync state: {e}")

    def _update_last_id(self, source_chat_id, message_id):
        """Update the last forwarded message ID and save state."""
        if not self.sync_enabled:
            return
        
        current_last = self.sync_state.get(source_chat_id, 0)
        
        # Only update if the new message is newer
        if message_id > current_last:
            self.sync_state[source_chat_id] = message_id
            self._save_state()

    # ─── Client & entity helpers ───────────────────────────────

    async def start_client(self):
        """Start the Telegram client and handle authentication."""
        if self.bot_token:
            await self.client.start(bot_token=self.bot_token)
        elif self.session_string:
            await self.client.start(session_string=self.session_string)
        else:
            await self.client.start()
            if not await self.client.is_user_authorized():
                phone = input("Enter your phone number: ")
                await self.client.send_code_request(phone)
                code = input("Enter the code you received: ")
                try:
                    await self.client.sign_in(phone, code)
                except SessionPasswordNeededError:
                    password = input("Enter your 2FA password: ")
                    await self.client.sign_in(password=password)

        logger.info("Client started successfully")

    async def get_entity_info(self, entity_id, topic_id=None):
        """Get information about an entity (user, chat, or channel), optionally with topic."""
        try:
            entity = await self.client.get_entity(entity_id)
            if hasattr(entity, 'title'):
                info = f"{entity.title} (ID: {entity_id})"
            elif hasattr(entity, 'first_name'):
                name = entity.first_name
                if hasattr(entity, 'last_name') and entity.last_name:
                    name += f" {entity.last_name}"
                info = f"{name} (ID: {entity_id})"
            else:
                info = f"Entity (ID: {entity_id})"
            if topic_id is not None:
                info += f" [Topic: {topic_id}]"
            return info
        except Exception as e:
            logger.error(f"Error getting entity info for {entity_id}: {e}")
            suffix = f" [Topic: {topic_id}]" if topic_id is not None else ""
            return f"Unknown Entity (ID: {entity_id}){suffix}"

    # ─── Topic helpers (for mirror mode) ───────────────────────

    def _get_message_topic_id(self, message):
        """Extract the forum topic ID from a message, or None if not in a topic."""
        reply_to = message.reply_to
        if reply_to is None:
            return None
        if getattr(reply_to, 'forum_topic', False):
            return reply_to.reply_to_top_id or reply_to.reply_to_msg_id
        return None


    # ─── Forwarding logic ──────────────────────────────────────

    def _find_targets(self, source_chat_id, msg_topic_id):
        """Find matching target list for a source chat + topic combination."""
        # Try exact match first
        targets = self.forwarding_map.get((source_chat_id, msg_topic_id))
        if targets:
            return targets
        # Fall back to wildcard (no topic filter)
        return self.forwarding_map.get((source_chat_id, None), [])

    async def _send_to_target(self, message, source_chat_id, target_chat, target_topic):
        """Send or forward a message to a specific target chat/topic."""
        target_info = await self.get_entity_info(target_chat, target_topic)

        if self.remove_forward_signature or target_topic:
            # Send as new message (required for topic placement)
            await self.client.send_message(
                entity=target_chat,
                message=message.message,
                file=message.media,
                parse_mode='html' if message.entities else None,
                reply_to=target_topic
            )
            if self.remove_forward_signature:
                logger.info(f"Sent message (no signature) to {target_info}")
            else:
                logger.info(f"Sent message to {target_info}")
        else:
            # Forward with "Forward from..." signature
            await self.client.forward_messages(
                entity=target_chat,
                messages=message.id,
                from_peer=source_chat_id
            )
            logger.info(f"Forwarded message to {target_info}")

    async def _process_message(self, message, source_chat_id, sender_id):
        """Process a single message: route it to targets and handle mirror mode."""
        msg_topic_id = self._get_message_topic_id(message)

        # ── Rule-based forwarding ──
        targets = self._find_targets(source_chat_id, msg_topic_id)
        if targets:
            source_info = await self.get_entity_info(source_chat_id, msg_topic_id)
            logger.info(f"Processing message {message.id} from {sender_id} in {source_info}")

            for target_chat, target_topic in targets:
                try:
                    await self._send_to_target(message, source_chat_id, target_chat, target_topic)
                except Exception as e:
                    target_info = await self.get_entity_info(target_chat, target_topic)
                    logger.error(f"Error forwarding to {target_info}: {e}")

    async def catch_up_missed_messages(self):
        """Fetch and process messages missed while the bot was offline."""
        if not self.sync_enabled:
            return
            
        if self.bot_token:
            logger.warning("Catch-up sync (SYNC_MISSED_MESSAGES) is not supported in Bot mode. Telegram restricts bots from fetching chat history. Skipping catch-up.")
            return

        logger.info("Starting catch-up sync for missed messages...")
        
        for source_chat_id in self.source_chat_ids:
            try:
                source_info = await self.get_entity_info(source_chat_id)
                last_id = self.sync_state.get(source_chat_id)
                
                if not last_id:
                    # First run: start from message ID 0 to pull ALL historical messages.
                    logger.info(f"First run for {source_info}: establishing base message ID 0 to sync all history.")
                    last_id = 0
                
                # Fetch newer messages in chronological order (reverse=True)
                logger.info(f"Catching up {source_info} starting from msg ID {last_id}")
                count = 0
                async for msg in self.client.iter_messages(source_chat_id, min_id=last_id, reverse=True):
                    # Strict protection against duplicate forwarding
                    if msg.id <= last_id:
                        continue
                        
                    sender_id = msg.sender_id if msg.sender_id else "Unknown"
                    await self._process_message(msg, source_chat_id, sender_id)
                    
                    # Track that we've seen this message ID, whether we forwarded it or ignored it
                    self._update_last_id(source_chat_id, msg.id)
                    count += 1
                    
                    # Small delay to prevent flood waits during mass catch-up
                    await asyncio.sleep(0.1)
                        
                if count > 0:
                    logger.info(f"Caught up with {count} missed messages in {source_info}")
                else:
                    logger.info(f"No missed messages in {source_info}")
                    
            except FloodWaitError as e:
                logger.warning(f"Rate limited during sync. Waiting {e.seconds} seconds...")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"Error catching up on {source_chat_id}: {e}")
                
        logger.info("Catch-up sync complete.")

    async def setup_forwarding(self):
        """Set up message forwarding from multiple sources to their respective targets."""
        # Log forwarding rules
        if self.forwarding_map:
            logger.info("Forwarding rules:")
            for (source_chat, source_topic), targets in self.forwarding_map.items():
                source_info = await self.get_entity_info(source_chat, source_topic)
                target_infos = []
                for target_chat, target_topic in targets:
                    target_info = await self.get_entity_info(target_chat, target_topic)
                    target_infos.append(target_info)
                logger.info(f"  {source_info} -> {', '.join(target_infos)}")


        @self.client.on(events.NewMessage(chats=self.source_chat_ids))
        async def forward_handler(event):
            """Handle new messages and forward them to configured targets."""
            try:
                message = event.message
                source_chat_id = event.chat_id
                sender_id = message.sender_id if message.sender_id else "Unknown"
                
                await self._process_message(message, source_chat_id, sender_id)
                
                # Track that we've seen this message ID via live events
                self._update_last_id(source_chat_id, message.id)

            except FloodWaitError as e:
                logger.warning(f"Rate limited. Waiting {e.seconds} seconds...")
                await asyncio.sleep(e.seconds)
            except Exception as e:
                logger.error(f"Error in forward handler: {e}")

        logger.info("Message forwarding handlers registered successfully")

    async def run(self):
        """Main method to run the forwarder."""
        try:
            await self.start_client()
            await self.setup_forwarding()
            
            # Catch up on any messages missed while offline
            await self.catch_up_missed_messages()

            logger.info("Telegram forwarder is now running. Press Ctrl+C to stop.")
            await self.client.run_until_disconnected()

        except KeyboardInterrupt:
            logger.info("Received interrupt signal. Stopping...")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
        finally:
            await self.client.disconnect()
            logger.info("Client disconnected")


async def main():
    """Main function to run the application."""
    parser = argparse.ArgumentParser(description='Telegram Message Forwarder')
    parser.add_argument('--remove-forward-signature', '-r', action='store_true', default=None,
                        help='Remove "Forward from..." signature (overrides REMOVE_FORWARD_SIGNATURE env)')
    parser.add_argument('--disable-console-log', '-q', action='store_true', default=None,
                        help='Disable console logging (overrides DISABLE_CONSOLE_LOG env)')

    args = parser.parse_args()

    # Resolve: CLI flag > env var > default
    disable_console = args.disable_console_log if args.disable_console_log else _env_bool('DISABLE_CONSOLE_LOG')
    setup_logging(disable_console=disable_console)

    remove_sig = args.remove_forward_signature if args.remove_forward_signature else None

    try:
        forwarder = TelegramForwarder(remove_forward_signature=remove_sig)
        await forwarder.run()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print("\nPlease check your .env file and ensure all required variables are set.")
        print("You can use .env.example as a template.")
    except Exception as e:
        logger.error(f"Application error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
