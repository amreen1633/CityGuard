import os
import json
from dotenv import load_dotenv
from openai import OpenAI
import base64
import mimetypes
import re

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
    "category": "pothole/garbage/streetlight/flooding/water_leakage/road_damage/other",
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

    elif "flood" in text or "waterlogging" in text or "water logging" in text:
        category = "flooding"

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


CATEGORY_DEPARTMENTS = {
    "pothole": "Roads and Public Works",
    "road_damage": "Roads and Public Works",
    "garbage": "Sanitation",
    "streetlight": "Electrical Services",
    "water_leakage": "Water and Drainage",
    "flooding": "Water and Drainage",
}

CATEGORY_ALIASES = {
    "streetlight issue": "streetlight",
    "street light": "streetlight",
    "water leakage": "water_leakage",
    "water leak": "water_leakage",
    "road damage": "road_damage",
    "potholes": "pothole",
    "waterlogging": "flooding",
    "water logging": "flooding",
}

EMERGENCY_INDICATORS = (
    ("major accident", "A major accident is described."),
    ("serious accident", "A serious accident is described."),
    ("multiple injured", "Multiple injured people are described."),
    ("people injured", "Injuries are described."),
    ("person injured", "An injury is described."),
    ("injured people", "Injuries are described."),
    ("road collapsed", "A road collapse is described."),
    ("collapsed road", "A road collapse is described."),
    ("road has collapsed", "A road collapse is described."),
    ("road collapse", "A road collapse is described."),
    ("exposed electrical wire", "An exposed electrical wire is described."),
    ("exposed wire", "An exposed electrical wire is described."),
    ("electrical wires are exposed", "Exposed electrical wires are described."),
    ("wire is exposed", "An exposed electrical wire is described."),
    ("wires are exposed", "Exposed electrical wires are described."),
    ("live wire", "A live electrical wire is described."),
    ("dangerous flooding", "Dangerous flooding is described."),
    ("trapped in flood", "Someone is described as trapped by flooding."),
    ("flood water entering", "Flood water is described as entering a building."),
    ("immediate threat", "An immediate threat is described."),
    ("life threatening", "A life-threatening hazard is described."),
    ("trapped under", "Someone is described as trapped."),
)


def _normalize_category(value):
    if not isinstance(value, str):
        return None
    normalized = value.strip().lower().replace("-", "_")
    normalized = CATEGORY_ALIASES.get(normalized, normalized)
    if normalized in {"pothole", "garbage", "streetlight", "flooding",
                      "water_leakage", "road_damage", "other"}:
        return normalized
    return None


def analyze_civic_report(title: str, description: str):
    """Classify a report and separately flag explicit potential emergency hazards."""
    text = "\n".join(part.strip() for part in (title, description) if part and part.strip())
    if not text:
        return {
            "category": "other",
            "severity": "low",
            "confidence": 0.0,
            "department": None,
            "ai_status": "invalid_input",
            "explanation": "No report text was supplied for classification.",
            "emergency_review": False,
            "emergency_reason": None,
            "recommended_next_step": "Request a title and description before assessment.",
            "emergency_ai_status": "not_assessed",
        }

    try:
        raw_classification = classify_civic_issue(text)
    except Exception as error:
        print("Civic classification error:", error)
        raw_classification = {}

    if not isinstance(raw_classification, dict):
        raw_classification = {}

    category = _normalize_category(raw_classification.get("category"))
    severity = raw_classification.get("severity")
    confidence = raw_classification.get("confidence")
    ai_status = raw_classification.get("ai_status")
    valid_severity = isinstance(severity, str) and severity.lower() in {
        "low", "medium", "high"
    }
    valid_confidence = (
        isinstance(confidence, (int, float))
        and not isinstance(confidence, bool)
        and 0 <= confidence <= 1
    )

    if category is None or not valid_severity or not valid_confidence:
        fallback = fallback_civic_analysis(text)
        category = _normalize_category(fallback.get("category")) or "other"
        severity = fallback.get("severity", "medium")
        confidence = fallback.get("confidence", 0.0)
        ai_status = "fallback"
        explanation = "AI output was missing or invalid; a conservative keyword-based classification is shown."
    else:
        severity = severity.lower()
        ai_status = "success" if ai_status == "success" else "fallback"
        explanation = (
            "Category and assessed severity were returned by the AI classifier."
            if ai_status == "success"
            else "AI classification was unavailable; a keyword-based fallback is shown."
        )

    matched_hazard = next(
        ((indicator, reason) for indicator, reason in EMERGENCY_INDICATORS
         if indicator in text.lower()),
        None,
    )
    emergency_review = matched_hazard is not None
    emergency_ai_status = "not_triggered"
    if emergency_review:
        emergency_ai_status = "fallback"
        try:
            emergency_result = analyze_emergency(text)
            if isinstance(emergency_result, dict) and emergency_result.get("ai_status") == "success":
                emergency_ai_status = "success"
        except Exception as error:
            print("Emergency assessment error:", error)

    emergency_reason = matched_hazard[1] if matched_hazard else None
    next_step = (
        "Send this report to a duty officer for immediate human verification. "
        "If someone is in immediate danger, contact local emergency services."
        if emergency_review
        else "Continue normal city-team review; no supported emergency indicator was found."
    )

    return {
        "category": category,
        "severity": severity,
        "confidence": float(confidence),
        "department": CATEGORY_DEPARTMENTS.get(category),
        "ai_status": ai_status,
        "explanation": explanation,
        "emergency_review": emergency_review,
        "emergency_reason": emergency_reason,
        "recommended_next_step": next_step,
        "emergency_ai_status": emergency_ai_status,
    }


