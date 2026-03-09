import asyncio
import logging
import os
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
        # Only log to file, not console
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('telegram_forwarder.log'),
            ]
        )
    else:
        # Log to both console and file
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler('telegram_forwarder.log')
            ]
        )

logger = logging.getLogger(__name__)

class TelegramForwarder:
    def __init__(self, remove_forward_signature=False):
        """Initialize the Telegram forwarder with environment variables."""
        self.api_id = os.getenv('API_ID')
        self.api_hash = os.getenv('API_HASH')
        self.bot_token = os.getenv('BOT_TOKEN')
        self.remove_forward_signature = remove_forward_signature
        
        # Check for legacy single source/target configuration
        self.source_id = os.getenv('SOURCE_ID')
        self.target_id = os.getenv('TARGET_ID')
        self.forwarding_rules = os.getenv('FORWARDING_RULES')
        
        # Validate required environment variables
        if not all([self.api_id, self.api_hash]):
            raise ValueError("Missing API_ID or API_HASH. Check your .env file.")
        
        # Parse forwarding configuration
        # forwarding_map: {(source_chat_id, source_topic_id|None): [(target_chat_id, target_topic_id|None), ...]}
        self.forwarding_map = self._parse_forwarding_rules()
        
        if not self.forwarding_map:
            raise ValueError("No forwarding rules configured. Set either SOURCE_ID/TARGET_ID or FORWARDING_RULES.")
        
        # Extract unique source chat IDs for event registration
        self.source_chat_ids = list({src_chat for src_chat, _ in self.forwarding_map.keys()})
        
        # Ensure session directory exists
        os.makedirs('sessions', exist_ok=True)
        
        # Initialize Telegram client
        if self.bot_token:
            # Bot mode
            self.client = TelegramClient('sessions/bot_session', self.api_id, self.api_hash)
            logger.info("Initialized in bot mode")
        else:
            # User mode
            self.client = TelegramClient('sessions/user_session', self.api_id, self.api_hash)
            logger.info("Initialized in user mode")
    
    @staticmethod
    def _parse_id_topic(part):
        """Parse a 'chat_id/topic_id' or 'chat_id' string into (chat_id, topic_id|None)."""
        if '/' in part:
            chat_str, topic_str = part.split('/', 1)
            chat_id = int(chat_str)
            topic_id = int(topic_str)
            return (chat_id, topic_id)
        else:
            return (int(part), None)
    
    def _parse_forwarding_rules(self):
        """Parse forwarding rules from environment variables.
        
        Returns a dict mapping (source_chat_id, source_topic_id|None) to
        a list of (target_chat_id, target_topic_id|None) tuples.
        
        Format: source_id[/topic]:target_id[/topic]:target_id[/topic],...
        """
        forwarding_map = {}
        
        # Check for legacy single source/target configuration
        if self.source_id and self.target_id:
            try:
                source_key = (int(self.source_id), None)
                target_val = (int(self.target_id), None)
                forwarding_map[source_key] = [target_val]
                logger.info("Using legacy single source/target configuration")
                return forwarding_map
            except ValueError:
                raise ValueError("SOURCE_ID and TARGET_ID must be valid integers.")
        
        # Parse multiple forwarding rules with optional topic IDs
        if self.forwarding_rules:
            try:
                rules = self.forwarding_rules.split(',')
                for rule in rules:
                    rule = rule.strip()
                    if not rule:
                        continue
                    
                    parts = rule.split(':')
                    if len(parts) < 2:
                        raise ValueError(f"Invalid forwarding rule format: {rule}")
                    
                    source_key = self._parse_id_topic(parts[0])
                    target_list = [self._parse_id_topic(t) for t in parts[1:]]
                    
                    if source_key in forwarding_map:
                        forwarding_map[source_key].extend(target_list)
                    else:
                        forwarding_map[source_key] = target_list
                
                logger.info(f"Parsed {len(forwarding_map)} forwarding rules")
                return forwarding_map
                
            except ValueError as e:
                raise ValueError(f"Error parsing FORWARDING_RULES: {e}")
        
        return {}
    
    async def start_client(self):
        """Start the Telegram client and handle authentication."""
        await self.client.start(bot_token=self.bot_token if self.bot_token else None)
        
        if not self.bot_token:
            # User authentication
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
    
    def _get_message_topic_id(self, message):
        """Extract the forum topic ID from a message, or None if not in a topic."""
        reply_to = message.reply_to
        if reply_to is None:
            return None
        # If forum_topic flag is set, the topic ID is in reply_to_top_id or reply_to_msg_id
        if getattr(reply_to, 'forum_topic', False):
            # reply_to_top_id is the topic root; if absent, reply_to_msg_id is the topic root itself
            return reply_to.reply_to_top_id or reply_to.reply_to_msg_id
        return None
    
    def _find_targets(self, source_chat_id, msg_topic_id):
        """Find matching target list for a source chat + topic combination.
        
        Priority:
          1. Exact match: (source_chat_id, msg_topic_id)
          2. Wildcard match: (source_chat_id, None) — matches all topics
        """
        # Try exact match first
        targets = self.forwarding_map.get((source_chat_id, msg_topic_id))
        if targets:
            return targets
        # Fall back to wildcard (no topic filter)
        return self.forwarding_map.get((source_chat_id, None), [])
    
    async def setup_forwarding(self):
        """Set up message forwarding from multiple sources to their respective targets."""
        # Log all forwarding rules
        logger.info("Setting up forwarding rules:")
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
                
                # Extract the topic ID from the incoming message
                msg_topic_id = self._get_message_topic_id(message)
                
                # Find matching targets (exact topic match, then wildcard)
                targets = self._find_targets(source_chat_id, msg_topic_id)
                if not targets:
                    logger.debug(f"No targets for source {source_chat_id} topic {msg_topic_id}, skipping")
                    return
                
                source_info = await self.get_entity_info(source_chat_id, msg_topic_id)
                logger.info(f"Received message from {sender_id} in {source_info}")
                
                # Forward to all matched targets
                for target_chat, target_topic in targets:
                    try:
                        target_info = await self.get_entity_info(target_chat, target_topic)
                        
                        if self.remove_forward_signature:
                            # Send as new message without "Forward from..." signature
                            await self.client.send_message(
                                entity=target_chat,
                                message=message.message,
                                file=message.media,
                                parse_mode='html' if message.entities else None,
                                reply_to=target_topic
                            )
                            logger.info(f"Successfully sent message (without forward signature) to {target_info}")
                        else:
                            if target_topic:
                                # forward_messages doesn't support topic placement,
                                # so we send as a new message to the target topic instead.
                                await self.client.send_message(
                                    entity=target_chat,
                                    message=message.message,
                                    file=message.media,
                                    parse_mode='html' if message.entities else None,
                                    reply_to=target_topic
                                )
                                logger.info(f"Successfully sent message to {target_info}")
                            else:
                                # Forward with "Forward from..." signature
                                await self.client.forward_messages(
                                    entity=target_chat,
                                    messages=message.id,
                                    from_peer=source_chat_id
                                )
                                logger.info(f"Successfully forwarded message to {target_info}")
                            
                    except Exception as e:
                        target_info = await self.get_entity_info(target_chat, target_topic)
                        logger.error(f"Error forwarding to {target_info}: {e}")
                
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
    parser.add_argument('--remove-forward-signature', '-r', action='store_true',
                        help='Remove "Forward from..." signature by sending as new messages instead of forwarding')
    parser.add_argument('--disable-console-log', '-q', action='store_true',
                        help='Disable console logging (only log to file)')
    
    args = parser.parse_args()
    
    # Setup logging based on arguments
    setup_logging(disable_console=args.disable_console_log)
    
    try:
        forwarder = TelegramForwarder(remove_forward_signature=args.remove_forward_signature)
        await forwarder.run()
    except ValueError as e:
        logger.error(f"Configuration error: {e}")
        print("\nPlease check your .env file and ensure all required variables are set.")
        print("You can use .env.example as a template.")
    except Exception as e:
        logger.error(f"Application error: {e}")

if __name__ == "__main__":
    asyncio.run(main())
