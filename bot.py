import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
import os
import aiohttp
import asyncio
import json
from dotenv import load_dotenv
from countdown import create_countdown_image # Correctly imported
import io
import pytz # Import pytz

# Load environment variables
load_dotenv()

# Bot configuration
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('COUNTDOWN_CHANNEL_ID'))
# Set RELEASE_DATE to midnight of the specific day in Japan timezone
JAPAN_TIMEZONE = pytz.timezone('Asia/Tokyo')
RELEASE_DATE_JST = datetime.datetime(2025, 6, 5, 0, 0, 0, tzinfo=JAPAN_TIMEZONE) # Midnight JST

STEAM_APP_ID = "1671210"  # Deltarune's Steam App ID
STATE_FILE = "deltarune_bot_state.json"  # File to store state

# Set up intents
intents = discord.Intents.default()
intents.message_content = True # Only if you use message content commands, not needed for slash commands only

# Initialize bot
bot = commands.Bot(command_prefix='!', intents=intents) # Prefix not strictly needed for slash-only bot

# Game release status (global, managed by tasks and API checks)
game_released = False

# Message tracking variables - we'll load these from file
tomorrow_message_sent = False
release_message_sent = False

def load_state():
    global tomorrow_message_sent, release_message_sent, game_released
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                tomorrow_message_sent = state.get('tomorrow_message_sent', False)
                release_message_sent = state.get('release_message_sent', False)
                # Persist game_released state as well, so if bot restarts after release, it knows.
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
            'game_released': game_released # Save game_released state
        }
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f, indent=4) # Added indent for readability
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

async def is_game_released_from_steam(): # Renamed to avoid confusion with global var
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
                            return True # Game is released on Steam
    except Exception as e:
        print(f"Error checking Steam status: {e}")
    return False

@tasks.loop(minutes=1) # Check frequently before release
async def check_steam_status():
    global game_released, release_message_sent

    if game_released and release_message_sent: # Already handled
        check_steam_status.cancel()
        print("Steam check: Game already released and announced. Task stopping.")
        return

    steam_confirms_release = await is_game_released_from_steam()

    if steam_confirms_release and not game_released: # Steam says released, and we haven't globally marked it
        print("Steam API confirms game is released!")
        game_released = True # Update global state
        save_state() # Save immediately

    if game_released and not release_message_sent: # Global state says released, but announcement not sent
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

                update_countdown.cancel() # Stop daily countdown
                check_steam_status.change_interval(hours=24) # Reduce frequency after release, or cancel
                print("Cancelled update_countdown task. Reduced check_steam_status frequency.")
                # check_steam_status.cancel() # Or stop it entirely
            except Exception as e:
                print(f"Error updating channel/sending message for release: {e}")
    elif not steam_confirms_release and datetime.datetime.now(JAPAN_TIMEZONE) > RELEASE_DATE_JST + datetime.timedelta(days=1) :
        # If past release date significantly and still not out, reduce check frequency
        check_steam_status.change_interval(hours=1)
        print("Past release date, game not detected as out. Reducing Steam check frequency.")


