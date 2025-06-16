import argparse
import os
import random as rnd

from typing import Optional, TypeAlias, Literal

Colormap: TypeAlias = dict[str, int]


# Argument Parser
parser = argparse.ArgumentParser()
parser.add_argument("-l", "--length", help="Word length", type=int, default=5)
# if __name__ == "__main__":
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

if not WORDS:
    raise Exception("No words found in wordlist or no wordlists found.")

class Solver:

    def __init__(self, greens: Optional[dict[int, str]] = None, yellows: Optional[dict[str, set[int]]] = None, greys: Optional[set[str]] = None, length: int = 5):
        """
        Initializes the Solver with optional color maps and word length.

        Args:
            greens (Optional[dict[int, str]], optional): Map of position to green letter. Defaults to None.
            yellows (Optional[dict[str, set[int]]], optional): Map of yellow letters to positions they cannot be in. Defaults to None.
            greys (Optional[set[str]], optional): Set of grey letters. Defaults to None.
            length (int, optional): Word length. Defaults to 5.
        """

        self.greens = greens or {}
        self.yellows = yellows or {}
        self.greys = greys or set()
        self.length = length

    def filter_candidates(self, words: list[str]) -> list[str]:
        """
        Returns a list of words that satisfy all constraints: no grey letters,
        green letters in correct positions, yellow letters present but not in bad positions.

        Args:
            words (list[str]): The list of words to filter.

        Returns:
            list[str]: The filtered list of words.
        """

        filtered = []
        for word in words:
            # Check greys
            if any(char in self.greys for char in word):
                continue
            # Check greens
            if any(word[pos] != letter for pos, letter in self.greens.items()):
                continue
            # Check yellows
            valid = True
            for letter, bad_positions in self.yellows.items():
                if letter not in word:
                    valid = False
                    break
                if any(word[pos] == letter for pos in bad_positions):
                    valid = False
                    break
            if valid:
                filtered.append(word)
        return filtered

    def candidates(self, words: list[str]) -> list[str]:
        """
        Returns a list of words that are legal given the green and yellow letters,
        and do not contain any grey letters.

        Args:
            words (list[str]): The list of words to filter.

        Returns:
            list[str]: The filtered list of words.
        """
        return self.filter_candidates(words)

    def score_candidate_by_usefulness(self, candidate: str, letter_counts_cache: dict[str, int], total_letters: int, position_counts_cache: list[dict[str, int]], letter_presence_cache: dict[str, int], total_candidates: int) -> float:
        """
        Scores a candidate word based on its usefulness.

        The score encourages the use of high frequency letters and discourages duplicate letters in the candidate word.
        It also gives a small bonus for letters being in more likely positions based on candidates.
        This improved version counts total occurrences of letters (not just unique per word),
        adds a presence bonus for letters appearing in many candidates,
        and adjusts duplicate letter penalty to be less harsh.

        Additionally, it rewards candidates that share letters with many other candidates, encouraging elimination of more candidates.

        Args:
            candidate (str): The candidate word to score.
            letter_counts_cache (dict[str, int]): Cached letter frequency counts.
            total_letters (int): Total number of letters counted.
            position_counts_cache (list[dict[str, int]]): Cached positional letter frequency counts.
            letter_presence_cache (dict[str, int]): Cached letter presence counts.
            total_candidates (int): Total number of candidates.

        Returns:
            float: The calculated usefulness score for the candidate word.
        """

        score = 0
        for char in candidate:
            freq = letter_counts_cache.get(char, 0) / total_letters if total_letters > 0 else 0
            presence = letter_presence_cache.get(char, 0) / total_candidates if total_candidates > 0 else 0
            # Weight frequency and presence, frequency weighted higher
            score += (freq * 60 + presence * 40)

        # Penalize duplicate letters
        unique_letters = set(candidate)
        duplicate_count = len(candidate) - len(unique_letters)
        score -= 100 * duplicate_count ** 3

        # Add positional letter frequency bonus using cached counts, weighted more
        score += self.positional_letter_bonus(candidate, position_counts_cache) * 1.5

        # Add bonus for sharing letters with many other candidates
        shared_letter_bonus = 0
        for char in set(candidate):
            shared_letter_bonus += letter_presence_cache.get(char, 0)
        # Normalize and weight the shared letter bonus
        score += (shared_letter_bonus / total_candidates) * 50

        return score

    def positional_letter_bonus(self, candidate: str, position_counts_cache: list[dict[str, int]]) -> float:
        """
        Calculates a bonus score for a candidate word based on how likely its letters are
        to appear in their respective positions, referencing the cached positional counts.

        Args:
            candidate (str): The candidate word to score.
            position_counts_cache (list[dict[str, int]]): Cached positional letter frequency counts.

        Returns:
            float: The positional letter frequency bonus.
        """
        bonus = 0.0
        for i, char in enumerate(candidate):
            if i >= len(position_counts_cache):
                continue
            char_count = position_counts_cache[i].get(char, 0)
            total_count = sum(position_counts_cache[i].values())
            freq = char_count / total_count if total_count > 0 else 0
            bonus += freq

        return bonus * 10

    def most_likely_candidates(self, candidates: list[str], n: int = -1) -> list[str]:
        """
        Returns a list of the most likely candidates to be the word.

        The most likely candidates are determined by scoring each candidate word based on its usefulness.
        The score takes into account the frequency of letters in the word and discourages duplicate letters.
        The candidates are then sorted by their score in descending order.

        Args:
            candidates (list[str]): The list of words to consider.
            n (int): The number of most likely candidates to return. Defaults to -1, which returns all candidates.

        Returns:
            list[str]: A list of the n most likely candidates.
        """
        # Cache letter frequency counts (total occurrences of letters)
        letter_counts = {}
        total_letters = 0
        for word in candidates:
            for char in word:
                letter_counts[char] = letter_counts.get(char, 0) + 1
                total_letters += 1

        # Cache letter presence counts (number of candidates containing the letter)
        letter_presence = {}
        for word in candidates:
            unique_chars = set(word)
            for char in unique_chars:
                letter_presence[char] = letter_presence.get(char, 0) + 1

        # Cache positional letter frequency counts
        position_counts = [{} for _ in range(self.length)]
        for word in candidates:
            if len(word) != self.length:
                continue
            for i, char in enumerate(word):
                position_counts[i][char] = position_counts[i].get(char, 0) + 1

        # Score candidates using cached counts
        scored_candidates = [(c, self.score_candidate_by_usefulness(c, letter_counts, total_letters, position_counts, letter_presence, len(candidates))) for c in candidates]
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        if n == -1:
            return [c[0] for c in scored_candidates]
        else:
            return [c[0] for c in scored_candidates[:n]]

    def update(self, guess: str, feedback: str) -> None:
        """
        Updates the Solver with a guess and its corresponding feedback.

        The green letters are stored in a map of position to letter,
        the yellow letters are stored in a map of letter to sets of positions they cannot be in,
        and the grey letters are stored in a set.
        The maps are updated based on the feedback.
        """

        for i, char in enumerate(guess):
            if feedback[i] == 'g':
                self.greens[i] = char
                if char in self.yellows:
                    if i in self.yellows[char]:
                        self.yellows[char].remove(i)
                    if not self.yellows[char]:
                        del self.yellows[char]
            elif feedback[i] == 'y':
                if char not in self.yellows:
                    self.yellows[char] = set()
                self.yellows[char].add(i)
            elif feedback[i] == 'x':
                self.greys.add(char)


