from flask import Flask, render_template, request, jsonify, session
import numpy as np
import pickle
import json
import os
import pandas as pd
import requests
import time
from gtts import gTTS  # Requires: pip install gTTS

from calculation import calculate_profit
from gemini_helper import get_crop_explanation, translate_text

# ================= CONFIGURATION =================
USE_MANUAL_PH = True
MANUAL_PH_VALUE = 6.3

# YOUR WEATHER API KEY
WEATHER_API_KEY = "558ed105a190d75b171bded956ac79ee"
WEATHER_URL = "http://api.openweathermap.org/data/2.5/forecast"

app = Flask(__name__)
app.secret_key = "super_secret_key_for_session"

# ================= PATHS =================
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
AUDIO_DIR = os.path.join(BASE_DIR, "static", "audio") # Directory for audio files

# Create directories if they don't exist
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(AUDIO_DIR, exist_ok=True)

CROP_DATA = pd.read_csv(os.path.join(DATA_DIR, "crop_yield.csv"))
UI_JSON = os.path.join(DATA_DIR, "ui_data.json")
SENSOR_JSON = os.path.join(DATA_DIR, "sensor_data.json")
FINAL_JSON = os.path.join(DATA_DIR, "unified_input.json")

# Load Models
model = pickle.load(open(os.path.join(BASE_DIR, "model.pkl"), "rb"))
sc = pickle.load(open(os.path.join(BASE_DIR, "standscaler.pkl"), "rb"))
mx = pickle.load(open(os.path.join(BASE_DIR, "minmaxscaler.pkl"), "rb"))

# ================= SCHEME DATABASE =================
SCHEME_DB = {
    "PM-KISAN": { "name": "PM-KISAN", "theme": "Income Support ₹6000/yr", "supporting": "100% DBT", "docs": "Aadhaar, RoR", "where": "PM-KISAN Portal", "link": "https://pmkisan.gov.in/" },
    "KCC": { "name": "Kisan Credit Card", "theme": "Credit up to ₹5L", "supporting": "4% Interest", "docs": "Land Docs", "where": "Bank", "link": "https://pmkisan.gov.in/Kcc/" },
    "PMFBY": { "name": "PM Fasal Bima Yojana", "theme": "Crop Insurance", "supporting": "Govt pays premium", "docs": "Sowing Cert", "where": "NCIP Portal", "link": "https://pmfby.gov.in/" },
    "PM-KUSUM": { "name": "PM-KUSUM (Solar)", "theme": "60% Subsidy for Solar Pumps", "supporting": "Central+State Subsidy", "docs": "Land Docs", "where": "Renewable Energy Portal", "link": "https://mnre.gov.in/" },
    "AIF": { "name": "Agri Infra Fund", "theme": "3% Interest Subvention", "supporting": "Post-Harvest Loans", "docs": "DPR, KYC", "where": "AIF Portal", "link": "https://agriinfra.dac.gov.in/" },
    "iKhedut": { "name": "Gujarat Tractor Subsidy", "theme": "Tractor Purchase Assistance", "supporting": "40-50% Subsidy", "docs": "7/12 Extracts", "where": "iKhedut", "link": "https://ikhedut.gujarat.gov.in/" }
}

CROP_SCHEME_MAP = {
    "Rice": "PMFBY", "Cotton": "PMFBY", "Jute": "PMFBY", "Mothbeans": "PMFBY",
    "Maize": "KCC", "Lentil": "KCC", "Blackgram": "KCC", "Mungbean": "KCC", 
    "Chickpea": "KCC", "Pigeonpeas": "KCC", "Kidneybeans": "KCC",
    "Apple": "AIF", "Orange": "AIF", "Grapes": "AIF", "Banana": "AIF", 
    "Mango": "AIF", "Papaya": "AIF", "Coconut": "AIF", "Coffee": "AIF",
    "Watermelon": "PM-KUSUM", "Muskmelon": "PM-KUSUM", "Pomegranate": "PM-KUSUM"
}

