import discord
from discord.ext import commands, tasks
import requests
import json
from typing import Dict
from config import BOT_TOKEN, CLASS_REGISTRAR_COOKIES

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

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='cn!', intents=intents, help_command=None)

# Data storage: guild_id -> {crn -> {class_info, users_to_notify, last_available_seats}, notify_channel_id -> channel_id}
guild_data: Dict[int, Dict[str, Dict]] = {}

def load_data():
    """Load persistent data from file"""
    global guild_data
    try:
        with open('bot_data.json', 'r') as f:
            guild_data = json.load(f)
            # Convert string keys back to int for guild_ids
            guild_data = {int(k): v for k, v in guild_data.items()}
    except FileNotFoundError:
        guild_data = {}

def save_data():
    """Save data to file"""
    with open('bot_data.json', 'w') as f:
        json.dump(guild_data, f, indent=2)

def check_class_seats(subject: str, course_number: str, year: str, term: str, crn: str) -> int:
    """Check available seats for a specific class"""
    try:
        # Keep JSESSIONID active
        requests.get(
            'https://banner.usask.ca/StudentRegistrationSsb/ssb/registration',
            cookies=CLASS_REGISTRAR_COOKIES,
            headers=HEADERS,
        )

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
        requests.post(
            'https://banner.usask.ca/StudentRegistrationSsb/ssb/term/search',
            params={'mode': 'registration'},
            cookies=CLASS_REGISTRAR_COOKIES,
            headers=HEADERS,
            data=data,
        )

        # Reset the search form
        requests.post(
            'https://banner.usask.ca/StudentRegistrationSsb/ssb/classSearch/resetDataForm',
            cookies=CLASS_REGISTRAR_COOKIES,
            headers=HEADERS,
        )

        # Get the search results
        response = requests.get(
            'https://banner.usask.ca/StudentRegistrationSsb/ssb/searchResults/searchResults',
            params=params,
            cookies=CLASS_REGISTRAR_COOKIES,
            headers=HEADERS,
        )

        if response.status_code == 200:
            json_data = response.json()
            data = json_data['data']
            for item in data:
                if item['courseReferenceNumber'] == crn:
                    return int(item['seatsAvailable'])
            return -1  # Class not found
        else:
            return -2  # Request failed
    except Exception as e:
        print(f"Error checking seats for {crn}: {e}")
        return -2

@bot.event
async def on_ready():
    print(f'{bot.user} has logged in!')
    load_data()
    seat_checker.start()

@bot.command(name='help')
async def help_command(ctx):
    """Show help for all available commands"""
    embed = discord.Embed(
        title="🤖 Class Notifier Bot - Help",
        description="Monitor University of Saskatchewan class seat availability",
        color=0x0099ff
    )
    
    embed.add_field(
        name="cn!setchannel [#channel]",
        value="**REQUIRED FIRST STEP**: Set notification channel\n"
              "• If no channel specified, uses current channel\n"
              "• Requires 'Manage Channels' permission\n"
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
        name="📋 How it works",
        value="• Bot checks all classes every 10 seconds\n"
              "• Notifications sent when seats go from 0 → available\n"
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
@commands.has_permissions(manage_channels=True)
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

@set_notify_channel.error
async def set_notify_channel_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("❌ You need the 'Manage Channels' permission to set the notification channel.")

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
    
    embed = discord.Embed(title="📚 Class Monitoring Status", color=0x00ff00)
    
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

@tasks.loop(seconds=10)
async def seat_checker():
    """Background task to check seats every 10 seconds"""
    for guild_id, guild_info in guild_data.items():
        # Get notification channel for this guild
        notify_channel_id = guild_info.get('notify_channel_id')
        if not notify_channel_id:
            continue  # Skip if no notification channel set
        
        notify_channel = bot.get_channel(notify_channel_id)
        if not notify_channel:
            continue  # Skip if channel no longer exists
        
        # Filter out non-class data (like notify_channel_id)
        classes = {crn: info for crn, info in guild_info.items() if crn != 'notify_channel_id'}
        
        for crn, class_info in classes.items():
            # Check available seats
            available_seats = check_class_seats(
                class_info['subject'],
                class_info['course_number'],
                class_info['year'],
                class_info['term'],
                crn
            )
            
            # Update last known seat count
            previous_seats = class_info.get('last_available_seats')
            class_info['last_available_seats'] = available_seats
            
            # If seats became available (changed from 0 to >0), notify users
            if available_seats > 0 and (previous_seats == 0 or previous_seats is None):
                # Create notification message
                user_mentions = []
                for user_id in class_info['users_to_notify']:
                    user = bot.get_user(user_id)
                    if user:
                        user_mentions.append(user.mention)
                
                if user_mentions:
                    embed = discord.Embed(
                        title="🎉 Seats Available!",
                        description=f"**{class_info['subject']} {class_info['course_number']}** (CRN: {crn})",
                        color=0x0c6b41
                    )
                    embed.add_field(name="Available Seats", value=str(available_seats), inline=True)
                    embed.add_field(name="Term", value=f"{class_info['term']} {class_info['year']}", inline=True)
                    
                    mentions_text = " ".join(user_mentions)
                    await notify_channel.send(content=mentions_text, embed=embed)
    
    # Save data periodically
    save_data()

@seat_checker.before_loop
async def before_seat_checker():
    await bot.wait_until_ready()

# Run the bot
if __name__ == "__main__":
    # You need to replace 'YOUR_BOT_TOKEN' with your actual Discord bot token
    bot.run(BOT_TOKEN) 