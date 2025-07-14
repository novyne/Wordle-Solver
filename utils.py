import argparse
import atexit
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

def get_feedback(guess: str, answer: str) -> int:
    """
    Implements Wordle feedback logic from scratch, ensuring correct handling of repeated letters.
    2 bits per position: 00=grey, 01=yellow, 10=green.
    """

    cache_key = (guess, answer)
    if cache_key in _feedback_cache:
        return _feedback_cache[cache_key]
    # Feedback has the same result for reversed guess and answer
    if (answer, guess) in _feedback_cache:
        return _feedback_cache[(answer, guess)]

    feedback_num = 0
    length = len(guess)

    # Count letters in answer manually without Counter
    answer_letter_counts = {ch: answer.count(ch) for ch in set(answer)}

    green_positions = [False] * length

    for i in range(length):
        if guess[i] == answer[i]:
            feedback_num |= 2 << (2 * i) # green
            answer_letter_counts[guess[i]] -= 1
            green_positions[i] = True

    for i in range(length):
        if not green_positions[i]:
            if guess[i] in answer_letter_counts and answer_letter_counts[guess[i]] > 0:
                feedback_num |= 1 << (2 * i) # yellow
                answer_letter_counts[guess[i]] -= 1

    _feedback_cache[cache_key] = feedback_num

    return feedback_num

def format_feedback(feedback_num: int) -> str:
    """
    Formats the feedback number back into a string of 'g', 'y', 'x' for printing.
    """

    feedback_str = []
    for i in range(args.length):
        # Extract 2 bits for position i
        bits = (feedback_num >> (2 * i)) & 0b11
        if bits == 2:
            feedback_str.append('g')
        elif bits == 1:
            feedback_str.append('y')
        elif bits == 0:
            feedback_str.append('x')
        else:
            raise Exception(f"Invalid feedback bits: {bits} from feedback number {feedback_num}.")
    return "".join(feedback_str)

def intify_feedback(feedback: str) -> int:
    reversed_feedback = feedback[::-1]
    return int(reversed_feedback.replace("g", "10").replace("y", "01").replace("x", "00"), 2)