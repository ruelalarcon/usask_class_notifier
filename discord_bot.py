import json
import time
from datetime import datetime
from traceback import print_exc
from typing import Dict

import discord
import requests
from discord.ext import commands, tasks

from config import BOT_TOKEN, CLASS_REGISTRAR_COOKIES, DEVELOPERS

# Program Constants
TERMS = {
    'FALL': '09',
    'WINTER': '01',
    'SPRING': '05',
    'SUMMER': '07',
}

HEADERS = {
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
    'Accept-Language': 'en-US,en;q=0.9,en-CA;q=0.8',
    'Cache-Control': 'no-cache',
    'Connection': 'keep-alive',
    'Pragma': 'no-cache',
    'Sec-Fetch-Dest': 'document',
    'Sec-Fetch-Mode': 'navigate',
    'Sec-Fetch-Site': 'none',
    'Sec-Fetch-User': '?1',
    'Upgrade-Insecure-Requests': '1',
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/137.0.0.0 Safari/537.36 Edg/137.0.0.0',
    'sec-ch-ua': '"Microsoft Edge";v="137", "Chromium";v="137", "Not/A)Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
}


COOKIE_REFRESH_INTERVAL = 300

# Session management
session = requests.Session()
session.headers.update(HEADERS)
last_cookie_refresh = 0

def clean_duplicate_cookies():
    """Remove duplicate cookies while keeping the most recent ones"""
    global session

    try:
        # Get all cookies as a list
        all_cookies = list(session.cookies)

        # Check for duplicates
        cookie_names = [cookie.name for cookie in all_cookies]
        duplicates = [name for name in set(cookie_names) if cookie_names.count(name) > 1]

        if duplicates:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Found duplicate cookies: {duplicates}")

            # Create a new cookie jar with only unique cookies (keeping the last one of each name)
            from requests.cookies import RequestsCookieJar
            new_jar = RequestsCookieJar()

            # Track which cookies we've seen to keep only the last occurrence
            seen_cookies = {}

            for cookie in all_cookies:
                # Always update to keep the latest one
                seen_cookies[cookie.name] = cookie

            # Add unique cookies to new jar
            for cookie_name, cookie in seen_cookies.items():
                new_jar.set_cookie(cookie)

            # Replace the session's cookie jar
            session.cookies = new_jar

            print(f"[{datetime.now().strftime('%H:%M:%S')}] After cleanup: {list(session.cookies.keys())}")

    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Error cleaning duplicate cookies: {e}")
        print_exc()

def initialize_session():
    """Initialize the session with the provided cookies"""
    global session, last_cookie_refresh
    session.cookies.update(CLASS_REGISTRAR_COOKIES)
    last_cookie_refresh = time.time()
    clean_duplicate_cookies()
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Session initialized with cookies: {list(session.cookies.keys())}")

