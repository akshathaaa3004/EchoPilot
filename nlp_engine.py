
import re
import spacy

# Load the English NLP model
nlp = spacy.load("en_core_web_sm")


def analyze_command(text: str) -> dict:
    """
    Extract named entities and useful command details
    from a user's natural-language command.
    """

    doc = nlp(text)

    entities = {
        "people": [],
        "places": [],
        "organizations": [],
        "dates_and_times": [],
        "durations": []
    }

    # Statistical named-entity recognition
    for ent in doc.ents:
        if ent.label_ == "PERSON":
            entities["people"].append(ent.text)

        elif ent.label_ in ("GPE", "LOC"):
            entities["places"].append(ent.text)

        elif ent.label_ == "ORG":
            entities["organizations"].append(ent.text)

        elif ent.label_ in ("DATE", "TIME"):
            entities["dates_and_times"].append({
                "text": ent.text,
                "type": ent.label_
            })

    # Exact duration extraction for commands like
    # "set a timer for 5 minutes"
    duration_pattern = (
        r"\b\d+\s*"
        r"(?:seconds?|secs?|minutes?|mins?|hours?|hrs?)\b"
    )

    for match in re.finditer(duration_pattern, text, re.I):
        entities["durations"].append(match.group(0))

    return {
        "original_text": text,
        "entities": entities
    }


if __name__ == "__main__":
    examples = [
        "Set a timer for 5 minutes",
        "Remind me to study tomorrow at 6 PM",
        "Search for cafes in Bengaluru"
    ]

    for example in examples:
        print(analyze_command(example))
