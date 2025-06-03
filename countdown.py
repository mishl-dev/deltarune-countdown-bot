from PIL import Image, ImageDraw, ImageFont, ImageOps
import datetime
import os
import math
import io
# import pytz # Not strictly needed here if target_date_override is already aware

# --- Configuration ---
IMG_WIDTH = 600
IMG_HEIGHT = 450
BACKGROUND_COLOR = (0, 0, 0)  # Black
TEXT_COLOR_WHITE = (255, 255, 255)
TEXT_COLOR_YELLOW = (255, 255, 0)
TEXT_COLOR_RELEASED = TEXT_COLOR_WHITE
TEXT_COLOR_TIMER_COUNTDOWN = (173, 173, 173) # For timer when counting down
TEXT_COLOR_FOOTNOTE = (204, 204, 204)      # For the new footnote

# --- Padding ---
PADDING = 25

# --- Logo Scaling ---
LOGO_SCALE_FACTOR = 0.50

# --- File Paths (relative to this script) ---
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FONT_PATH = os.path.join(_SCRIPT_DIR, "assets/pixel-font.ttf")
LOGO_PATH = os.path.join(_SCRIPT_DIR, "assets/logo.png")


# --- Font Sizes ---
FONT_SIZE_SUBTITLE = 30
FONT_SIZE_DATE = 25
FONT_SIZE_TIMER = 40
FONT_SIZE_FOOTNOTE = 18

# --- Hardcoded Footnote Text ---
FOOTNOTE_TEXT_HARDCODED = "* June 5 in Japan, Australia, and New Zealand"

# --- Helper Function to Center Text within Padded Area ---
def draw_text_centered_padded(draw, text, y, font, fill, image_width, padding):
    available_width = image_width - (2 * padding)
    if available_width <= 0:
        print("Warning: Padding is too large for image width.")
        available_width = image_width

    try:
        # Use textbbox for better centering, especially with variable-width fonts
        # (left, top, right, bottom)
        bbox_lt = draw.textbbox((padding, y), text, font=font) # anchor 'lt' is default for textbbox
        text_width = bbox_lt[2] - bbox_lt[0]
        text_height = bbox_lt[3] - bbox_lt[1]

        # Calculate x for centering within the padded area
        inner_x = (available_width - text_width) / 2
        x = padding + inner_x
        x = max(padding, x) # Ensure text doesn't go outside left padding

        draw.text((x, y), text, font=font, fill=fill)
        # Return the actual drawn bounding box for layout purposes
        final_bbox = (x, y, x + text_width, y + text_height)
        return final_bbox
    except Exception as e:
        print(f"Error drawing text '{text}': {e}")
        return None

