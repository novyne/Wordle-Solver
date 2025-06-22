import argparse
import os
import sqlite3
import threading
import time
import atexit

# Argument Parser
parser = argparse.ArgumentParser()
parser.add_argument("-l", "--length", help="Word length", type=int, default=5)
parser.add_argument("-c", "--candidate-number", help="Number of candidates to return (-1 for all)", type=int, default=10)
parser.add_argument("-w", "--wordlist", help="Wordlist to use (none defaults to all in directory)", type=str, default="all")
args = parser.parse_args()

def load_words_from_file(file: str) -> list[str]:
    """
    Loads words from a specified file.

    If the file does not exist in the current directory, it is assumed to be in the same directory as this script.
    If the file does not have an extension, '.txt' is appended to the end of the name.

    Args:
        file (str): The filename of the file from which to load words.

    Returns:
        list[str]: A list of words from the file, all of which are the same length as specified by the command line argument.
    """

    # Caution where extension is not specified
    if not file.endswith(".txt") and '.' not in file:
        file += ".txt"

    if not os.path.exists(file):
        # Try to find the file in the current directory
        file = os.path.join(os.getcwd(), file)
        if not os.path.exists(file):
            raise FileNotFoundError(f"File {file} does not exist in the current directory.")

    with open(file, "r") as f:
        wordset = f.read().splitlines()
        print("Words loaded from", file)
    
    return [w.lower() for w in wordset if w.isalpha() and len(w) == args.length]

def load_words_from_all_files() -> list[str]:
    """
    Loads all words from all text files in the same directory as the script.
    
    Scans the current directory for files with the .txt extension, and loads all words from them, 
    all of which must be the same length as specified by the command line argument.
    
    Returns:
        list[str]: A list of all words from all text files.
    """

    wordset = set()
    for file in os.listdir():
        if file.endswith(".txt"):
            wordset.update(load_words_from_file(file))
    
    return list(wordset)

if args.wordlist != "all":
    WORDS = load_words_from_file(args.wordlist)
else:
    WORDS = load_words_from_all_files()
WORDS.sort()

if not WORDS:
    raise Exception("No words found in wordlist or no wordlists found.")

# SQLite database setup for feedback map
DB_PATH = "feedback.db"
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# Drop old tables if exist (to update schema)
# cursor.execute("DROP TABLE IF EXISTS feedback")
# cursor.execute("DROP TABLE IF EXISTS entropy")

# Create table for feedback
cursor.execute("""
CREATE TABLE IF NOT EXISTS feedback (
    guess TEXT NOT NULL,
    answer TEXT,
    feedback_num INTEGER,
    PRIMARY KEY (guess, answer)
)
""")

# Create table for entropy with candidate_set_hash column
cursor.execute("""
CREATE TABLE IF NOT EXISTS entropy (
    guess TEXT NOT NULL,
    answer TEXT,
    entropy REAL,
    candidate_set_hash TEXT,
    PRIMARY KEY (guess, answer, candidate_set_hash)
)
""")
conn.commit()

def format_candidates(candidates: list[str]) -> str:
    return "".join(word.ljust(10 + args.length) for word in candidates)

def save_feedback_map():
    """
    Commit changes to the SQLite database.
    """
    conn.commit()

# Auto-save feedback map at regular intervals (e.g., every 60 seconds)
def _auto_save_feedback_map(interval=60):
    while True:
        time.sleep(interval)
        print("Committing SQLite data, do not quit the program...")
        save_feedback_map()

# Start auto-save thread as daemon
_auto_save_thread = threading.Thread(target=_auto_save_feedback_map, daemon=True)
_auto_save_thread.start()

# Also commit feedback map on program exit
atexit.register(save_feedback_map)

_feedback_cache = {}

def get_feedback(guess: str, answer: str) -> int:
    """
    Returns a single number representing feedback for the guess compared to the answer.
    Each position is encoded as a base-3 digit:
    0 = grey (x), 1 = yellow (y), 2 = green (g).
    The number is constructed as sum of digit * 3^position.
    """

    cache_key = (guess, answer)
    if cache_key in _feedback_cache:
        return _feedback_cache[cache_key]

    base = 3
    feedback_num = 0
    for i, char in enumerate(guess):
        if char == answer[i]:
            digit = 2
        elif char in answer:
            digit = 1
        else:
            digit = 0
        feedback_num += digit * (base ** i)

    # Save feedback to SQLite database
    cursor.execute("""
    INSERT OR REPLACE INTO feedback (guess, answer, feedback_num)
    VALUES (?, ?, ?)
    """, (guess, answer, feedback_num))

    _feedback_cache[cache_key] = feedback_num

    return feedback_num

def format_feedback(feedback_num: int, length: int) -> str:
    """
    Formats the feedback number back into a string of 'g', 'y', 'x' for printing.
    """

    base = 3
    feedback_chars = []
    for _ in range(length):
        digit = feedback_num % base
        feedback_num //= base
        if digit == 2:
            feedback_chars.append('g')
        elif digit == 1:
            feedback_chars.append('y')
        else:
            feedback_chars.append('x')
    return "".join(feedback_chars)

def intify_feedback(feedback: str) -> int:
    """
    Converts a string of 'g', 'y', 'x' into an integer.
    """

    base = 3
    feedback_num = 0
    for i, char in enumerate(feedback):
        if char == 'g':
            digit = 2
        elif char == 'y':
            digit = 1
        else:
            digit = 0
        feedback_num += digit * (base ** i)
    return feedback_num
