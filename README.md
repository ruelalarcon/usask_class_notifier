# Class Notifier Discord Bot

A Discord bot that monitors University of Saskatchewan class seat availability and notifies users when seats become available.

## Setup

1. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Create a Discord Bot:**
   - Go to https://discord.com/developers/applications
   - Create a new application
   - Go to the "Bot" section
   - Create a bot and copy the token
   - Enable "Message Content Intent" in the bot settings

3. **Configure the bot:**
   - Replace `'YOUR_BOT_TOKEN'` in `config.py` with your actual bot token
   - Update the `CLASS_REGISTRAR_COOKIES` in `config.py` as well

4. **Invite bot to your server:**
   - Go to OAuth2 -> URL Generator
   - Select "bot" scope and "Send Messages", "Read Message History", "Mention Everyone" permissions
   - Use the generated URL to invite the bot to your server

5. **Run the bot:**
   ```bash
   python discord_bot.py
   ```

## Commands

- `cn!help`
  - Shows detailed help for all commands

- `cn!setchannel [#channel]`
  - **REQUIRED FIRST STEP**: Sets the channel where seat availability notifications will be sent
  - If no channel is specified, uses the current channel
  - Requires "Manage Channels" permission
  - Example: `cn!setchannel #class-alerts` or `cn!setchannel` (uses current channel)

- `cn!add CRN SUBJECT COURSE_NUMBER YEAR TERM`
  - Adds a class to be monitored and adds you to the notification list
  - Example: `cn!add 12345 CMPT 332 2024 FALL`

- `cn!remove CRN`
  - Stops monitoring a class
  - Example: `cn!remove 12345`

- `cn!status`
  - Shows seat counts for all monitored classes in the server
  - Also shows which channel is set for notifications

## Features

- Checks all monitored classes every 10 seconds
- Sends notifications when seats become available (when count goes from 0 to >0)
- Per-server class monitoring (classes are tracked separately for each Discord server)
- Persistent data storage (survives bot restarts)
- Multiple users can monitor the same class

## Valid Terms

- FALL
- WINTER
- SPRING
- SUMMER

## Notes

- The bot uses the University of Saskatchewan's Banner system
- You may need to update the cookies periodically as they expire
- **You must run `cn!setchannel` first** before the bot can send any notifications
- Only users with "Manage Channels" permission can set the notification channel
- All commands use the prefix `cn!` 