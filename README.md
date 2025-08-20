# Guess Human

A simple FastAPI + LangGraph + Gemini web app where an AI tries to guess the human among four answers within up to 3 questions.

## Project Structure (brief)

```
guess_human/
├── app/                     # FastAPI application
│   ├── main.py              # Application entry point, mounts static, registers routes
│   └── routes/
│       └── game.py          # Game API: /game/start and /game/answer
├── src/                     # Core logic
│   ├── orchestrator.py      # Game engine, GuessingAI, QuestionTool, session management
│   └── utils/
│       └── observability.py # Langfuse-safe no-op observability helpers
├── config/
│   └── settings.py          # App settings and env config (uses .env)
├── static/
│   └── index.html           # Minimal UI to play the game
├── requirements.txt         # Python dependencies
├── Dockerfile               # Image for running the app
├── docker-compose.yml       # Local dev compose (maps host 8001 -> container 8000)
└── README.md                # This file
```

## Run (Docker)

- Ensure `.env` exists at repo root with your existing keys (not shown here).
- Build and run:

```powershell
# PowerShell uses ; instead of &&
cd C:\Users\tonyl\Project\manulife_project\guess_human; docker compose up -d
```

Open `http://localhost:8001`.

## Gameplay Flow
- Start: LLM generates 5 creative discriminative questions; one is chosen at random for the first round.
- User answers in one sentence; 3 AI candidate answers are generated in a single structured call.
- Guessing agent decides either:
  - `respond`: guesses the human index and shows the reason, ending the game, or
  - `use_tool`: generates a better follow-up question based on full history.
- AI wins if it identifies the human within 3 rounds; otherwise, human wins.

## Notes
- Uses Gemini structured outputs for both candidate generation and decision making.
- UI clearly highlights the AI’s guessed answer and displays a color banner when the game ends.
