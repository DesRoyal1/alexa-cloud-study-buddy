# Cloud Study Buddy – Alexa Skill

## Overview

Cloud Study Buddy is a custom **Alexa skill** that quizzes users on cloud fundamentals through voice.
The skill is implemented with the **Alexa Skills Kit** and an **AWS Lambda** backend.

- Ask Alexa for cloud questions.
- Answer by voice and get immediate feedback.
- Track your score within a session and keep practicing.

---

## Architecture

- **Alexa Skills Kit**
  - Custom skill with intents for:
    - Starting a quiz
    - Answering a question
    - Repeating a question
    - Ending the session
  - Interaction model defined in [`interaction-model/en-US.json`](interaction-model/en-US.json)

- **AWS Lambda**
  - Runtime: **[Node.js / Python]**
  - Main handler in [`lambda/index.js`](lambda/index.js) (or `lambda_function.py`)
  - Handles session state, random question selection, scoring, and building Alexa responses.

- **Monitoring**
  - Uses **CloudWatch Logs** to debug incoming requests and skill behavior.

---

## Files

- `lambda/`
  - `index.js` – Lambda handler for the skill logic.
- `interaction-model/`
  - `en-US.json` – Alexa interaction model (intents, slots, and sample utterances).
- `README.md` – Project overview and architecture.

---

## How the skill works

1. User says:  
   > “Alexa, open Cloud Study Buddy”  
2. Alexa greets the user and offers a question.  
3. User answers; the Lambda function checks the answer and responds with:
   - Correct / incorrect
   - The right answer (if wrong)
   - Current score in this session
4. User can ask for another question, repeat the question, or end the quiz.

---

## Why this project

This project demonstrates:

- Designing a **voice interaction model** with intents and sample utterances.
- Building a **serverless backend** for Alexa using **AWS Lambda**.
- Handling session state, user input, and spoken responses.
- Using **AWS CloudWatch Logs** to monitor and debug a voice application.
