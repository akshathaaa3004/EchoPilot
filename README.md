# EchoPilot Step-by-Step Upgrade (v3)

## Step 1: Extract and open
Extract this ZIP into a NEW folder. Open that folder in VS Code.

## Step 2: Create environment and install
Windows PowerShell:
```powershell
py -m venv .venv
.venv\Scripts\activate
python -m pip install -r requirements.txt
```

## Step 3: Run
```powershell
python -m uvicorn main:app --reload
```
Open http://127.0.0.1:8000 and keep the terminal running. API docs: http://127.0.0.1:8000/docs.

## Step 4: Test clarification
1. Type `Set a timer` and click Interpret command.
2. It should ask how long.
3. Type `5 minutes` and click Interpret command.
4. It should preview a five-minute timer. Click Confirm & run.

## Step 5: Test multiple actions
Type:
`Take a note: meeting at 3 pm and set a timer for 10 seconds`
Review the combined preview and confirm. The note is stored locally and timer starts.

## Supported commands
- `Set a timer for 30 seconds` / `Set a timer for 5 minutes`
- `Cancel timer`
- `Remind me in 1 minute to stretch`
- `Take a note: buy milk`
- `Calculate 12 * (3 + 2)`
- `What time is it`
- `What is today's date`
- `Open example.com`
- `Search for Python tutorials`
- `Help`

## Limitations
This is a rule-based MVP, not a general LLM. Multi-action splitting is deliberately conservative and only supports recognized action patterns joined with “and”. The contextual clarification currently handles common follow-ups such as a timer duration and missing note content; it is not full conversation memory. Timers/reminders require the page to stay open. Notes are local to the browser. Calendar-style reminders like “tomorrow at 5 pm” and automatic speech-confidence scoring are not implemented. Test each feature before the demo.
