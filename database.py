import os
import logging
from motor.motor_asyncio import AsyncIOMotorClient
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

class Database:
    def __init__(self):
        self._db_url = os.getenv('DATABASE_URL')
        self._client = None
        self._db = None
        
        # Collections
        self.settings = None
        self.sessions = None
        self.sync_state = None
        
    async def connect(self):
        """Connect to the database and initialize collections"""
        if not self._db_url:
            logger.warning("No DATABASE_URL found. Running without database persistence.")
            return False
            
        try:
            self._client = AsyncIOMotorClient(self._db_url)
            self._db = self._client['tg_forwarder']
            
            self.settings = self._db['settings']
            self.sessions = self._db['sessions']
            self.sync_state = self._db['sync_state']
            
            # Verify connection
            await self._client.server_info()
            logger.info("Successfully connected to MongoDB")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to MongoDB: {e}")
            self._client = None
            return False

    async def get_settings(self):
        """Get all environment variables from DB"""
        if not self.settings:
            return {}
            
        settings = {}
        cursor = self.settings.find({})
        async for document in cursor:
            settings[document['_id']] = document['value']
        return settings

    async def update_setting(self, key, value):
        """Update a specific setting in DB"""
        if not self.settings:
            return
            
        await self.settings.update_one(
            {'_id': key},
            {'$set': {'value': value}},
            upsert=True
        )

    async def save_session(self, session_name, session_string):
        """Save a StringSession to DB"""
        if not self.sessions:
            return
            
        await self.sessions.update_one(
            {'_id': session_name},
            {'$set': {'session_string': session_string}},
            upsert=True
        )

    async def get_session(self, session_name):
        """Retrieve a StringSession from DB"""
        if not self.sessions:
            return None
            
        doc = await self.sessions.find_one({'_id': session_name})
        return doc.get('session_string') if doc else None

    async def get_sync_state(self):
        """Get the full sync state from DB"""
        if not self.sync_state:
            return {}
            
        state = {}
        cursor = self.sync_state.find({})
        async for doc in cursor:
            state[doc['_id']] = doc['last_id']
        return state

    async def save_sync_state(self, state_dict):
        """Save the full sync state to DB"""
        if not self.sync_state:
            return
            
        operations = []
        from pymongo import UpdateOne
        
        for chat_id, last_id in state_dict.items():
            operations.append(
                UpdateOne(
                    {'_id': str(chat_id)},
                    {'$set': {'last_id': last_id}},
                    upsert=True
                )
            )
            
        if operations:
            await self.sync_state.bulk_write(operations)

    async def clear_sync_state(self):
        """Clear all stored sync states from DB"""
        if not self.sync_state:
            return
        await self.sync_state.delete_many({})

    async def clear_forwarding_rules(self):
        """Clear all stored source and target rules from DB"""
        if not self.settings:
            return
        await self.settings.delete_many({
            '$or': [
                {'_id': {'$regex': '^SOURCE_'}},
                {'_id': {'$regex': '^TARGET_'}},
                {'_id': 'FORWARDING_RULES'}
            ]
        })

# Global singleton
db = Database()
