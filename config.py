# config.py
import os
import logging


GEMINI_API_KEY_ENV_VAR = "GEMINI_API_KEY"


SPIN_WRITE_MODEL = 'gemini-1.5-flash'
SUMMARIZE_MODEL = 'gemini-2.5-flash' 


REVIEW_MODEL = 'gemini-1.5-pro'


PROMPT_GENERATOR_MODEL = 'gemini-1.5-pro-latest'


CHROMA_DB_PATH = "./chroma_data"

CHROMA_COLLECTION_NAME = "book_chapter_versions"


BASE_URL = "https://en.wikisource.org/wiki/"
# Default book and chapter for initial workflow
DEFAULT_BOOK_NAME_SLUG = "The_Gates_of_Morning"
DEFAULT_BOOK_NUM = 1
DEFAULT_CHAP_NUM = 1
# Full default URL (derived from above)
DEFAULT_URL_TO_SCRAPE = f"{BASE_URL}{DEFAULT_BOOK_NAME_SLUG}/Book_{DEFAULT_BOOK_NUM}/Chapter_{DEFAULT_CHAP_NUM}"


PLAYWRIGHT_HEADLESS = False# Set to False for visible browser during scraping/screenshots
PLAYWRIGHT_TIMEOUT_MS = 30000 


# File to store prompt scores
PROMPTS_FILE = 'prompt_scores.json'

# Adaptive prompt selection parameters
EXPLORATION_RATE = 0.35 # Probability of choosing a random prompt 
LEARNING_RATE = 0.1     # How much new reward impacts a prompt's score

# Score boundaries for prompts
MIN_PROMPT_SCORE = -10.0 
MAX_PROMPT_SCORE = 10.0
# Prompts with scores below this threshold will be excluded from adaptive selection
PROMPT_EXCLUDE_SCORE_THRESHOLD = -5.0


LOG_FILE = 'application.log'
LOG_LEVEL = 'INFO' # Options: DEBUG, INFO, WARNING, ERROR, CRITICAL
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'

def setup_logging():
    """Configures the global logger for the application."""
    log_level = getattr(logging, LOG_LEVEL.upper(), logging.INFO)

    # Get the root logger
    logger = logging.getLogger()
    logger.setLevel(log_level)
    logger.propagate = False # Prevent messages from being duplicated by root logger

    # Clear existing handlers to prevent duplicates on re-runs (
    if logger.handlers:
        for handler in logger.handlers[:]:
            logger.removeHandler(handler)

    # Console Handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    formatter = logging.Formatter(LOG_FORMAT)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # File Handler
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    # Suppress verbose logging from third-party libraries if desired
    logging.getLogger('playwright').setLevel(logging.WARNING)
    logging.getLogger('google.generativeai').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING) # For network requests made by genai/other http clients

    logger.info("Configuration and logging initialized.")

# Call setup_logging when config.py is imported
setup_logging()

# Get the logger instance to be used by other modules

logger = logging.getLogger() 