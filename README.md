# SpaceComputer Quiz Bot 🛰️

A Telegram quiz bot for the SpaceComputer community. Questions are AI-generated fresh every round using SpaceComputer's own documentation. Question order, answer shuffling, and tiebreakers all use verifiable cosmic randomness from SpaceComputer's cTRNG satellite beacon.

---

## How it works

- An admin runs `/startquiz` — the bot fetches a live cosmic seed from SpaceComputer's cTRNG IPFS beacon
- Claude (Anthropic API) generates fresh multiple-choice questions grounded in SpaceComputer's knowledge base
- Questions and answer options are shuffled using the cosmic seed — fully verifiable on-chain
- Players tap A / B / C / D — speed matters, faster correct answers earn more points
- After all questions, the winner is announced. Ties are broken by a second cTRNG draw
- All round messages are automatically deleted after the round to keep the chat clean

---

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Set your credentials

Set `TELEGRAM_BOT_TOKEN` and `ANTHROPIC_API_KEY` in your environment before running the bot.

Optional — set `QUIZ_BANNER_IMAGE_URL` to a local image filename or a public URL to show a banner at quiz start.

### 3. Build the knowledge base

Fetches all SpaceComputer docs and blog posts into a local file used for question generation.

```bash
python knowledge_base.py
```

Re-run this whenever SpaceComputer publishes new content, or use `/updatekb` from inside the group.

### 4. Run the bot

```bash
python bot.py
```

### 5. Add the bot to your Telegram group

- Add the bot as a group member
- Give it **"Delete messages" admin permission** — required for auto-cleanup of round messages
- All commands (except `/mystats` and `/alltime`) only work for group admins

---

## Commands

| Command | Who | Description |
|---|---|---|
| `/startquiz` | Admin | Start a new quiz round |
| `/startquiz topic:cTRNG count:10` | Admin | Specific topic and question count (3–20) |
| `/endquiz` | Admin | Force end the current round |
| `/leaderboard` | Admin | Current round standings |
| `/updatekb` | Admin | Re-fetch SpaceComputer docs to refresh question content |
| `/mystats` | Anyone | Your all-time stats — sent to your DMs |
| `/alltime` | Anyone | Hall of Fame — top players across all rounds, sent to DMs |

> Admin commands are group-only and auto-delete after `AUTO_DELETE_DELAY` seconds.  
> Error replies and non-admin attempts also auto-delete.

---

## Topics

Built-in topics (custom topics also accepted):

- `cTRNG`
- `KMS`
- `orbital computing`
- `SpaceComputer architecture`
- `blockchain randomness`
- `general`

---

## Scoring

- Each correct answer earns up to **1000 points** (configurable)
- Points scale with time remaining — faster correct answers earn more
- Minimum 1 point for a correct answer regardless of speed

---

## Database

SQLite (`quiz_data.db`) stores previously asked questions and all-time player scores.

### Reset before testing

```bash
python reset_db.py
```

Wipes all scores and question history for a clean slate.

---

## Configuration (`config.py`)

| Setting | Default | Description |
|---|---|---|
| `QUESTIONS_PER_ROUND` | `5` | Default number of questions per round |
| `QUESTION_TIMER` | `30` | Seconds per question |
| `BASE_POINTS` | `100` | Max points per correct answer |
| `BETWEEN_QUESTION_DELAY` | `5` | Seconds between questions |
| `MIN_QUESTIONS_PER_ROUND` | `3` | Minimum via `count:` param |
| `MAX_QUESTIONS_PER_ROUND` | `20` | Maximum via `count:` param |
| `AUTO_DELETE_DELAY` | `10` | Seconds before transient messages are auto-deleted |

---

## Deployment

Host on any VPS or [Railway.app](https://railway.app) for 24/7 uptime. Set your env vars in the platform dashboard and use `python bot.py` as the start command.
