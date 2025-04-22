import streamlit as st
import pymongo
import google.generativeai as genai
import os
import requests
import io
from PIL import Image
from dotenv import load_dotenv
import base64
import json
import re
from datetime import datetime
import streamlit.components.v1 as components
from urllib.parse import urljoin
from bson import ObjectId # Needed for deleting by ID

from PIL import Image, UnidentifiedImageError
from io import BytesIO
import hashlib
import time
import json
from bs4 import BeautifulSoup  # You'll need to install this: pip install beautifulsoup4
from typing import Union, Optional, Tuple

# --- Configuration ---
load_dotenv()

# Configure API keys
# GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
# MONGODB_URI = os.getenv("MONGODB_URI")
GEMINI_API_KEY = st.secrets["GEMINI_API_KEY"]
MONGODB_URI = st.secrets["MONGODB_URI"]


# Check if keys are loaded
if not GEMINI_API_KEY:
    st.error("❌ Gemini API Key not found. Please set the GEMINI_API_KEY environment variable.")
    st.stop()
if not MONGODB_URI:
    st.error("❌ MongoDB URI not found. Please set the MONGODB_URI environment variable.")
    st.stop()


# Configure Gemini
try:
    genai.configure(api_key=GEMINI_API_KEY)
except Exception as e:
    st.error(f"❌ Error configuring Gemini: {e}")
    st.stop()

# --- MongoDB Connection ---
try:
    client = pymongo.MongoClient(MONGODB_URI)
    db = client["recipe_keeper"]
    recipes_collection = db["recipes"]
    # Test connection
    client.admin.command('ping')
    # print("Successfully connected to MongoDB!") # Optional: for debugging
except pymongo.errors.ConnectionFailure as e:
    st.error(f"❌ Could not connect to MongoDB: {e}")
    st.stop()
except Exception as e:
    st.error(f"❌ An unexpected error occurred during MongoDB setup: {e}")
    st.stop()


# --- MongoDB Text Index ---
# Create text index for natural language search (run once)
try:
    recipes_collection.create_index(
        [
            ("title", "text"),
            ("ingredients", "text"),
            ("instructions", "text"),
            ("cuisine", "text"),
            ("meal_type", "text"),
            ("description", "text"),
            ("keywords", "text"),
        ],
        name="recipe_text_index" # Give the index a name
    )
    # print("Text index ensured.") # Optional: for debugging
except Exception as e:
    # It's okay if index already exists, but log other errors
    if "index already exists" not in str(e):
         print(f"Warning: Could not ensure text index: {e}")
    pass # Silently handle index existence

# --- Hebrew Translations ---
TRANSLATIONS = {
    "app_title": "המתכונים של ערגה",
    "add_recipe": "הוספת מתכון",
    "my_recipes": "המתכונים שלי",
    "search_recipes": "חיפוש מתכונים",
    "add_from_url": "מקישור אינטרנט",
    "add_from_image": "מתמונה",
    "enter_url": "הכניסי קישור (URL) למתכון:",
    "extract_recipe": "🔎 חלצי מתכון",
    "upload_image": "📷 העלי תמונת מתכון:",
    "extract_from_image": "🖼️ חלצי מתכון מתמונה",
    "recipe_preview": "תצוגה מקדימה של המתכון:",
    "save_recipe": "💾 שמרי מתכון",
    "recipe_saved": "✅ המתכון נשמר בהצלחה!",
    "extraction_failed": "⚠️ חילוץ המתכון נכשל. בדקי את המקור או נסי שוב.",
    "recipe_collection": "📖 אוסף המתכונים שלי",
    "refresh_recipes": "🔄 רענני רשימה",
    "no_recipes": "עדיין לא שמרת מתכונים.",
    "you_have": "יש לך",
    "saved_recipes": "מתכונים שמורים.",
    "filter_recipes": "סינון מתכונים",
    "cuisine": "מטבח",
    "meal_type": "סוג ארוחה",
    "all": "הכל",
    "search_placeholder": "הקלידי מילות חיפוש (למשל: 'עוגת שוקולד קלה')...",
    "searching": "🔍 מחפשת...",
    "found": "נמצאו",
    "matching_recipes": "מתכונים תואמים.",
    "no_matches": "לא נמצאו מתכונים תואמים לשאילתה שלך.",
    "ingredients": "מצרכים",
    "instructions": "הוראות הכנה",
    "tags": "תגיות",
    "prep_time": "זמן הכנה",
    "cook_time": "זמן בישול",
    "total_time": "זמן כולל",
    "serves": "מספר מנות",
    "view_original": "🔗 צפי במתכון המקורי",
    "processing": "⏳ מעבדת...",
    "recipe_extracted": "👍 המתכון חולץ בהצלחה! בדקי את התצוגה המקדימה ולחצי 'שמרי'.",
    "error_extract_url": "❌ שגיאה בחילוץ המתכון מהקישור",
    "error_extract_image": "❌ שגיאה בחילוץ המתכון מהתמונה",
    "error_save": "❌ שגיאה בשמירת המתכון",
    "error_search": "❌ שגיאה בחיפוש",
    "error_fetch": "❌ שגיאה בטעינת המתכונים",
    "delete_recipe": "🗑️ מחקי מתכון",
    "confirm_delete": "האם את בטוחה שברצונך למחוק את המתכון '{title}'?",
    "recipe_deleted": "🗑️ המתכון '{title}' נמחק בהצלחה!",
    "error_delete": "❌ שגיאה במחיקת המתכון",
    "sort_by": "מייני לפי",
    "newest_first": "החדש ביותר",
    "oldest_first": "הישן ביותר",
    "title_az": "שם (א-ת)",
    "enter_url_warning": "אנא הכניסי קישור למתכון.",
    "img_upload_error": "שגיאה בעיבוד התמונה:",
    "search_prompt": "הקלידי מונח חיפוש כדי למצוא מתכונים.",
    "filter_no_results": "לא נמצאו מתכונים התואמים לסינון.",
    "manual_img_upload": "לא הצלחנו למצוא תמונה למתכון זה באופן אוטומטי. האם תרצי להוסיף תמונה בעצמך?",
    "upload_img_recipe": "העלאת תמונה למתכון",
    "img_upload_success": "התמונה הועלתה בהצלחה!",
    "yes_delete": "כן, מחקי",
    "cancel": "ביטול",
}

def get_translation(key, **kwargs):
    """Get Hebrew translation for a key, with optional formatting."""
    translation = TRANSLATIONS.get(key, key)
    if kwargs:
        try:
            translation = translation.format(**kwargs)
        except KeyError:
            pass # Ignore if placeholder not in translation
    return translation

import re
import requests
from urllib.parse import urljoin, urlparse
from io import BytesIO
from PIL import Image, UnidentifiedImageError
import json
from bs4 import BeautifulSoup
import base64
import streamlit as st
import time
from typing import Union, Optional, Tuple
import hashlib

