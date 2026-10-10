
import re

PATTERNS = {
    "set_timer": [
        r"\b(?:set|start|create)\s+(?:a\s+)?timer\b",
        r"\bcount\s+down\b",
    ],
    "create_reminder": [
        r"\bremind\s+me\b",
        r"\bset\s+a\s+reminder\b",
    ],
    "create_note": [
        r"\b(?:take|create|save|write)\s+a?\s*note\b",
        r"\bwrite\s+down\b",
    ],
    "get_time": [
        r"\bwhat\s+time\s+is\s+it\b",
        r"\btell\s+me\s+the\s+time\b",
    ],
    "get_date": [
        r"\bwhat(?:'s| is)?\s+today'?s?\s+date\b",
        r"\bwhat\s+is\s+the\s+date\b",
    ],
    "open_website": [
        r"\bopen\s+\w+",
        r"\blaunch\s+\w+",
    ],
    "web_search": [
        r"\b(?:search|look\s+up|find)\s+for\b",
    ],
    "calculate": [
        r"\bcalculate\b",
        r"\bwhat\s+is\s+[\d(]",
    ],
    "cancel_timer": [
        r"\b(?:cancel|stop)\s+(?:the\s+)?timer\b",
        r"\bstop\s+the\s+countdown\b",
    ],
    "help": [
        r"\bhelp\b",
        r"\bwhat\s+can\s+you\s+do\b",
    ],
}


def classify_intent(text: str) -> dict:
    text = text.strip().lower()

    if not text:
        return {"intent": "unknown", "confidence": 0.0}

    matches = [
        intent
        for intent, patterns in PATTERNS.items()
        if any(re.search(pattern, text) for pattern in patterns)
    ]

    if len(matches) == 1:
        return {
            "intent": matches[0],
            "confidence": 0.90,
        }

    if len(matches) > 1:
        return {
            "intent": "ambiguous",
            "confidence": 0.0,
        }

    return {"intent": "unknown", "confidence": 0.0}


if __name__ == "__main__":
    while True:
        command = input("Enter a command (or 'quit'): ").strip()

        if command.lower() == "quit":
            break

        print(classify_intent(command))