# ================= CROP ADVISORY DATABASE =================
CROP_ADVISORY = {
    "Rice": { "sowing": "June-July. Transplant 20-25 day seedlings.", "fertilizer": "N:P:K 100:60:60. Zinc is crucial.", "irrigation": "Maintain 2-5cm water depth.", "harvest": "Drain water 10 days before harvest." },
    "Maize": { "sowing": "June-July. Ridge & furrow method.", "fertilizer": "N:P:K 120:60:40. Nitrogen split doses.", "irrigation": "Critical at Tasseling & Silking.", "harvest": "When husk turns pale brown." },
    "Jute": { "sowing": "Feb-May. Fine seedbed needed.", "fertilizer": "N:P:K 60:30:30.", "irrigation": "Life irrigation 4 days after sowing.", "harvest": "120 days (small pod stage)." },
    "Cotton": { "sowing": "May-June. Dibbling method.", "fertilizer": "N:P:K 120:60:60. Foliar MgSO4.", "irrigation": "Avoid water stress at boll formation.", "harvest": "Pick dry bolls in morning." },
    "Coconut": { "sowing": "Plant 1-year-old seedlings in large pits.", "fertilizer": "500g N, 320g P, 1200g K per tree/year.", "irrigation": "Drip irrigation is best.", "harvest": "Harvest fully mature nuts (12 months)." },
    "Papaya": { "sowing": "Transplant 2-month seedlings.", "fertilizer": "200g N, 200g P, 250g K bimonthly.", "irrigation": "Ring method. Keep water off stem.", "harvest": "When skin shows yellow streaks." },
    "Orange": { "sowing": "Budded plants in July-Aug.", "fertilizer": "600g N, 200g P, 400g K per tree.", "irrigation": "Regular watering. Stress for flowering.", "harvest": "At color break stage." },
    "Apple": { "sowing": "Planting Dec-Jan (Dormant).", "fertilizer": "700:350:700g NPK per mature tree.", "irrigation": "Critical in April-August.", "harvest": "Check TSS and fruit firmness." },
    "Muskmelon": { "sowing": "Feb-March. Riverbed/Pits.", "fertilizer": "N:P:K 100:60:60.", "irrigation": "Stop water 3 days before picking.", "harvest": "When stem slips easily from fruit." },
    "Watermelon": { "sowing": "Jan-March. Spacing 2-3m.", "fertilizer": "N:P:K 100:60:60.", "irrigation": "Weekly. Stop before harvest.", "harvest": "When tendril dries & thud sound." },
    "Grapes": { "sowing": "Rooted cuttings in Oct/Feb.", "fertilizer": "High Potash demand.", "irrigation": "Stop before harvest for sweetness.", "harvest": "When sweet (does not ripen after picking)." },
    "Mango": { "sowing": "Grafts in July-Aug.", "fertilizer": "1kg N, 0.5kg P, 1kg K per tree.", "irrigation": "During fruit set (Feb-March).", "harvest": "When shoulder becomes rounded." },
    "Banana": { "sowing": "Tissue culture/Suckers. June-July.", "fertilizer": "Heavy feeder. High K and N.", "irrigation": "Drip irrigation highly recommended.", "harvest": "When fruit ridges disappear." },
    "Pomegranate": { "sowing": "Rainy season planting.", "fertilizer": "600:200:200g NPK per tree.", "irrigation": "Regular to prevent cracking.", "harvest": "Skin turns yellowish-red." },
    "Lentil": { "sowing": "Oct-Nov (Rabi).", "fertilizer": "N:P:K 20:40:20. Sulphur beneficial.", "irrigation": "Pod filling stage is critical.", "harvest": "When pods turn brown." },
    "Blackgram": { "sowing": "June-July or Feb-March.", "fertilizer": "N:P:K 20:40:20.", "irrigation": "Avoid waterlogging.", "harvest": "When pods turn black." },
    "Mungbean": { "sowing": "Summer or Kharif.", "fertilizer": "N:P:K 20:40:20.", "irrigation": "Critical at flowering.", "harvest": "Pick when pods turn brown." },
    "Mothbeans": { "sowing": "July (Monsoon). Drought hardy.", "fertilizer": "FYM + Low NPK.", "irrigation": "Rainfed crop.", "harvest": "Whole plant when dry." },
    "Pigeonpeas": { "sowing": "June-July. Ridge sowing.", "fertilizer": "N:P:K 20:50:20.", "irrigation": "Flower initiation is critical.", "harvest": "When 80% pods turn brown." },
    "Kidneybeans": { "sowing": "Oct-Nov (Plains).", "fertilizer": "N:P:K 100:60:30 (High N).", "irrigation": "Sensitive to stress. 4-5 irrigations.", "harvest": "Pods turn yellow/brown." },
    "Chickpea": { "sowing": "Oct-Nov. Deep sowing.", "fertilizer": "N:P 20:50. Use biofertilizer.", "irrigation": "Pre-flowering & Pod development.", "harvest": "Leaves turn reddish-brown." },
    "Coffee": { "sowing": "Seeds in nursery Dec-Jan.", "fertilizer": "N:P:K 100:60:80.", "irrigation": "Blossom showers in Feb-March.", "harvest": "Pick fully ripe red berries." },
    "General": { "sowing": "Sow at season start.", "fertilizer": "Apply FYM + Soil test NPK.", "irrigation": "Critical at Flowering/Fruiting.", "harvest": "At physiological maturity." }
}

