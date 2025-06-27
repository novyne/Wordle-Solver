import argparse
import atexit
import importlib
import os
import sqlite3

import sys

# Argument Parser
parser = argparse.ArgumentParser()
parser.add_argument("-l", "--length", help="Word length", type=int, default=5)
parser.add_argument("-c", "--candidate-number", help="Number of candidates to return (-1 for all)", type=int, default=10)
parser.add_argument("-w", "--wordlist", help="Wordlist to use (none defaults to all in directory)", type=str, default="all")

if 'ipykernel' in sys.modules:
    # Running inside Jupyter notebook, ignore argv
    args = parser.parse_args(args=[])
else:
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

# Ensure feedback directory exists
feedback_dir = os.path.join(os.getcwd(), "feedback")
if not os.path.exists(feedback_dir):
    os.makedirs(feedback_dir)

# SQLite database setup for feedback map in feedback directory
DB_PATH = os.path.join(feedback_dir, "feedback.db")
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# Drop old tables if exist (to update schema)
# cursor.execute("DROP TABLE IF EXISTS feedback")
# cursor.execute("DROP TABLE IF EXISTS entropy")

# Create table for feedback
# cursor.execute("""
# CREATE TABLE IF NOT EXISTS feedback (
#     guess TEXT NOT NULL,
#     answer TEXT,
#     feedback_num INTEGER,
#     PRIMARY KEY (guess, answer)
# )
# """)

cursor.execute("""
CREATE TABLE IF NOT EXISTS entropy (
    guess TEXT NOT NULL,
    answer TEXT NOT NULL DEFAULT '',
    entropy REAL,
    candidate_set_hash TEXT,
    PRIMARY KEY (guess, answer, candidate_set_hash)
)
""")
conn.commit()

def format_candidates(candidates: list[str]) -> str:
    return "".join(word.ljust(10 + args.length) for word in candidates)

# Also commit feedback map on program exit
atexit.register(conn.commit)

_feedback_cache = {}

ord_dict = {c: i for i, c in enumerate("abcdefghijklmnopqrstuvwxyz")}

def old_get_feedback(guess: str, answer: str) -> int:
    """
    Optimized version of get_feedback using bitwise operations and integer encoding.
    Returns a single integer representing feedback for the guess compared to the answer.
    Each position uses 2 bits:
    00 = grey (x), 01 = yellow (y), 10 = green (g).
    The integer is constructed by shifting bits accordingly.

    This version ensures the number of yellows and greens matches the answer's letter counts.
    """

    cache_key = (guess, answer)
    if cache_key in _feedback_cache:
        return _feedback_cache[cache_key]

    length = len(guess)
    feedback_num = 0

    guess_ords = tuple(ord_dict[c] for c in guess)
    answer_ords = tuple(ord_dict[c] for c in answer)

    # Use fixed-size arrays for letter counts (assuming ASCII lowercase letters)
    answer_letter_counts = [0] * 26
    for i in range(length):
        answer_letter_counts[answer_ords[i]] += 1

    feedback_digits = [0] * length

    # First pass: mark greens and reduce counts
    for i in range(length):
        g_char = guess[i]
        a_char = answer[i]
        if g_char == a_char:
            feedback_digits[i] = 2  # green
            answer_letter_counts[guess_ords[i]] -= 1

    # Second pass: mark yellows if letter exists in answer counts
    for i in range(length):
        if feedback_digits[i] == 0:
            idx = guess_ords[i]
            if answer_letter_counts[idx] > 0:
                feedback_digits[i] = 1  # yellow
                answer_letter_counts[idx] -= 1

    # Construct feedback number using bitwise shifts (2 bits per position)
    for i in range(length):
        feedback_num |= (feedback_digits[i] << (2 * i))

    _feedback_cache[cache_key] = feedback_num

    return feedback_num

def get_feedback(guess: str, answer: str) -> int:
    cache_key = (guess, answer)
    if cache_key in _feedback_cache:
        return _feedback_cache[cache_key]

    length = len(guess)
    feedback_num = 0

    # Precompute character ordinals
    guess_ords = tuple(ord_dict[c] for c in guess)
    answer_ords = tuple(ord_dict[c] for c in answer)

    # Use array for letter counts (faster than list)
    answer_letter_counts = [0] * 26
    for a_ord in answer_ords:
        answer_letter_counts[a_ord] += 1

    # First pass: mark greens and reduce counts
    green_positions = []
    for i in range(length):
        g_ord = guess_ords[i]
        a_ord = answer_ords[i]
        if g_ord == a_ord:
            feedback_num |= (2 << (2 * i))  # green
            answer_letter_counts[g_ord] -= 1
            green_positions.append(i)

    # Second pass: mark yellows if letter exists in answer counts
    for i in range(length):
        if i not in green_positions:
            g_ord = guess_ords[i]
            if answer_letter_counts[g_ord] > 0:
                feedback_num |= (1 << (2 * i))  # yellow
                answer_letter_counts[g_ord] -= 1

    _feedback_cache[cache_key] = feedback_num
    return feedback_num

def format_feedback(feedback_num: int, length: int) -> str:
    """
    Formats the feedback number back into a string of 'g', 'y', 'x' for printing.
    """

    feedback_chars = []
    for i in range(length):
        # Extract 2 bits per position
        digit = (feedback_num >> (2 * i)) & 0b11
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

    feedback_num = 0
    for i, char in enumerate(feedback):
        if char == 'g':
            digit = 2
        elif char == 'y':
            digit = 1
        else:
            digit = 0
        feedback_num |= (digit << (2 * i))
    return feedback_num
