from flask import Flask, render_template, jsonify, request, redirect
from google import genai
from google.genai import types
import requests
import json
import time

import os
from dotenv import load_dotenv
from pydantic import BaseModel 
import enum

load_dotenv() 
GOOGLE_API_KEY = os.getenv("GEMINI_API_KEY")
GEOCODING_API_KEY = os.getenv("GEOCODING_API_KEY")

"""
- "head": ["baseball-cap", "umbrella", "winter-hat", "none"]
- "torso": ["tshirt", "jacket", "none"]
- "hands": ["christmas-gloves", "none"]
- "legs": ["jeans", "snow-pants", "none"]
- "feet": ["sneakers", "boots", "snow-boots", "none"]
"""

class Head(str, enum.Enum):
    CAP = "baseball-cap"
    RAIN_HAT = "umbrella"
    WINTER_HAT = "winter-hat"
    NONE = "none"

class Torso(str, enum.Enum):
    TSHIRT = "tshirt"
    JACKET = "jacket"
    NONE = "none"

class Hands(str, enum.Enum):
    GLOVES = "christmas-gloves"
    NONE = "none"

class Legs(str, enum.Enum):
    JEANS = "jeans"
    SNOW_PANTS = "snow_pants"
    NONE = "none"

class Feet(str, enum.Enum):
    SNEAKERS = "sneakers"
    RAIN_BOOTS = "boots"
    SNOW_BOOTS = "snow_boots"
    NONE = "none"

# 1. Define your desired JSON structure using Pydantic
class JSON_schema(BaseModel):
    head: Head
    torso: Torso
    hands: Hands
    legs: Legs
    feet: Feet

app = Flask(__name__)

# --- 1. AI KONFIGURATION ---  
# The client gets the API key from the environment variable `GEMINI_API_KEY`.
client = genai.Client(api_key=GOOGLE_API_KEY)

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

# Define the configuration with your system prompt
config = types.GenerateContentConfig(
    system_instruction=system_instruction,
    response_mime_type="application/json",
    response_schema=JSON_schema,
)

# Här sparar vi datan i Pi:ns minne!
cached_data = None
last_update_time = 0

def parse_user_coordinates():
    with open('settings.json', 'r', encoding='utf-8') as f:
        contents = json.load(f)
        post_code = contents['post_code']    
    try:
        url = f"https://api.geoapify.com/v1/geocode/search?text={post_code}&lang=en&limit=10&type=postcode&filter=countrycode:se&apiKey={GEOCODING_API_KEY}"

        resp = requests.get(url)
        data = resp.json()
        properties = data['features'][0]['properties']
        lon = str(round(float(properties['lon']), 4))
        lat = str(round(float(properties['lat']), 4))
        return lon, lat
    except Exception as e:
        if os.path.exists("settings.json"):
            print("exception found: ", e)
            os.remove("settings.json")
        else:
            print("The file does not exist") 
    

def get_smhi_weather(lon, lat):
    url = f"https://opendata-download-metfcst.smhi.se/api/category/snow1g/version/1/geotype/point/lon/{lon}/lat/{lat}/data.json"
    print(url)
    
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
    # 1. TRAFIKPOLISEN: Har användaren redan gjort setupen?
    # Vi kollar om filen 'settings.json' existerar på Raspberry Pi:n.
    if not os.path.exists('settings.json'):
        # Filen saknas! Detta är första uppstarten. Visa setup-sidan.
        return render_template('setup.html')
    
    # 2. Om filen fanns, ladda den vanliga skärmen!
    return render_template('index.html')

@app.route('/setup', methods=['POST'])
def handle_setup():
    # Denna rutt används nu BARA när kunden trycker på "Spara"-knappen
    wifi_namn = request.form['ssid']
    wifi_losen = request.form['password']
    postal_code = request.form['postal_code']

    data_obj = {
        "ssid" : wifi_namn,
        "password" : wifi_losen,
        "post_code" : postal_code
    }
    # set up wifi with some bash script maybe? or modify config file?
    
    with open('settings.json', 'w', encoding='utf-8') as f:
        json.dump(data_obj, f)
    
    return redirect('/')

@app.route('/api/get-clothes')
def get_clothes():
    global cached_data, last_update_time
    current_time = time.time()

    if cached_data and (current_time - last_update_time < 900):
        print("Använder sparad väderdata (Cache hit) - Sparar API-anrop!")
        return jsonify(cached_data)
    
    try:
        # A. Hämta riktig data från SMHI
        lon, lat = parse_user_coordinates()
        weather = get_smhi_weather(lon, lat)
        
        # B. Bygg prompten till Gemini
        prompt = f"It is currently {weather['temperature_celsius']}°C, wind speed is {weather['wind_ms']} m/s, and the general condition is {weather['condition']}."
        
        # C. Fråga Gemini enbart om kläderna
        response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt,
        config=config
        )

        clothes_data = json.loads(response.text)
        print("response from Gemini: ", clothes_data)
        
        # D. Slå ihop SMHI-vädret med Geminis klädval!
        final_payload = {
            "condition": weather['condition'],
            "temperature": f"{int(weather['temperature_celsius'])}°C",
            "clothes": clothes_data # Här ligger Geminis svar (head, torso, etc)
        }
        last_update_time = current_time
        return jsonify(final_payload)

    except Exception as e:
        print(f"Ett fel uppstod: {e}")
        # Reservdata om internet dör
        return jsonify({
            "condition": "rainy", 
            "temperature": "?",
            "clothes": {"head": "none", "torso": "jacket", "hands": "none", "legs": "jeans", "feet": "boots"}
        }), 500

if __name__ == '__main__':
    app.run(port=5000, debug=False)