def refresh_session_cookies():
    """Attempt to refresh session cookies using the redirect mechanism"""
    global session, last_cookie_refresh

    try:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Attempting to refresh session cookies...")

        # Store original cookies for comparison
        original_cookies = dict(session.cookies)

        # Clear existing cookies to prevent duplicates
        session.cookies.clear()

        # Re-add the most recent saved cookies from bot_data.json, or fall back to config
        try:
            with open('bot_data.json', 'r') as f:
                saved_data = json.load(f)
                if 'cookies' in saved_data and saved_data['cookies']:
                    session.cookies.update(saved_data['cookies'])
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Restored cookies from bot_data.json: {list(session.cookies.keys())}")
                else:
                    session.cookies.update(CLASS_REGISTRAR_COOKIES)
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] No saved cookies found, using config baseline: {list(session.cookies.keys())}")
        except (FileNotFoundError, json.JSONDecodeError, KeyError):
            # Fall back to config cookies if file doesn't exist or is corrupted
            session.cookies.update(CLASS_REGISTRAR_COOKIES)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Error loading saved cookies, using config baseline: {list(session.cookies.keys())}")

        # This mimics clicking the "registration" link that you described
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Trying registration endpoint...")
        registration_response = session.get(
            'https://banner.usask.ca/StudentRegistrationSsb/ssb/registration',
            allow_redirects=True,
            timeout=30
        )

        # Check for new cookies after each step
        cookies_after_registration = dict(session.cookies)
        new_from_registration = {k: v for k, v in cookies_after_registration.items()
                               if k not in original_cookies or original_cookies[k] != v}

        if new_from_registration:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Got new cookies from registration: {list(new_from_registration.keys())}")

        # Try the main Banner entry point (potential SSO refresh)
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Trying main Banner entry point...")
        banner_response = session.get(
            'https://banner.usask.ca/StudentRegistrationSsb/',
            allow_redirects=True,
            timeout=30
        )

        # Try accessing the menu/home page that might trigger auth refresh
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Trying Banner menu...")
        session.get(
            'https://banner.usask.ca/StudentRegistrationSsb/ssb/classRegistration/classRegistration',
            allow_redirects=True,
            timeout=30
        )

        # Try the term search endpoint which might refresh session
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Trying term search...")
        current_year = datetime.now().year
        current_month = datetime.now().month

        # Determine current or next term
        if current_month >= 9:  # September or later = Fall term
            term_code = f"{current_year}09"
        elif current_month >= 5:  # May or later = Summer term
            term_code = f"{current_year}07"
        elif current_month >= 1:  # January or later = Winter term
            term_code = f"{current_year}01"
        else:
            term_code = f"{current_year-1}09"  # Fall of previous year

        session.post(
            'https://banner.usask.ca/StudentRegistrationSsb/ssb/term/search',
            params={'mode': 'registration'},
            data={'term': term_code},
            allow_redirects=True,
            timeout=30
        )

        # Clean any duplicate cookies that might have been created
        clean_duplicate_cookies()

        # Check final cookie state
        final_cookies = dict(session.cookies)
        all_updated_cookies = {k: v for k, v in final_cookies.items()
                             if k not in original_cookies or original_cookies[k] != v}

        if all_updated_cookies:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully refreshed cookies! Updated: {list(all_updated_cookies.keys())}")
            for cookie_name, cookie_value in all_updated_cookies.items():
                print(f"[{datetime.now().strftime('%H:%M:%S')}]   {cookie_name}: {cookie_value[:20]}...")

            # Save updated cookies
            save_data()
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] No new cookies received during refresh")

        last_cookie_refresh = time.time()

        # Test if the refresh worked by making a simple API call
        test_response = session.get(
            'https://banner.usask.ca/StudentRegistrationSsb/ssb/classRegistration/classRegistration',
            timeout=10
        )

        if test_response.status_code == 200:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Cookie refresh verification: SUCCESS")
            return True
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Cookie refresh verification: FAILED (status {test_response.status_code})")
            return False

    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Error refreshing session cookies: {e}")
        print_exc()
        return False
    finally:
        # Always ensure we clean duplicates even if there was an error
        try:
            clean_duplicate_cookies()
        except Exception as cleanup_error:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Error in final cleanup: {cleanup_error}")

def should_refresh_cookies():
    """Determine if cookies should be refreshed"""
    return time.time() - last_cookie_refresh > COOKIE_REFRESH_INTERVAL

def make_authenticated_request(method: str, url: str, **kwargs) -> requests.Response:
    """Make a request with automatic cookie refresh if needed"""
    global session

    # Refresh cookies if it's been a while
    if should_refresh_cookies():
        refresh_session_cookies()

    # Make the request
    response = session.request(method, url, **kwargs)

    # If we get auth errors, try refreshing cookies once
    if response.status_code in [401, 403]:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Auth error (status {response.status_code}), attempting cookie refresh...")
        if refresh_session_cookies():
            # Retry the request with fresh cookies
            response = session.request(method, url, **kwargs)

    return response

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='cn!', intents=intents, help_command=None)

# Data storage: guild_id -> {crn -> {class_info, users_to_notify, last_available_seats}, notify_channel_id -> channel_id}
guild_data: Dict[int, Dict[str, Dict]] = {}

