from ai_service import (
    analyze_emergency,
    classify_civic_issue,
    classify_civic_image
)

import os


# ==========================================
# EMERGENCY AI TEST
# ==========================================

print("\n--- EMERGENCY TEST ---")

emergency = analyze_emergency(
    "Accident at Main Junction. Two people are injured."
)

print(emergency)


# ==========================================
# CIVIC TEXT AI TEST
# ==========================================

print("\n--- CIVIC ISSUE TEST ---")

civic = classify_civic_issue(
    "There is a large pothole on the road near Main Junction."
)

print(civic)

# ==========================================
# EMERGENCY FILE TESTS
# ==========================================

print("\n--- EMERGENCY FILE TESTS ---")

emergency_folder = "data/emergencies"

for filename in os.listdir(emergency_folder):

    if filename.endswith(".txt"):

        file_path = os.path.join(
            emergency_folder,
            filename
        )

        with open(
            file_path,
            "r",
            encoding="utf-8"
        ) as file:

            message = file.read().strip()

        print(f"\nTesting: {filename}")
        print(f"Message: {message}")

        result = analyze_emergency(message)

        print("AI Result:")
        print(result)
