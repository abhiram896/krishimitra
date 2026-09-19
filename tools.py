import os
import logging
import requests
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("tools")

# Illustrative market estimates for 30 major Indian agricultural commodities (prices in INR per kg unless noted)
PRICE_TRENDS = {
    'rice': {'current': 38, 'forecast': 42, 'trend': 'up'},
    'wheat': {'current': 28, 'forecast': 30, 'trend': 'up'},
    'maize': {'current': 24, 'forecast': 23, 'trend': 'down'},
    'tomato': {'current': 45, 'forecast': 52, 'trend': 'up'},
    'onion': {'current': 35, 'forecast': 30, 'trend': 'down'},
    'potato': {'current': 25, 'forecast': 27, 'trend': 'up'},
    'brinjal': {'current': 30, 'forecast': 32, 'trend': 'up'},
    'cabbage': {'current': 20, 'forecast': 18, 'trend': 'down'},
    'cauliflower': {'current': 32, 'forecast': 36, 'trend': 'up'},
    'chili': {'current': 120, 'forecast': 135, 'trend': 'up'},
    'groundnut': {'current': 75, 'forecast': 80, 'trend': 'up'},
    'soybean': {'current': 48, 'forecast': 46, 'trend': 'down'},
    'sugarcane': {'current': 35, 'forecast': 37, 'trend': 'up'},
    'cotton': {'current': 78, 'forecast': 74, 'trend': 'down'},
    'coconut': {'current': 25, 'forecast': 27, 'trend': 'up'},
    'banana': {'current': 35, 'forecast': 38, 'trend': 'up'},
    'mango': {'current': 65, 'forecast': 60, 'trend': 'down'},
    'grapes': {'current': 90, 'forecast': 98, 'trend': 'up'},
    'turmeric': {'current': 140, 'forecast': 155, 'trend': 'up'},
    'ginger': {'current': 110, 'forecast': 125, 'trend': 'up'},
    'tea': {'current': 210, 'forecast': 225, 'trend': 'up'},
    'coffee': {'current': 280, 'forecast': 295, 'trend': 'up'},
    'jute': {'current': 55, 'forecast': 58, 'trend': 'up'},
    'mustard': {'current': 62, 'forecast': 65, 'trend': 'up'},
    'gram': {'current': 68, 'forecast': 72, 'trend': 'up'},
    'tur dal': {'current': 115, 'forecast': 122, 'trend': 'up'},
    'moong': {'current': 95, 'forecast': 92, 'trend': 'down'},
    'okra': {'current': 35, 'forecast': 32, 'trend': 'down'},
    'cucumber': {'current': 22, 'forecast': 25, 'trend': 'up'},
    'garlic': {'current': 160, 'forecast': 175, 'trend': 'up'},
}

# Post-harvest stability window (days until initial spoilage/quality loss under standard storage)
PERISHABILITY = {
    'rice': 180,
    'wheat': 180,
    'maize': 120,
    'tomato': 4,
    'onion': 25,
    'potato': 20,
    'brinjal': 5,
    'cabbage': 7,
    'cauliflower': 6,
    'chili': 14,
    'groundnut': 90,
    'soybean': 90,
    'sugarcane': 10,
    'cotton': 90,
    'coconut': 30,
    'banana': 6,
    'mango': 5,
    'grapes': 7,
    'turmeric': 180,
    'ginger': 30,
    'tea': 180,
    'coffee': 180,
    'jute': 120,
    'mustard': 120,
    'gram': 120,
    'tur dal': 150,
    'moong': 150,
    'okra': 4,
    'cucumber': 5,
    'garlic': 60,
}