def is_developer():
    """Custom check to verify if user is in the DEVELOPERS list"""
    def predicate(ctx):
        if not DEVELOPERS:
            # If no developers are configured, allow the first user to set themselves up
            return True
        return ctx.author.id in DEVELOPERS
    return commands.check(predicate)

def is_admin_or_developer():
    """Custom check for server admins (owner/manage server) OR config.py developers"""
    def predicate(ctx):
        # Check if user is a developer (config.py DEVELOPERS)
        if ctx.author.id in DEVELOPERS:
            return True
        # Check if user is server owner
        if ctx.author.id == ctx.guild.owner_id:
            return True
        # Check if user has server admin permissions
        return ctx.author.guild_permissions.administrator
    return commands.check(predicate)

def load_data():
    """Load persistent data from file"""
    global guild_data
    try:
        with open('bot_data.json', 'r') as f:
            data = json.load(f)
            guild_data = {int(k): v for k, v in data['guilds'].items()}

            # Load cookies if they exist
            if 'cookies' in data:
                session.cookies.update(data['cookies'])
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Loaded {len(data['cookies'])} saved cookies")

    except FileNotFoundError:
        guild_data = {}

def save_data():
    """Save data to file"""
    try:
        # Clean duplicates before saving to prevent CookieConflictError
        clean_duplicate_cookies()

        # Now safely convert cookies to dict
        try:
            cookies_dict = dict(session.cookies)
        except Exception as cookie_error:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Error converting cookies to dict: {cookie_error}")
            # Fall back to manual extraction if dict conversion fails
            cookies_dict = {}
            for cookie in session.cookies:
                cookies_dict[cookie.name] = cookie.value
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Used fallback cookie extraction, got {len(cookies_dict)} cookies")

        data = {
            'guilds': guild_data,
            'cookies': cookies_dict,
            'last_updated': datetime.now().isoformat()
        }

        with open('bot_data.json', 'w') as f:
            json.dump(data, f, indent=2)

    except Exception as e:
        print(f"[{datetime.now().strftime('%H:%M:%S')}] Error in save_data: {e}")
        print_exc()

def check_class_seats(subject: str, course_number: str, year: str, term: str, crn: str) -> int:
    """Check available seats for a specific class"""
    try:
        params = {
            'txt_subject': subject,
            'txt_courseNumber': course_number,
            'txt_term': f'{year}{TERMS[term.upper()]}',
            'startDatepicker': '',
            'endDatepicker': '',
            'pageOffset': '0',
            'pageMaxSize': '10',
            'sortColumn': 'subjectDescription',
            'sortDirection': 'asc',
        }

        data = {
            'term': f'{year}{TERMS[term.upper()]}',
            'studyPath': '',
            'studyPathText': '',
            'startDatepicker': '',
            'endDatepicker': '',
        }

        # Put user into search mode for the correct term
        make_authenticated_request(
            'POST',
            'https://banner.usask.ca/StudentRegistrationSsb/ssb/term/search',
            params={'mode': 'registration'},
            data=data,
        )

        # Reset the search form
        make_authenticated_request(
            'POST',
            'https://banner.usask.ca/StudentRegistrationSsb/ssb/classSearch/resetDataForm',
        )

        # Get the search results
        response = make_authenticated_request(
            'GET',
            'https://banner.usask.ca/StudentRegistrationSsb/ssb/searchResults/searchResults',
            params=params,
        )

        if response.status_code == 200:
            json_data = response.json()
            data = json_data['data']
            for item in data:
                if item['courseReferenceNumber'] == crn:
                    return int(item['seatsAvailable'])
            return -1  # Class not found
        else:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] HTTP {response.status_code} when checking seats for {crn}")
            return -2  # Request failed
    except Exception as e:
        print(f"Error checking seats for {crn}: {e}")
        return -2

@bot.event
async def on_ready():
    print(f'{bot.user} has logged in!')
    initialize_session()
    load_data()
    seat_checker.start()