# --- Main Image Creation ---
def create_countdown_image(game_released=False, target_date_override=None):
    """
    Creates countdown image with optional "Released!" state and a hardcoded JST footnote.
    The displayed date in the image will be "June 4, YYYY" while the countdown
    target remains based on target_date_override.

    Args:
        game_released (bool, optional): If True, displays "Released!"
                                         instead of the countdown timer and hides footnote.
                                         Defaults to False.
        target_date_override (datetime.datetime, optional): The specific release date to count down to.
                                                            Should be offset-aware for accurate countdown.
                                                            If None, this function will not produce a valid countdown.
    Returns:
        io.BytesIO or None: An io.BytesIO buffer containing the PNG image
                            data, or None if an error occurs.
    """
    if target_date_override is None:
        print("Error: target_date_override is required for create_countdown_image.")
        return None
    
    effective_target_date = target_date_override # This is June 5 JST for the *actual* countdown

    if not os.path.exists(FONT_PATH):
        print(f"Error: Font file not found at '{FONT_PATH}'. Ensure 'assets' folder is next to countdown.py.")
        return None
    if not os.path.exists(LOGO_PATH):
        print(f"Error: Logo file not found at '{LOGO_PATH}'. Ensure 'assets' folder is next to countdown.py.")
        return None

    try:
        logo_img_original = Image.open(LOGO_PATH)
        original_width, original_height = logo_img_original.size
        new_width = int(original_width * LOGO_SCALE_FACTOR)
        new_height = int(original_height * LOGO_SCALE_FACTOR)
        logo_img = logo_img_original.resize((new_width, new_height), Image.Resampling.NEAREST)

        if logo_img.mode != 'RGBA':
            # Attempt to convert to RGBA if it's palettized with transparency
            if logo_img.mode == 'P' and 'transparency' in logo_img.info:
                logo_img = logo_img.convert('RGBA')
            elif logo_img.mode != 'RGB': # Convert other modes like 'L' or 'CMYK' to RGBA for consistency
                 logo_img = logo_img.convert('RGBA')
        logo_width, logo_height = logo_img.size
    except Exception as e:
        print(f"Error opening, resizing, or processing logo image '{LOGO_PATH}': {e}")
        return None

    logo_x = (IMG_WIDTH - logo_width) // 2
    logo_y = PADDING

    img = Image.new('RGB', (IMG_WIDTH, IMG_HEIGHT), color=BACKGROUND_COLOR)
    draw = ImageDraw.Draw(img)

    try:
        font_subtitle = ImageFont.truetype(FONT_PATH, FONT_SIZE_SUBTITLE)
        font_date = ImageFont.truetype(FONT_PATH, FONT_SIZE_DATE)
        font_timer = ImageFont.truetype(FONT_PATH, FONT_SIZE_TIMER)
        font_footnote = ImageFont.truetype(FONT_PATH, FONT_SIZE_FOOTNOTE)
    except Exception as e:
        print(f"An error occurred loading font variants: {e}")
        return None

    # MODIFICATION: Change display date to June 4, but keep year from actual target
    # The year is derived from effective_target_date (which is June 5, 2025 JST)
    # This makes the displayed date "June 4, 2025"
    release_date_display_text = f"Releasing on June 4, {effective_target_date.strftime('%Y')}"
    
    timer_color_actual = TEXT_COLOR_TIMER_COUNTDOWN

    if game_released:
        timer_text = "Released!"
        timer_color_actual = TEXT_COLOR_RELEASED
    else:
        # Countdown logic still uses the precise effective_target_date (June 5 JST)
        if effective_target_date.tzinfo is not None:
            now = datetime.datetime.now(effective_target_date.tzinfo)
        else:
            # This case should ideally not happen if target_date_override is always tz-aware
            print("Warning: effective_target_date is naive. Countdown might be inaccurate if a specific timezone was intended.")
            now = datetime.datetime.now() 
        
        time_diff = effective_target_date - now

        if time_diff.total_seconds() <= 0:
            # Game is past release time according to target_date_override
            days, hours, minutes, seconds = 0, 0, 0, 0
            timer_text = f"{days:02d} : {hours:02d} : {minutes:02d} : {seconds:02d}"
        else:
            days = time_diff.days
            remaining_seconds = time_diff.seconds
            hours = remaining_seconds // 3600
            minutes = (remaining_seconds % 3600) // 60
            seconds = remaining_seconds % 60
            timer_text = f"{days:02d} : {hours:02d} : {minutes:02d} : {seconds:02d}"

    try:
        paste_position = (logo_x, logo_y)
        if logo_img.mode == 'RGBA':
            img.paste(logo_img, paste_position, logo_img) # Use logo's alpha channel as mask
        else:
             img.paste(logo_img, paste_position) # No alpha mask needed or available
    except Exception as e:
        print(f"Error pasting logo: {e}")

    current_y = logo_y + logo_height + 20 # Start Y-position below the logo

    subtitle_bbox = draw_text_centered_padded(draw, "Chapters 1-4", current_y, font_subtitle, TEXT_COLOR_WHITE, IMG_WIDTH, PADDING)
    if subtitle_bbox:
        current_y = subtitle_bbox[3] + 45 # Y-pos for next element is bottom of current + spacing
    else:
        current_y += FONT_SIZE_SUBTITLE + 45 # Fallback if drawing fails

    date_bbox = draw_text_centered_padded(draw, release_date_display_text, current_y, font_date, TEXT_COLOR_YELLOW, IMG_WIDTH, PADDING)
    if date_bbox:
        current_y = date_bbox[3] + 25
    else:
        current_y += FONT_SIZE_DATE + 25

    timer_bbox = draw_text_centered_padded(draw, timer_text, current_y, font_timer, timer_color_actual, IMG_WIDTH, PADDING)
    if timer_bbox:
        current_y = timer_bbox[3] + 25 # Increased spacing after timer
    else:
        current_y += FONT_SIZE_TIMER + 25 # Increased spacing
    
    # Only draw footnote if game is not released
    if not game_released:
        footnote_bbox = draw_text_centered_padded(draw, FOOTNOTE_TEXT_HARDCODED, current_y, font_footnote, TEXT_COLOR_FOOTNOTE, IMG_WIDTH, PADDING)
        # if footnote_bbox:
        #     current_y = footnote_bbox[3] + PADDING # Update if more elements were below

    try:
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        return buffer
    except Exception as e:
        print(f"Error saving image to buffer: {e}")
        return None

if __name__ == "__main__":
    import pytz # Import for testing with aware datetimes
    JST = pytz.timezone('Asia/Tokyo')
    
    # This is the ACTUAL release time (June 5 JST), used for countdown calculation
    actual_release_date_for_testing = datetime.datetime(2025, 6, 5, 0, 0, 0, tzinfo=JST)

    # Create assets directory if it doesn't exist for local testing
    if not os.path.exists(os.path.join(_SCRIPT_DIR, "assets")):
        print(f"Warning: 'assets' directory not found at {os.path.join(_SCRIPT_DIR, 'assets')}")
        print("Please create it and add 'pixel-font.ttf' and 'logo.png' for local testing.")
    else:
        print("\nGenerating countdown image (simulating 'not released' with June 4 display date)...")
        image_buffer_countdown = create_countdown_image(
            game_released=False,
            target_date_override=actual_release_date_for_testing 
        )
        if image_buffer_countdown:
            try:
                with open("deltarune_countdown_june4_display.png", "wb") as f:
                    f.write(image_buffer_countdown.getvalue())
                print("Saved countdown image: deltarune_countdown_june4_display.png")
                print("It should display 'Releasing on June 4, 2025' but count down to June 5 JST.")
            except Exception as e:
                print(f"Error saving countdown buffer: {e}")
        else:
            print("Failed to create countdown image buffer.")

        print("-" * 20)

        print("Generating 'Released!' image (footnote should NOT appear)...")
        image_buffer_released = create_countdown_image(
            game_released=True,
            target_date_override=actual_release_date_for_testing # Target date still needed for year
        )
        if image_buffer_released:
            try:
                with open("deltarune_released_june4_display.png", "wb") as f:
                    f.write(image_buffer_released.getvalue())
                print("Saved 'Released!' image: deltarune_released_june4_display.png")
                print("It should display 'Releasing on June 4, 2025' and 'Released!' text.")
            except Exception as e:
                print(f"Error saving released buffer: {e}")
        else:
            print("Failed to create 'Released!' image buffer.")