def receive_word() -> str | Literal[False]:
    """
    Prompts the user to enter a word and returns it if valid.

    Continually prompts the user to enter the most recent word tried until a valid word is entered
    or the user types "DONE" to indicate completion. The word is validated to ensure it only contains
    alphabetic characters and matches the specified length.

    Returns:
        str: The valid word entered by the user.
        Literal[False]: If the user indicates completion with "DONE".
    """

    while True:
        word = input("\nEnter a word you have tried (DONE in all caps to end): ")
        if word == "DONE":
            return False
        
        if not word.isalpha():
            print("Please enter a valid word.")
            continue
        if len(word) != args.length:
            print("Please enter a word of the correct length.")
            continue
        if word not in WORDS:
            print("Please enter a valid word. (Not in word list)")
            continue
        break
    return word.lower()

def receive_word_data() -> str:
    """
    Prompts the user to enter the colour of each letter in the word and returns the result.

    Continually prompts the user to enter the colour of each letter in the word until valid data is entered.
    The data is validated to ensure it only contains valid colours (g, y, x) and matches the specified length.

    Returns:
        str: The valid colour data entered by the user.
    """
    
    while True:
        returned_data = input("Enter the colour of each letter (g for green, y for yellow, x for grey): ")
        if not all(char.lower() in ['g', 'y', 'x'] for char in returned_data):
            print("Please enter valid colours.")
            continue
        if len(returned_data) != args.length:
            print("Please enter data of the correct length.")
            continue
        break

    return returned_data.lower()

def update_solver_from_input(solver: Solver) -> Solver:
    """
    Continually prompts the user to enter a word and its corresponding colour data and updates the solver.

    Continually prompts the user to enter a word and its corresponding colour data until the user enters "DONE".
    The data is validated and used to update the solver.

    Args:
        solver (Solver): The solver to be updated.

    Returns:
        Solver: The updated solver.
    """

    while True:

        word = receive_word()
        if word is False:
            return solver
        
        returned_data = receive_word_data()

        solver.update(word, returned_data)

def format_candidates(candidates: list[str]) -> str:
    return "".join(word.ljust(10 + args.length) for word in candidates)


def main():

    solver = Solver()

    while True:
        solver = update_solver_from_input(solver)

        candidates = solver.candidates(WORDS)
        candidates = solver.most_likely_candidates(candidates, args.candidate_number)

        if len(candidates) == 0:
            print("No candidates found. Please revise your input data.\nSolver has been reset.")
            solver = Solver()
            continue
        elif len(candidates) == 1:
            print(f"The word is: {candidates[0]}")
            return
        print(f"\nHere are {len(candidates)} possible candidates you can try:")
        print(format_candidates(candidates))

if __name__ == "__main__":
    main()
