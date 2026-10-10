from datetime import datetime, timedelta
import re
from pathlib import Path
import ast
import operator
import uuid
from typing import Optional, Dict, Any, List

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from nlp_engine import analyze_command

ROOT = Path(__file__).resolve().parent
app = FastAPI(title="EchoPilot Voice Command API", version="3.0")
pending: Dict[str, Dict[str, Any]] = {}

class CommandRequest(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    context: Optional[Dict[str, Any]] = None

class ConfirmRequest(BaseModel):
    command_id: str
    confirmed: bool

OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
       ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv,
       ast.Mod: operator.mod, ast.Pow: operator.pow,
       ast.USub: operator.neg, ast.UAdd: operator.pos}

def safe_calculate(expression: str):
    tree = ast.parse(expression, mode="eval")
    def visit(node):
        if isinstance(node, ast.Expression): return visit(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)): return node.value
        if isinstance(node, ast.BinOp) and type(node.op) in OPS:
            left, right = visit(node.left), visit(node.right)
            if isinstance(node.op, ast.Pow) and abs(right) > 8: raise ValueError("Exponent too large")
            result = OPS[type(node.op)](left, right)
            if abs(result) > 1e15: raise ValueError("Result too large")
            return result
        if isinstance(node, ast.UnaryOp) and type(node.op) in OPS: return OPS[type(node.op)](visit(node.operand))
        raise ValueError("Only basic arithmetic is supported")
    return visit(tree)

def result(raw, intent, *, entities=None, missing=None, question=None, preview=None,
           action=None, status="awaiting_confirmation", message=None, cid=None):
    cid = cid or str(uuid.uuid4())[:8]
    if action is not None:
        pending[cid] = action
    return {"command_id": cid, "transcript": raw, "intent": intent,
            "entities": entities or {}, "missing_fields": missing or [],
            "clarification": question, "preview": preview, "status": status,
            "message": message, "context": None}



def extract_reminder_details(text):
    text = text.strip()

    match = re.fullmatch(
        r"remind me to (.+?)\s+"
        r"(?:(today|tomorrow)\s+)?"
        r"(?:at\s+(\d{1,2}(?::\d{2})?\s*(?:am|pm)))?",
        text,
        re.IGNORECASE
    )

    if not match:
        return None

    task, day, clock_time = match.groups()

    if not day and not clock_time:
        return {
            "task": task.strip(),
            "when": None
        }

    when_parts = []

    if day:
        when_parts.append(day.lower())

    if clock_time:
        if not validate_clock_time(clock_time):
            return {
                "task": task.strip(),
                "when": clock_time.strip(),
                "invalid_time": True
            }

        when_parts.append(clock_time.strip().upper())

    return {
        "task": task.strip(),
        "when": " ".join(when_parts),
        "invalid_time": False
    }



def validate_clock_time(time_text):
    """Validate a clock time such as 6 PM or 6:30 PM."""
    if not time_text:
        return False

    try:
        datetime.strptime(time_text.strip().upper(), "%I %p")
        return True
    except ValueError:
        pass

    try:
        datetime.strptime(time_text.strip().upper(), "%I:%M %p")
        return True
    except ValueError:
        return False