@tasks.loop(minutes=5)
async def update_countdown():
    global tomorrow_message_sent, game_released

    if game_released: # If global state says released, stop this task.
        print("Countdown update: Game is marked released. Task stopping.")
        update_countdown.cancel()
        return

    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print(f"Error: Could not find channel with ID {CHANNEL_ID} for countdown update.")
        return

    today = datetime.datetime.now(JAPAN_TIMEZONE)  # Get current time in Japan timezone
    delta = RELEASE_DATE_JST - today
    total_seconds = delta.total_seconds()
    hours_remaining = int(total_seconds // 3600)
    days_remaining = delta.days

    new_name = ""
    send_message_content = None

    if days_remaining > 1:
        new_name = f"deltarune-in-{days_remaining}-days"
    elif days_remaining == 1:
        new_name = "deltarune-tomorrow"
        if not tomorrow_message_sent:
            send_message_content = ("@everyone **DELTARUNE LAUNCHES TOMORROW!** \n" +
                                    "Get ready to play! The wait is almost over!")
            tomorrow_message_sent = True
            save_state() # Save state after marking message sent
            print("Sent 'tomorrow' notification.")
    elif days_remaining == 0 and hours_remaining > 0:
        new_name = f"deltarune-in-{hours_remaining}-hours"
    elif days_remaining == 0 and hours_remaining <= 0:
        # It's release day, but Steam API might not have confirmed yet.
        # check_steam_status will handle the "is-out-now" change when confirmed.
        new_name = "deltarune-releases-today"
    else: # days_remaining < 0 (RELEASE_DATE has passed)
        # If RELEASE_DATE has passed but game_released is still False,
        # check_steam_status is still looking. Channel name reflects uncertainty.
        new_name = "deltarune-check-steam"
        # This also means the game might be delayed, or our RELEASE_DATE was early.

    if new_name and channel.name != new_name:
        try:
            await channel.edit(name=new_name)
            print(f"Updated channel name to {new_name}")
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
    await interaction.response.defer(ephemeral=False) # Defer for image generation

    try:
        # Use the global game_released status, which is updated by check_steam_status
        # For the command, we can also do a fresh check if not globally marked yet
        current_release_status_for_image = game_released
        if not current_release_status_for_image: # If not globally marked, do a quick check
            current_release_status_for_image = await is_game_released_from_steam()
            if current_release_status_for_image and not game_released: # Update global if fresh check finds it
                global game_released_global_ref
                game_released_global_ref = True # Access global game_released for update
                save_state()


        # The image generator needs the target date for its "Releasing on" text and countdown calc
        image_buffer = create_countdown_image(
            game_released=current_release_status_for_image,
            target_date_override=RELEASE_DATE_JST
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
            now = datetime.datetime.now(JAPAN_TIMEZONE)
            delta = RELEASE_DATE_JST - now
            total_seconds = delta.total_seconds()
            hours_remaining = int(total_seconds // 3600)
            days_remaining = delta.days

            if days_remaining > 1:
                text_message = f"**{days_remaining} days** until Deltarune's target release date ({RELEASE_DATE_JST.strftime('%B %d, %Y')})!"
            elif days_remaining == 1:
                text_message = f"**Deltarune's target release is tomorrow ({RELEASE_DATE_JST.strftime('%B %d, %Y')})!** Get ready!"
            elif days_remaining == 0 and hours_remaining > 1:
                text_message = f"**{hours_remaining} hours** until Deltarune's target release date ({RELEASE_DATE_JST.strftime('%B %d, %Y')})!"
            elif days_remaining == 0 and hours_remaining == 1:
                text_message = f"**{hours_remaining} hour** until Deltarune's target release date ({RELEASE_DATE_JST.strftime('%B %d, %Y')})!"
            elif days_remaining == 0 and hours_remaining <= 0:
                text_message = f"**Deltarune's target release is today ({RELEASE_DATE_JST.strftime('%B %d, %Y')})!** Keep an eye on Steam!"
            else: # RELEASE_DATE has passed, but not confirmed released by Steam via current_release_status_for_image
                text_message = (f"The target release date ({RELEASE_DATE_JST.strftime('%B %d, %Y')}) has passed. "
                                "It should be out or releasing very soon! Check Steam for the latest.")

        await interaction.followup.send(content=text_message, file=file)

    except Exception as e:
        print(f"Error in countdown command: {e}")
        # Check if already responded to avoid "Interaction already responded"
        if not interaction.response.is_done():
            await interaction.response.send_message("Sorry, I encountered an error processing your request.", ephemeral=True)
        else:
            await interaction.followup.send("Sorry, I encountered an error processing your request.", ephemeral=True)

# This is needed to modify global game_released within countdown_command if a fresh check is done.
# A cleaner way would be to pass bot instance or use a class for the cog.
game_released_global_ref = game_released

if __name__ == "__main__":
    if TOKEN is None or CHANNEL_ID is None:
        print("Error: DISCORD_TOKEN or COUNTDOWN_CHANNEL_ID not found in .env file or environment variables.")
    else:
        bot.run(TOKEN)