def recommend_traffic_signal_timing(congestion_level: str, vehicle_count: str):
    """Recommend a simulation-only green phase from aggregate simulated inputs."""
    level = congestion_level.strip().lower() if isinstance(congestion_level, str) else ""
    if level not in {"low", "medium", "high"}:
        return {
            "ai_status": "invalid_input",
            "congestion_level": level or "unknown",
            "vehicle_count": vehicle_count,
            "directional_counts_available": False,
            "recommended_green_seconds": None,
            "reason": "Traffic input must use LOW, MEDIUM, or HIGH simulation congestion.",
        }

    match = re.fullmatch(r"\s*(\d+)\s*\+?\s*", str(vehicle_count))
    if not match:
        return {
            "ai_status": "invalid_input",
            "congestion_level": level,
            "vehicle_count": vehicle_count,
            "directional_counts_available": False,
            "recommended_green_seconds": None,
            "reason": "A simulated vehicle count is required.",
        }
    count = int(match.group(1))
    if count < 0:
        return {
            "ai_status": "invalid_input",
            "congestion_level": level,
            "vehicle_count": vehicle_count,
            "directional_counts_available": False,
            "recommended_green_seconds": None,
            "reason": "Simulated vehicle count cannot be negative.",
        }

    fallback_durations = {"low": 30, "medium": 40, "high": 50}
    fallback_reason = (
        f"The {level} simulation level with {vehicle_count} displayed vehicles "
        f"maps to a {fallback_durations[level]} second green phase in the transparent demo rule."
    )

    if client is None:
        return {
            "ai_status": "fallback",
            "congestion_level": level,
            "vehicle_count": vehicle_count,
            "directional_counts_available": False,
            "recommended_green_seconds": fallback_durations[level],
            "reason": fallback_reason,
        }

    prompt = f"""
You are advising an operator on a traffic SIMULATION, not real-world traffic.
Inputs: congestion level={level}; displayed simulated vehicle count={vehicle_count}
(numeric lower bound {count}).
There are no directional counts, queue sizes, or real traffic measurements.
Return only JSON with integer recommended_green_seconds between 15 and 90 and
a short reason that mentions this limitation. Do not imply a signal was changed.
"""
    try:
        response = client.responses.create(model=MODEL, input=prompt)
        data = json.loads(response.output_text.strip())
        seconds = data.get("recommended_green_seconds")
        reason = data.get("reason")
        if (
            not isinstance(seconds, int)
            or isinstance(seconds, bool)
            or not 15 <= seconds <= 90
            or not isinstance(reason, str)
            or not reason.strip()
        ):
            raise ValueError("AI returned an invalid traffic timing recommendation")
        return {
            "ai_status": "success",
            "congestion_level": level,
            "vehicle_count": vehicle_count,
            "directional_counts_available": False,
            "recommended_green_seconds": seconds,
            "reason": reason.strip(),
        }
    except Exception as error:
        print("Traffic recommendation error:", error)
        return {
            "ai_status": "fallback",
            "congestion_level": level,
            "vehicle_count": vehicle_count,
            "directional_counts_available": False,
            "recommended_green_seconds": fallback_durations[level],
            "reason": fallback_reason,
        }


def classify_civic_image(image_path: str):
    """
    Analyze a civic issue image using AI.
    Returns category, severity, confidence and description.
    """

    if not os.path.exists(image_path):
        return {
            "category": "unknown",
            "severity": "low",
            "confidence": 0.0,
            "description": "Image file not found",
            "ai_status": "invalid_input"
        }

    if client is None:
        return {
            "category": "unknown",
            "severity": "medium",
            "confidence": 0.0,
            "description": "AI API key not available",
            "ai_status": "fallback"
        }

    try:
        # Read image
        with open(image_path, "rb") as image_file:
            image_data = base64.b64encode(
                image_file.read()
            ).decode("utf-8")

        # Detect image type
        mime_type, _ = mimetypes.guess_type(image_path)

        if mime_type is None:
            mime_type = "image/jpeg"

        image_url = f"data:{mime_type};base64,{image_data}"

        prompt = """
You are CityGuard's civic issue image analysis AI.

Analyze the uploaded image and identify the main civic problem.

Possible categories:

- pothole
- garbage
- streetlight
- flooding
- water_leakage
- road_damage
- other

Return ONLY valid JSON in exactly this format:

{
    "category": "pothole",
    "severity": "low",
    "confidence": 0.0,
    "description": "short description of the problem"
}

Rules:

- category must be one of the categories listed above.
- severity must be low, medium, or high.
- confidence must be a number between 0 and 1.
- Give a short description of what is visible.
- Do not invent details that cannot be seen.
- Return no text outside the JSON.
"""

        response = client.responses.create(
            model=MODEL,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": prompt
                        },
                        {
                            "type": "input_image",
                            "image_url": image_url,
                            "detail": "auto"
                        }
                    ]
                }
            ]
        )

        result = response.output_text.strip()

        data = json.loads(result)

        return {
            "category": data.get("category", "other"),
            "severity": data.get("severity", "medium"),
            "confidence": float(data.get("confidence", 0.5)),
            "description": data.get(
                "description",
                "Civic issue detected"
            ),
            "ai_status": "success"
        }

    except Exception as e:
        print("Image AI error:", e)

        return {
            "category": "unknown",
            "severity": "medium",
            "confidence": 0.0,
            "description": "Unable to analyze image",
            "ai_status": "error"
        }