def parse_single(raw: str):
    text = raw.strip()
    low = text.lower()
    cid = str(uuid.uuid4())[:8]

    if low in {"help", "what can you do", "what commands can i say", "show commands"}:
        return result(text, "help", status="info",
          message="Try timers, relative reminders, notes, calculations, date/time, opening websites, web search, or 'help'.",
          cid=cid)

    if any(p in low for p in ("what time is it", "tell me the time", "current time", "what's the time")):
        now = datetime.now().astimezone().strftime("%I:%M %p %Z").strip()
        return result(text, "tell_time", entities={"time":now}, preview=f"The current server time is {now}.",
                      action={"type":"tell_time","value":now}, message="Confirm to display the time.", cid=cid)

    if any(p in low for p in ("what is today's date", "what's today's date", "what is the date", "today's date", "current date")):
        today = datetime.now().astimezone().strftime("%A, %d %B %Y")
        return result(text, "tell_date", entities={"date":today}, preview=f"Today's date is {today}.",
                      action={"type":"tell_date","value":today}, message="Confirm to display the date.", cid=cid)

    if any(w in low for w in ("timer", "countdown", "set a timer", "start a timer")):
        m = re.search(r"\b(\d{1,4})\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h)\b", low)
        if not m:
            return result(text, "set_timer", missing=["duration"],
              question="How long should the timer run? Reply with a duration, such as '5 minutes'.",
              status="needs_clarification", message="Timer duration is missing.", cid=cid)
        amount = int(m.group(1)); unit = m.group(2)
        multiplier = 1 if unit.startswith(("s","sec")) else 60 if unit.startswith(("m","min")) else 3600
        seconds = amount * multiplier
        if seconds <= 0 or seconds > 604800:
            return result(text, "set_timer", missing=["valid_duration"],
              question="Choose a duration from 1 second to 7 days.", status="needs_clarification", cid=cid)
        label = f"{amount} {unit}"
        return result(text, "set_timer", entities={"duration":label,"seconds":seconds},
          preview=f"Start a countdown for {label}.", action={"type":"set_timer","seconds":seconds,"label":label},
          message="Confirm to start the countdown in this webpage.", cid=cid)

    if any(p in low for p in ("cancel timer", "stop timer", "stop the timer")):
        return result(text, "cancel_timer", preview="Cancel the active countdown.",
          action={"type":"cancel_timer"}, message="Confirm to cancel the active countdown.", cid=cid)

    calc = re.match(r"^(?:calculate|compute|solve|what is|what's)\s+(.+?)\s*[?。]?$", text, re.I)
    if calc and re.search(r"\d", calc.group(1)) and re.fullmatch(r"[\d\s().,+*/%\-^]+", calc.group(1)):
        expression = calc.group(1).replace("^", "**")
        try:
            value = safe_calculate(expression)
            return result(text, "calculate", entities={"expression":expression,"result":value},
              preview=f"{expression} = {value}", action={"type":"show_result","label":f"{expression} = {value}"},
              message="Confirm to display the result.", cid=cid)
        except (ValueError, SyntaxError, ZeroDivisionError, OverflowError):
            return result(text, "calculate", status="needs_clarification",
              question="Try a calculation like 'calculate 12 * (3 + 2)'.", cid=cid)

    if any(p in low for p in ("take a note", "make a note", "save a note", "write down", "note:")):
        note = re.sub(r"^(?:please\s+)?(?:take a note(?: saying| that)?|make a note(?: saying| that)?|save a note(?: saying| that)?|write down|note)\s*:?\s*", "", text, flags=re.I).strip()
        if not note:
            return result(text, "create_note", missing=["note_text"], question="What should the note say?",
                          status="needs_clarification", cid=cid)
        return result(text, "create_note", entities={"note_text":note}, preview=f"Save this note: “{note}”",
          action={"type":"create_note","note":note}, message="Confirm to save this note in this browser.", cid=cid)

   # Create reminder using extract_reminder_details
    reminder = extract_reminder_details(text)

    if reminder:
        task = reminder["task"]
        when = reminder["when"]

        if not task:
            return result(
                text, "create_reminder",
                missing=["task"],
                question="What would you like me to remind you about?",
                status="needs_clarification",
                cid=cid
            )

        if not when:
            return result(
                text, "create_reminder",
                missing=["when"],
                question=f"When should I remind you to {task}?",
                status="needs_clarification",
                message=f"When should I remind you to {task}?",
                cid=cid
            )

        if re.search(r"\b(?:at|tomorrow|today)\b", when, re.IGNORECASE):
            time_match = re.search(
                r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm)\b",
                when,
                re.IGNORECASE
            )

            if time_match and not validate_clock_time(time_match.group()):
                return result(
                    text, "create_reminder",
                    status="needs_clarification",
                    question="That time doesn't look valid. Please provide a time such as 6 PM or 6:30 PM.",
                    message="Invalid clock time provided.",
                    cid=cid
                )

        return result(
            text, "create_reminder",
            entities={"task": task, "when": when},
            preview=f"Create a reminder: {task} ({when})?",
            action={
                "type": "create_reminder",
                "task": task,
                "when": when
            },
            message=f"Create a reminder: {task} ({when})?",
            cid=cid
        )

    if "remind me" in low or "reminder" in low:
        return result(text, "create_reminder", missing=["relative_time","task"],
          question="Try: 'Remind me in 10 minutes to take a break.' This prototype supports relative reminders.",
          status="needs_clarification", cid=cid)

    if low.startswith(("open ", "go to ", "visit ")):
        target = re.sub(r"^(open|go to|visit)\s+", "", text, flags=re.I).strip()
        if not target:
            return result(text, "open_website", missing=["website"], question="Which website should I open?",
                          status="needs_clarification", cid=cid)
        return result(text, "open_website", entities={"website":target}, preview=f"Open {target} in a new tab.",
          action={"type":"open_website","website":target}, message="Confirm to open the website.", cid=cid)

    sm = re.match(r"^(?:search for|google|look up)\s+(.+)$", text, re.I)
    if sm:
        query = sm.group(1).strip()
        return result(text, "web_search", entities={"query":query}, preview=f"Search the web for: {query}",
          action={"type":"web_search","query":query}, message="Confirm to open search results.", cid=cid)

    return result(text, "unknown", status="unsupported",
      question="Try 'help' for supported commands, or rephrase your request.",
      message="I couldn't confidently match this to a supported action.", cid=cid)