@bot.command(name='help')
async def help_command(ctx):
    """Show help for all available commands"""
    embed = discord.Embed(
        title="Class Notifier Bot - Help",
        description="Monitor University of Saskatchewan class seat availability",
        color=0x0c6b41
    )

    embed.add_field(
        name="cn!setchannel [#channel]",
        value="**REQUIRED FIRST STEP**: Set notification channel\n"
              "• If no channel specified, uses current channel\n"
              "• Server admins or developers only\n"
              "• Example: `cn!setchannel #class-alerts`",
        inline=False
    )

    embed.add_field(
        name="cn!add CRN SUBJECT COURSE_NUMBER YEAR TERM",
        value="Add a class to monitoring list\n"
              "• You'll be pinged when seats become available\n"
              "• Example: `cn!add 12345 CMPT 332 2024 FALL`\n"
              "• Valid terms: FALL, WINTER, SPRING, SUMMER",
        inline=False
    )

    embed.add_field(
        name="cn!remove CRN",
        value="Stop monitoring a class\n"
              "• Example: `cn!remove 12345`",
        inline=False
    )

    embed.add_field(
        name="cn!status",
        value="Show all monitored classes and seat counts\n"
              "• Shows notification channel status\n"
              "• Shows number of users watching each class",
        inline=False
    )

    embed.add_field(
        name="cn!help",
        value="Show this help message",
        inline=False
    )

    embed.add_field(
        name="cn!cookies",
        value="Show session cookie status (Developers only)\n"
              "• Tells you which cookies are active and when they were last refreshed\n"
              "• Developers only (defined in config.py)",
        inline=False
    )

    embed.add_field(
        name="cn!refresh",
        value="Manually refresh session cookies (Developers only)\n"
              "• Forces immediate cookie refresh\n"
              "• Developers only (defined in config.py)",
        inline=False
    )

    embed.add_field(
        name="📋 How it works",
        value="• Bot checks all classes every 20 seconds\n"
              "• Notifications sent when seats go from 0 → available\n"
              "• Automatic cookie refresh every 5 minutes\n"
              "• Each Discord server has independent monitoring",
        inline=False
    )

    embed.set_footer(text="University of Saskatchewan Class Monitor")

    await ctx.send(embed=embed)

@bot.command(name='add')
async def add_class(ctx, crn: str, subject: str, course_number: str, year: str, term: str):
    """Add a class to be monitored"""
    guild_id = ctx.guild.id
    user_id = ctx.author.id

    # Validate term
    if term.upper() not in TERMS:
        await ctx.send(f"Invalid term '{term}'. Valid terms are: {', '.join(TERMS.keys())}")
        return

    # Initialize guild data if needed
    if guild_id not in guild_data:
        guild_data[guild_id] = {}

    # Initialize class data if needed
    if crn not in guild_data[guild_id]:
        guild_data[guild_id][crn] = {
            'subject': subject.upper(),
            'course_number': course_number,
            'year': year,
            'term': term.upper(),
            'users_to_notify': [],
            'last_available_seats': None
        }

    # Add user to notification list if not already there
    if user_id not in guild_data[guild_id][crn]['users_to_notify']:
        guild_data[guild_id][crn]['users_to_notify'].append(user_id)

    save_data()

    class_info = guild_data[guild_id][crn]
    await ctx.send(f"✅ Added {class_info['subject']} {class_info['course_number']} (CRN: {crn}) for {class_info['term']} {class_info['year']}. You'll be notified when seats become available!")

@bot.command(name='remove')
async def remove_class(ctx, crn: str):
    """Remove a class from monitoring"""
    guild_id = ctx.guild.id

    if guild_id not in guild_data or crn not in guild_data[guild_id]:
        await ctx.send(f"❌ CRN {crn} is not being monitored in this server.")
        return

    class_info = guild_data[guild_id][crn]
    del guild_data[guild_id][crn]
    save_data()

    await ctx.send(f"✅ Removed {class_info['subject']} {class_info['course_number']} (CRN: {crn}) from monitoring.")

