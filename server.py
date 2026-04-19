from flask import Flask, render_template, jsonify
import google.generativeai as genai
import requests
import json
import os
from dotenv import load_dotenv 

app = Flask(__name__)

# --- 1. AI KONFIGURATION ---
load_dotenv() 
GOOGLE_API_KEY = os.getenv("API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

system_instruction = """
You are a children's stylist. Based on the provided weather conditions, decide what clothes a child (represented by a bear) should wear outside.

You MUST respond with ONLY a valid JSON object containing a "clothes" object with 5 zones. No markdown, no small talk. 

Choose EXACTLY ONE item per zone from the lists below, or "none":
- "head": ["baseball-cap", "umbrella", "winter-hat", "none"]
- "torso": ["tshirt", "jacket", "none"]
- "hands": ["christmas-gloves", "none"]
- "legs": ["jeans", "snow-pants", "none"]
- "feet": ["sneakers", "boots", "snow-boots", "none"]

Example output:
{
  "head": "baseball-cap",
  "torso": "jacket",
  "hands": "none",
  "legs": "jeans",
  "feet": "sneakers"
}
"""

model = genai.GenerativeModel(
    model_name="gemini-2.5-flash",
    system_instruction=system_instruction,
    generation_config={"response_mime_type": "application/json"} 
)

def get_smhi_weather():
    # Koordinater för Linköping
    url = "https://opendata-download-metfcst.smhi.se/api/category/snow1g/version/1/geotype/point/lon/15.6214/lat/58.4108/data.json"
    
    response = requests.get(url)
    data = response.json()
    
    # Hämta den närmaste timmens prognos (index 0)
    current_forecast = data['timeSeries'][0]
    
    temp = current_forecast['data']['air_temperature']
    wind = current_forecast['data']['wind_speed']
    symbol_code = current_forecast['data']['symbol_code']

    # Översätt SMHI:s sifferkod (1-27) till din apps format
    # 1-3 = Klart/Halvklart, 4-7 = Mulet, 8-14 = Regn, 15-27 = Snö/Blandat
    if symbol_code in [1, 2, 3]:
        condition = "sunny"
    elif symbol_code in [4, 5, 6, 7]:
        condition = "cloudy"
    elif symbol_code in [8, 9, 10, 11, 12, 13, 14, 18, 19, 20, 21, 22, 23, 24]:
        condition = "rainy"
    else:
        condition = "snowy"
    return {
        "temperature_celsius": temp,
        "wind_ms": wind,
        "condition": condition,
    }

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/get-clothes')
def get_clothes():
    try:
        # A. Hämta riktig data från SMHI
        weather = get_smhi_weather()
        
        # B. Bygg prompten till Gemini
        prompt = f"It is currently {weather['temperature_celsius']}°C, wind speed is {weather['wind_ms']} m/s, and the general condition is {weather['condition']}."
        
        # C. Fråga Gemini enbart om kläderna
        ai_response = model.generate_content(prompt)
        clothes_data = json.loads(ai_response.text)
        
        # D. Slå ihop SMHI-vädret med Geminis klädval!
        final_payload = {
            "condition": weather['condition'],
            "temperature": f"{int(weather['temperature_celsius'])}°C",
            "clothes": clothes_data['clothes'] # Här ligger Geminis svar (head, torso, etc)
        }
        
        return jsonify(final_payload)

    except Exception as e:
        print(f"Ett fel uppstod: {e}")
        # Reservdata om internet dör
        return jsonify({
            "condition": "cloudy", 
            "temperature": "ERROR",
            "clothes": {"head": "none", "torso": "jacket", "hands": "none", "legs": "jeans", "feet": "sneakers"}
        }), 500

if __name__ == '__main__':
    # Tryggt och säkert stängt för omvärlden!
    app.run(port=5000, debug=True)