# Default Sensor
if not os.path.exists(SENSOR_JSON):
    with open(SENSOR_JSON, "w") as f:
        json.dump({"Temperature": 0, "Humidity": 0, "pH": MANUAL_PH_VALUE}, f, indent=4)


# ================= INTELLIGENT WEATHER ENGINE =================
def generate_weather_advisory(forecast_list):
    """
    Analyzes forecast for: Rain Prob, Dry Spells, Heat Stress, Thunderstorms.
    """
    alerts = []
    advice = "Conditions are favorable for standard farming activities."
    
    max_temp_3days = 0
    max_rain_prob_3days = 0
    dry_days_count = 0
    total_rain_volume = 0
    has_thunderstorm = False
    
    # Analyze next 24 segments (approx 3 days)
    steps_to_analyze = min(24, len(forecast_list))
    
    for i in range(steps_to_analyze): 
        item = forecast_list[i]
        temp = item['main']['temp']
        pop = item.get('pop', 0) * 100 # Probability of Precipitation %
        rain_vol = item.get('rain', {}).get('3h', 0)
        weather_id = item['weather'][0]['id'] # Condition Code
        
        # Track Max Values
        if temp > max_temp_3days: max_temp_3days = temp
        if pop > max_rain_prob_3days: max_rain_prob_3days = pop
        total_rain_volume += rain_vol
        
        # Thunderstorm Check (2xx codes)
        if 200 <= weather_id <= 232:
            has_thunderstorm = True

        # Dry Spell Counter
        if i % 8 == 0:
            daily_rain_sum = 0
            for j in range(8):
                if i+j < len(forecast_list):
                    daily_rain_sum += forecast_list[i+j].get('rain', {}).get('3h', 0)
            if daily_rain_sum < 1.0: 
                dry_days_count += 1

    # --- INTELLIGENCE LOGIC ---
    
    # 1. Thunderstorm Alert
    if has_thunderstorm:
        alerts.append("⛈️ Thunderstorm Alert")
        advice = "⚠️ WARNING: Thunderstorms predicted. Do not apply sprays. Secure loose equipment."

    # 2. Rain Intelligence
    elif total_rain_volume > 15.0 or max_rain_prob_3days > 80:
        alerts.append("🌧️ Heavy Rain Alert")
        advice = "⚠️ ADVICE: Postpone sowing and fertilizer. Ensure drainage channels are open."
    elif max_rain_prob_3days > 50:
        alerts.append("☁️ Rain Likely")
        advice = "ℹ️ ADVICE: Moderate rain expected. You can likely skip irrigation for 2-3 days."

    # 3. Heat Stress Intelligence
    if max_temp_3days > 40:
        alerts.append("🔥 Extreme Heatwave")
        advice = "⚠️ CRITICAL: Extreme heat! Irrigate frequently to save crops from scorching. Use shade nets for nurseries."
    elif max_temp_3days > 35:
        alerts.append("☀️ Heat Stress")
        advice = "⚠️ ADVICE: High temperatures. Ensure soil moisture is adequate. Irrigate in the evening."

    # 4. Dry Spell Intelligence
    if dry_days_count >= 3 and total_rain_volume < 2.0 and max_temp_3days > 30:
        alerts.append("🍂 Dry Spell Alert")
        advice = "💧 ADVICE: No rain forecast for 3+ days. Irrigation is mandatory to maintain crop health."

    return {
        "max_temp_3days": round(max_temp_3days, 1),
        "rain_prob": round(max_rain_prob_3days, 1),
        "alerts": alerts,
        "advice": advice
    }