@bot.command(name='setchannel')
@is_admin_or_developer()
async def set_notify_channel(ctx, channel: discord.TextChannel = None):
    """Set the channel where seat availability notifications will be sent"""
    guild_id = ctx.guild.id

    # Use current channel if no channel specified
    if channel is None:
        channel = ctx.channel

    # Initialize guild data if needed
    if guild_id not in guild_data:
        guild_data[guild_id] = {}

    # Store the notification channel ID
    guild_data[guild_id]['notify_channel_id'] = channel.id
    save_data()

    await ctx.send(f"✅ Notification channel set to {channel.mention}. All seat availability notifications will be sent here.")

@bot.event
async def on_command_error(ctx, error):
    """Global error handler for commands"""
    if isinstance(error, commands.CheckFailure):
        await ctx.send("❌ You need proper permissions to use this command. Server admins can use `cn!setchannel`, developers (defined in config.py) can use other admin commands.")
    elif isinstance(error, commands.CommandNotFound):
        # Silently ignore unknown commands
        pass
    else:
        # For other errors, you might want to log them or handle them differently
        print(f"Command error in {ctx.command}: {error}")

@bot.command(name='status')
async def status(ctx):
    """Show status of all monitored classes"""
    guild_id = ctx.guild.id

    if guild_id not in guild_data:
        await ctx.send("📋 No classes are currently being monitored in this server.")
        return

    # Check if notification channel is set
    notify_channel_id = guild_data[guild_id].get('notify_channel_id')
    notify_channel = None
    if notify_channel_id:
        notify_channel = bot.get_channel(notify_channel_id)

    # Filter out non-class data (like notify_channel_id)
    classes = {crn: info for crn, info in guild_data[guild_id].items() if crn != 'notify_channel_id'}

    if not classes:
        await ctx.send("📋 No classes are currently being monitored in this server.")
        return

    embed = discord.Embed(title="📚 Class Monitoring Status", color=0x0c6b41)

    # Add notification channel info
    if notify_channel:
        embed.add_field(
            name="📢 Notification Channel",
            value=notify_channel.mention,
            inline=False
        )
    else:
        embed.add_field(
            name="⚠️ Notification Channel",
            value="Not set! Use `cn!setchannel` to set where notifications will be sent.",
            inline=False
        )

    for crn, class_info in classes.items():
        subject = class_info['subject']
        course_number = class_info['course_number']
        year = class_info['year']
        term = class_info['term']
        users_count = len(class_info['users_to_notify'])
        last_seats = class_info.get('last_available_seats', 'Unknown')

        status_text = f"**Term:** {term} {year}\n"
        status_text += f"**Users watching:** {users_count}\n"
        status_text += f"**Available seats:** {last_seats if last_seats is not None else 'Checking...'}"

        embed.add_field(
            name=f"{subject} {course_number} (CRN: {crn})",
            value=status_text,
            inline=True
        )

    await ctx.send(embed=embed)

@bot.command(name='cookies')
@is_developer()
async def cookie_status(ctx):
    """Show current cookie status and allow manual refresh"""
    global session, last_cookie_refresh

    embed = discord.Embed(title="🍪 Cookie Status", color=0x0c6b41)

    # Show current cookies
    current_cookies = dict(session.cookies)
    cookie_names = list(current_cookies.keys())

    embed.add_field(
        name="Active Cookies",
        value=f"```{', '.join(cookie_names) if cookie_names else 'None'}```",
        inline=False
    )

    # Show last refresh time
    if last_cookie_refresh > 0:
        last_refresh = datetime.fromtimestamp(last_cookie_refresh)
        embed.add_field(
            name="Last Refresh",
            value=f"{last_refresh.strftime('%Y-%m-%d %H:%M:%S')}",
            inline=True
        )
    else:
        embed.add_field(
            name="Last Refresh",
            value="Never",
            inline=True
        )

    # Show next scheduled refresh
    if last_cookie_refresh > 0:
        next_refresh = datetime.fromtimestamp(last_cookie_refresh + COOKIE_REFRESH_INTERVAL)
        embed.add_field(
            name="Next Auto-Refresh",
            value=f"{next_refresh.strftime('%Y-%m-%d %H:%M:%S')}",
            inline=True
        )
    else:
        embed.add_field(
            name="Next Auto-Refresh",
            value="Will refresh on first API call",
            inline=True
        )

    embed.add_field(
        name="Manual Refresh",
        value="Use `cn!refresh` to manually refresh cookies now\nCookies are saved in bot_data.json",
        inline=False
    )

    await ctx.send(embed=embed)

