from PIL import Image, ImageDraw, ImageFont, ImageOps
import datetime
import os
import math
import io

# --- Configuration ---
IMG_WIDTH = 600
IMG_HEIGHT = 450
BACKGROUND_COLOR = (0, 0, 0)  # Black
TEXT_COLOR_WHITE = (255, 255, 255)
TEXT_COLOR_YELLOW = (255, 255, 0)
TEXT_COLOR_GREY = (150, 150, 150)
TEXT_COLOR_RELEASED = TEXT_COLOR_WHITE

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

# TARGET_DATE is now passed as an argument to create_countdown_image

# --- Helper Function to Center Text within Padded Area ---
def draw_text_centered_padded(draw, text, y, font, fill, image_width, padding):
    available_width = image_width - (2 * padding)
    if available_width <= 0:
        print("Warning: Padding is too large for image width.")
        available_width = image_width

    try:
        # Pillow versions >= 9.2.0 prefer `anchor` in `textbbox` as well.
        # For older versions, anchor might not be available in textbbox.
        # We calculate based on left, top (lt) anchor for positioning.
        bbox_lt = draw.textbbox((padding, y), text, font=font) # Get bbox assuming (0,0) or a known point
        text_width = bbox_lt[2] - bbox_lt[0]
        text_height = bbox_lt[3] - bbox_lt[1]

        inner_x = (available_width - text_width) / 2
        x = padding + inner_x
        x = max(padding, x) # Ensure it doesn't go outside left padding

        draw.text((x, y), text, font=font, fill=fill) # Default anchor is 'la' (left, top of ascender)
                                                      # or 'lt' for some fonts/versions.
                                                      # For pixel fonts, 'lt' often works best.
        # Return the actual drawn bounding box
        final_bbox = (x, y, x + text_width, y + text_height)
        return final_bbox
    except Exception as e:
        print(f"Error drawing text '{text}': {e}")
        return None

# --- Main Image Creation ---
def create_countdown_image(game_released=False, target_date_override=None):
    """
    Creates countdown image with optional "Released!" state.

    Args:
        game_released (bool, optional): If True, displays "Released!"
                                         instead of the countdown timer.
                                         Defaults to False.
        target_date_override (datetime.datetime, optional): The specific release date to count down to.
                                                            If None, this function will not produce a valid countdown.
    Returns:
        io.BytesIO or None: An io.BytesIO buffer containing the PNG image
                            data, or None if an error occurs.
    """
    if target_date_override is None:
        print("Error: target_date_override is required for create_countdown_image.")
        return None
    
    effective_target_date = target_date_override

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
            if logo_img.mode == 'P' and 'transparency' in logo_img.info:
                logo_img = logo_img.convert('RGBA')
            elif logo_img.mode != 'RGB': # Ensure conversion if not RGB or RGBA (e.g. L, LA)
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
    except Exception as e:
        print(f"An error occurred loading font variants: {e}")
        return None

    release_text_formatted = f"Releasing on {effective_target_date.strftime('%B %d, %Y')}"
    timer_color = TEXT_COLOR_GREY

    if game_released:
        timer_text = "Released!"
        timer_color = TEXT_COLOR_RELEASED
    else:
        now = datetime.datetime.now()
        time_diff = effective_target_date - now

        if time_diff.total_seconds() <= 0: # Use <= to include the exact moment
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
            img.paste(logo_img, paste_position, logo_img)
        else:
             img.paste(logo_img, paste_position)
    except Exception as e:
        print(f"Error pasting logo: {e}")
        # Optionally return None here if logo is critical

    current_y = logo_y + logo_height + 20

    subtitle_bbox = draw_text_centered_padded(draw, "Chapters 1-4", current_y, font_subtitle, TEXT_COLOR_WHITE, IMG_WIDTH, PADDING)
    if subtitle_bbox:
        current_y = subtitle_bbox[3] + 45
    else: # Handle error if text drawing failed
        current_y += FONT_SIZE_SUBTITLE + 45 # Approximate advance


    date_bbox = draw_text_centered_padded(draw, release_text_formatted, current_y, font_date, TEXT_COLOR_YELLOW, IMG_WIDTH, PADDING)
    if date_bbox:
        current_y = date_bbox[3] + 25
    else:
        current_y += FONT_SIZE_DATE + 25 # Approximate advance


    # Check vertical space for timer text
    # Pillow's textbbox can be used to estimate height before drawing if needed
    # timer_test_bbox = draw.textbbox((PADDING, current_y), timer_text, font=font_timer)
    # timer_height = timer_test_bbox[3] - timer_test_bbox[1]
    # if current_y + timer_height > IMG_HEIGHT - PADDING:
    #      print(f"Warning: Timer text might extend below padding.")

    timer_bbox = draw_text_centered_padded(draw, timer_text, current_y, font_timer, timer_color, IMG_WIDTH, PADDING)
    # No need to advance current_y further if this is the last element

    try:
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        # print("Image successfully created in buffer.") # Less verbose for bot use
        return buffer
    except Exception as e:
        print(f"Error saving image to buffer: {e}")
        return None

if __name__ == "__main__":
    # Define the actual release date used by the bot for consistent testing
    actual_release_date_for_testing = datetime.datetime(2025, 6, 4, 0, 0, 0)

    # Ensure assets folder exists for standalone testing
    if not os.path.exists(os.path.join(_SCRIPT_DIR, "assets")):
        print(f"Error: 'assets' directory not found at {os.path.join(_SCRIPT_DIR, 'assets')}")
        print("Please create it and add 'pixel-font.ttf' and 'logo.png'.")
    else:
        print("\nGenerating countdown image (simulating 'not released')...")
        # Test with the actual release date
        image_buffer_countdown = create_countdown_image(
            game_released=False,
            target_date_override=actual_release_date_for_testing
        )
        if image_buffer_countdown:
            try:
                with open("deltarune_countdown_generated.png", "wb") as f:
                    f.write(image_buffer_countdown.getvalue())
                print("Saved countdown image: deltarune_countdown_generated.png")
            except Exception as e:
                print(f"Error saving countdown buffer: {e}")
        else:
            print("Failed to create countdown image buffer.")

        print("-" * 20)

        print("Generating 'Released!' image...")
        image_buffer_released = create_countdown_image(
            game_released=True,
            target_date_override=actual_release_date_for_testing
        )
        if image_buffer_released:
            try:
                with open("deltarune_released_generated.png", "wb") as f:
                    f.write(image_buffer_released.getvalue())
                print("Saved 'Released!' image: deltarune_released_generated.png")
            except Exception as e:
                print(f"Error saving released buffer: {e}")
        else:
            print("Failed to create 'Released!' image buffer.")

        print("-" * 20)
        print("Testing countdown to a future date (e.g., +1 day from now)")
        future_date_for_testing = datetime.datetime.now() + datetime.timedelta(days=1)
        image_buffer_future = create_countdown_image(
            game_released=False,
            target_date_override=future_date_for_testing
        )
        if image_buffer_future:
            try:
                with open("deltarune_future_countdown_generated.png", "wb") as f:
                    f.write(image_buffer_future.getvalue())
                print("Saved future countdown image: deltarune_future_countdown_generated.png")
            except Exception as e:
                print(f"Error saving future countdown buffer: {e}")
        else:
            print("Failed to create future countdown image buffer.")
