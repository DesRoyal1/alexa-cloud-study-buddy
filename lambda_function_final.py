# -*- coding: utf-8 -*-
# Cloud Study Buddy — Final Version
# Features: Auto-flow, Spaced Repetition, Streaks, Hints, Skip, Repeat, Progress Report

import logging
import random
import os
import json
import urllib.request
import urllib.error
import boto3
from datetime import datetime, timezone, timedelta

from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.utils import is_request_type, is_intent_name
from ask_sdk_core.handler_input import HandlerInput

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")
CLAUDE_MODEL = "claude-haiku-4-5-20251001"
ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
PROGRESS_TABLE = "CloudStudyProgress"
REVIEW_TABLE = "CloudStudyReview"
SESSION_LENGTH = 10

dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
progress_table = dynamodb.Table(PROGRESS_TABLE)
review_table = dynamodb.Table(REVIEW_TABLE)

AWS_SAA_TOPICS = [
    "EC2 instance types and purchasing options",
    "S3 storage classes and lifecycle policies",
    "IAM users roles and policies",
    "VPC subnets route tables and security groups",
    "RDS Multi-AZ and Read Replicas",
    "DynamoDB partition keys and read write capacity",
    "Lambda functions and event triggers",
    "CloudFront distributions and origins",
    "Auto Scaling groups and launch templates",
    "Elastic Load Balancing types",
    "Route 53 routing policies",
    "CloudWatch metrics and alarms",
    "SQS vs SNS messaging patterns",
    "EBS volume types and snapshots",
    "AWS shared responsibility model",
    "AWS Well-Architected Framework pillars",
    "Disaster recovery strategies RTO and RPO",
    "CloudTrail vs CloudWatch vs Config"
]

FALLBACK_QUESTIONS = [
    {
        "question": "A company needs to grant temporary access to an S3 bucket for a third party vendor. Which IAM feature should they use?",
        "options": ["A) IAM User", "B) IAM Role", "C) IAM Group", "D) Access Key"],
        "answer": "B",
        "explanation": "IAM Roles grant temporary access without sharing long term credentials.",
        "topic": "IAM users roles and policies"
    },
    {
        "question": "Which S3 storage class is most cost effective for data rarely accessed but retrievable within 12 hours?",
        "options": ["A) S3 Standard", "B) S3 Glacier Flexible Retrieval", "C) S3 Intelligent Tiering", "D) S3 One Zone IA"],
        "answer": "B",
        "explanation": "S3 Glacier Flexible Retrieval is designed for archival data with retrieval times of minutes to hours.",
        "topic": "S3 storage classes and lifecycle policies"
    },
    {
        "question": "Which AWS service automatically distributes incoming traffic across multiple EC2 instances?",
        "options": ["A) Auto Scaling", "B) CloudFront", "C) Elastic Load Balancing", "D) Route 53"],
        "answer": "C",
        "explanation": "Elastic Load Balancing automatically distributes incoming application traffic across multiple targets.",
        "topic": "Elastic Load Balancing types"
    },
    {
        "question": "What is the purpose of an AWS VPC?",
        "options": ["A) Store files", "B) Create a private network", "C) Monitor costs", "D) Deploy containers"],
        "answer": "B",
        "explanation": "A VPC lets you provision a logically isolated section of AWS where you can launch resources in a virtual network.",
        "topic": "VPC subnets route tables and security groups"
    }
]

