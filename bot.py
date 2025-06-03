from PIL import Image, ImageDraw, ImageFont, ImageOps
import datetime
import os
import math
import io
import pytz

# --- Configuration ---
IMG_WIDTH = 600
IMG_HEIGHT = 450
BACKGROUND_COLOR = (0, 0, 0)  # Black
TEXT_COLOR_WHITE = (255, 255, 255)
TEXT_COLOR_YELLOW = (255, 255, 0)
TEXT_COLOR_GREY = (150, 150, 150)
# Optional: Define a specific color for the "Released!" text if desired
TEXT_COLOR_RELEASED = TEXT_COLOR_WHITE # Use white for "Released!"

# --- Padding ---
PADDING = 25

# --- Logo Scaling ---
LOGO_SCALE_FACTOR = 0.50

# --- File Paths ---
FONT_PATH = "assets/pixel-font.ttf"
LOGO_PATH = "assets/logo.png"

# --- Font Sizes ---
FONT_SIZE_SUBTITLE = 30
FONT_SIZE_DATE = 25
FONT_SIZE_TIMER = 40 # Font size for countdown AND "Released!" text

# --- Target Date ---
TARGET_DATE = datetime.datetime(2025, 6, 5, 0, 0, 0) # June 5, 2025, midnight
TIMEZONE = pytz.timezone('Asia/Tokyo') # Define the Japan timezone

# --- Helper Function to Center Text within Padded Area ---
def draw_text_centered_padded(draw, text, y, font, fill, image_width, padding):
    """Draws text horizontally centered within the padded area and returns its bounding box."""
    available_width = image_width - (2 * padding)
    if available_width <= 0:
        print("Warning: Padding is too large for image width.")
        available_width = image_width

    try:
        bbox = draw.textbbox((padding, y), text, font=font, anchor='lt')
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]

        inner_x = (available_width - text_width) / 2
        x = padding + inner_x
        x = max(padding, x)

        draw.text((x, y), text, font=font, fill=fill, anchor='lt')

        final_bbox = (x, y, x + text_width, y + text_height)
        return final_bbox
    except Exception as e:
        print(f"Error drawing text '{text}': {e}")
        return None