# Complete mapping of 28 Indian States + 8 Union Territories to capital cities for weather query fallbacks
STATE_CAPITALS = {
    'andhra pradesh': 'Amaravati',
    'arunachal pradesh': 'Itanagar',
    'assam': 'Dispur',
    'bihar': 'Patna',
    'chhattisgarh': 'Raipur',
    'goa': 'Panaji',
    'gujarat': 'Gandhinagar',
    'haryana': 'Chandigarh',
    'himachal pradesh': 'Shimla',
    'jharkhand': 'Ranchi',
    'karnataka': 'Bengaluru',
    'kerala': 'Thiruvananthapuram',
    'madhya pradesh': 'Bhopal',
    'maharashtra': 'Mumbai',
    'manipur': 'Imphal',
    'meghalaya': 'Shillong',
    'mizoram': 'Aizawl',
    'nagaland': 'Kohima',
    'odisha': 'Bhubaneswar',
    'punjab': 'Chandigarh',
    'rajasthan': 'Jaipur',
    'sikkim': 'Gangtok',
    'tamil nadu': 'Chennai',
    'telangana': 'Hyderabad',
    'tripura': 'Agartala',
    'uttar pradesh': 'Lucknow',
    'uttarakhand': 'Dehradun',
    'west bengal': 'Kolkata',
    # Union Territories
    'andaman and nicobar islands': 'Port Blair',
    'chandigarh': 'Chandigarh',
    'dadra and nagar haveli and daman and diu': 'Daman',
    'delhi': 'New Delhi',
    'delhi (nct)': 'New Delhi',
    'jammu and kashmir': 'Srinagar',
    'ladakh': 'Leh',
    'lakshadweep': 'Kavaratti',
    'puducherry': 'Puducherry',
}


def get_price_trend(crop_name: str) -> dict:
    crop = crop_name.lower().strip()
    data = PRICE_TRENDS.get(crop)
    if not data:
        # Default for unlisted crops
        data = {'current': 40, 'forecast': 42, 'trend': 'stable'}
    return {
        'crop': crop_name.title(),
        'current': data['current'],
        'forecast': data['forecast'],
        'trend': data['trend']
    }


def get_crop_perishability(crop_name: str) -> dict:
    crop = crop_name.lower().strip()
    days = PERISHABILITY.get(crop, 10)
    return {'crop': crop_name.title(), 'days_until_spoils': days}


def get_weather_forecast(region: str, city: str = "") -> dict:
    region_clean = region.strip()
    city_clean = city.strip()
    
    # Determine search location
    if city_clean:
        query_location = city_clean
    else:
        # Fall back to state capital
        query_location = STATE_CAPITALS.get(region_clean.lower(), region_clean)

    api_key = os.getenv("WEATHER_API_KEY")
    
    if api_key and api_key.strip():
        try:
            # Query OpenWeatherMap current weather endpoint
            url = "https://api.openweathermap.org/data/2.5/weather"
            params = {
                "q": f"{query_location},IN",
                "appid": api_key.strip(),
                "units": "metric",
            }
            logger.info(f"Querying OpenWeatherMap for location: {query_location},IN")
            res = requests.get(url, params=params, timeout=10)
            
            if res.status_code == 200:
                data = res.json()
                weather_main = data.get("weather", [{}])[0].get("main", "Clear")
                weather_desc = data.get("weather", [{}])[0].get("description", "clear sky")
                temp_c = round(data.get("main", {}).get("temp", 26.0), 1)
                humidity = data.get("main", {}).get("humidity", 60)
                
                # Estimate clear forecast window (default to 4 days if clear, 1-2 days if rain)
                clear_days = 1 if "rain" in weather_main.lower() or "storm" in weather_main.lower() else 4
                
                return {
                    "region": region_clean,
                    "city": query_location,
                    "forecast": weather_main,
                    "description": weather_desc.title(),
                    "temp_c": temp_c,
                    "humidity": humidity,
                    "days": clear_days,
                    "is_live": True,
                }
            else:
                logger.warning(f"OpenWeatherMap API status {res.status_code}: {res.text[:150]}")
        except Exception as exc:
            logger.error(f"OpenWeatherMap request failed: {exc}")

    # Graceful fallback when API key is unconfigured, invalid, or request fails
    return {
        "region": region_clean,
        "city": query_location,
        "forecast": "Clear / Mild",
        "description": "Seasonal climate pattern (Estimated fallback data)",
        "temp_c": 27.5,
        "humidity": 62,
        "days": 4,
        "is_live": False,
    }
