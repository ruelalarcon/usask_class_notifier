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
   - Replace `'YOUR_BOT_TOKEN'` and `CLASS_REGISTRAR_COOKIES` in `config.py` with your actual bot token
   - Add your Discord user ID to the `DEVELOPERS` list in `config.py` to use developer commands
   - An example config file can be found in `config.py.example`

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
  - Server admins or developers only
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

- `cn!cookies` (Developers only)
  - Shows session cookie status and refresh times
  - Developers only (user ID must be in DEVELOPERS list in config.py)

- `cn!refresh` (Developers only)
  - Manually refresh session cookies
  - Developers only (user ID must be in DEVELOPERS list in config.py)

## Features

- Checks all monitored classes every 20 seconds
- Sends notifications when seats become available (when count goes from 0 to >0)
- Per-server class monitoring (classes are tracked separately for each Discord server)
- Persistent data storage (survives bot restarts)
- Multiple users can monitor the same class
- Automatic session cookie refresh every 5 minutes
- Robust error handling and logging

## Valid Terms

- FALL
- WINTER
- SPRING
- SUMMER

## Notes

- The bot uses the University of Saskatchewan's Banner system
- **You must run `cn!setchannel` first** before the bot can send any notifications
- Only users in the DEVELOPERS list (defined in config.py) can use developer commands
- Session cookies are automatically refreshed every 5 minutes to maintain connectivity
- All bot data including cookies are saved in `bot_data.json`
- All commands use the prefix `cn!`
- To find your Discord user ID: Enable Developer Mode in Discord settings, then right-click your username and select "Copy ID"
