import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import os
import aiohttp
import asyncio
import json
from dotenv import load_dotenv
from countdown import create_countdown_image
import io
import pytz

# Load environment variables
load_dotenv()

# Bot configuration
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('COUNTDOWN_CHANNEL_ID'))

# Set RELEASE_DATE to match official Deltarune website: June 5, 2025 at 00:00 JST
# Using pytz for proper timezone handling
jst = pytz.timezone('Asia/Tokyo')
RELEASE_DATE = jst.localize(datetime.datetime(2025, 6, 5, 0, 0, 0))

STEAM_APP_ID = "1671210"  # Deltarune's Steam App ID
STATE_FILE = "deltarune_bot_state.json"  # File to store state

# Set up intents
intents = discord.Intents.default()
intents.message_content = True

# Initialize bot
bot = commands.Bot(command_prefix='!', intents=intents)

# Game release status (global, managed by tasks and API checks)
game_released = False

# Message tracking variables - we'll load these from file
tomorrow_message_sent = False
release_message_sent = False

def get_current_utc_time():
    """Get current time in UTC for consistent timezone handling"""
    return datetime.datetime.now(pytz.UTC)

def load_state():
    global tomorrow_message_sent, release_message_sent, game_released
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                tomorrow_message_sent = state.get('tomorrow_message_sent', False)
                release_message_sent = state.get('release_message_sent', False)
                game_released = state.get('game_released', False)
                print(f"Loaded state: tomorrow_message_sent={tomorrow_message_sent}, release_message_sent={release_message_sent}, game_released={game_released}")
        else:
            print("State file not found, starting with default state.")
    except Exception as e:
        print(f"Error loading state: {e}. Using default state.")
        tomorrow_message_sent = False
        release_message_sent = False
        game_released = False

def save_state():
    try:
        state = {
            'tomorrow_message_sent': tomorrow_message_sent,
            'release_message_sent': release_message_sent,
            'game_released': game_released
        }
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=4)
            print("State saved to file")
    except Exception as e:
        print(f"Error saving state: {e}")

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    load_state()

    # Start tasks only if the game hasn't been marked as released and announced
    if not game_released or not release_message_sent:
        update_countdown.start()
        check_steam_status.start()
        print("Countdown and Steam check tasks started.")
    else:
        print("Game already marked as released and announced. Tasks not started.")
        # Optionally, ensure channel name is correct if bot restarts after release
        channel = bot.get_channel(CHANNEL_ID)
        if channel and not channel.name.endswith("-is-out-now"):
            try:
                await channel.edit(name="deltarune-is-out-now")
                print("Corrected channel name to 'deltarune-is-out-now' on restart.")
            except Exception as e:
                print(f"Could not correct channel name on restart: {e}")

    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")

async def is_game_released_from_steam():
    """Check if the game is available on Steam. Does NOT modify global game_released directly."""
    try:
        async with aiohttp.ClientSession() as session:
            url = f"https://store.steampowered.com/api/appdetails?appids={STEAM_APP_ID}"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    if STEAM_APP_ID in data and data[STEAM_APP_ID]['success']:
                        game_data = data[STEAM_APP_ID]['data']
                        if not game_data.get('release_date', {}).get('coming_soon', True):
                            return True
    except Exception as e:
        print(f"Error checking Steam status: {e}")
    return False

@tasks.loop(minutes=1)
async def check_steam_status():
    global game_released, release_message_sent

    if game_released and release_message_sent:
        check_steam_status.cancel()
        print("Steam check: Game already released and announced. Task stopping.")
        return

    steam_confirms_release = await is_game_released_from_steam()

    if steam_confirms_release and not game_released:
        print("Steam API confirms game is released!")
        game_released = True
        save_state()

    if game_released and not release_message_sent:
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            try:
                new_name = "deltarune-is-out-now"
                if channel.name != new_name:
                    await channel.edit(name=new_name)
                print(f"Game released! Updated channel name to {new_name}")

                await channel.send("@everyone **DELTARUNE IS OUT NOW!** \n" +
                                  "https://store.steampowered.com/app/1671210/DELTARUNE/")
                print("Sent release announcement.")
                release_message_sent = True
                save_state()

                update_countdown.cancel()
                check_steam_status.change_interval(hours=24)
                print("Cancelled update_countdown task. Reduced check_steam_status frequency.")
            except Exception as e:
                print(f"Error updating channel/sending message for release: {e}")
    elif not steam_confirms_release and get_current_utc_time() > RELEASE_DATE.astimezone(pytz.UTC) + datetime.timedelta(days=1):
        check_steam_status.change_interval(hours=1)
        print("Past release date, game not detected as out. Reducing Steam check frequency.")