@bot.command(name='refresh')
@is_developer()
async def manual_refresh(ctx):
    """Manually refresh session cookies"""
    await ctx.send("🔄 Attempting to refresh cookies...")

    success = refresh_session_cookies()

    if success:
        await ctx.send("✅ Cookie refresh completed! Check `cn!cookies` for updated status.")
    else:
        await ctx.send("❌ Cookie refresh failed. Check bot logs for details.")

@tasks.loop(seconds=20)
async def seat_checker():
    """Background task to check seats every 20 seconds"""
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Checking seats...")

    # Session keep-alive and cookie refresh is now handled automatically in make_authenticated_request()

    for guild_id, guild_info in guild_data.items():
        # Get notification channel for this guild
        notify_channel_id = guild_info.get('notify_channel_id')
        if not notify_channel_id:
            continue  # Skip if no notification channel set

        notify_channel = bot.get_channel(notify_channel_id)
        if not notify_channel:
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Warning: Notification channel {notify_channel_id} not found for guild {guild_id}")
            continue  # Skip if channel no longer exists

        # Filter out non-class data (like notify_channel_id)
        classes = {crn: info for crn, info in guild_info.items() if crn != 'notify_channel_id'}

        for crn, class_info in classes.items():
            try:
                # Check available seats
                available_seats = check_class_seats(
                    class_info['subject'],
                    class_info['course_number'],
                    class_info['year'],
                    class_info['term'],
                    crn
                )

                # Get previous seat count
                previous_seats = class_info.get('last_available_seats')

                # Handle API errors
                if available_seats == -1:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Warning: Class {crn} not found in search results")
                    continue  # Don't update seat count if class not found
                elif available_seats == -2:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Error: Failed to check seats for {crn}")
                    continue  # Don't update seat count if request failed

                # Update last known seat count only if we got a valid response
                class_info['last_available_seats'] = available_seats


                # Improved notification logic: only notify if we have a valid previous state
                # and seats went from 0 to >0 (not on first check when previous_seats is None)
                should_notify = (
                    available_seats > 0 and
                    previous_seats is not None and
                    previous_seats == 0
                )

                if should_notify:
                    print(f"[{datetime.now().strftime('%H:%M:%S')}] Seats became available for {crn}! ({previous_seats} -> {available_seats})")

                    # Create notification message
                    user_mentions = []
                    for user_id in class_info['users_to_notify']:
                        user_mentions.append(f"<@{user_id}>")

                    if user_mentions:
                        try:
                            embed = discord.Embed(
                                title="🎉 Seats Available!",
                                description=f"**{class_info['subject']} {class_info['course_number']}** (CRN: {crn})",
                                color=0x0c6b41
                            )
                            embed.add_field(name="Available Seats", value=str(available_seats), inline=True)
                            embed.add_field(name="Term", value=f"{class_info['term']} {class_info['year']}", inline=True)

                            mentions_text = " ".join(user_mentions)
                            await notify_channel.send(content=mentions_text, embed=embed)
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Successfully sent notification for {crn} to {len(user_mentions)} users")

                        except discord.Forbidden:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Error: Bot lacks permission to send messages in channel {notify_channel.name}")
                        except discord.HTTPException as e:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Error sending notification: {e}")
                        except Exception as e:
                            print(f"[{datetime.now().strftime('%H:%M:%S')}] Unexpected error sending notification for {crn}: {e}")
                    else:
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Warning: No valid users to notify for {crn}")

            except Exception as e:
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Error processing class {crn}: {e}")
                # Continue processing other classes even if one fails

    # Save data after all classes have been checked
    save_data()

@seat_checker.before_loop
async def before_seat_checker():
    await bot.wait_until_ready()

# Run the bot
if __name__ == "__main__":
    # You need to replace 'YOUR_BOT_TOKEN' with your actual Discord bot token
    bot.run(BOT_TOKEN)
