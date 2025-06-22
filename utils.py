import argparse
import json
import os

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

if not os.path.exists("feedback_map.json"):
    with open("feedback_map.json", "w") as f:
        json.dump({}, f)
FEEDBACK_MAP = json.load(open("feedback_map.json", "r"))

def format_candidates(candidates: list[str]) -> str:
    return "".join(word.ljust(10 + args.length) for word in candidates)

import atexit
import threading
import time

def save_feedback_map():
    """
    Saves the FEEDBACK_MAP dictionary to the feedback_map.json file in a pretty and readable format.
    """
    with open("feedback_map.json", "w") as f:
        json.dump(FEEDBACK_MAP, f, indent=4, sort_keys=True)

# Auto-save feedback map at regular intervals (e.g., every 60 seconds)
def _auto_save_feedback_map(interval=60):
    while True:
        time.sleep(interval)
        print("Saving .json data, do not quit the program...")
        save_feedback_map()

# Start auto-save thread as daemon
_auto_save_thread = threading.Thread(target=_auto_save_feedback_map, daemon=True)
_auto_save_thread.start()

# Also save feedback map on program exit
atexit.register(save_feedback_map)

def get_feedback(guess: str, answer: str) -> int:
    """
    Returns a single number representing feedback for the guess compared to the answer.
    Each position is encoded as a base-3 digit:
    0 = grey (x), 1 = yellow (y), 2 = green (g).
    The number is constructed as sum of digit * 3^position.
    """

    feedback_num = 0
    base = 3
    for i, char in enumerate(guess):
        if char == answer[i]:
            digit = 2
        elif char in answer:
            digit = 1
        else:
            digit = 0
        feedback_num += digit * (base ** i)
    
    # Save to feedback map in memory only
    if guess not in FEEDBACK_MAP:
        FEEDBACK_MAP[guess] = {}
    FEEDBACK_MAP[guess][answer] = feedback_num

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