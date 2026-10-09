import os
import json
import base64
import mimetypes

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")

# Keep your existing model setting, but allow it to be changed in .env.
MODEL = os.getenv("CITYGUARD_AI_MODEL", "gpt-6-luna")

client = OpenAI(api_key=API_KEY) if API_KEY else None

CIVIC_CATEGORIES = {
    "pothole",
    "garbage",
    "streetlight",
    "water_leakage",
    "road_damage",
    "other",
}

CIVIC_SEVERITIES = {"low", "medium", "high"}
EMERGENCY_TYPES = {"accident", "fire", "medical", "other"}
EMERGENCY_SEVERITIES = {"low", "medium", "high", "critical"}


def parse_json_response(result: str) -> dict:
    """Parse a JSON response from the AI."""
    result = result.strip()

    # Handle responses wrapped in Markdown code fences.
    if result.startswith("```"):
        lines = result.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        result = "\n".join(lines).strip()

    data = json.loads(result)

    if not isinstance(data, dict):
        raise ValueError("AI response must be a JSON object")

    return data


def validate_civic_result(data: dict) -> dict:
    """Validate and normalize a civic issue classification."""
    category = str(data.get("category", "other")).lower().strip()
    severity = str(data.get("severity", "medium")).lower().strip()

    if category not in CIVIC_CATEGORIES:
        category = "other"

    if severity not in CIVIC_SEVERITIES:
        severity = "medium"

    try:
        confidence = float(data.get("confidence", 0.0))
    except (TypeError, ValueError):
        confidence = 0.0

    if not 0.0 <= confidence <= 1.0:
        confidence = max(0.0, min(1.0, confidence))

    description = str(
        data.get("description", "Civic issue detected")
    ).strip()

    if not description:
        description = "Civic issue detected"

    return {
        "category": category,
        "severity": severity,
        "confidence": confidence,
        "description": description,
    }


def analyze_emergency(message: str) -> dict:
    """Analyze an emergency report and return structured information."""
    if not isinstance(message, str) or not message.strip():
        return {
            "emergency_type": "unknown",
            "severity": "low",
            "location": "unknown",
            "injured_people": 0,
            "requires_ambulance": False,
            "ai_status": "invalid_input",
        }

    if client is None:
        return fallback_emergency_analysis(message)

    prompt = f"""
You are the emergency analysis AI for CityGuard.

Analyze this citizen emergency report:
{json.dumps(message)}

Return ONLY a JSON object with these fields:
{{
  "emergency_type": "accident/fire/medical/other",
  "severity": "low/medium/high/critical",
  "location": "location mentioned or unknown",
  "injured_people": 0,
  "requires_ambulance": false
}}

Rules:
- Use only information supported by the report.
- If the number of injured people is not stated, use 0.
- If the location is not stated, use unknown.
- If an accident or medical emergency suggests urgent medical help,
  set requires_ambulance to true.
- Do not invent facts.
"""

    try:
        response = client.responses.create(
            model=MODEL,
            input=prompt,
        )
        data = parse_json_response(response.output_text)

        emergency_type = str(
            data.get("emergency_type", "other")
        ).lower().strip()

        severity = str(
            data.get("severity", "medium")
        ).lower().strip()

        if emergency_type not in EMERGENCY_TYPES:
            emergency_type = "other"

        if severity not in EMERGENCY_SEVERITIES:
            severity = "medium"

        try:
            injured_people = int(data.get("injured_people", 0))
        except (TypeError, ValueError):
            injured_people = 0

        injured_people = max(0, injured_people)

        location = str(data.get("location", "unknown")).strip()
        if not location:
            location = "unknown"

        return {
            "emergency_type": emergency_type,
            "severity": severity,
            "location": location,
            "injured_people": injured_people,
            "requires_ambulance": bool(
                data.get("requires_ambulance", False)
            ),
            "ai_status": "success",
        }

    except Exception as e:
        print("Emergency AI error:", e)
        return fallback_emergency_analysis(message)


def fallback_emergency_analysis(message: str) -> dict:
    """Basic keyword-based emergency analysis when AI is unavailable."""
    text = message.lower()

    emergency_type = "other"
    severity = "medium"
    injured_people = 0

    if any(word in text for word in ("accident", "crash", "collision")):
        emergency_type = "accident"
    elif "fire" in text:
        emergency_type = "fire"
    elif any(word in text for word in ("heart", "medical", "injured")):
        emergency_type = "medical"

    if any(
        phrase in text
        for phrase in ("critical", "multiple injured", "life-threatening")
    ):
        severity = "critical"
    elif any(
        word in text
        for word in ("injured", "accident", "fire", "dangerous")
    ):
        severity = "high"

    number_words = {
        "one": 1,
        "two": 2,
        "three": 3,
        "four": 4,
        "five": 5,
    }

    for word, number in number_words.items():
        if word in text:
            injured_people = number
            break

    requires_ambulance = (
        "ambulance" in text
        or "injured" in text
        or emergency_type in {"accident", "medical"}
    )

    return {
        "emergency_type": emergency_type,
        "severity": severity,
        "location": extract_location(text),
        "injured_people": injured_people,
        "requires_ambulance": requires_ambulance,
        "ai_status": "fallback",
    }


