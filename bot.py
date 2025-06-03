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

    if not game_released or not release_message_sent:
        update_countdown.start()
        check_steam_status.start()
        print("Countdown and Steam check tasks started.")
    else:
        print("Game already marked as released and announced. Tasks not started.")
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
    global game_released, release_message_sent # Correctly at the top of the function

    if game_released and release_message_sent:
        check_steam_status.cancel()
        print("Steam check: Game already released and announced. Task stopping.")
        return

    steam_confirms_release = await is_game_released_from_steam()

    if steam_confirms_release and not game_released:
        print("Steam API confirms game is released!")
        game_released = True # Modifies global
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
                                  f"https://store.steampowered.com/app/{STEAM_APP_ID}/DELTARUNE/")
                print("Sent release announcement.")
                release_message_sent = True # Modifies global
                save_state()

                update_countdown.cancel()
                check_steam_status.change_interval(hours=24) # Keep checking, but very infrequently, e.g. if bot restarts after a while
                print("Cancelled update_countdown task. Reduced check_steam_status frequency.")
            except Exception as e:
                print(f"Error updating channel/sending message for release: {e}")
    elif not steam_confirms_release and datetime.datetime.now(JAPAN_TIMEZONE) > RELEASE_DATE_JST + datetime.timedelta(days=1) :
        check_steam_status.change_interval(hours=1)
        print("Past release date, game not detected as out. Reducing Steam check frequency to hourly.")


@tasks.loop(minutes=5)
async def update_countdown():
    global tomorrow_message_sent, game_released # Correctly at the top

    if game_released:
        print("Countdown update: Game is marked released. Task stopping.")
        update_countdown.cancel()
        return

    channel = bot.get_channel(CHANNEL_ID)
    if not channel:
        print(f"Error: Could not find channel with ID {CHANNEL_ID} for countdown update.")
        return

    today = datetime.datetime.now(JAPAN_TIMEZONE)
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
            # ******** MODIFICATION START: Specify JST in "tomorrow" announcement ********
            target_dt_str_for_announcement = RELEASE_DATE_JST.strftime('%B %d, %Y at %I:%M %p %Z')
            send_message_content = (f"@everyone **DELTARUNE LAUNCHES TOMORROW!** (Target: {target_dt_str_for_announcement})\n" +
                                    "Get ready to play! The wait is almost over!")
            # ******** MODIFICATION END ********
            tomorrow_message_sent = True # Modifies global
            save_state()
            print("Sent 'tomorrow' notification.")
    elif days_remaining == 0 and hours_remaining > 0:
        new_name = f"deltarune-in-{hours_remaining}-hours"
    elif days_remaining == 0 and hours_remaining <= 0: # Could also be < 0 if loop runs slightly late
        new_name = "deltarune-releases-today" # Or "deltarune-imminent"
    else: # days_remaining < 0 (release date has passed)
        new_name = "deltarune-check-steam" # Or "deltarune-should-be-out"

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
    await interaction.response.defer(ephemeral=False)

    global game_released

    try:
        current_release_status_for_image = game_released

        if not current_release_status_for_image:
            steam_check_result = await is_game_released_from_steam()
            if steam_check_result:
                current_release_status_for_image = True
                if not game_released:
                    game_released = True
                    save_state()

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

        # ******** MODIFICATION START: Use detailed date string with JST ********
        target_dt_str = RELEASE_DATE_JST.strftime('%B %d, %Y at %I:%M %p %Z') # e.g., June 05, 2025 at 12:00 AM JST
        # ******** MODIFICATION END ********

        if current_release_status_for_image:
            text_message = f"Deltarune is out now! Go play it! https://store.steampowered.com/app/{STEAM_APP_ID}/DELTARUNE/"
        else:
            now = datetime.datetime.now(JAPAN_TIMEZONE)
            delta = RELEASE_DATE_JST - now
            total_seconds = delta.total_seconds()
            hours_remaining = int(total_seconds // 3600)
            days_remaining = delta.days

            # ******** MODIFICATION START: Update text messages to use target_dt_str and adjust phrasing ********
            if days_remaining > 1:
                text_message = f"**{days_remaining} days** until Deltarune releases (target: {target_dt_str})!"
            elif days_remaining == 1:
                text_message = f"**Deltarune releases tomorrow!** (Target: {target_dt_str}) Get ready!"
            elif days_remaining == 0 and hours_remaining > 1:
                text_message = f"**{hours_remaining} hours** until Deltarune releases (target: {target_dt_str})!"
            elif days_remaining == 0 and hours_remaining == 1:
                text_message = f"**{hours_remaining} hour** until Deltarune releases (target: {target_dt_str})!"
            elif days_remaining == 0 and hours_remaining <= 0: # Could be <0 if command is run just after release time but before Steam check
                text_message = f"**Deltarune releases today!** (Target: {target_dt_str}) Keep an eye on Steam!"
            else: # days_remaining < 0
                text_message = (f"The target release time ({target_dt_str}) has passed. "
                                "It should be out or releasing very soon! Check Steam for the latest.")
            # ******** MODIFICATION END ********

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
