import os
import json

from dotenv import load_dotenv

from tools import get_price_trend, get_weather_forecast, get_crop_perishability

load_dotenv()

try:
    import anthropic
except ImportError:  # pragma: no cover
    anthropic = None


def _build_fallback(crop_name: str, disease_severity: str, current_price: int, region: str, city: str = "") -> dict:
    price_data = get_price_trend(crop_name)
    weather_data = get_weather_forecast(region, city)
    perishability_data = get_crop_perishability(crop_name)

    projected_gap = price_data["forecast"] - current_price
    days = perishability_data["days_until_spoils"]
    weather = weather_data["forecast"].lower()
    severe = disease_severity.lower() in {"moderate", "severe"}
    urgent = severe or "rain" in weather or "storm" in weather or days <= 5

    location_str = f"{city}, {region}" if city else region
    if urgent or projected_gap >= 6:
        recommendation = "SELL NOW"
        reasoning = (
            f"Market price forecast for {crop_name.title()} is ₹{price_data['forecast']}/unit. "
            f"Crop has ~{days} days before quality degradation in {location_str}. "
            f"Weather condition ({weather_data['forecast']}) and {disease_severity} disease severity make a timely sale recommended to lock in current market value."
        )
    else:
        hold_days = max(1, min(5, days - 2))
        recommendation = f"HOLD {hold_days} days"
        reasoning = (
            f"Market trends for {crop_name.title()} suggest potential price gain up to ₹{price_data['forecast']}/unit. "
            f"Produce quality remains stable ({days} days window) under favorable weather ({weather_data['forecast']}) in {location_str}."
        )

    weather_display = f"{weather_data['forecast']} ({weather_data.get('description', '')})" if weather_data.get('description') else weather_data['forecast']
    if weather_data.get('temp_c'):
        weather_display += f" • {weather_data['temp_c']}°C"

    return {
        "recommendation": recommendation,
        "reasoning": reasoning,
        "price_forecast": price_data["forecast"],
        "weather": weather_display,
        "perishability": f"{days} days remaining",
        "confidence_score": 85 if recommendation == "SELL NOW" else 79,
        "tool_outputs": [
            {"tool": "get_price_trend", "output": price_data},
            {"tool": "get_weather_forecast", "output": weather_data},
            {"tool": "get_crop_perishability", "output": perishability_data},
        ],
    }


def get_sell_hold_advice(crop_name: str, disease_severity: str, current_price: int, region: str, city: str = "") -> dict:
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic and api_key:
        try:
            client = anthropic.Anthropic(api_key=api_key)
            tools = [
                {
                    "name": "get_price_trend",
                    "description": "Fetch price trend for a crop and its forecast",
                    "input_schema": {
                        "type": "object",
                        "properties": {"crop_name": {"type": "string"}},
                        "required": ["crop_name"],
                    },
                },
                {
                    "name": "get_weather_forecast",
                    "description": "Get weather trend and clear-day window for a region and city in India",
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "region": {"type": "string"},
                            "city": {"type": "string"},
                        },
                        "required": ["region"],
                    },
                },
                {
                    "name": "get_crop_perishability",
                    "description": "Get the crop's spoilage window in days",
                    "input_schema": {
                        "type": "object",
                        "properties": {"crop_name": {"type": "string"}},
                        "required": ["crop_name"],
                    },
                },
            ]
            location_desc = f"{city}, {region}" if city else region
            messages = [{
                "role": "user",
                "content": f"I have {crop_name} with {disease_severity} disease severity. Current price: ₹{current_price}/kg. Location: {location_desc}. Please investigate price, weather, and perishability and recommend SELL NOW or HOLD for X days.",
            }]
            response = client.messages.create(
                model="claude-3-5-sonnet-latest",
                max_tokens=800,
                system="You are an AI agronomist. Use the tools for price, weather, and perishability, then recommend SELL NOW or HOLD X days with a short reasoning summary.",
                tools=tools,
                messages=messages,
            )
            if response.stop_reason == "tool_use":
                tool_outputs = []
                for block in response.content:
                    if getattr(block, "type", None) == "tool_use":
                        if block.name == "get_price_trend":
                            result = get_price_trend(block.input["crop_name"])
                        elif block.name == "get_weather_forecast":
                            result = get_weather_forecast(block.input["region"], block.input.get("city", city))
                        elif block.name == "get_crop_perishability":
                            result = get_crop_perishability(block.input["crop_name"])
                        else:
                            result = {"error": "unknown tool"}
                        tool_outputs.append({"type": "tool_result", "tool_use_id": block.id, "content": json.dumps(result)})
                if tool_outputs:
                    final_response = client.messages.create(
                        model="claude-3-5-sonnet-latest",
                        max_tokens=800,
                        system="You are an AI agronomist. Provide concise advice in plain English.",
                        messages=[
                            {"role": "assistant", "content": response.content},
                            {"role": "user", "content": tool_outputs},
                        ],
                    )
                    final_text = "\n".join(block.text for block in final_response.content if hasattr(block, "text"))
                    weather_res = get_weather_forecast(region, city)
                    return {
                        "recommendation": "SELL NOW" if "sell" in final_text.lower() else "HOLD",
                        "reasoning": final_text,
                        "price_forecast": get_price_trend(crop_name)["forecast"],
                        "weather": f"{weather_res['forecast']} ({weather_res.get('description', '')})",
                        "perishability": f"{get_crop_perishability(crop_name)['days_until_spoils']} days remaining",
                        "confidence_score": 87,
                        "tool_outputs": tool_outputs,
                    }
            final_text = "\n".join(block.text for block in response.content if hasattr(block, "text"))
            weather_res = get_weather_forecast(region, city)
            return {
                "recommendation": "SELL NOW" if "sell" in final_text.lower() else "HOLD",
                "reasoning": final_text,
                "price_forecast": get_price_trend(crop_name)["forecast"],
                "weather": f"{weather_res['forecast']} ({weather_res.get('description', '')})",
                "perishability": f"{get_crop_perishability(crop_name)['days_until_spoils']} days remaining",
                "confidence_score": 87,
                "tool_outputs": [],
            }
        except Exception:
            pass

    return _build_fallback(crop_name, disease_severity, current_price, region, city)


def get_diagnosis_explanation(disease_name: str, severity: str, confidence: float) -> str:
    """Generate a simple, actionable AI agronomist explanation and remedies using Claude."""
    api_key = os.getenv("ANTHROPIC_API_KEY")
    if anthropic and api_key:
        try:
            client = anthropic.Anthropic(api_key=api_key)
            prompt = (
                f"You are an agronomist. A farmer's crop was diagnosed with {disease_name} "
                f"at {severity} severity, {confidence}% confidence. In under 100 words, "
                f"explain what this means in simple language and give 2-3 practical, actionable "
                f"next steps or remedies a smallholder Indian farmer could realistically follow."
            )
            response = client.messages.create(
                model="claude-3-5-sonnet-latest",
                max_tokens=300,
                system="You are an expert AI agronomist for Indian smallholder farmers. Provide simple, concise, practical advice.",
                messages=[{"role": "user", "content": prompt}],
            )
            text_blocks = [block.text for block in response.content if hasattr(block, "text")]
            if text_blocks:
                return "\n".join(text_blocks).strip()
        except Exception as exc:
            pass
    return ""
