# -*- coding: utf-8 -*-

import logging
import random

from ask_sdk_core.skill_builder import SkillBuilder
from ask_sdk_core.dispatch_components import AbstractRequestHandler
from ask_sdk_core.utils import is_request_type, is_intent_name
from ask_sdk_core.handler_input import HandlerInput
from ask_sdk_model import Response

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# --- Data section: cloud concepts, quiz questions, study tips ---

CLOUD_CONCEPTS = {
    "ec2": "Amazon EC2 is a web service that provides resizable compute capacity in the cloud. "
           "You can think of it as virtual machines you rent by the hour or second.",
    "s3": "Amazon S3 is a storage service for objects like files, images, and backups. "
          "It is highly durable and scalable.",
    "lambda": "AWS Lambda is a serverless compute service. You run code without managing servers, "
              "and you only pay for the compute time you use.",
    "vpc": "A Virtual Private Cloud, or VPC, is your private network inside AWS where you can "
           "control IP ranges, subnets, and routing.",
    "serverless": "Serverless means you do not manage servers directly. The cloud provider handles "
                  "scaling, patching, and infrastructure, and you focus only on your code.",
    "rds": "Amazon RDS is a managed relational database service for engines like MySQL and PostgreSQL. "
           "AWS handles backups, patching, and scaling.",
    "dynamodb": "Amazon DynamoDB is a managed NoSQL database that offers single-digit millisecond "
                "performance at any scale.",
    "autoscaling": "Auto Scaling automatically increases or decreases the number of EC2 instances "
                   "based on demand.",
    "cloudfront": "Amazon CloudFront is a content delivery network that caches content closer to "
                  "users to reduce latency.",
    "region": "An AWS Region is a physical location in the world that contains multiple "
              "Availability Zones.",
    "availability zone": "An Availability Zone is one or more data centers within a Region, "
                         "designed for high availability."
}

QUIZ_QUESTIONS = [
    {
        "question": "What does EC2 stand for?",
        "answer": "Elastic Compute Cloud",
        "explanation": "EC2 stands for Elastic Compute Cloud. It lets you launch virtual servers "
                       "in the cloud."
    },
    {
        "question": "Which AWS service is best for storing files and backups, EC2 or S3?",
        "answer": "S3",
        "explanation": "S3 is designed for object storage like files, images, and backups."
    },
    {
        "question": "Is AWS Lambda a serverless or virtual machine service?",
        "answer": "Serverless",
        "explanation": "Lambda is a serverless compute service where AWS manages the servers for you."
    },
    {
        "question": "Which service is a managed relational database: EC2 or RDS?",
        "answer": "RDS",
        "explanation": "RDS is a managed relational database service; AWS handles backups and patching."
    },
    {
        "question": "Which service is a managed NoSQL database: DynamoDB or CloudFront?",
        "answer": "DynamoDB",
        "explanation": "DynamoDB is a managed NoSQL database; CloudFront is a content delivery network."
    },
    {
        "question": "What AWS service is used as a content delivery network?",
        "answer": "CloudFront",
        "explanation": "CloudFront caches content at edge locations to reduce latency for users."
    }
]

STUDY_TIPS = [
    "Break your study time into 25 minute focus blocks with a 5 minute break in between. "
    "This is called the Pomodoro Technique.",
    "Write down three specific tasks to finish today, like review EC2, finish one homework "
    "problem set, and read one chapter.",
    "Study cloud concepts by explaining them out loud in simple language, like you are teaching a friend.",
    "Remove distractions by putting your phone in another room while you study for 30 minutes.",
    "Review one AWS service per day and write a one-paragraph summary in your own words.",
    "Mix cloud practice with school work: do 20 minutes of AWS labs, then 20 minutes of class assignments.",
    "Set a daily study window, even if it is only 30 minutes, and protect it like an appointment."
]

# --- Request Handlers ---

class LaunchRequestHandler(AbstractRequestHandler):
    """Handler for Skill Launch."""
    def can_handle(self, handler_input):
        return is_request_type("LaunchRequest")(handler_input)

    def handle(self, handler_input):
        speak_output = (
            "Welcome to Cloud Study Buddy. You can ask me to explain a cloud concept, "
            "quiz you on cloud, or give you a study tip. What would you like to do?"
        )
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask("What would you like to do?")
                .response
        )