@tasks.loop(minutes=5)
async def update_countdown():
    global tomorrow_message_sent, game_released

    if game_released:
        print("Countdown update: Game is marked released. Task stopping.")
        update_countdown.cancel()
        return

    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print(f"Error: Could not find channel with ID {CHANNEL_ID} for countdown update.")
        return

    # Use timezone-aware time for consistent calculations
    current_utc = get_current_utc_time()
    # Convert release date to UTC for comparison
    release_date_utc = RELEASE_DATE.astimezone(pytz.UTC)
    delta = release_date_utc - current_utc
    days_remaining = delta.days
    hours_remaining = delta.seconds // 3600

    new_name = ""
    send_message_content = None

    if days_remaining > 1:
        new_name = f"deltarune-in-{days_remaining}-days"
    elif days_remaining == 1 or (days_remaining == 0 and hours_remaining > 12):
        # If less than 24 hours but more than 12 hours, still consider it "tomorrow"
        new_name = "deltarune-tomorrow"
        if not tomorrow_message_sent:
            send_message_content = ("@everyone **DELTARUNE LAUNCHES TOMORROW!** \n" +
                                    "Get ready to play! The wait is almost over!")
            tomorrow_message_sent = True
            save_state()
            print("Sent 'tomorrow' notification.")
    elif days_remaining == 0 and hours_remaining >= 0:
        # It's release day, but Steam API might not have confirmed yet.
        new_name = "deltarune-releases-today"
    else:  # RELEASE_DATE has passed
        new_name = "deltarune-check-steam"

    if new_name and channel.name != new_name:
        try:
            await channel.edit(name=new_name)
            print(f"Updated channel name to {new_name} (UTC time: {current_utc}, Days remaining: {days_remaining}, Hours remaining: {hours_remaining})")
        except discord.Forbidden:
            print("Error: Bot doesn't have permission to edit channel name.")
        except discord.HTTPException as e:
            print(f"Error updating channel name: {e}")

    if send_message_content:
        try:
            await channel.send(send_message_content)
        except Exception as e:
            print(f"Error sending scheduled message: {e}")

@bot.tree.command(name="countdown", description="Get a visual countdown to Deltarune's release")
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
async def countdown_command(interaction: discord.Interaction):
    global game_released
    
    await interaction.response.defer(ephemeral=False)

    try:
        # Use the global game_released status, which is updated by check_steam_status
        current_release_status_for_image = game_released
        if not current_release_status_for_image:
            current_release_status_for_image = await is_game_released_from_steam()
            if current_release_status_for_image and not game_released:
                game_released = True
                save_state()

        # The image generator needs the target date for its "Releasing on" text and countdown calc
        image_buffer = create_countdown_image(
            game_released=current_release_status_for_image,
            target_date_override=RELEASE_DATE
        )

        if image_buffer is None:
            await interaction.followup.send("Sorry, there was an error generating the countdown image.", ephemeral=True)
            return

        image_buffer.seek(0)
        file = discord.File(fp=image_buffer, filename="deltarune_status.png")
        text_message = ""

        if current_release_status_for_image:
            text_message = "Deltarune is out now! Go play it! https://store.steampowered.com/app/1671210/DELTARUNE/"
        else:
            # Use timezone-aware time for consistent calculations
            current_utc = get_current_utc_time()
            # Convert release date to UTC for comparison
            release_date_utc = RELEASE_DATE.astimezone(pytz.UTC)
            delta = release_date_utc - current_utc
            days_remaining = delta.days
            hours_remaining = delta.seconds // 3600
            total_hours = int(delta.total_seconds() // 3600)

            if total_hours > 48:
                text_message = f"**{days_remaining} days** until Deltarune's release date ({RELEASE_DATE.strftime('%B %d, %Y %H:%M JST')})!"
            elif total_hours > 24:
                text_message = f"**Deltarune releases tomorrow ({RELEASE_DATE.strftime('%B %d, %Y %H:%M JST')})!** Get ready!"
            elif total_hours > 0:
                text_message = f"**Deltarune releases today in {total_hours} hours ({RELEASE_DATE.strftime('%B %d, %Y %H:%M JST')})!** Keep an eye on Steam!"
            elif total_hours >= -12:  # Within 12 hours past release time
                text_message = f"**Deltarune should be releasing now ({RELEASE_DATE.strftime('%B %d, %Y %H:%M JST')})!** Check Steam!"
            else:  # RELEASE_DATE has passed by more than 12 hours
                text_message = (f"The target release date ({RELEASE_DATE.strftime('%B %d, %Y %H:%M JST')}) has passed. "
                                "It should be out or releasing very soon! Check Steam for the latest.")
                                
        await interaction.followup.send(content=text_message, file=file)

    except Exception as e:
        print(f"Error in countdown command: {e}")
        if not interaction.response.is_done():
            await interaction.response.send_message("Sorry, I encountered an error processing your request.", ephemeral=True)
        else:
            await interaction.followup.send("Sorry, I encountered an error processing your request.", ephemeral=True)

if __name__ == "__main__":
    if TOKEN is None or CHANNEL_ID is None:
        print("Error: DISCORD_TOKEN or COUNTDOWN_CHANNEL_ID not found in .env file or environment variables.")
    else:
        bot.run(TOKEN)
