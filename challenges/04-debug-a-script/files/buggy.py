#!/usr/bin/env python3
"""
Grade Report Generator
Processes a list of students and their scores.

BUG CHALLENGE: This script has several bugs. Find and fix them all!
Use: gh copilot explain "<error message>" to understand each error.
Use: gh copilot suggest "<what you want to do>" to find fixes.
"""

# Student data: (name, score out of 100)
student_data = [
    ("Alice", 92),
    ("Bob", 78),
    ("Carol", 85),
    ("Dave", 61),
    ("Eve", 95),
]


def get_letter_grade(score):
    """Convert a numeric score to a letter grade."""
    if score >= 90:
        return "A+" if score >= 95 else "A"
    elif score >= 80:
        return "B"
    elif score >= 70:
        return "C+"  # BUG 1: should be "C+" for 77-79, "C" for 70-76 — but let's keep it simple
    elif score >= 60:
        return "D"
    else:
        return "F"


def print_report(students):
    """Print the grade report."""
    print("Grade Report")
    print("============")

    total = 0
    for name, score in students:
        grade = get_letter_grade(score)
        # BUG 2: String formatting error — wrong variable name
        print(f"{name}: {scor}/100 ({grade})")
        total = total + score

    # BUG 3: Division to get average is using wrong variable (len vs count)
    average = total / lenght(students)
    print(f"\nClass average: {average:.1f}")

    # BUG 4: max() is called incorrectly — key function missing
    best = max(students)
    worst = min(students)
    print(f"Highest score: {best[0]} ({best[1]})")
    print(f"Lowest score: {worst[0]} ({worst[1]})")


# BUG 5: Function called with wrong argument name
print_report(student_data=student_data)