# --- Enhanced Image Fetching Functions ---

def is_valid_image_url(url: str, timeout: int = 3) -> bool:
    """
    Check if a URL points to a valid image by making a HEAD request
    and checking content type.
    """
    if not url or not isinstance(url, str):
        return False

    # Normalize URL and handle basic issues
    url = url.strip()

    # Skip URLs that aren't HTTP/HTTPS
    if not url.startswith(('http://', 'https://')):
        return False

    try:
        # Make a HEAD request first to check content type without downloading the whole image
        response = requests.head(
            url,
            timeout=timeout,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )

        # Check if response is successful and content type is an image
        content_type = response.headers.get('Content-Type', '')
        return response.status_code == 200 and content_type.startswith('image/')
    except (requests.RequestException, Exception):
        return False


def follow_redirects(url: str, max_redirects: int = 3) -> str:
    """Follow URL redirects up to a maximum number and return the final URL."""
    if not url:
        return url

    try:
        # Don't download content, just follow redirects
        response = requests.head(
            url,
            allow_redirects=True,
            timeout=5,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        return response.url
    except (requests.RequestException, Exception):
        return url  # Return original if error


def fetch_meta_image(page_url: str) -> str | None:
    """
    Enhanced function to grab image URLs from meta tags.
    Supports more variants and follows redirects.
    """
    try:
        resp = requests.get(
            page_url,
            timeout=5,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        html = resp.text

        # Try using BeautifulSoup for more reliable parsing if available
        try:
            soup = BeautifulSoup(html, 'html.parser')

            # Look for meta tags in priority order
            # 1. OpenGraph image (og:image)
            og_image = soup.find('meta', property='og:image') or soup.find('meta', attrs={'property': 'og:image'})
            if og_image and og_image.get('content'):
                url = urljoin(page_url, og_image['content'])
                if is_valid_image_url(url):
                    return url

            # 2. Twitter image
            twitter_image = soup.find('meta', name='twitter:image') or soup.find('meta', attrs={'name': 'twitter:image'})
            if twitter_image and twitter_image.get('content'):
                url = urljoin(page_url, twitter_image['content'])
                if is_valid_image_url(url):
                    return url

            # 3. Image_src link
            image_src = soup.find('link', rel='image_src')
            if image_src and image_src.get('href'):
                url = urljoin(page_url, image_src['href'])
                if is_valid_image_url(url):
                    return url

            # 4. Article image
            article_image = soup.find('meta', property='og:article:image') or soup.find('meta', attrs={'property': 'og:article:image'})
            if article_image and article_image.get('content'):
                url = urljoin(page_url, article_image['content'])
                if is_valid_image_url(url):
                    return url

            # 5. Look for schema.org Recipe image
            for script in soup.find_all('script', type='application/ld+json'):
                try:
                    data = json.loads(script.string)
                    if isinstance(data, dict):
                        # Check for Recipe schema
                        if data.get('@type') == 'Recipe' and data.get('image'):
                            # Handle both string and array image values
                            img = data['image']
                            if isinstance(img, list) and img:
                                img = img[0]  # Take first image if it's a list
                            if isinstance(img, str):
                                url = urljoin(page_url, img)
                                if is_valid_image_url(url):
                                    return url
                            elif isinstance(img, dict) and img.get('url'):
                                url = urljoin(page_url, img['url'])
                                if is_valid_image_url(url):
                                    return url
                except (json.JSONDecodeError, AttributeError):
                    continue

            # 6. Last resort: look for the largest image in the page
            # Find all images above a certain size (to avoid icons, etc.)
            significant_images = []
            for img in soup.find_all('img'):
                src = img.get('src')
                if not src:
                    continue

                # Skip tiny images, data URLs, or SVGs
                if (
                    'icon' in src.lower() or
                    'logo' in src.lower() or
                    'avatar' in src.lower() or
                    'data:' in src or
                    '.svg' in src.lower()
                ):
                    continue

                # Try to get image dimensions from attributes
                width = img.get('width')
                height = img.get('height')
                try:
                    # Check if dimensions suggest a significant image (not small icons)
                    if width and height and int(width) >= 200 and int(height) >= 200:
                        url = urljoin(page_url, src)
                        if is_valid_image_url(url):
                            significant_images.append((int(width) * int(height), url))
                except (ValueError, TypeError):
                    # Width/height weren't valid numbers
                    pass

            # Sort by image size (largest first) and return the biggest one
            if significant_images:
                significant_images.sort(reverse=True)
                return significant_images[0][1]  # Return URL of largest image

        except (ImportError, Exception):
            # Fallback to basic regex if BeautifulSoup fails or isn't available
            pass

        # Fallback to regex approach if BeautifulSoup didn't find anything
        # 1) og:image - expanded regex to catch more variations
        patterns = [
            # Standard OG image
            r'<meta[^>]+(?:property|name)=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
            # Reverse attribute order
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']og:image["\']',
            # Twitter image
            r'<meta[^>]+(?:property|name)=["\']twitter:image(?::src)?["\'][^>]+content=["\']([^"\']+)["\']',
            r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\']twitter:image(?::src)?["\']',
            # Image_src link
            r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']',
            r'<link[^>]+href=["\']([^"\']+)["\'][^>]+rel=["\']image_src["\']',
            # Schema.org Recipe image
            r'"@type"\s*:\s*"Recipe"[^}]*"image"\s*:\s*"([^"]+)"',
            r'"@type"\s*:\s*"Recipe"[^}]*"image"\s*:\s*\[\s*"([^"]+)"',
        ]

        for pattern in patterns:
            m = re.search(pattern, html, flags=re.IGNORECASE)
            if m:
                url = urljoin(page_url, m.group(1))
                if is_valid_image_url(url):
                    return url

        # If we got this far, try noembed as a last resort
        try:
            oe_response = requests.get(
                "https://noembed.com/embed",
                params={"url": page_url},
                timeout=4
            )
            if oe_response.status_code == 200:
                data = oe_response.json()
                thumb = data.get("thumbnail_url")
                if thumb and is_valid_image_url(thumb):
                    return thumb
        except Exception:
            pass

    except requests.RequestException:
        return None

    return None


def get_recipe_image(url: str, recipe_data: dict) -> str:
    """
    Comprehensive function to get the best image for a recipe using multiple strategies.
    Returns a valid image URL or None.
    """
    image_url = recipe_data.get("image_url")

    # Only try to fetch an image if one wasn't already provided or it's invalid
    if not image_url or not is_valid_image_url(image_url):
        # Strategy 1: Try meta tags
        image_url = fetch_meta_image(url)

        # Strategy 2: If recipe has a source_url different from the given URL, try that too
        source_url = recipe_data.get("source_url")
        if not image_url and source_url and source_url != url:
            image_url = fetch_meta_image(source_url)

        # Strategy 3: Try noembed service if we still don't have an image
        if not image_url:
            try:
                response = requests.get(
                    "https://noembed.com/embed",
                    params={"url": url},
                    timeout=4
                )
                if response.status_code == 200:
                    data = response.json()
                    image_url = data.get("thumbnail_url")
                    # Verify it's valid
                    if not is_valid_image_url(image_url):
                        image_url = None
            except Exception:
                pass

        # Strategy 4: Try simple domain-level favicon as a last resort
        if not image_url:
            try:
                parsed_url = urlparse(url)
                base_url = f"{parsed_url.scheme}://{parsed_url.netloc}"
                favicon_url = f"{base_url}/favicon.ico"
                if is_valid_image_url(favicon_url):
                    image_url = favicon_url
            except Exception:
                pass

    # If we found an image URL, follow any redirects and update recipe_data
    if image_url:
        image_url = follow_redirects(image_url)
        recipe_data["image_url"] = image_url
        return image_url

    return None


# --- Image Caching System ---

def get_image_cache_key(url: str) -> str:
    """Generate a cache key from an image URL."""
    return hashlib.md5(url.encode()).hexdigest()


def cache_image(url: str, max_age_hours: int = 24) -> None:
    """
    Cache an image from a URL in the session state.
    Includes verification and expiration.
    """
    if not url:
        return

    cache_key = get_image_cache_key(url)

    # Check if already in cache and not expired
    now = time.time()
    if cache_key in st.session_state:
        cached = st.session_state[cache_key]
        # If cache is still valid, don't reload
        if cached.get('timestamp') and now - cached['timestamp'] < (max_age_hours * 3600):
            return

    # Not in cache or expired, try to fetch
    try:
        response = requests.get(
            url,
            timeout=5,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )

        if response.status_code == 200 and response.headers.get('Content-Type', '').startswith('image/'):
            # Verify it's an actual image by trying to open it
            try:
                img = Image.open(BytesIO(response.content))
                # Store in session state cache
                st.session_state[cache_key] = {
                    'content': response.content,
                    'content_type': response.headers.get('Content-Type'),
                    'timestamp': now
                }
            except UnidentifiedImageError:
                # Not a valid image
                pass
    except Exception:
        # Any error, just skip caching
        pass


def get_cached_image(url: str) -> Union[bytes, None]:
    """Retrieve an image from cache if available."""
    if not url:
        return None

    cache_key = get_image_cache_key(url)

    if cache_key in st.session_state:
        return st.session_state[cache_key].get('content')

    return None


# --- Display Functions ---

def display_recipe_image(recipe: dict, use_container_width: bool = True, width: Optional[int] = None) -> None:
    """
    Enhanced function to display a recipe image with fallbacks and caching.
    If the image can't be displayed, shows a better placeholder.

    Now optimized for desktop view - limits image width on larger screens.
    """
    image_url = recipe.get("image_url")

    # Set a maximum width for desktop displays
    max_desktop_width = 500  # This controls the maximum size on desktop

    # If width is not specified and on desktop, use the max_desktop_width
    if width is None and use_container_width:
        width = max_desktop_width

    if image_url and isinstance(image_url, str) and image_url.startswith(('http://', 'https://')):
        # Try to get from cache first
        image_data = get_cached_image(image_url)

        if image_data:
            # Display from cached data
            try:
                img = Image.open(BytesIO(image_data))
                st.image(img, use_container_width=use_container_width, width=width, caption=recipe.get('title', ''))
                return
            except Exception:
                # Fall through to direct URL if cached image fails
                pass

        # Try loading directly from URL (will be cached for next time)
        try:
            # Attempt to cache the image first
            cache_image(image_url)

            # Most reliable way - always try to load through requests first to handle redirects, etc.
            response = requests.get(
                image_url,
                timeout=5,
                headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
            )

            if response.status_code == 200 and response.headers.get('Content-Type', '').startswith('image/'):
                try:
                    img = Image.open(BytesIO(response.content))
                    st.image(img, use_container_width=use_container_width, width=width, caption=recipe.get('title', ''))
                    return
                except UnidentifiedImageError:
                    # Not a valid image, fall through to placeholder
                    pass
            else:
                # Direct attempt with Streamlit
                st.image(image_url, use_container_width=use_container_width, width=width, caption=recipe.get('title', ''))
                return
        except Exception:
            # Any error, fall through to placeholder
            pass

    # If we got here, we need to show a placeholder
    # Use a nicer food-themed placeholder
    placeholder_urls = [
        # Use a food-themed placeholder with the recipe title if available
        f"https://placehold.co/600x400/FFF8DC/8B4513?text={recipe.get('title', 'Recipe')}",
        "https://placehold.co/600x400/FFF8DC/8B4513?text=Recipe+Image",
        # Hebrew version as final fallback
        "https://via.placeholder.com/600x300/F5F5DC/8B4513?text=אין+תמונה+זמינה"
    ]

    # Try placeholders in order until one works
    for placeholder_url in placeholder_urls:
        try:
            st.image(placeholder_url, use_container_width=use_container_width, width=width)
            break
        except Exception:
            continue

# --- Gemini Recipe Extraction ---

def parse_gemini_json_output(response_text):
    """Attempts to parse JSON from Gemini's response text, handling common issues."""
    # Try finding JSON within ```json ... ```
    json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL | re.IGNORECASE)
    if json_match:
        json_str = json_match.group(1)
    else:
        # Try finding JSON starting with { and ending with }
        json_match = re.search(r"({[\s\S]*})", response_text)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Assume the whole text might be JSON (last resort)
            json_str = response_text

    # Clean common issues before parsing
    json_str = json_str.strip()
    # Sometimes Gemini might add comments // or trailing commas
    json_str = re.sub(r"//.*", "", json_str) # Remove single line comments
    json_str = re.sub(r",\s*([\]}])", r"\1", json_str) # Remove trailing commas

    try:
        # First attempt to parse directly
        return json.loads(json_str)
    except json.JSONDecodeError as e1:
        # print(f"Initial JSON parse failed: {e1}. Trying to clean...") # Debug
        # Try cleaning newlines within strings etc. (more aggressive)
        try:
            clean_json_str = re.sub(r"[\n\r\t]", "", json_str)
            return json.loads(clean_json_str)
        except json.JSONDecodeError as e2:
            # print(f"Cleaned JSON parse failed: {e2}. Raw string was:\n{json_str}") # Debug
            raise ValueError(f"Failed to parse JSON from LLM response: {e2}")


def fetch_meta_image(page_url: str) -> str | None:
    """
    Grab <meta property="og:image">, <meta name="twitter:image"> or <link rel="image_src">
    from the raw HTML. Returns the first absolute URL found, or None.
    """
    try:
        resp = requests.get(page_url, timeout=5, headers={"User-Agent": "Mozilla/5.0"})
        html = resp.text
    except requests.RequestException:
        return None

    # 1) og:image
    m = re.search(
        r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)["\']',
        html, flags=re.IGNORECASE
    )
    if m:
        return urljoin(page_url, m.group(1))

    # 2) twitter:image
    m = re.search(
        r'<meta[^>]+name=["\']twitter:image["\'][^>]+content=["\']([^"\']+)["\']',
        html, flags=re.IGNORECASE
    )
    if m:
        return urljoin(page_url, m.group(1))

    # 3) legacy link rel image_src
    m = re.search(
        r'<link[^>]+rel=["\']image_src["\'][^>]+href=["\']([^"\']+)["\']',
        html, flags=re.IGNORECASE
    )
    if m:
        return urljoin(page_url, m.group(1))

    return None

def extract_recipe_from_image(image):
    """Extract recipe information from an image using Gemini Pro Vision."""
    try:
        # Choose appropriate model, flash is faster/cheaper, pro might be more accurate
        model = genai.GenerativeModel("gemini-1.5-flash-latest")

        prompt = """
        You are an expert recipe analyser. Extract the complete recipe from the provided image.
        Return the result ONLY as a valid JSON object with the following fields:
        {
            "title": "Recipe title (string)",
            "description": "Brief description of the dish (string, optional)",
            "prep_time": "Preparation time (string, e.g., '15 minutes', optional)",
            "cook_time": "Cooking time (string, e.g., '30 minutes', optional)",
            "total_time": "Total time (string, e.g., '45 minutes', optional)",
            "servings": "Number of servings (string or number, optional)",
            "ingredients": ["List of ingredients with quantities (array of strings)"],
            "instructions": ["List of preparation/cooking steps (array of strings)"],
            "cuisine": "Type of cuisine (string, e.g., 'Italian', 'Asian', optional)",
            "meal_type": "Type of meal (string, e.g., 'Breakfast', 'Dinner', 'Dessert', optional)",
            "keywords": ["List of relevant keywords/tags (array of strings, optional)"]
        }
        If a field is not clearly present in the image, use null or an empty array/string as appropriate for the field type.
        Focus ONLY on extracting information present in the image. Do not add external knowledge.
        Ensure the output is a single, valid JSON object and nothing else.
        """

        response = model.generate_content(
            contents=[prompt, image],
            generation_config=genai.types.GenerationConfig(
                temperature=0.1, # Lower temperature for more deterministic extraction
                response_mime_type="application/json" # Request JSON directly if model supports
                )
        )

        # Assuming response_mime_type worked, response.text should be JSON
        try:
            recipe_data = json.loads(response.text)
            return recipe_data
        except json.JSONDecodeError:
             # Fallback parsing if response_mime_type didn't enforce JSON correctly
            try:
                return parse_gemini_json_output(response.text)
            except ValueError as e:
                 st.error(f"{get_translation('error_extract_image')}: Failed to decode JSON from response. {e}")
                 # print("Failed JSON Response Text:", response.text) # Debugging
                 return None
        except Exception as e: # Catch other potential Gemini errors
             st.error(f"{get_translation('error_extract_image')}: {str(e)}")
             # print("Gemini Response:", response) # Debugging
             return None


    except Exception as e:
        st.error(f"{get_translation('error_extract_image')}: An unexpected error occurred: {str(e)}")
        return None


def extract_recipe_from_url(url):
    """Extract recipe information from a URL using Gemini, with enhanced image handling."""
    try:
        model = genai.GenerativeModel("gemini-1.5-pro-latest") # Or your preferred model

        # --- Enhanced Prompt ---
        prompt = f"""
        Please analyze the content of the webpage at the following URL: {url}
        This page contains a recipe. Extract the complete recipe details.
        Return the result ONLY as a single, valid JSON object with the following fields:
        {{
            "title": "Recipe title (string)",
            "description": "Brief description of the dish (string, optional)",
            "prep_time": "Preparation time (string, e.g., '15 minutes', optional)",
            "cook_time": "Cooking time (string, e.g., '30 minutes', optional)",
            "total_time": "Total time (string, e.g., '45 minutes', optional)",
            "servings": "Number of servings (string or number, optional)",
            "ingredients": ["List of ingredients with quantities (array of strings)"],
            "instructions": ["List of preparation/cooking steps (array of strings)"],
            "cuisine": "Type of cuisine (string, e.g., 'Italian', 'Asian', optional)",
            "meal_type": "Type of meal (string, e.g., 'Breakfast', 'Dinner', 'Dessert', optional)",
            "keywords": ["List of relevant keywords/tags (array of strings, optional)"],
            "image_url": "URL of the main, featured recipe image (string, optional). Prioritize images specified in meta tags (like og:image) or the primary image clearly associated with the finished dish."
        }}
        If a field is not clearly present on the page, use null or an empty array/string as appropriate.
        Focus ONLY on extracting information present on the webpage. Do not add external knowledge.

        IMPORTANT for image_url: Identify the primary, featured image representing the final dish. Check for meta tags like 'og:image' or 'twitter:image' content if possible from the page structure you analyze. Avoid logos, ingredient photos, user avatars, or advertisement images. If no suitable main image URL is found, return null for the 'image_url' field.

        Ensure the output is a single, valid JSON object and nothing else.
        """
        # --- End Enhanced Prompt ---

        response = model.generate_content(
            prompt,
             generation_config=genai.types.GenerationConfig(
                temperature=0.1,
                response_mime_type="application/json" # Request JSON directly
                )
            )

        # Attempt to parse the response
        try:
            recipe_data = json.loads(response.text)
        except json.JSONDecodeError:
            try:
                 recipe_data = parse_gemini_json_output(response.text)
            except ValueError as e:
                 st.error(f"{get_translation('error_extract_url')}: Failed to decode JSON. {e}")
                 return None
        except Exception as e: # Catch other potential Gemini errors
             st.error(f"{get_translation('error_extract_url')}: {str(e)}")
             return None

        # --- Enhanced Image Handling ---
        if recipe_data:
            recipe_data["source_url"] = url # Add source URL

            # Use our enhanced image fetching function
            get_recipe_image(url, recipe_data)

            # If we have an image URL, try to cache it in advance
            if recipe_data.get("image_url"):
                try:
                    cache_image(recipe_data["image_url"])
                except Exception:
                    # Ignore caching errors
                    pass

        return recipe_data

    except Exception as e:
        st.error(f"{get_translation('error_extract_url')}: An unexpected error occurred: {str(e)}")
        return None

# --- Database Operations ---

def save_recipe_to_db(recipe_data):
    """Save the recipe to MongoDB."""
    try:
        # Add timestamp
        recipe_data["added_on"] = datetime.now()

        # Ensure ingredients and instructions are lists
        if "ingredients" not in recipe_data or not isinstance(recipe_data["ingredients"], list):
            recipe_data["ingredients"] = []
        if "instructions" not in recipe_data or not isinstance(recipe_data["instructions"], list):
            recipe_data["instructions"] = []
        if "keywords" not in recipe_data or not isinstance(recipe_data["keywords"], list):
            recipe_data["keywords"] = []


        # Insert into MongoDB
        result = recipes_collection.insert_one(recipe_data)
        return result.inserted_id

    except pymongo.errors.PyMongoError as e:
        st.error(f"{get_translation('error_save')}: Database error: {str(e)}")
        return None
    except Exception as e:
        st.error(f"{get_translation('error_save')}: An unexpected error occurred: {str(e)}")
        return None

def search_recipes(query):
    """Search recipes using MongoDB text search."""
    try:
        # Use MongoDB text search
        results = recipes_collection.find(
            {"$text": {"$search": query}}, {"score": {"$meta": "textScore"}}
        ).sort([("score", {"$meta": "textScore"})])

        return list(results)
    except pymongo.errors.PyMongoError as e:
        st.error(f"{get_translation('error_search')}: Database error: {str(e)}")
        return []
    except Exception as e:
        st.error(f"{get_translation('error_search')}: An unexpected error occurred: {str(e)}")
        return []


def get_all_recipes(sort_option="newest"):
    """Get all saved recipes, with sorting."""
    try:
        sort_criteria = ("added_on", -1) # Default: newest first
        if sort_option == "oldest":
            sort_criteria = ("added_on", 1)
        elif sort_option == "title":
             sort_criteria = ("title", 1) # Sort A-Z by title

        return list(recipes_collection.find().sort([sort_criteria]))
    except pymongo.errors.PyMongoError as e:
        st.error(f"{get_translation('error_fetch')}: Database error: {str(e)}")
        return []
    except Exception as e:
        st.error(f"{get_translation('error_fetch')}: An unexpected error occurred: {str(e)}")
        return []

def delete_recipe_from_db(recipe_id):
    """Delete a recipe from MongoDB by its ID."""
    try:
        result = recipes_collection.delete_one({"_id": ObjectId(recipe_id)})
        return result.deleted_count > 0
    except pymongo.errors.PyMongoError as e:
        st.error(f"{get_translation('error_delete')}: Database error: {str(e)}")
        return False
    except Exception as e:
        st.error(f"{get_translation('error_delete')}: An unexpected error occurred: {str(e)}")
        return False

# --- UI Rendering ---

def render_recipe_card(recipe, show_delete_button=False):
    """Render a beautiful recipe card with RTL support and optional delete button."""
    card_key = str(recipe.get('_id', 'new_recipe')) # Unique key for elements within loop/map

    # Use st.container with a border for card effect
    with st.container(border=True):
        col1, col2 = st.columns([2, 1]) # Image on left, details on right for wider screens maybe? Let's try simple top-down first.

        # Title
        st.markdown(
            f"<h3 dir='rtl' class='recipe-title'>{recipe.get('title', 'מתכון ללא שם')}</h3>",
            unsafe_allow_html=True,
        )

        # Enhanced Image Display - use our improved function with desktop sizing
        display_recipe_image(recipe, use_container_width=True)

        # Description
        if recipe.get("description"):
            st.markdown(
                f"<p dir='rtl' class='recipe-description'>{recipe['description']}</p>",
                unsafe_allow_html=True,
            )

        # Metadata (Prep Time, Cook Time, Servings etc.) in columns for better layout
        meta_cols = st.columns(3)
        metadata_items = []
        if recipe.get("prep_time"):
            metadata_items.append(f"⏱️ {get_translation('prep_time')}: {recipe['prep_time']}")
        if recipe.get("cook_time"):
            metadata_items.append(f"🔥 {get_translation('cook_time')}: {recipe['cook_time']}")
        if recipe.get("total_time"):
             metadata_items.append(f"⌛ {get_translation('total_time')}: {recipe['total_time']}")
        if recipe.get("servings"):
             metadata_items.append(f"👥 {get_translation('serves')}: {recipe['servings']}")
        if recipe.get("cuisine"):
             metadata_items.append(f"🌍 {get_translation('cuisine')}: {recipe['cuisine']}")
        if recipe.get("meal_type"):
             metadata_items.append(f"🍽️ {get_translation('meal_type')}: {recipe['meal_type']}")

        # Distribute metadata items across columns
        items_per_col = (len(metadata_items) + len(meta_cols) - 1) // len(meta_cols) if metadata_items else 0
        for i, col in enumerate(meta_cols):
             with col:
                 for item in metadata_items[i*items_per_col:min((i+1)*items_per_col, len(metadata_items))]:
                     st.markdown(f"<span dir='rtl' class='recipe-metadata-item'>{item}</span>", unsafe_allow_html=True)


        st.markdown("---") # Separator

        # Expander for Ingredients and Instructions
        with st.expander(f"{get_translation('ingredients')} & {get_translation('instructions')}", expanded=False):
             ing_col, inst_col = st.columns(2)

             # Ingredients
             with ing_col:
                 st.markdown(f"<h5 dir='rtl'>{get_translation('ingredients')}</h5>", unsafe_allow_html=True)
                 if recipe.get("ingredients") and len(recipe["ingredients"]) > 0:
                     ingredients_html = "<ul dir='rtl' class='recipe-ingredients'>"
                     for ingredient in recipe["ingredients"]:
                         if ingredient: # Avoid rendering empty items
                             ingredients_html += f"<li>{ingredient}</li>"
                     ingredients_html += "</ul>"
                     st.markdown(ingredients_html, unsafe_allow_html=True)
                 else:
                     st.write(f"({get_translation('no_matches')})") # Or some placeholder

             # Instructions
             with inst_col:
                 st.markdown(f"<h5 dir='rtl'>{get_translation('instructions')}</h5>", unsafe_allow_html=True)
                 if recipe.get("instructions") and len(recipe["instructions"]) > 0:
                     instructions_html = "<ol dir='rtl' class='recipe-instructions'>"
                     for i, step in enumerate(recipe["instructions"]):
                         if step: # Avoid rendering empty steps
                             instructions_html += f"<li>{step}</li>"
                     instructions_html += "</ol>"
                     st.markdown(instructions_html, unsafe_allow_html=True)
                 else:
                      st.write(f"({get_translation('no_matches')})") # Or some placeholder


        # Keywords/tags
        if recipe.get("keywords") and len(recipe["keywords"]) > 0:
             # Filter out empty keywords that might come from extraction
             valid_keywords = [kw for kw in recipe["keywords"] if kw and isinstance(kw, str) and kw.strip()]
             if valid_keywords:
                 st.markdown(f"<h5 dir='rtl'>{get_translation('tags')}</h5>", unsafe_allow_html=True)
                 keywords_html = "<div dir='rtl' class='recipe-tags'>" + " ".join(
                     [f'<span class="recipe-tag">{kw.strip()}</span>' for kw in valid_keywords]
                 ) + "</div>"
                 st.markdown(keywords_html, unsafe_allow_html=True)

        # Source link if available
        if recipe.get("source_url"):
            st.markdown(
                f"<div dir='rtl' class='source-link-container'><a href='{recipe['source_url']}' target='_blank' class='source-link'>{get_translation('view_original')}</a></div>",
                unsafe_allow_html=True,
            )

        # Add Delete Button (conditionally)
        if show_delete_button and '_id' in recipe:
             st.markdown("---")
             delete_key = f"delete_{card_key}"
             confirm_key = f"confirm_delete_{card_key}"

             if confirm_key not in st.session_state:
                  st.session_state[confirm_key] = False

             if st.session_state[confirm_key]:
                  st.warning(get_translation('confirm_delete', title=recipe.get('title', '')), icon="⚠️")
                  col_confirm, col_cancel = st.columns(2)
                  with col_confirm:
                       if st.button(get_translation("yes_delete"), key=f"confirm_yes_{card_key}", type="primary", use_container_width=True):
                            if delete_recipe_from_db(recipe['_id']):
                                st.success(get_translation('recipe_deleted', title=recipe.get('title', '')))
                                st.session_state[confirm_key] = False # Reset confirmation state
                                # Clear potentially cached recipe data if needed
                                if 'recipes_cache' in st.session_state:
                                    del st.session_state['recipes_cache']
                                st.rerun() # Refresh the page to show updated list
                            else:
                                # Error message is shown by delete_recipe_from_db
                                st.session_state[confirm_key] = False # Reset confirmation state
                                st.rerun() # Still rerun to clear confirmation UI
                  with col_cancel:
                       if st.button(get_translation("cancel"), key=f"confirm_no_{card_key}", use_container_width=True):
                            st.session_state[confirm_key] = False
                            st.rerun()
             else:
                  if st.button(get_translation("delete_recipe"), key=delete_key, type="secondary", use_container_width=True):
                       st.session_state[confirm_key] = True
                       st.rerun() # Rerun to show the confirmation message

        # Add a little space at the bottom of the card
        st.markdown("<div style='margin-bottom: 10px;'></div>", unsafe_allow_html=True)


def add_manual_image_upload(recipe_data):
    """Allow manual image upload if automatic fetching fails."""
    if not recipe_data.get("image_url"):
        st.markdown("---")
        st.info(get_translation("manual_img_upload"))

        uploaded_file = st.file_uploader(
            get_translation("upload_img_recipe"),
            type=["jpg", "jpeg", "png"],
            key="manual_recipe_image"
        )

        if uploaded_file is not None:
            try:
                # Convert to base64 for storage
                image_bytes = uploaded_file.getvalue()
                image_b64 = base64.b64encode(image_bytes).decode()
                recipe_data["image_data_b64"] = image_b64
                st.success(get_translation("img_upload_success"))

                # Display the uploaded image
                image = Image.open(BytesIO(image_bytes))
                st.image(image, use_container_width=True, width=300)

                return True
            except Exception as e:
                st.error(f"{get_translation('img_upload_error')} {e}")

    return False

# --- Main Application ---
def main():
    st.set_page_config(
        page_title=get_translation("app_title"),
        page_icon="🍲",
        layout="wide",
        initial_sidebar_state="collapsed", # Tabs are used instead of sidebar
    )

    # --- Custom CSS ---
    st.markdown(
        """
    <style>
    /* --- Base & Fonts --- */
    @import url('https://fonts.googleapis.com/css2?family=Heebo:wght@300;400;500;700&display=swap');

    html, body, [class*="st-"] {
        font-family: 'Heebo', sans-serif;
        direction: rtl; /* Set base direction */
    }

    .main {
        background-color: #FEFBF6; /* Lighter background */
        padding: 1rem;
        direction: rtl;
    }

    @media (min-width: 768px) {
        .main {
            padding: 2rem 4rem; /* More padding on desktop */
        }
    }

    h1, h2, h3, h4, h5, h6 {
        color: #8B4513; /* Saddle Brown */
        text-align: right;
        direction: rtl;
        font-weight: 700; /* Bolder titles */
    }

    h1 {
         text-align: center;
         margin-bottom: 1.5rem;
    }

    h3.recipe-title { /* Recipe card title */
        margin-top: 0;
        margin-bottom: 0.5rem;
        color: #A0522D; /* Sienna */
    }


    /* --- Buttons --- */
    .stButton button {
        background-color: #8B4513; /* Saddle Brown */
        color: white;
        font-family: 'Heebo', sans-serif;
        font-weight: 500;
        border-radius: 8px;
        border: none;
        padding: 0.6rem 1.2rem;
        font-size: 1rem;
        transition: background-color 0.2s ease;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        width: auto; /* Allow button to size naturally */
        min-width: 120px; /* Minimum width */
    }
    .stButton button:hover {
        background-color: #A0522D; /* Sienna on hover */
        color: white;
    }
    .stButton button:active {
         transform: scale(0.98); /* Slight press effect */
    }
    .stButton button[kind="secondary"] { /* Style for secondary buttons like delete */
        background-color: #D2B48C; /* Tan */
        color: #5C4033; /* Darker text */
    }
    .stButton button[kind="secondary"]:hover {
         background-color: #BC8F8F; /* Rosy Brown on hover */
         color: white;
    }


    /* --- Inputs & Selects --- */
    input, textarea, select, .stTextInput div[data-baseweb="input"], .stSelectbox div[data-baseweb="select"] {
        direction: rtl;
        text-align: right;
        border-radius: 8px !important;
        border: 1px solid #D2B48C !important; /* Tan border */
        background-color: #FFFfff; /* White background */
    }
    div[data-baseweb="input"] > div { /* Target inner input div */
        background-color: #FFFfff !important;
    }
    /* Placeholder text */
    ::placeholder {
        color: #AAAAAA !important;
        opacity: 1; /* Firefox */
        text-align: right !important;
    }
    :-ms-input-placeholder { /* Internet Explorer 10-11 */
       color: #AAAAAA !important;
       text-align: right !important;
    }
    ::-ms-input-placeholder { /* Microsoft Edge */
       color: #AAAAAA !important;
       text-align: right !important;
    }
    /* Select dropdown menu */
     div[data-baseweb="popover"] {
        direction: rtl;
    }
    li[role="option"] {
        direction: rtl;
        text-align: right;
    }

    /* --- Tabs --- */
    .stTabs [data-baseweb="tab-list"] {
        gap: 5px; /* Space between tabs */
        direction: rtl;
        justify-content: center; /* Center tabs */
        border-bottom: 2px solid #D2B48C; /* Tan underline for tab bar */
        margin-bottom: 1.5rem;
    }
    .stTabs [data-baseweb="tab"] {
        height: auto;
        padding: 0.8rem 1.5rem;
        white-space: nowrap;
        font-family: 'Heebo', sans-serif;
        font-size: 1.1rem;
        font-weight: 500;
        color: #8B4513; /* Saddle Brown */
        background-color: #F5F5DC; /* Beige */
        border: none;
        border-radius: 8px 8px 0 0; /* Rounded top corners */
        margin: 0;
        transition: background-color 0.2s ease, color 0.2s ease;
    }
    .stTabs [aria-selected="true"] {
        background-color: #8B4513 !important; /* Saddle Brown */
        color: white !important;
        border: none;
    }
    .stTabs [data-baseweb="tab"]:hover {
         background-color: #D2B48C !important; /* Tan on hover */
         color: #5C4033 !important;
    }


    /* --- Recipe Card Styling --- */
    div[data-testid="stVerticalBlock"]:has(>.stContainer) { /* Target containers holding recipe cards */
         display: flex;
         flex-direction: column;
         gap: 1.5rem; /* Space between cards */
    }

    div[data-testid="stContainer"][border=true] { /* Card container */
        border: 1px solid #E0D8C7 !important; /* Lighter border */
        border-radius: 12px;
        padding: 1.5rem !important;
        background-color: #ffffff;
        box-shadow: 0 4px 8px rgba(0, 0, 0, 0.05);
        transition: box-shadow 0.3s ease;
    }
    div[data-testid="stContainer"][border=true]:hover {
        box-shadow: 0 6px 12px rgba(0, 0, 0, 0.1);
    }

    .recipe-description {
        font-style: normal;
        color: #555;
        text-align: right;
        direction: rtl;
        margin-bottom: 1rem;
        line-height: 1.6;
    }

    .recipe-metadata-item {
        font-size: 0.9rem;
        margin-bottom: 0.5rem; /* Space below each metadata item */
        color: #666;
        display: block; /* Make items stack vertically in columns */
        text-align: right;
    }

    .recipe-tags {
        margin-top: 0.5rem;
        margin-bottom: 1rem;
        text-align: right;
        direction: rtl;
    }

    .recipe-tag {
        display: inline-block;
        background-color: #F5F5DC; /* Beige */
        color: #8B4513; /* Saddle Brown */
        padding: 0.3rem 0.8rem;
        margin: 0.2rem 0.3rem; /* Adjust spacing */
        border-radius: 15px; /* More rounded */
        font-size: 0.85em;
        font-weight: 500;
        border: 1px solid #E0D8C7; /* Subtle border */
    }

    .recipe-ingredients, .recipe-instructions {
        text-align: right;
        direction: rtl;
        padding-right: 1.5rem; /* Indent list */
        line-height: 1.7; /* Better readability */
        color: #333;
    }
     .recipe-ingredients li, .recipe-instructions li {
         margin-bottom: 0.5rem; /* Space between list items */
     }

    .source-link-container {
         margin-top: 1rem;
         text-align: right;
    }
    .source-link {
        color: #A0522D; /* Sienna */
        text-decoration: none;
        font-weight: 500;
    }
    .source-link:hover {
         text-decoration: underline;
         color: #8B4513; /* Saddle Brown */
    }


    /* --- General Layout & Alignment --- */
    .stRadio > label { /* Align radio button labels correctly */
       text-align: right;
       direction: rtl;
       padding-right: 0.5rem;
    }

    div[data-testid="stExpander"] > div[role="button"] { /* Expander header */
        direction: rtl; /* Ensure arrow is on the left for RTL */
    }

    /* Fix potential alignment issues */
    div[data-testid="stVerticalBlock"], div[data-testid="stForm"], div[data-testid="stMarkdown"], div[data-testid="stText"] {
        direction: rtl;
        text-align: right;
    }

    /* Custom image placeholder styling */
    .recipe-placeholder {
        background-color: #F5F5DC;
        color: #8B4513;
        border: 1px dashed #D2B48C;
        border-radius: 8px;
        padding: 2rem;
        text-align: center;
        font-family: 'Heebo', sans-serif;
        margin-bottom: 1rem;
    }
    .recipe-placeholder svg {
        width: 48px;
        height: 48px;
        margin-bottom: 1rem;
        color: #8B4513;
    }

    /* --- Fix for hero image size on desktop --- */
    @media (min-width: 992px) {
        .stImage img {
            max-width: 500px !important;
            margin: 0 auto !important;
            display: block !important;
        }
    }

    /* Mobile Adjustments */
     @media (max-width: 768px) {
        .stButton button {
            width: 100%; /* Full width buttons on mobile */
            font-size: 1rem;
        }
        .stTabs [data-baseweb="tab"] {
            font-size: 0.9rem;
            padding: 0.6rem 1rem;
        }
        div[data-testid="stContainer"][border=true] {
            padding: 1rem !important;
        }
        .main {
             padding: 0.5rem;
        }
        .stTabs [data-baseweb="tab-list"] {
            margin-bottom: 1rem;
        }
     }

    </style>
    """,
        unsafe_allow_html=True,
    )

    st.title(get_translation("app_title"), anchor=False)

    # --- Session State Initialization ---
    if "extracted_recipe" not in st.session_state:
        st.session_state.extracted_recipe = None
    if "recipe_saved_flag" not in st.session_state:
        st.session_state.recipe_saved_flag = False # Use a flag to show message once

    # --- Navigation Tabs ---
    tabs = st.tabs(
        [
            f"📝 {get_translation('add_recipe')}",
            f"📚 {get_translation('my_recipes')}",
            f"🔍 {get_translation('search_recipes')}",
        ]
    )

    # ============================
    # TAB 1: ADD RECIPE
    # ============================
    with tabs[0]:
        st.header(get_translation("add_recipe"), anchor=False, divider="rainbow")

        add_method = st.radio(
            "בחרי שיטת הוספה:", # Updated to female form
            [get_translation("add_from_url"), get_translation("add_from_image")],
            horizontal=True,
            label_visibility="visible", # Keep label visible
        )

        # --- Add from URL ---
        if add_method == get_translation("add_from_url"):
            with st.form(key="url_form"):
                url = st.text_input(get_translation("enter_url"), key="url_input", placeholder="https://www.example-recipe.com/...")
                submit_extract_url = st.form_submit_button(get_translation("extract_recipe"))

                if submit_extract_url and url:
                    with st.spinner(get_translation("processing")):
                        recipe_data = extract_recipe_from_url(url)
                        if recipe_data:
                            st.session_state.extracted_recipe = recipe_data
                            st.session_state.recipe_saved_flag = False # Reset saved flag for new extraction
                            # Allow manual image upload if needed
                            if not recipe_data.get("image_url"):
                                add_manual_image_upload(recipe_data)

                            st.success(get_translation("recipe_extracted"))
                        else:
                            st.session_state.extracted_recipe = None # Clear previous if extraction failed
                            st.error(get_translation("extraction_failed"))
                elif submit_extract_url and not url:
                    st.warning(get_translation("enter_url_warning"))


        # --- Add from Image ---
        elif add_method == get_translation("add_from_image"):
            uploaded_file = st.file_uploader(
                get_translation("upload_image"), type=["jpg", "jpeg", "png"], label_visibility="collapsed"
            )

            if uploaded_file is not None:
                try:
                    image = Image.open(uploaded_file)
                    # Display smaller preview
                    st.image(image, caption=uploaded_file.name, width=300)

                    if st.button(get_translation("extract_from_image"), key="extract_image_btn"):
                        with st.spinner(get_translation("processing")):
                            recipe_data = extract_recipe_from_image(image)
                            if recipe_data:
                                st.session_state.extracted_recipe = recipe_data
                                st.session_state.recipe_saved_flag = False # Reset saved flag
                                st.success(get_translation("recipe_extracted"))
                            else:
                                st.session_state.extracted_recipe = None # Clear previous if extraction failed
                                st.error(get_translation("extraction_failed"))
                except Exception as e:
                    st.error(f"{get_translation('img_upload_error')} {e}")


        # --- Recipe Preview and Save Area ---
        if st.session_state.extracted_recipe:
            st.markdown("---")
            st.subheader(get_translation("recipe_preview"), anchor=False)

            # If recipe hasn't been saved yet in this session for this extraction
            if not st.session_state.recipe_saved_flag:
                render_recipe_card(st.session_state.extracted_recipe, show_delete_button=False) # Don't show delete for preview

                if st.button(get_translation("save_recipe"), key="save_extracted_recipe", type="primary"):
                    recipe_id = save_recipe_to_db(st.session_state.extracted_recipe)
                    if recipe_id:
                        st.success(get_translation("recipe_saved"))
                        st.session_state.recipe_saved_flag = True # Mark as saved for this extraction
                        st.session_state.extracted_recipe = None # Clear preview after successful save
                        # Clear cache if implemented
                        if 'recipes_cache' in st.session_state:
                            del st.session_state['recipes_cache']
                        st.rerun() # Rerun to clear the preview section
                    else:
                        # Error message is shown by save_recipe_to_db
                        pass
            # If recipe *was* just saved
            elif st.session_state.recipe_saved_flag:
                 st.success(get_translation("recipe_saved")) # Show confirmation briefly
                 # Optional: Automatically clear the message/state after a few seconds? Harder in Streamlit.
                 # For now, it just shows until the next interaction.

    # ============================
    # TAB 2: MY RECIPES
    # ============================
    with tabs[1]:
        st.header(get_translation("recipe_collection"), anchor=False, divider="rainbow")

        col_refresh, col_sort = st.columns([1, 3])
        with col_refresh:
             if st.button(get_translation("refresh_recipes")):
                  # Clear cache if implemented before rerun
                  if 'recipes_cache' in st.session_state:
                       del st.session_state['recipes_cache']
                  st.rerun()

        # --- Sorting ---
        with col_sort:
             sort_options_map = {
                 get_translation("newest_first"): "newest",
                 get_translation("oldest_first"): "oldest",
                 get_translation("title_az"): "title",
             }
             selected_sort_label = st.selectbox(
                 get_translation("sort_by"),
                 options=list(sort_options_map.keys()),
                 index=0, # Default to Newest First
                 label_visibility="collapsed"
             )
             sort_key = sort_options_map[selected_sort_label]


        # --- Fetch Recipes ---
        # Cache to improve performance
        cache_key = f"recipes_{sort_key}" # Cache based on sort order
        if cache_key not in st.session_state:
            with st.spinner(get_translation("processing")):
                st.session_state[cache_key] = get_all_recipes(sort_option=sort_key)
        recipes = st.session_state[cache_key]


        if not recipes:
            st.info(get_translation("no_recipes"))
        else:
            st.write(
                f"{get_translation('you_have')} **{len(recipes)}** {get_translation('saved_recipes')}"
            )

            # --- Filtering ---
            with st.expander(get_translation("filter_recipes")):
                col1, col2 = st.columns(2)

                # Collect unique filter options with safe handling
                cuisines_set = set()
                meal_types_set = set()
                for r in recipes:
                    # Process Cuisine
                    cuisine_val = r.get("cuisine") # Get value (can be None)
                    if cuisine_val and isinstance(cuisine_val, str): # Check if it's a non-None string
                        stripped_cuisine = cuisine_val.strip()
                        if stripped_cuisine: # Check if not empty after stripping
                            cuisines_set.add(stripped_cuisine)

                    # Process Meal Type
                    meal_type_val = r.get("meal_type") # Get value (can be None)
                    if meal_type_val and isinstance(meal_type_val, str): # Check if it's a non-None string
                        stripped_meal_type = meal_type_val.strip()
                        if stripped_meal_type: # Check if not empty after stripping
                            meal_types_set.add(stripped_meal_type)

                cuisines = sorted(list(cuisines_set))
                meal_types = sorted(list(meal_types_set))

                with col1:
                    selected_cuisine = st.selectbox(
                        get_translation("cuisine"), [get_translation("all")] + cuisines
                    )

                with col2:
                    selected_meal_type = st.selectbox(
                        get_translation("meal_type"),
                        [get_translation("all")] + meal_types,
                    )


            # Apply filters
            filtered_recipes = recipes
            if selected_cuisine != get_translation("all"):
                filtered_recipes = [r for r in filtered_recipes if r.get("cuisine") == selected_cuisine]
            if selected_meal_type != get_translation("all"):
                filtered_recipes = [r for r in filtered_recipes if r.get("meal_type") == selected_meal_type]

            # Display recipes
            if not filtered_recipes:
                 st.warning(get_translation("filter_no_results"))
            else:
                 # Use st.columns for potential grid layout in future, or just render linearly
                 for recipe in filtered_recipes:
                    render_recipe_card(recipe, show_delete_button=True) # Show delete button here


    # ============================
    # TAB 3: SEARCH RECIPES
    # ============================
    with tabs[2]:
        st.header(get_translation("search_recipes"), anchor=False, divider="rainbow")

        search_query = st.text_input(
            "חפשי מתכון", # Updated to female form
            placeholder=get_translation("search_placeholder"),
            label_visibility="collapsed",
            key="search_input"
        )

        if search_query:
            with st.spinner(get_translation("searching")):
                results = search_recipes(search_query)

                if results:
                    st.success(
                        f"{get_translation('found')} **{len(results)}** {get_translation('matching_recipes')}"
                    )
                    for recipe in results:
                        render_recipe_card(recipe, show_delete_button=True) # Show delete here too
                else:
                    st.info(get_translation("no_matches"))
        else:
             st.info(get_translation("search_prompt"))


if __name__ == "__main__":
    main()