STUDY_TIPS = [
    "Focus on WHY an answer is correct, not just memorizing it. The exam tests application.",
    "The AWS SAA exam is scenario based. Practice reading long questions and identifying key constraints.",
    "Know when to use RDS Multi AZ versus Read Replicas. Multi AZ is availability, Read Replicas are performance.",
    "S3 storage classes come up constantly. Know Glacier, Intelligent Tiering, and One Zone IA cold.",
    "Understand the shared responsibility model. AWS owns the cloud, you own what is in it."
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def get_user_id(handler_input):
    try:
        return handler_input.request_envelope.context.system.user.user_id
    except Exception:
        return "default_user"


# ---------------------------------------------------------------------------
# Claude API
# ---------------------------------------------------------------------------

def call_claude(system_prompt, user_prompt, max_tokens=300):
    if not ANTHROPIC_API_KEY:
        logger.error("ANTHROPIC_API_KEY not set")
        return None

    payload = json.dumps({
        "model": CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [{"role": "user", "content": user_prompt}]
    }).encode("utf-8")

    headers = {
        "Content-Type": "application/json",
        "x-api-key": ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01"
    }

    req = urllib.request.Request(ANTHROPIC_API_URL, data=payload, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=8) as response:
            result = json.loads(response.read().decode("utf-8"))
            return result["content"][0]["text"].strip()
    except Exception as e:
        logger.error(f"Claude API error: {e}")
        return None


def generate_question(topic):
    system_prompt = (
        "You are an AWS Solutions Architect Associate exam question generator. "
        "Respond in this EXACT format, no deviations, no markdown:\n"
        "QUESTION: [question text]\n"
        "A) [option]\n"
        "B) [option]\n"
        "C) [option]\n"
        "D) [option]\n"
        "ANSWER: [single letter only]\n"
        "EXPLANATION: [one sentence, under 30 words]"
    )
    raw = call_claude(system_prompt, f"Generate one AWS SAA exam question about: {topic}", max_tokens=280)
    if not raw:
        logger.warning("Claude failed, using fallback question")
        return random.choice(FALLBACK_QUESTIONS)

    try:
        lines = [l.strip() for l in raw.split("\n") if l.strip()]
        question_text = ""
        options = []
        answer = ""
        explanation = ""

        for line in lines:
            if line.startswith("QUESTION:"):
                question_text = line.replace("QUESTION:", "").strip()
            elif line.startswith(("A)", "B)", "C)", "D)")):
                options.append(line)
            elif line.startswith("ANSWER:"):
                answer = line.replace("ANSWER:", "").strip().upper()[0]
            elif line.startswith("EXPLANATION:"):
                explanation = line.replace("EXPLANATION:", "").strip()

        if question_text and len(options) == 4 and answer and explanation:
            return {
                "question": question_text,
                "options": options,
                "answer": answer,
                "explanation": explanation,
                "topic": topic
            }
    except Exception as e:
        logger.error(f"Parse error: {e}")

    return random.choice(FALLBACK_QUESTIONS)


def evaluate_answer(question, correct_answer, explanation, user_answer):
    system_prompt = (
        "You are an AWS exam coach giving feedback through Alexa. "
        "Under 50 words. Plain text only. "
        "Start with Correct or Incorrect. One sentence why. End with encouragement."
    )
    user_prompt = (
        f"Question: {question}\n"
        f"Correct answer: {correct_answer}\n"
        f"Explanation: {explanation}\n"
        f"Student answered: {user_answer}\n"
        "Evaluate and give brief feedback."
    )
    result = call_claude(system_prompt, user_prompt, max_tokens=100)
    if not result:
        if user_answer and user_answer.upper().startswith(correct_answer.upper()):
            return f"Correct! {explanation} Keep it up!"
        else:
            return f"Not quite. The correct answer is {correct_answer}. {explanation} Keep studying!"
    return result


def get_hint(question, answer, explanation):
    system_prompt = (
        "You are an AWS exam coach. Give a helpful hint without revealing the answer. "
        "Under 30 words. Plain text only."
    )
    result = call_claude(system_prompt,
        f"Question: {question}\nAnswer: {answer}\nExplanation: {explanation}\nGive a hint.",
        max_tokens=60)
    return result if result else "Think about which service is specifically designed for this use case."


# ---------------------------------------------------------------------------
# DynamoDB — Progress
# ---------------------------------------------------------------------------

def log_attempt(user_id, topic, correct):
    try:
        timestamp = datetime.now(timezone.utc).isoformat()
        progress_table.put_item(Item={
            "User_ID": user_id,
            "timestamp": timestamp,
            "topic": topic,
            "correct": correct
        })
    except Exception as e:
        logger.error(f"Progress log error: {e}")


def get_progress(user_id):
    try:
        from boto3.dynamodb.conditions import Key
        response = progress_table.query(
            KeyConditionExpression=Key("User_ID").eq(user_id)
        )
        items = [i for i in response.get("Items", []) if i.get("timestamp") != "streak"]
        if not items:
            return None

        total = len(items)
        correct = sum(1 for i in items if i.get("correct", False))
        accuracy = round((correct / total) * 100) if total > 0 else 0

        topic_stats = {}
        for item in items:
            topic = item.get("topic", "Unknown")
            if topic not in topic_stats:
                topic_stats[topic] = {"correct": 0, "total": 0}
            topic_stats[topic]["total"] += 1
            if item.get("correct", False):
                topic_stats[topic]["correct"] += 1

        weak_topics = [
            t for t, s in topic_stats.items()
            if s["total"] >= 2 and (s["correct"] / s["total"]) < 0.6
        ]
        best_topic = max(
            topic_stats.items(),
            key=lambda x: x[1]["correct"] / x[1]["total"] if x[1]["total"] > 0 else 0
        )[0] if topic_stats else None

        return {
            "total": total,
            "correct": correct,
            "accuracy": accuracy,
            "weak_topics": weak_topics,
            "best_topic": best_topic
        }
    except Exception as e:
        logger.error(f"Progress fetch error: {e}")
        return None


# ---------------------------------------------------------------------------
# DynamoDB — Streak
# ---------------------------------------------------------------------------

def get_streak(user_id):
    try:
        response = progress_table.get_item(
            Key={"User_ID": f"{user_id}_streak", "timestamp": "streak"}
        )
        item = response.get("Item")
        if not item:
            return {"streak": 0, "last_session": None}
        return {"streak": int(item.get("streak", 0)), "last_session": item.get("last_session")}
    except Exception as e:
        logger.error(f"Get streak error: {e}")
        return {"streak": 0, "last_session": None}


def update_streak(user_id):
    try:
        today = datetime.now(timezone.utc).date().isoformat()
        streak_data = get_streak(user_id)
        last_session = streak_data.get("last_session")
        current_streak = streak_data.get("streak", 0)

        if last_session == today:
            return current_streak, False

        yesterday = (datetime.now(timezone.utc).date() - timedelta(days=1)).isoformat()
        new_streak = current_streak + 1 if last_session == yesterday else 1

        progress_table.put_item(Item={
            "User_ID": f"{user_id}_streak",
            "timestamp": "streak",
            "streak": new_streak,
            "last_session": today
        })
        return new_streak, True
    except Exception as e:
        logger.error(f"Update streak error: {e}")
        return 1, True


# ---------------------------------------------------------------------------
# DynamoDB — Spaced Repetition
# ---------------------------------------------------------------------------

def schedule_review(user_id, question, answer, explanation, topic, interval=3):
    try:
        review_table.put_item(Item={
            "User_ID": user_id,
            "Question_Id": f"{user_id}_{datetime.now(timezone.utc).timestamp()}",
            "question": question,
            "answer": answer,
            "explanation": explanation,
            "topic": topic,
            "interval": interval,
            "due_after": interval
        })
    except Exception as e:
        logger.error(f"Schedule review error: {e}")


def get_due_review(user_id):
    try:
        from boto3.dynamodb.conditions import Key
        response = review_table.query(
            KeyConditionExpression=Key("User_ID").eq(user_id)
        )
        items = response.get("Items", [])
        due = [i for i in items if int(i.get("due_after", 999)) <= 0]
        if due:
            item = due[0]
            q = generate_question(item["topic"])
            q["Question_Id"] = item["Question_Id"]
            q["interval"] = int(item.get("interval", 3))
            q["is_review"] = True
            return q
        return None
    except Exception as e:
        logger.error(f"Get due review error: {e}")
        return None


def decrement_review_counters(user_id):
    try:
        from boto3.dynamodb.conditions import Key
        response = review_table.query(
            KeyConditionExpression=Key("User_ID").eq(user_id)
        )
        for item in response.get("Items", []):
            new_due = max(0, int(item.get("due_after", 0)) - 1)
            review_table.update_item(
                Key={"User_ID": user_id, "Question_Id": item["Question_Id"]},
                UpdateExpression="SET due_after = :d",
                ExpressionAttributeValues={":d": new_due}
            )
    except Exception as e:
        logger.error(f"Decrement review error: {e}")


def resolve_review(user_id, question_id, got_correct, current_interval):
    try:
        if got_correct:
            new_interval = current_interval * 2
            if new_interval >= 24:
                review_table.delete_item(Key={"User_ID": user_id, "Question_Id": question_id})
            else:
                review_table.update_item(
                    Key={"User_ID": user_id, "Question_Id": question_id},
                    UpdateExpression="SET due_after = :d",
                    ExpressionAttributeValues={":d": new_interval}
                )
        else:
            review_table.update_item(
                Key={"User_ID": user_id, "Question_Id": question_id},
                UpdateExpression="SET due_after = :d",
                ExpressionAttributeValues={":d": 3}
            )
    except Exception as e:
        logger.error(f"Resolve review error: {e}")


def get_weighted_topic(user_id):
    try:
        progress = get_progress(user_id)
        if progress and progress["weak_topics"]:
            if random.random() < 0.7:
                return random.choice(progress["weak_topics"])
    except Exception as e:
        logger.error(f"Weighted topic error: {e}")
    return random.choice(AWS_SAA_TOPICS)


# ---------------------------------------------------------------------------
# Core Auto-flow Function
# ---------------------------------------------------------------------------

def load_and_ask_next_question(handler_input, user_id, prefix_speak=""):
    attrs = handler_input.attributes_manager.session_attributes
    session_count = int(attrs.get("session_count", 0))

    # Session complete
    if session_count >= SESSION_LENGTH:
        session_correct = int(attrs.get("session_correct", 0))
        topic_stats = attrs.get("session_topic_stats", {})

        weakest = None
        if topic_stats:
            try:
                weakest = min(
                    topic_stats.items(),
                    key=lambda x: x[1]["correct"] / x[1]["total"] if x[1]["total"] > 0 else 1
                )[0]
            except Exception:
                pass

        summary = (
            f"{prefix_speak}"
            f"Session complete! You got {session_correct} out of {SESSION_LENGTH} correct. "
        )
        if weakest:
            summary += f"Your weakest topic was {weakest}. "
        summary += "Say start quiz for another session or say progress report for your full stats."

        attrs["q_active"] = False
        attrs["session_count"] = 0
        attrs["session_correct"] = 0
        attrs["session_topic_stats"] = {}

        return handler_input.response_builder.speak(summary).ask("Say start quiz to continue.").response

    # Every 3rd question check for review
    due_review = None
    if session_count > 0 and session_count % 3 == 0:
        due_review = get_due_review(user_id)

    if due_review:
        q = due_review
        review_notice = "Review question coming up. "
    else:
        topic = get_weighted_topic(user_id)
        q = generate_question(topic)
        q["is_review"] = False
        q["Question_Id"] = ""
        review_notice = ""

    # Store in session
    attrs["q_active"] = True
    attrs["q_text"] = q["question"]
    attrs["q_answer"] = q["answer"]
    attrs["q_explanation"] = q["explanation"]
    attrs["q_topic"] = q.get("topic", "AWS")
    attrs["q_is_review"] = q.get("is_review", False)
    attrs["q_review_id"] = q.get("Question_Id", "")
    attrs["q_review_interval"] = int(q.get("interval", 3))
    attrs["session_count"] = session_count + 1

    questions_left = SESSION_LENGTH - session_count - 1
    progress_note = f"{questions_left} questions left. " if questions_left > 0 else "Last question. "

    options_spoken = ". ".join(q["options"])
    speak = (
        f"{prefix_speak}"
        f"{review_notice}"
        f"{progress_note}"
        f"{q['question']} "
        f"{options_spoken}. "
        f"What is your answer?"
    )

    return handler_input.response_builder.speak(speak).ask("Say my answer is A, B, C, or D.").response


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

class LaunchRequestHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        user_id = get_user_id(handler_input)
        streak, is_new_day = update_streak(user_id)

        if streak == 1 and is_new_day:
            streak_msg = "Welcome to Cloud Study Buddy."
        elif is_new_day:
            streak_msg = f"Welcome back. You are on a {streak} day study streak. Keep it going."
        else:
            streak_msg = f"Welcome back. You are on a {streak} day streak."

        speak = (
            f"{streak_msg} "
            "Say start quiz to begin a 10 question session, "
            "explain a concept, give me a study tip, or say progress report."
        )
        return handler_input.response_builder.speak(speak).ask("What would you like to do?").response


class StartQuizIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return (
            is_intent_name("StartQuizIntent")(handler_input) or
            is_intent_name("QuizMeCloudIntent")(handler_input)
        )

    def handle(self, handler_input):
        user_id = get_user_id(handler_input)
        attrs = handler_input.attributes_manager.session_attributes
        attrs["session_count"] = 0
        attrs["session_correct"] = 0
        attrs["session_topic_stats"] = {}
        attrs["q_active"] = False
        return load_and_ask_next_question(handler_input, user_id, "Starting your 10 question session. ")


class EvaluateAnswerIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("EvaluateAnswerIntent")(handler_input)

    def handle(self, handler_input):
        user_id = get_user_id(handler_input)
        attrs = handler_input.attributes_manager.session_attributes

        q_active = attrs.get("q_active", False)
        q_text = attrs.get("q_text", "")
        q_answer = attrs.get("q_answer", "")
        q_explanation = attrs.get("q_explanation", "")
        q_topic = attrs.get("q_topic", "AWS")
        q_is_review = attrs.get("q_is_review", False)
        q_review_id = attrs.get("q_review_id", "")
        q_review_interval = int(attrs.get("q_review_interval", 3))

        slots = handler_input.request_envelope.request.intent.slots or {}
        answer_slot = slots.get("UserAnswer")
        user_answer = answer_slot.value if answer_slot and answer_slot.value else ""

        if not q_active or not q_text:
            speak = "Say start quiz to begin a session."
            return handler_input.response_builder.speak(speak).ask(speak).response

        if not user_answer:
            speak = "I didn't catch that. Say my answer is A, B, C, or D."
            return handler_input.response_builder.speak(speak).ask(speak).response

        is_correct = user_answer.upper().startswith(q_answer.upper())

        # Log to DynamoDB
        log_attempt(user_id, q_topic, is_correct)
        decrement_review_counters(user_id)

        # Update session stats
        if is_correct:
            attrs["session_correct"] = int(attrs.get("session_correct", 0)) + 1

        topic_stats = attrs.get("session_topic_stats", {})
        if q_topic not in topic_stats:
            topic_stats[q_topic] = {"correct": 0, "total": 0}
        topic_stats[q_topic]["total"] += 1
        if is_correct:
            topic_stats[q_topic]["correct"] += 1
        attrs["session_topic_stats"] = topic_stats

        # Spaced repetition
        if q_is_review and q_review_id:
            resolve_review(user_id, q_review_id, is_correct, q_review_interval)
        elif not is_correct:
            schedule_review(user_id, q_text, q_answer, q_explanation, q_topic, interval=3)

        # Get feedback
        feedback = evaluate_answer(q_text, q_answer, q_explanation, user_answer)
        if not is_correct and not q_is_review:
            feedback += " I will bring this one back for review."

        # Clear question and auto-flow
        attrs["q_active"] = False
        return load_and_ask_next_question(handler_input, user_id, f"{feedback} ")


class HintIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("HintIntent")(handler_input)

    def handle(self, handler_input):
        attrs = handler_input.attributes_manager.session_attributes
        q_text = attrs.get("q_text", "")
        q_answer = attrs.get("q_answer", "")
        q_explanation = attrs.get("q_explanation", "")

        if not q_text:
            speak = "No active question. Say start quiz to begin."
            return handler_input.response_builder.speak(speak).ask(speak).response

        hint = get_hint(q_text, q_answer, q_explanation)
        speak = f"Here is your hint: {hint} Now what is your answer?"
        return handler_input.response_builder.speak(speak).ask("Say my answer is A, B, C, or D.").response


class RepeatQuestionIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("RepeatQuestionIntent")(handler_input)

    def handle(self, handler_input):
        attrs = handler_input.attributes_manager.session_attributes
        q_text = attrs.get("q_text", "")

        if not q_text:
            speak = "No active question. Say start quiz to begin."
            return handler_input.response_builder.speak(speak).ask(speak).response

        speak = f"Here is the question again. {q_text} What is your answer?"
        return handler_input.response_builder.speak(speak).ask("Say my answer is A, B, C, or D.").response


class SkipQuestionIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("SkipQuestionIntent")(handler_input)

    def handle(self, handler_input):
        user_id = get_user_id(handler_input)
        attrs = handler_input.attributes_manager.session_attributes

        if not attrs.get("q_active", False):
            speak = "No active question to skip. Say start quiz to begin."
            return handler_input.response_builder.speak(speak).ask(speak).response

        attrs["q_active"] = False
        return load_and_ask_next_question(handler_input, user_id, "Skipping that one. ")


class QuestionsLeftIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("QuestionsLeftIntent")(handler_input)

    def handle(self, handler_input):
        attrs = handler_input.attributes_manager.session_attributes
        session_count = int(attrs.get("session_count", 0))
        questions_left = max(0, SESSION_LENGTH - session_count)
        speak = f"You have {questions_left} questions remaining in this session."
        return handler_input.response_builder.speak(speak).ask("What is your answer?").response


class ProgressReportIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("ProgressReportIntent")(handler_input)

    def handle(self, handler_input):
        user_id = get_user_id(handler_input)
        progress = get_progress(user_id)
        streak_data = get_streak(user_id)
        streak = streak_data.get("streak", 0)

        if not progress:
            speak = "No progress data yet. Say start quiz to begin your first session."
            return handler_input.response_builder.speak(speak).ask("Say start quiz.").response

        total = progress["total"]
        correct = progress["correct"]
        accuracy = progress["accuracy"]
        weak_topics = progress["weak_topics"]
        best_topic = progress["best_topic"]

        speak = (
            f"Here is your progress report. "
            f"You are on a {streak} day study streak. "
            f"You have answered {total} questions with {correct} correct, "
            f"giving you {accuracy} percent accuracy. "
        )

        if best_topic:
            speak += f"Your strongest area is {best_topic}. "

        if weak_topics:
            weak_list = " and ".join(weak_topics[:2])
            speak += f"Your weakest areas are {weak_list}. I am scheduling extra review questions there. "
        else:
            speak += "You are performing well across all topics. "

        if total >= 5:
            if accuracy >= 80:
                speak += "You are looking exam ready. Keep it up."
            elif accuracy >= 60:
                speak += "Solid progress. Focus on weak areas and you will be ready soon."
            else:
                speak += "Keep going. Daily practice adds up fast."

        return handler_input.response_builder.speak(speak).ask("Say start quiz to keep practicing.").response


class ExplainConceptIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("GetCloudConceptIntent")(handler_input)

    def handle(self, handler_input):
        slots = handler_input.request_envelope.request.intent.slots or {}
        concept_slot = slots.get("ConceptName")
        concept = concept_slot.value if concept_slot and concept_slot.value else None

        if not concept:
            speak = "Which AWS concept would you like explained? Try EC2, S3, Lambda, or IAM."
            return handler_input.response_builder.speak(speak).ask(speak).response

        system_prompt = (
            "You are an AWS SAA exam tutor on Alexa. "
            "Explain in under 70 words. Plain text, no markdown. Exam focused."
        )
        result = call_claude(system_prompt, f"Explain {concept} for the AWS SAA exam.", max_tokens=120)
        speak = result if result else f"I couldn't explain {concept} right now. Try again."
        return handler_input.response_builder.speak(speak).ask("What else would you like to know?").response


class StudyTipIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("StudyTipIntent")(handler_input)

    def handle(self, handler_input):
        system_prompt = (
            "You are an AWS SAA exam coach on Alexa. "
            "One specific actionable tip under 50 words. Plain text only."
        )
        result = call_claude(system_prompt, "Give me one AWS SAA study tip.", max_tokens=80)
        tip = result if result else random.choice(STUDY_TIPS)
        return handler_input.response_builder.speak(f"Here is your study tip: {tip}").ask("Say start quiz when ready.").response


class HelpIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        speak = (
            "Say start quiz to begin a 10 question session. "
            "During a question say my answer is B, give me a hint, repeat the question, or skip this question. "
            "Say how many questions left to check your progress. "
            "Say explain E C 2 for any concept. "
            "Say progress report for your stats and streak. "
            "Say bye to exit."
        )
        return handler_input.response_builder.speak(speak).ask(speak).response


class FallbackIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        attrs = handler_input.attributes_manager.session_attributes
        if attrs.get("q_active", False):
            speak = "I didn't catch that. Say my answer is A, B, C, or D. Or say give me a hint."
        else:
            speak = "Say start quiz, explain a concept, progress report, or give me a study tip."
        return handler_input.response_builder.speak(speak).ask("What would you like to do?").response


class CancelStopIntentHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return (
            is_intent_name("AMAZON.CancelIntent")(handler_input) or
            is_intent_name("AMAZON.StopIntent")(handler_input) or
            is_intent_name("CloseSkillIntent")(handler_input)
        )

    def handle(self, handler_input):
        return handler_input.response_builder.speak(
            "Good luck with your AWS studies. You got this. Bye!"
        ).response


class SessionEndedHandler(AbstractRequestHandler):
    def can_handle(self, handler_input):
        return is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        return handler_input.response_builder.response


# ---------------------------------------------------------------------------
# Skill Builder
# ---------------------------------------------------------------------------

sb = SkillBuilder()
sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(StartQuizIntentHandler())
sb.add_request_handler(EvaluateAnswerIntentHandler())
sb.add_request_handler(HintIntentHandler())
sb.add_request_handler(RepeatQuestionIntentHandler())
sb.add_request_handler(SkipQuestionIntentHandler())
sb.add_request_handler(QuestionsLeftIntentHandler())
sb.add_request_handler(ProgressReportIntentHandler())
sb.add_request_handler(ExplainConceptIntentHandler())
sb.add_request_handler(StudyTipIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelStopIntentHandler())
sb.add_request_handler(SessionEndedHandler())

lambda_handler = sb.lambda_handler()