def split_actions(text: str) -> List[str]:
    # MVP splitter: split "and" only when followed by a recognizable new action phrase.
    pattern = r"\s+and\s+(?=(?:set (?:a )?timer|start (?:a )?timer|take a note|make a note|save a note|remind me|open |go to |visit |search for |google |look up |calculate |compute |cancel timer))"
    parts = re.split(pattern, text, flags=re.I)
    return [p.strip(" .") for p in parts if p.strip(" .")]


def interpret(text: str, context: Optional[dict] = None):
    raw = text.strip()

    # Step 1: Complete an earlier command when the user supplies
    # the missing information.
    if context:
        intent = context.get("intent")

        if intent == "set_timer":
            if re.fullmatch(
                r"\d{1,4}\s*(?:seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h)",
                raw,
                re.I
            ):
                raw = "Set a timer for " + raw

        elif intent == "create_note" and raw:
            raw = "Take a note: " + raw

        elif intent == "create_reminder":
            # Accept a complete relative reminder as a follow-up.
            if re.match(
                r"^\d{1,4}\s*(?:seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h)\s+(?:to\s+)?\S+",
                raw,
                re.I
            ):
                raw = "Remind me in " + raw

            # If only the task or only the delay was provided,
            # ask for the remaining details.
            else:
                return result(
                    raw,
                    "create_reminder",
                    missing=["relative_time", "task"],
                    question=(
                        "Please provide both a delay and a task, "
                        "for example: '10 minutes to take a break'."
                    ),
                    status="needs_clarification",
                    message="The reminder still needs more information."
                )

    # Step 2: Split commands that contain multiple supported actions.
    parts = split_actions(raw)

    if len(parts) > 1:
        parsed = [parse_single(part) for part in parts]

        # Do not prepare a combined action if any part is incomplete
        # or unsupported.
        bad = next(
            (
                item for item in parsed
                if item["status"] in (
                    "needs_clarification",
                    "unsupported"
                )
            ),
            None
        )

        if bad:
            bad["transcript"] = text
            bad["message"] = (
                "One part of your command needs clarification. "
                "Please provide the missing information."
            )
            bad["context"] = {
                "intent": bad["intent"],
                "original_text": text
            }
            return bad

        actions = []

        for item in parsed:
            action = pending.pop(item["command_id"], None)

            if action is not None:
                actions.append(action)

        if len(actions) != len(parts):
            return result(
                text,
                "multi_action",
                status="unsupported",
                message=(
                    "I couldn't prepare every action safely. "
                    "Please try the commands separately."
                )
            )

        previews = [
            item["preview"] or item["intent"]
            for item in parsed
        ]

        entities = {
            "actions": [
                {
                    "intent": item["intent"],
                    "entities": item["entities"]
                }
                for item in parsed
            ]
        }

        return result(
            text,
            "multi_action",
            entities=entities,
            preview=(
                "Review these actions:\n"
                + "\n".join(
                    f"{i + 1}. {preview}"
                    for i, preview in enumerate(previews)
                )
            ),
            action={
                "type": "multi_action",
                "actions": actions
            },
            message="Review every action before confirming."
        )

    # Step 3: Interpret a single command.
    output = parse_single(raw)
    output["transcript"] = text

    # Preserve the intent so a later reply can complete the command.
    if output["status"] == "needs_clarification":
        output["context"] = {
            "intent": output["intent"],
            "original_text": text
        }

    return output

@app.get("/api/health")
def health():
    return {"status":"ok","service":"EchoPilot"}


@app.post("/api/interpret")
def parse_command(cmd: CommandRequest):
    output = interpret(cmd.text, cmd.context)
    analysis = analyze_command(cmd.text)
    output["nlp_entities"] = analysis["entities"]

    return output


@app.post("/api/confirm")
def confirm_command(req: ConfirmRequest):
    action = pending.pop(req.command_id, None)
    if action is None:
        return {"status":"error","message":"This command expired. Please submit it again."}
    if not req.confirmed:
        return {"status":"cancelled","message":"Cancelled. Nothing was done."}
    return {"status":"executed","message":"Command confirmed.","action":action}

app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
@app.get("/")
def home():
    return FileResponse(ROOT / "static" / "index.html")


if __name__ == "__main__":
    examples = [
        "Remind me to submit my assignment tomorrow at 6 PM",
        "Remind me to call my friend",
        "Remind me to attend class at 8:30 AM",
    ]

    for example in examples:
        print(example)
        print(extract_reminder_details(example))
        print()

        print(extract_reminder_details("Remind me to study at 6 PM"))
        print(extract_reminder_details("Remind me to study tomorrow at 6 PM"))