class GetCloudConceptIntentHandler(AbstractRequestHandler):
    """Explain a specific cloud concept."""
    def can_handle(self, handler_input):
        return is_intent_name("GetCloudConceptIntent")(handler_input)

    def handle(self, handler_input):
        intent = handler_input.request_envelope.request.intent
        slots = intent.slots if intent.slots else {}
        concept_slot = slots.get("ConceptName")
        concept_name_raw = concept_slot.value if concept_slot and concept_slot.value else None

        logger.info(f"User asked for concept: {concept_name_raw}")

        if not concept_name_raw:
            speak_output = (
                "Which cloud concept do you want me to explain, like EC2, S3, Lambda, "
                "V P C, or serverless?"
            )
        else:
            key = concept_name_raw.lower()
            explanation = CLOUD_CONCEPTS.get(key)
            if explanation:
                speak_output = explanation
            else:
                speak_output = (
                    f"I don't have an explanation for {concept_name_raw} yet. "
                    "Try asking about EC2, S3, Lambda, V P C, or serverless."
                )

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask("What else would you like to know?")
                .response
        )


class QuizMeCloudIntentHandler(AbstractRequestHandler):
    """Give a random cloud quiz question."""
    def can_handle(self, handler_input):
        return is_intent_name("QuizMeCloudIntent")(handler_input)

    def handle(self, handler_input):
        question_data = random.choice(QUIZ_QUESTIONS)
        question = question_data["question"]
        answer = question_data["answer"]
        explanation = question_data["explanation"]

        logger.info(f"Selected quiz question: {question}")

        speak_output = (
            f"Here is your question: {question} "
            f"The correct answer is: {answer}. {explanation} "
            "Want another question or a cloud concept explained?"
        )

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask("Want another question or a cloud concept explained?")
                .response
        )


class StudyTipIntentHandler(AbstractRequestHandler):
    """Return a random study tip."""
    def can_handle(self, handler_input):
        return is_intent_name("StudyTipIntent")(handler_input)

    def handle(self, handler_input):
        tip = random.choice(STUDY_TIPS)
        logger.info("Serving study tip.")
        speak_output = f"Here is a study tip: {tip}"

        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask("Would you like another tip or a cloud concept?")
                .response
        )


class HelpIntentHandler(AbstractRequestHandler):
    """Handler for Help Intent."""
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.HelpIntent")(handler_input)

    def handle(self, handler_input):
        speak_output = (
            "You can say things like, explain EC2, quiz me on cloud, "
            "or give me a study tip. What would you like to try?"
        )
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask(speak_output)
                .response
        )


class CancelOrStopIntentHandler(AbstractRequestHandler):
    """Single handler for Cancel and Stop Intent."""
    def can_handle(self, handler_input):
        return (
            is_intent_name("AMAZON.CancelIntent")(handler_input)
            or is_intent_name("AMAZON.StopIntent")(handler_input)
        )

    def handle(self, handler_input):
        speak_output = "Good luck with your cloud studies. Bye!"
        return handler_input.response_builder.speak(speak_output).response


class FallbackIntentHandler(AbstractRequestHandler):
    """Handler for AMAZON.FallbackIntent."""
    def can_handle(self, handler_input):
        return is_intent_name("AMAZON.FallbackIntent")(handler_input)

    def handle(self, handler_input):
        logger.info("Fallback intent triggered.")
        speak_output = (
            "I'm not sure which cloud concept you meant. "
            "Try asking something like, what is E C 2, what is S 3, or explain Lambda."
        )
        return (
            handler_input.response_builder
                .speak(speak_output)
                .ask("Which cloud concept would you like to hear about?")
                .response
        )


class SessionEndedRequestHandler(AbstractRequestHandler):
    """Handler for Session End."""
    def can_handle(self, handler_input):
        return is_request_type("SessionEndedRequest")(handler_input)

    def handle(self, handler_input):
        # Any cleanup logic goes here.
        return handler_input.response_builder.response


# --- Skill Builder registration ---

sb = SkillBuilder()
sb.add_request_handler(LaunchRequestHandler())
sb.add_request_handler(GetCloudConceptIntentHandler())
sb.add_request_handler(QuizMeCloudIntentHandler())
sb.add_request_handler(StudyTipIntentHandler())
sb.add_request_handler(FallbackIntentHandler())
sb.add_request_handler(HelpIntentHandler())
sb.add_request_handler(CancelOrStopIntentHandler())
sb.add_request_handler(SessionEndedRequestHandler())

lambda_handler = sb.lambda_handler()

