
import re
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

# Example commands for each supported intent.
training_data = [
    ("set a timer for five minutes", "set_timer"),
    ("start a timer for ten seconds", "set_timer"),
    ("count down for two minutes", "set_timer"),
    ("remind me to study in ten minutes", "create_reminder"),
    ("remind me to drink water", "create_reminder"),
    ("schedule a reminder for my meeting", "create_reminder"),
    ("take a note", "create_note"),
    ("write down buy groceries", "create_note"),
    ("save a note about my project", "create_note"),
    ("what time is it", "get_time"),
    ("tell me today's date", "get_date"),
    ("open google", "open_website"),
    ("launch youtube", "open_website"),
    ("search for cafes in Bengaluru", "web_search"),
    ("look up machine learning tutorials", "web_search"),
    ("calculate 25 plus 17", "calculate"),
    ("what is 100 divided by 4", "calculate"),
    ("cancel my timer", "cancel_timer"),
    ("stop the countdown", "cancel_timer"),
    ("help me", "help"),
]

texts = [text for text, label in training_data]
labels = [label for text, label in training_data]

classifier = Pipeline([
    ("tfidf", TfidfVectorizer(ngram_range=(1, 2))),
    ("model", LogisticRegression(max_iter=1000))
])

classifier.fit(texts, labels)


def classify_intent(text: str) -> dict:
    prediction = classifier.predict([text])[0]
    probabilities = classifier.predict_proba([text])[0]
    confidence = float(max(probabilities))

    return {
        "intent": prediction,
        "confidence": round(confidence, 3)
    }


if __name__ == "__main__":
    while True:
        command = input("Enter a command (or 'quit'): ").strip()

        if command.lower() == "quit":
            break

        print(classify_intent(command))