def extract_location(text: str) -> str:
    """Simple location extraction for fallback mode."""
    locations = [
        "main junction",
        "hitech city",
        "charminar",
        "madhapur",
        "banjara hills",
        "gachibowli",
        "secunderabad",
    ]

    text = text.lower()

    for location in locations:
        if location in text:
            return location.title()

    return "unknown"


def classify_civic_issue(description: str) -> dict:
    """Classify a civic problem described in text."""
    if not isinstance(description, str) or not description.strip():
        return {
            "category": "unknown",
            "severity": "low",
            "confidence": 0.0,
            "ai_status": "invalid_input",
        }

    if client is None:
        return fallback_civic_analysis(description)

    prompt = f"""
You are CityGuard's civic issue classification AI.

Analyze this citizen report:
{json.dumps(description)}

Return ONLY JSON:
{{
  "category": "pothole/garbage/streetlight/water_leakage/road_damage/other",
  "severity": "low/medium/high",
  "confidence": 0.0
}}

Confidence must be between 0 and 1.
Do not invent details.
"""

    try:
        response = client.responses.create(
            model=MODEL,
            input=prompt,
        )
        data = parse_json_response(response.output_text)
        validated = validate_civic_result(data)

        return {
            "category": validated["category"],
            "severity": validated["severity"],
            "confidence": validated["confidence"],
            "ai_status": "success",
        }

    except Exception as e:
        print("Civic text AI error:", e)
        return fallback_civic_analysis(description)


def fallback_civic_analysis(description: str) -> dict:
    """Keyword-based civic issue classification."""
    text = description.lower()

    category = "other"
    severity = "medium"

    if "pothole" in text:
        category = "pothole"
    elif "garbage" in text or "waste" in text or "rubbish" in text:
        category = "garbage"
    elif "streetlight" in text or "street light" in text:
        category = "streetlight"
    elif "water" in text or "leak" in text or "waterlogging" in text:
        category = "water_leakage"
    elif "road" in text or "damaged" in text:
        category = "road_damage"

    if any(word in text for word in ("dangerous", "large", "severe")):
        severity = "high"

    return {
        "category": category,
        "severity": severity,
        "confidence": 0.70,
        "ai_status": "fallback",
    }


def classify_civic_image(image_path: str) -> dict:
    """Analyze an image and classify the visible civic issue."""
    if not image_path or not os.path.isfile(image_path):
        return {
            "category": "unknown",
            "severity": "low",
            "confidence": 0.0,
            "description": "Image file not found",
            "ai_status": "invalid_input",
        }

    if client is None:
        return {
            "category": "unknown",
            "severity": "medium",
            "confidence": 0.0,
            "description": "AI API key not available",
            "ai_status": "fallback",
        }

    try:
        mime_type, _ = mimetypes.guess_type(image_path)

        allowed_image_types = {
            "image/jpeg",
            "image/png",
            "image/webp",
            "image/gif",
        }

        if mime_type not in allowed_image_types:
            return {
                "category": "unknown",
                "severity": "low",
                "confidence": 0.0,
                "description": "Unsupported image format",
                "ai_status": "invalid_input",
            }

        with open(image_path, "rb") as image_file:
            raw_image = image_file.read()

        if not raw_image:
            return {
                "category": "unknown",
                "severity": "low",
                "confidence": 0.0,
                "description": "Image file is empty",
                "ai_status": "invalid_input",
            }

        image_data = base64.b64encode(raw_image).decode("utf-8")
        image_url = f"data:{mime_type};base64,{image_data}"

        prompt = """
You are CityGuard's civic issue image analysis AI.

Identify the main visible civic problem.

Possible categories:
pothole, garbage, streetlight, water_leakage, road_damage, other

Return ONLY JSON:
{
  "category": "other",
  "severity": "low",
  "confidence": 0.0,
  "description": "Short description of what is visible"
}

Rules:
- Severity must be low, medium, or high.
- Confidence must be between 0 and 1.
- Describe only what can actually be seen.
- If no civic issue is visible, use category other.
- Do not invent details.
"""

        response = client.responses.create(
            model=MODEL,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt,
                        },
                        {
                            "type": "input_image",
                            "image_url": image_url,
                            "detail": "auto",
                        },
                    ],
                }
            ],
        )

        data = parse_json_response(response.output_text)
        validated = validate_civic_result(data)

        return {
            **validated,
            "ai_status": "success",
        }

    except Exception as e:
        print("Image AI error:", e)

        return {
            "category": "unknown",
            "severity": "medium",
            "confidence": 0.0,
            "description": "Unable to analyze image",
            "ai_status": "error",
        }
