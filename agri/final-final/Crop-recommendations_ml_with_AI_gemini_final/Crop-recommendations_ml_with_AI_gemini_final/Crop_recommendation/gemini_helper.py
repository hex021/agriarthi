import google.generativeai as genai
import os
import hashlib
import json

# ================= GEMINI CONFIG =================
# Ensure your API Key is set in your environment variables or replace directly here
# os.environ["GEMINI_API_KEY"] = "YOUR_ACTUAL_API_KEY" 
genai.configure(api_key=os.getenv("AIzaSyCZRW0UA1EWbSRzAbIzpi62c4k8kIB1H1E"))

# ================= CACHE SETUP =================
DATA_DIR = "data"
CACHE_FILE = os.path.join(DATA_DIR, "gemini_cache.json")

os.makedirs(DATA_DIR, exist_ok=True)

# Load cache
if os.path.exists(CACHE_FILE):
    with open(CACHE_FILE, "r") as f:
        try:
            CACHE = json.load(f)
        except json.JSONDecodeError:
            CACHE = {}
else:
    CACHE = {}

def save_cache():
    with open(CACHE_FILE, "w") as f:
        json.dump(CACHE, f, indent=2)

# ================= CACHE KEY =================
def get_cache_key(crop, values):
    # Round values to reduce cache misses on tiny sensor variations
    rounded_values = {k: round(v, 1) if isinstance(v, float) else v for k, v in values.items()}
    key_str = crop + json.dumps(rounded_values, sort_keys=True)
    return hashlib.md5(key_str.encode()).hexdigest()

# ================= MAIN FUNCTIONS =================

def get_crop_explanation(crop, values):
    """
    Generates a detailed, structured explanation for the recommended crop.
    """
    cache_key = get_cache_key(crop, values)

    # ✅ Return cached response if available
    if cache_key in CACHE:
        return CACHE[cache_key]

    prompt = f"""
    You are an expert agriculture advisor for Indian farmers.
    
    The recommended crop is **{crop}**.
    
    Field Conditions:
    - Nitrogen: {values['Nitrogen']}
    - Phosphorus: {values['Phosporus']}
    - Potassium: {values['Potassium']}
    - Temperature: {values['Temperature']}°C
    - Humidity: {values['Humidity']}%
    - pH: {values['pH']}
    - Rainfall: {values['Rainfall']} mm

    Provide advice in the following EXACT structure. Keep it simple and actionable.
    Total length under 120 words.

    Structure:
    Why suitable: 
    - (1-2 bullet points explaining why this crop fits the soil/weather)
    
    Key Care Tips:
    - (1 specific tip on water or fertilizer based on the input NPK/Rainfall)
    
    Profit Tip:
    - (1 short tip to maximize market value)
    """

    try:
        model = genai.GenerativeModel("models/gemini-1.5-flash")
        response = model.generate_content(prompt)
        text = response.text.strip()

    except Exception as e:
        print(f"Gemini API Error: {e}")
        # ✅ Fallback text if API fails
        text = (
            f"**Why suitable:** {crop} matches your current soil nutrient profile and climate conditions.\n\n"
            "**Key Care Tips:** Maintain regular irrigation. Ensure proper drainage to prevent waterlogging. "
            "Apply NPK fertilizers as per the stage of growth.\n\n"
            "**Profit Tip:** Harvest at physiological maturity for the best market price."
        )

    # Save to cache
    CACHE[cache_key] = text
    save_cache()

    return text

def translate_text(text, target_lang_code):
    """
    Translates the given text into the target Indian language.
    Codes: 'gu' (Gujarati), 'hi' (Hindi), 'mr' (Marathi), 'en' (English)
    """
    if target_lang_code == 'en':
        return text
    
    # Map common codes to full language names for better prompting
    lang_map = {
        'gu': 'Gujarati',
        'hi': 'Hindi',
        'mr': 'Marathi',
        'te': 'Telugu',
        'ta': 'Tamil',
        'kn': 'Kannada',
        'bn': 'Bengali'
    }
    
    target_language = lang_map.get(target_lang_code, "English")
    
    # Cache key for translation to avoid re-translating same advice
    trans_cache_key = f"TRANS_{target_lang_code}_{hashlib.md5(text.encode()).hexdigest()}"
    
    if trans_cache_key in CACHE:
        return CACHE[trans_cache_key]

    prompt = f"""
    Translate the following agricultural advice into {target_language}.
    Keep the meaning accurate but use simple terms a farmer would understand.
    Do not change technical numbers (like NPK values).

    Text to translate:
    {text}
    """

    try:
        model = genai.GenerativeModel("models/gemini-1.5-flash")
        response = model.generate_content(prompt)
        translated_text = response.text.strip()
        
        # Save to cache
        CACHE[trans_cache_key] = translated_text
        save_cache()
        
        return translated_text
    except Exception as e:
        print(f"Translation Error: {e}")
        return text # Return original text if translation fails