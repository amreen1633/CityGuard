from ai_service import (
    analyze_emergency,
    classify_civic_issue
)


print("\n--- EMERGENCY TEST ---")

emergency = analyze_emergency(
    "Accident at Main Junction. Two people are injured."
)

print(emergency)


print("\n--- CIVIC ISSUE TEST ---")

civic = classify_civic_issue(
    "There is a large pothole on the road near Main Junction."
)

print(civic)