# ================= ROUTES =================
@app.route("/")
def index():
    if 'last_result' in session:
        data = session['last_result']
        return render_template(
            "index.html",
            result=data['result'],
            values=data['values'],
            explanation=data['explanation'],
            scheme=data['scheme'],
            user_land_size=data['user_land_size'],
            advisory=data['advisory']
        )
    return render_template("index.html")

@app.route("/reset")
def reset():
    session.pop('last_result', None)
    return render_template("index.html")

@app.route('/get_weather', methods=['POST'])
def get_weather():
    try:
        city = request.form.get('city')
        params = {'q': city, 'appid': WEATHER_API_KEY, 'units': 'metric'}
        response = requests.get(WEATHER_URL, params=params)
        data = response.json()
        
        if response.status_code != 200: 
            return jsonify({'error': data.get('message')}), 400
        
        # Analyze data using the new Intelligence Engine
        intelligence = generate_weather_advisory(data['list'])
        
        return jsonify({
            'Advisory': intelligence
        })
    except Exception as e: return jsonify({'error': str(e)}), 500

@app.route("/sensor", methods=["POST"])
def receive_sensor():
    try:
        data = request.get_json(force=True)
        sensor_data = {
            "Temperature": float(data["Temperature"]),
            "Humidity": float(data["Humidity"]),
            "pH": MANUAL_PH_VALUE if USE_MANUAL_PH else float(data["pH"])
        }
        with open(SENSOR_JSON, "w") as f:
            json.dump(sensor_data, f, indent=4)
        return jsonify({"status": "saved"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/predict", methods=["POST"])
def predict():
    # 1. Get User Inputs
    ui_data = {
        "Nitrogen": float(request.form["Nitrogen"]),
        "Phosporus": float(request.form["Phosporus"]),
        "Potassium": float(request.form["Potassium"]),
        "Rainfall": float(request.form["Rainfall"]),
        "LandSize": float(request.form["LandSize"]),
        "Income": float(request.form["Income"])
    }
    with open(UI_JSON, "w") as f: json.dump(ui_data, f, indent=4)
    
    # 2. Get Sensor Data
    with open(SENSOR_JSON, "r") as f: sensor = json.load(f)
    
    # 3. Combine for Model
    model_input = { 
        "Nitrogen": ui_data["Nitrogen"], 
        "Phosporus": ui_data["Phosporus"], 
        "Potassium": ui_data["Potassium"], 
        "Temperature": sensor["Temperature"], # From Sensor
        "Humidity": sensor["Humidity"],       # From Sensor
        "pH": sensor["pH"],                   # From Sensor
        "Rainfall": ui_data["Rainfall"] 
    }
    with open(FINAL_JSON, "w") as f: json.dump(model_input, f, indent=4)
    
    # 4. Predict
    crop = predict_crop(model_input)
    
    # 5. Gemini Explanation (Detailed & Personalized)
    explanation = get_crop_explanation(crop, model_input)
    
    # 6. Scheme Logic
    land_hectares = ui_data["LandSize"] / 10000.0
    is_small_farmer = land_hectares <= 2.0
    scheme_key = CROP_SCHEME_MAP.get(crop, "PM-KISAN")
    scheme_details = SCHEME_DB.get(scheme_key, SCHEME_DB["PM-KISAN"]).copy()

    if is_small_farmer:
        scheme_details["eligibility_msg"] = "✅ Eligible for Small Farmer Benefits"
        if scheme_key == "iKhedut": scheme_details["supporting"] = "Small/Marginal Rate: 50% Subsidy"
    else:
        scheme_details["eligibility_msg"] = "ℹ️ General Category Eligibility"

    # 7. Advisory Logic
    advisory = CROP_ADVISORY.get(crop, CROP_ADVISORY["General"])

    # 8. Save Session
    session['last_result'] = {
        'result': crop,
        'values': model_input, # Contains Sensor + User Data
        'explanation': explanation,
        'scheme': scheme_details,
        'user_land_size': ui_data["LandSize"],
        'advisory': advisory
    }

    return render_template(
        "index.html", 
        result=crop, 
        values=model_input, # Pass this to display sensor data
        explanation=explanation, 
        scheme=scheme_details, 
        user_land_size=ui_data["LandSize"], 
        advisory=advisory
    )

# --- NEW ROUTE FOR AUDIO GENERATION ---
@app.route('/get_audio', methods=['POST'])
def get_audio():
    try:
        data = request.json
        text = data.get('text')
        lang = data.get('lang', 'en-IN') # Default English India
        
        # Extract the language code (e.g., 'gu' from 'gu-IN')
        short_lang = lang.split('-')[0] 

        # 1. Translate text using Gemini
        translated_text = translate_text(text, short_lang)

        # 2. Generate Audio file using gTTS
        filename = f"speech_{int(time.time())}.mp3"
        filepath = os.path.join(AUDIO_DIR, filename)
        
        # Clean up old files to save space
        for f in os.listdir(AUDIO_DIR):
            try:
                os.remove(os.path.join(AUDIO_DIR, f))
            except: pass

        # Create Audio
        tts = gTTS(text=translated_text, lang=short_lang, slow=False)
        tts.save(filepath)
        
        return jsonify({
            "audio_url": f"/static/audio/{filename}", 
            "translated_text": translated_text
        })
    except Exception as e:
        print(f"Audio Error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route("/profit-page")
def profit_page():
    crop = request.args.get("crop")
    land_size = request.args.get("land_size", "") 
    return render_template("profit.html", crop=crop, saved_land_size=land_size)

@app.route("/profit", methods=["POST"])
def profit():
    crop = request.form["crop"]
    land_size = float(request.form["land_size"])
    market_price = float(request.form["market_price"])
    fertilizer_cost = float(request.form["fertilizer_cost"])
    electricity_cost = float(request.form["electricity_cost"])
    labour_cost = float(request.form["labour_cost"])
    misc_cost = float(request.form["misc_cost"])

    crop_row = CROP_DATA[CROP_DATA["crop"].str.strip().str.lower() == crop.lower()]
    
    if not crop_row.empty:
        yield_val = crop_row.iloc[0]["yield_per_m2"]
    else:
        yield_val = 0.5 

    total_yield, revenue, total_cost, net_profit = calculate_profit(
        land_size, yield_val, market_price,
        fertilizer_cost, electricity_cost, labour_cost, misc_cost
    )

    return render_template("profit.html", crop=crop, total_yield=round(total_yield, 2),
                           revenue=round(revenue, 2), total_cost=round(total_cost, 2),
                           net_profit=round(net_profit, 2), saved_land_size=land_size)

def predict_crop(data):
    features = np.array([[ 
        data["Nitrogen"], data["Phosporus"], data["Potassium"],
        data["Temperature"], data["Humidity"], data["pH"], data["Rainfall"]
    ]])
    features = mx.transform(features)
    features = sc.transform(features)
    pred = model.predict(features)[0]
    
    crops = {
        1: "Rice", 2: "Maize", 3: "Jute", 4: "Cotton", 5: "Coconut", 6: "Papaya",
        7: "Orange", 8: "Apple", 9: "Muskmelon", 10: "Watermelon", 11: "Grapes",
        12: "Mango", 13: "Banana", 14: "Pomegranate", 15: "Lentil", 16: "Blackgram",
        17: "Mungbean", 18: "Mothbeans", 19: "Pigeonpeas", 20: "Kidneybeans",
        21: "Chickpea", 22: "Coffee"
    }
    return crops.get(pred, "Unknown")

if __name__ == "__main__":
    app.run(debug=True)