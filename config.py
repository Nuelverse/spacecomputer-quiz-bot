# config.py
import os
from dotenv import load_dotenv

load_dotenv()

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]

QUESTIONS_PER_ROUND = 5
QUESTION_TIMER = 30       # seconds per question
BASE_POINTS = 100         # max points per correct answer
BETWEEN_QUESTION_DELAY = 5  # seconds to show mini leaderboard before next question

CTRNG_IPFS_GATEWAYS = [
    "https://dweb.link/ipns/k2k4r8lvomw737sajfnpav0dpeernugnryng50uheyk1k39lursmn09f",
    "https://ipfs.io/ipns/k2k4r8lvomw737sajfnpav0dpeernugnryng50uheyk1k39lursmn09f",
]

TOPICS = ["cTRNG", "KMS", "orbital computing", "SpaceComputer architecture", "blockchain randomness", "general"]

# Optional: set to a publicly accessible image URL to show a banner at quiz start.
# Leave empty to use text-only messages.
# Example: a Hubble or NASA space image URL
QUIZ_BANNER_IMAGE_URL = os.environ.get("QUIZ_BANNER_IMAGE_URL", "")

MIN_QUESTIONS_PER_ROUND = 3
MAX_QUESTIONS_PER_ROUND = 20

# Seconds before transient bot messages (errors, acks) are auto-deleted from the chat
AUTO_DELETE_DELAY = 10
