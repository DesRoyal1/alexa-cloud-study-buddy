# Cloud Study Buddy

> **A voice-first AWS exam prep platform that quizzes you out loud, evaluates your spoken answers in real time, and adapts to your weaknesses.**

Built on Amazon Alexa, AWS Lambda, DynamoDB, and Anthropic's Claude API — with spaced repetition forgetting curve.

---

## Why I built this

Every AWS exam prep tool I tried had one of three problems:

- **Passive** — flashcards and multiple choice you forget by morning because you never produced the answer out loud
- **Expensive** — $400+ courses with content that doesn't adapt to *your* weaknesses
- **Static** — fixed question banks you memorize the wording of instead of the concept

I didn't want a study tool. I wanted a study *partner*. So I built one.

---

## What it does

Open it: **"Alexa, open Cloud Study Buddy"**

The skill greets you with your current study streak ("You're on a 4-day streak"), then offers a **10-question session**. Each question is generated fresh by Claude, weighted toward your weakest topics — 70% of new questions target areas you've struggled with.

You answer out loud. Claude evaluates your *reasoning*, not just your letter pick, and gives personalized feedback. The next question loads automatically — no need to say "next."

**During any question, you can also say:**
- "Give me a hint" — Claude generates a hint without revealing the answer
- "Repeat the question" — hear it again
- "Skip this question" — move on without penalty
- "How many questions left?" — check session progress

**Other commands:**
- "Progress report" — total stats, accuracy %, weak/strong topics, current streak, exam readiness assessment
- "Explain EC2" (or any AWS concept) — Claude explains it in under 70 words, exam-focused
- "Give me a study tip" — actionable AWS SAA prep advice
- "Bye" — exits

Wrong answers are automatically scheduled for spaced repetition. Every 3rd question in a session is a review of something you got wrong — coming back at increasing intervals (3 → 6 → 12 → 24 sessions) until mastered.

---

## Architecture

```
   ┌─────────────┐     ┌──────────────┐     ┌──────────────┐
   │   Amazon    │────▶│     AWS      │────▶│   Claude AI  │
   │    Alexa    │     │    Lambda    │     │  (Haiku 4.5) │
   │             │◀────│              │◀────│              │
   └─────────────┘     └──────┬───────┘     └──────────────┘
   Voice Interface     Serverless Compute   Intelligence Layer
                              │
                              ▼
                       ┌──────────────┐
                       │   Amazon     │
                       │   DynamoDB   │
                       └──────────────┘
                       Persistent Storage

   DynamoDB Tables:
     • CloudStudyProgress — quiz attempts, accuracy, streaks, weak topics
     • CloudStudyReview   — spaced repetition queue, review intervals
```

### Why each component

| Component | Why this choice |
|---|---|
| **Alexa** | Voice forces *active recall* — saying an answer out loud is the actual mechanism that builds long-term memory. Reading flashcards is passive. |
| **Lambda** | Bursty workload (20-minute study sessions, then idle). Pay-per-invocation, near-zero cost at this scale. |
| **Claude (Haiku 4.5)** | Generates infinite fresh questions, evaluates spoken reasoning, explains concepts. Haiku is fast and cheap — keeps end-to-end voice latency low. |
| **DynamoDB** | Access patterns are key-based by user ID, never relational joins. Single-digit-millisecond reads. No connection pooling pain that RDS has with Lambda. |
| **`urllib` (no SDK)** | Standard library only — no extra Lambda layer needed, smaller deployment, faster cold start. Trade-off: more verbose HTTP code. Worth it for serverless. |

---

## Repository structure

```
.
├── lambda/
│   └── lambda_function.py     # Main handler — intent routing, Claude API, DynamoDB I/O
├── interaction-model/
│   └── en-US.json             # Alexa skill model — intents, slots, sample utterances
├── Privacy_policy
├── requirements.txt
├── .gitignore
└── README.md
```

---

## Tech stack

- **Runtime:** Python 3 on AWS Lambda
- **Voice:** Amazon Alexa Skills Kit (custom intents + slot resolution)
- **AI:** Anthropic Claude API (Haiku 4.5)
- **Persistence:** Amazon DynamoDB (two tables, partition + sort key design)
- **Observability:** Amazon CloudWatch Logs (structured logging on every invocation)
- **Secrets:** Lambda environment variables (Claude API key never hardcoded)

---

## How it works under the hood

### Intent routing
Alexa NLU maps user utterances to one of 11 custom intents and 3 built-ins (Help, Cancel/Stop, Fallback). The Lambda handler routes on intent name and pulls session attributes for in-progress quiz state. Slot resolution handles answer variations — "B," "option B," "the answer is B" all resolve cleanly.

### Adaptive question generation
A weighted topic selector reads each user's accuracy from `CloudStudyProgress` and biases new questions 70% toward topics where they're below 60% accuracy. Claude generates each question fresh against a strict format — never the same question twice. If parsing fails, the skill falls back to one of four sample questions and logs the parse error.

### Spaced repetition (Ebbinghaus)
Wrong answers go into `CloudStudyReview` with `due_after = 3` (review in 3 sessions). Every question answered decrements every review counter by 1. Every 3rd question in a session checks if any review items are due (`due_after <= 0`) and injects one if so. Correct review answers double the interval (3 → 6 → 12 → 24); incorrect ones reset to 3. Once `interval >= 24`, the item is removed (mastered).

### Streak tracking
A separate record per user (`{user_id}_streak`) tracks the last study date. Opening the skill on a new day increments the streak; opening it after a gap day resets to 1. Same-day reopens don't change anything.

### State across sessions
Alexa skills are stateless by default. DynamoDB persistence is what makes this an actual *study system* — streaks, weak-topic detection, review scheduling, and the readiness score all require continuity across sessions and devices.

### Defensive design
Every external call (Claude API, DynamoDB read/write) is wrapped in try/except with a graceful fallback. The skill never fully breaks for the user — Claude downtime falls back to hardcoded questions, DynamoDB errors fall back to non-personalized defaults.
