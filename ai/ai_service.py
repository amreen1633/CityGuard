import os
import json
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI(api_key=API_KEY) if API_KEY else None

MODEL = "gpt-6-luna"


def analyze_emergency(message: str):
    """
    Analyze an emergency message and return structured information.
    """

    if not message or not message.strip():
        return {
            "emergency_type": "unknown",
            "severity": "low",
            "location": "unknown",
            "injured_people": 0,
            "requires_ambulance": False,
            "ai_status": "invalid_input"
        }

    # Safe fallback if API is unavailable
    if client is None:
        return fallback_emergency_analysis(message)

    prompt = f"""
You are the emergency analysis AI for CityGuard,
an AI Smart City Command Center.

Analyze this emergency report:

"{message}"

Return ONLY valid JSON.

Use exactly these fields:

{{
    "emergency_type": "accident/fire/medical/other",
    "severity": "low/medium/high/critical",
    "location": "location mentioned in the report",
    "injured_people": 0,
    "requires_ambulance": true
}}

Rules:
- If the number of injured people is not mentioned, use 0.
- If location is not mentioned, use "unknown".
- An accident with injured people should normally require an ambulance.
- Return no extra text outside JSON.
"""

    try:
        response = client.responses.create(
            model=MODEL,
            input=prompt
        )

        result = response.output_text.strip()

        data = json.loads(result)

        return {
            "emergency_type": data.get("emergency_type", "other"),
            "severity": data.get("severity", "medium"),
            "location": data.get("location", "unknown"),
            "injured_people": data.get("injured_people", 0),
            "requires_ambulance": data.get(
                "requires_ambulance",
                False
            ),
            "ai_status": "success"
        }

    except Exception as e:
        print("AI error:", e)

        return fallback_emergency_analysis(message)


def fallback_emergency_analysis(message: str):
    """
    Backup analysis if the AI API is unavailable.
    """

    text = message.lower()

    emergency_type = "other"
    severity = "medium"
    injured_people = 0
    requires_ambulance = False

    if "accident" in text or "crash" in text or "collision" in text:
        emergency_type = "accident"

    elif "fire" in text:
        emergency_type = "fire"

    elif "heart" in text or "medical" in text or "injured" in text:
        emergency_type = "medical"

    if (
        "critical" in text
        or "multiple injured" in text
        or "serious" in text
    ):
        severity = "critical"

    elif (
        "injured" in text
        or "accident" in text
        or "fire" in text
    ):
        severity = "high"

    if "two" in text:
        injured_people = 2
    elif "three" in text:
        injured_people = 3
    elif "four" in text:
        injured_people = 4
    elif "five" in text:
        injured_people = 5

    if (
        "ambulance" in text
        or "injured" in text
        or emergency_type == "accident"
        or emergency_type == "medical"
    ):
        requires_ambulance = True

    return {
        "emergency_type": emergency_type,
        "severity": severity,
        "location": extract_location(text),
        "injured_people": injured_people,
        "requires_ambulance": requires_ambulance,
        "ai_status": "fallback"
    }


def extract_location(text: str):
    """
    Very simple fallback location extraction.
    """

    locations = [
        "main junction",
        "hitech city",
        "charminar",
        "madhapur",
        "banjara hills",
        "gachibowli",
        "secunderabad"
    ]

    for location in locations:
        if location in text:
            return location.title()

    return "unknown"


def classify_civic_issue(description: str):
    """
    Classify a civic problem from its description.
    """

    if not description or not description.strip():
        return {
            "category": "unknown",
            "severity": "low",
            "confidence": 0.0,
            "ai_status": "invalid_input"
        }

    if client is None:
        return fallback_civic_analysis(description)

    prompt = f"""
You are CityGuard's civic issue classification AI.

Analyze this citizen report:

"{description}"

Return ONLY valid JSON:

{{
    "category": "pothole/garbage/streetlight/water_leakage/road_damage/other",
    "severity": "low/medium/high",
    "confidence": 0.0
}}

Confidence must be a number between 0 and 1.
Return no extra text.
"""

    try:
        response = client.responses.create(
            model=MODEL,
            input=prompt
        )

        result = response.output_text.strip()

        data = json.loads(result)

        return {
            "category": data.get("category", "other"),
            "severity": data.get("severity", "medium"),
            "confidence": float(data.get("confidence", 0.5)),
            "ai_status": "success"
        }

    except Exception as e:
        print("AI error:", e)

        return fallback_civic_analysis(description)


def fallback_civic_analysis(description: str):
    """
    Backup civic issue classifier.
    """

    text = description.lower()

    category = "other"
    severity = "medium"

    if "pothole" in text:
        category = "pothole"

    elif "garbage" in text or "waste" in text:
        category = "garbage"

    elif "streetlight" in text or "street light" in text:
        category = "streetlight"

    elif "water" in text or "leak" in text:
        category = "water_leakage"

    elif "road" in text or "damaged" in text:
        category = "road_damage"

    if "dangerous" in text or "large" in text:
        severity = "high"

    return {
        "category": category,
        "severity": severity,
        "confidence": 0.70,
        "ai_status": "fallback"
    }
