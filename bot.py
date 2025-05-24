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

# Load environment variables
load_dotenv()

# Bot configuration
TOKEN = os.getenv('DISCORD_TOKEN')
CHANNEL_ID = int(os.getenv('COUNTDOWN_CHANNEL_ID'))
RELEASE_DATE = datetime.datetime(2025, 6, 4)
STEAM_APP_ID = "1671210"  # Deltarune's Steam App ID
STATE_FILE = "deltarune_bot_state.json"  # File to store state

# Set up intents
intents = discord.Intents.default()
intents.message_content = True

# Initialize bot
bot = commands.Bot(command_prefix='!', intents=intents)

# Game release status
game_released = False

# Message tracking variables - we'll load these from file
tomorrow_message_sent = False
release_message_sent = False

def load_state():
    """Load state from file"""
    global tomorrow_message_sent, release_message_sent
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                tomorrow_message_sent = state.get('tomorrow_message_sent', False)
                release_message_sent = state.get('release_message_sent', False)
                print(f"Loaded state: tomorrow_message_sent={tomorrow_message_sent}, release_message_sent={release_message_sent}")
    except Exception as e:
        print(f"Error loading state: {e}")

def save_state():
    """Save state to file"""
    try:
        state = {
            'tomorrow_message_sent': tomorrow_message_sent,
            'release_message_sent': release_message_sent
        }
        with open(STATE_FILE, 'w') as f:
            json.dump(state, f)
            print("State saved to file")
    except Exception as e:
        print(f"Error saving state: {e}")

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    # Load state from file
    load_state()
    # Start the tasks when bot is ready
    update_countdown.start()
    check_steam_status.start()
    
    # Sync the slash command
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(f"Error syncing commands: {e}")

async def is_game_released():
    """Check if the game is available on Steam"""
    global game_released
    
    # If we already know it's released, don't need to check again
    if game_released:
        return True
        
    try:
        async with aiohttp.ClientSession() as session:
            # Using the Steam Store API to get app details
            url = f"https://store.steampowered.com/api/appdetails?appids={STEAM_APP_ID}"
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    
                    # Check if game exists and is released
                    if STEAM_APP_ID in data and data[STEAM_APP_ID]['success']:
                        game_data = data[STEAM_APP_ID]['data']
                        
                        # Check if the game is released (not coming soon)
                        if not game_data.get('release_date', {}).get('coming_soon', True):
                            game_released = True
                            return True
    except Exception as e:
        print(f"Error checking Steam status: {e}")
    
    return False

@tasks.loop(minutes=1)
async def check_steam_status():
    """Check Steam API every minute for game availability"""
    global release_message_sent
    
    if await is_game_released() and not release_message_sent:
        # Game is available, update channel name
        channel = bot.get_channel(CHANNEL_ID)
        if channel:
            try:
                new_name = "deltarune-is-out-now"
                await channel.edit(name=new_name)
                print(f"Game released! Updated channel name to {new_name}")
                
                # Send announcement to the channel
                await channel.send("@everyone **DELTARUNE IS OUT NOW!** \n" + 
                                  "https://store.steampowered.com/app/1671210/DELTARUNE/")
                
                # Mark that we've sent the release message
                release_message_sent = True
                # Save updated state to file
                save_state()
                
                # Stop the daily countdown task since game is out
                update_countdown.cancel()
                
                # We only need to send this once, so stop this task
                check_steam_status.cancel()
            except Exception as e:
                print(f"Error updating channel for release: {e}")

@tasks.loop(minutes=5)
async def update_countdown():
    """Updates the channel name with days remaining until Deltarune release"""
    global tomorrow_message_sent
    
    # Check if game is already out first
    if await is_game_released():
        return
    
    # Get the countdown channel
    channel = bot.get_channel(CHANNEL_ID)
    
    if not channel:
        print(f"Error: Could not find channel with ID {CHANNEL_ID}")
        return
    
    # Calculate days remaining
    today = datetime.datetime.now()
    delta = RELEASE_DATE - today
    days_remaining = delta.days
    
    # Format the channel name
    if days_remaining > 1:
        new_name = f"deltarune-in-{days_remaining}-days"
    elif days_remaining == 1:
        new_name = "deltarune-tomorrow"
        # Send a message when there's only 1 day left, but only once
        if not tomorrow_message_sent:
            await channel.send("@everyone **DELTARUNE LAUNCHES TOMORROW!** \n" + 
                              "Get ready to play! The wait is almost over!")
            tomorrow_message_sent = True
            # Save updated state to file
            save_state()
            print("Sent 'tomorrow' notification")
    elif days_remaining == 0:
        new_name = "deltarune-releases-today"
    else:
        # Only handle channel name update here, not the announcement
        is_out = await is_game_released()
        new_name = "deltarune-is-out-now" if is_out else "deltarune-check-steam"

    # Update the channel name
    try:
        await channel.edit(name=new_name)
        print(f"Updated channel name to {new_name}")
    except discord.Forbidden:
        print("Error: Bot doesn't have permission to edit channel name")
    except discord.HTTPException as e:
        print(f"Error updating channel name: {e}")

# Add the countdown slash command
@app_commands.allowed_installs(guilds=True, users=True)
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@bot.tree.command(name="countdown", description="Get a visual countdown to Deltarune's release")
async def countdown_command(interaction: discord.Interaction):
    """Send a visual countdown image for Deltarune"""
    try:
        # Check if game is already released
        if await is_game_released():
            await interaction.response.send_message("Deltarune is out now! Go play it! https://store.steampowered.com/app/1671210/DELTARUNE/")
            return
        
        # Calculate time remaining
        now = datetime.datetime.now()
        delta = RELEASE_DATE - now
        
        # Get the countdown image as bytes buffer
        image_buffer = create_countdown_image(game_released)
        
        # Convert buffer to discord.File
        image_buffer.seek(0)  # Reset buffer position to beginning
        file = discord.File(fp=image_buffer, filename="deltarune_countdown.png")
        
        # Format the message based on time remaining
        days_remaining = delta.days
        if days_remaining > 1:
            message = f"**{days_remaining} days** until Deltarune releases!"
        elif days_remaining == 1:
            message = "**Deltarune launches tomorrow!** Get ready!"
        elif days_remaining == 0:
            message = "**Deltarune releases today!** Keep an eye on Steam!"
        else:
            message = "Deltarune should be releasing very soon! Check Steam!"
        
        # Send the response with the image
        await interaction.response.send_message(content=message, file=file)
        
    except Exception as e:
        print(f"Error in countdown command: {e}")
        await interaction.response.send_message("Sorry, I encountered an error generating the countdown image.", ephemeral=True)

# Run the bot
bot.run(TOKEN)
