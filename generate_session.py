#!/usr/bin/env python3
"""
Generate a Telegram session file for use in Docker.

This script creates a session file that can be copied to Docker containers,
avoiding the need for interactive authentication in containers.

Usage:
    python generate_session.py

The session file will be saved to: sessions/user_session.session
"""

import os
import asyncio
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
from dotenv import load_dotenv

load_dotenv()


async def main():
    api_id = os.getenv('API_ID')
    api_hash = os.getenv('API_HASH')

    if not api_id or not api_hash:
        print("ERROR: API_ID and API_HASH must be set in .env file")
        print("\nPlease set these values first:")
        print("  API_ID=your_api_id")
        print("  API_HASH=your_api_hash")
        return 1

    # Create sessions directory if it doesn't exist
    os.makedirs('sessions', exist_ok=True)

    session_path = 'sessions/user_session'
    client = TelegramClient(session_path, int(api_id), api_hash)

    print("Connecting to Telegram...")
    await client.connect()

    if await client.is_user_authorized():
        print("✓ Already authorized!")
    else:
        print("\n--- Authentication Required ---")
        phone = input("Enter your phone number (with country code, e.g., +1234567890): ")

        await client.send_code_request(phone)
        print(f"Code sent to {phone}")

        code = input("Enter the verification code you received: ")

        try:
            await client.sign_in(phone, code)
        except SessionPasswordNeededError:
            password = input("Enter your 2FA password: ")
            await client.sign_in(password=password)

        print("✓ Authentication successful!")

    # Get user info
    me = await client.get_me()
    print(f"\nLogged in as: {me.first_name} (@{me.username or 'no_username'})")

    await client.disconnect()

    session_file = f'{session_path}.session'
    print(f"\n{'=' * 60}")
    print("SUCCESS! Session file created:")
    print(f"  {session_file}")
    print(f"{'=' * 60}")
    print("\nFor Docker, copy this file to your sessions volume:")
    print("  docker cp sessions/user_session.session tg-forwarder:/app/sessions/")
    print("\nOr if using docker-compose with ./sessions:/app/sessions volume,")
    print("the session file is already available to the container!")
    print(f"{'=' * 60}\n")

    return 0


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    exit(exit_code or 0)