# --- Main Image Creation ---
def create_countdown_image(game_released=False): # Added game_released parameter
    """
    Creates countdown image with optional "Released!" state.

    Args:
        game_released (bool, optional): If True, displays "Released!"
                                         instead of the countdown timer.
                                         Defaults to False.

    Returns:
        io.BytesIO or None: An io.BytesIO buffer containing the PNG image
                            data, or None if an error occurs.
    """

    # --- Pre-checks ---
    if not os.path.exists(FONT_PATH):
        print(f"Error: Font file not found at '{FONT_PATH}'.")
        return None
    if not os.path.exists(LOGO_PATH):
        print(f"Error: Logo file not found at '{LOGO_PATH}'.")
        return None

    # --- Load and Resize Logo ---
    try:
        logo_img_original = Image.open(LOGO_PATH)
        original_width, original_height = logo_img_original.size
        new_width = int(original_width * LOGO_SCALE_FACTOR)
        new_height = int(original_height * LOGO_SCALE_FACTOR)
        logo_img = logo_img_original.resize((new_width, new_height), Image.Resampling.NEAREST)

        if logo_img.mode != 'RGBA':
            if logo_img.mode == 'P' and 'transparency' in logo_img.info:
                logo_img = logo_img.convert('RGBA')
            elif logo_img.mode != 'RGB':
                 logo_img = logo_img.convert('RGBA')
        logo_width, logo_height = logo_img.size
    except Exception as e:
        print(f"Error opening, resizing, or processing logo image '{LOGO_PATH}': {e}")
        return None

    # --- Calculate Logo Position ---
    logo_x = (IMG_WIDTH - logo_width) // 2
    logo_y = PADDING

    # --- Create Base Image ---
    img = Image.new('RGB', (IMG_WIDTH, IMG_HEIGHT), color=BACKGROUND_COLOR)
    draw = ImageDraw.Draw(img)

    # Load fonts
    try:
        font_subtitle = ImageFont.truetype(FONT_PATH, FONT_SIZE_SUBTITLE)
        font_date = ImageFont.truetype(FONT_PATH, FONT_SIZE_DATE)
        font_timer = ImageFont.truetype(FONT_PATH, FONT_SIZE_TIMER) # Used for timer & "Released!"
    except Exception as e:
        print(f"An error occurred loading font variants: {e}")
        return None

    # --- Determine Text Content based on game_released ---
    # Always format the date text
    release_text_formatted = f"Releasing on {TARGET_DATE.strftime('%B %d, %Y').replace(f' {TARGET_DATE.day},', f' {TARGET_DATE.day:02d},')}"

    timer_color = TEXT_COLOR_GREY # Default color for countdown

    if game_released:
        timer_text = "Released!"
        timer_color = TEXT_COLOR_RELEASED # Use specific color for released state
    else:
        # Calculate Countdown only if not released
        now = datetime.datetime.now(TIMEZONE) # Get current time in Japan timezone
        target_date_localized = TIMEZONE.localize(TARGET_DATE) # Localize TARGET_DATE to Japan timezone
        time_diff = target_date_localized - now

        if time_diff.total_seconds() < 0:
            # If date passed but game_released wasn't explicitly set to True, show 0s
            days, hours, minutes, seconds = 0, 0, 0, 0
            # Optionally, you could auto-set timer_text to "Released!" here too
            # timer_text = "Released!"
            # timer_color = TEXT_COLOR_RELEASED
            timer_text = f"{days:02d} : {hours:02d} : {minutes:02d} : {seconds:02d}"

        else:
            days = time_diff.days
            remaining_seconds = time_diff.seconds
            hours = remaining_seconds // 3600
            minutes = (remaining_seconds % 3600) // 60
            seconds = remaining_seconds % 60
            timer_text = f"{days:02d} : {hours:02d} : {minutes:02d} : {seconds:02d}"


    # --- Draw Elements ---

    # 1. Paste Resized Logo
    try:
        paste_position = (logo_x, logo_y)
        if logo_img.mode == 'RGBA':
            img.paste(logo_img, paste_position, logo_img)
        else:
             img.paste(logo_img, paste_position)
    except Exception as e:
        print(f"Error pasting logo: {e}")

    current_y = logo_y + logo_height + 20

    # 2. Draw Subtitle
    subtitle_bbox = draw_text_centered_padded(draw, "Chapters 1-4", current_y, font_subtitle, TEXT_COLOR_WHITE, IMG_WIDTH, PADDING)
    if subtitle_bbox:
        current_y = subtitle_bbox[3] + 45

    # 3. Draw Release Date Text (Always drawn for now)
    date_bbox = draw_text_centered_padded(draw, release_text_formatted, current_y, font_date, TEXT_COLOR_YELLOW, IMG_WIDTH, PADDING)
    if date_bbox:
        current_y = date_bbox[3] + 25

    # 4. Draw Timer or "Released!" Text
    timer_test_bbox = draw.textbbox((PADDING, current_y), timer_text, font=font_timer, anchor='lt')
    timer_height = timer_test_bbox[3] - timer_test_bbox[1]
    bottom_limit = IMG_HEIGHT - PADDING

    if current_y + timer_height > bottom_limit:
         print(f"Warning: Bottom text might extend below padding.")

    # Draw the final text (either countdown or "Released!") using the determined color
    timer_bbox = draw_text_centered_padded(draw, timer_text, current_y, font_timer, timer_color, IMG_WIDTH, PADDING)


    # --- Save to Buffer ---
    try:
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        print("Image successfully created in buffer.")
        return buffer
    except Exception as e:
        print(f"Error saving image to buffer: {e}")
        return None


# Run the bot
bot.run(TOKEN)
