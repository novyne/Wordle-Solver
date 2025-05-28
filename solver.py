import argparse
import os
import random as rnd

from typing import Optional, TypeAlias, Literal

Colormap: TypeAlias = dict[str, int]


# Argument Parser
parser = argparse.ArgumentParser()
parser.add_argument("-l", "--length", help="Word length", type=int, default=5)
if __name__ == "__main__":
    parser.add_argument("-c", "--candidate-number", help="Number of candidates to return", type=int, default=10)
args = parser.parse_args()


wordset = set()
for file in os.listdir():
    if file.endswith(".txt"):
        with open(file, "r") as f:
            wordset.update(f.read().splitlines())
WORDS: list[str] = list(w.lower() for w in wordset if w.isalpha() and len(w) == args.length)


class Solver:

    def __init__(self, greens: Optional[dict[int, str]] = None, yellows: Optional[dict[str, set[int]]] = None, greys: Optional[list[str]] = None, length: int = 5):
        """
        Initializes the Solver with optional color maps and word length.

        Args:
            greens (Optional[dict[int, str]], optional): Map of position to green letter. Defaults to None.
            yellows (Optional[dict[str, set[int]]], optional): Map of yellow letters to positions they cannot be in. Defaults to None.
            greys (Optional[list[str]], optional): List of grey letters. Defaults to None.
            length (int, optional): Word length. Defaults to 5.
        """

        self.greens = greens or {}
        self.yellows = yellows or {}
        self.greys = greys or []
        self.length = length

    def filter_by_greys(self, words: list[str]) -> list[str]:
        """
        Returns a list of words that do not contain any grey letters.
        Args:
            words (list[str]): The list of words to filter.
        Returns:
            list[str]: The filtered list of words.
        """
        
        return [word for word in words if all(char not in self.greys for char in word)]

    def is_legal_by_greens(self, word: str) -> bool:
        """
        Checks if a word is legal given the green letters.
        Args:
            word (str): The word to check.
        Returns:
            bool: True if the word is legal, False otherwise.
        """

        # Check that all green positions have the correct letter
        for pos, letter in self.greens.items():
            if word[pos] != letter:
                return False
        return True
    
    def filter_by_greens(self, words: list[str]) -> list[str]:
        """
        Returns a list of words that are legal given the green letters.
        Args:
            words (list[str]): The list of words to filter.
        Returns:
            list[str]: The filtered list of words.
        """
        
        return [word for word in words if self.is_legal_by_greens(word)]
        
    def is_legal_by_yellows(self, word: str) -> bool:
        """
        Checks if a word is legal given the yellow letters.
        A word is legal if it contains all yellow letters and they are not in the same position as in the yellow map.
        Args:
            word (str): The word to check.
        Returns:
            bool: True if the word is legal, False otherwise.
        """

        # Check that all yellow letters are present in the word
        for letter, bad_positions in self.yellows.items():
            if word.count(letter) == 0:
                return False
            # Check that letter is not in any of the bad positions
            for pos in bad_positions:
                if word[pos] == letter:
                    return False
        return True
    
    def filter_by_yellows(self, words: list[str]) -> list[str]:
        """
        Returns a list of words that are legal given the yellow letters.
        A word is legal if it contains all yellow letters and they are not in the same position as in the yellow map.
        Args:
            words (list[str]): The list of words to filter.
        Returns:
            list[str]: The filtered list of words.
        """
        
        return [word for word in words if self.is_legal_by_yellows(word)]
    
    def candidates(self, words: list[str]) -> list[str]:
        """
        Returns a list of words that are legal given the green and yellow letters.
        A word is legal if it contains all green letters in the same position as in the green map,
        contains all yellow letters but not in the same position as in the yellow map,
        and does not contain any grey letters.
        Args:
            words (list[str]): The list of words to filter.
        Returns:
            list[str]: The filtered list of words.
        """

        candidates = self.filter_by_greys(words)
        candidates = self.filter_by_greens(candidates)
        candidates = self.filter_by_yellows(candidates)

        return candidates

    def score_candidate_by_usefulness(self, candidate: str) -> float:
        """
        Scores a candidate word based on its usefulness.

        The score encourages the use of high frequency letters and discourages duplicate letters in the candidate word.
        It also gives a small bonus for letters being in more likely positions based on WORDS.
        
        Args:
            candidate (str): The candidate word to score.
        
        Returns:
            float: The calculated usefulness score for the candidate word.
        """

        # Encourage high frequency letters
        frequency = 'etaonrishdlfcmugypwbvkjxzq'
        score = sum(26 - frequency.index(char) for char in candidate)

        # Discourage duplicate letters
        score += len(set(candidate)) ** 1.5

        # Add positional letter frequency bonus
        score += self.positional_letter_bonus(candidate)

        return score

    def positional_letter_bonus(self, candidate: str, sample_number: int = 100) -> float:
        """
        Calculates a bonus score for a candidate word based on how likely its letters are
        to appear in their respective positions, referencing the WORDS list.

        Args:
            candidate (str): The candidate word to score.
            sample_number (int): The number of words to sample from WORDS to calculate frequencies.

        Returns:
            float: The positional letter frequency bonus.
        """
        # Calculate positional frequencies for letters in WORDS
        position_counts = [{} for _ in range(self.length)]

        for word in rnd.choices(WORDS, k=sample_number):
            if len(word) != self.length:
                continue
            for i, char in enumerate(word):
                position_counts[i][char] = position_counts[i].get(char, 0) + 1

        bonus = 0.0
        for i, char in enumerate(candidate):
            if i >= len(position_counts):
                # Defensive check for candidate length mismatch
                continue
            char_count = position_counts[i].get(char, 0)
            # Normalize by total words to get frequency
            freq = char_count / sample_number
            bonus += freq

        # Scale bonus to be a small addition
        return bonus * 10

    def most_likely_candidates(self, candidates: list[str], n: int=10) -> list[str]:
        """
        Returns a list of the most likely candidates to be the word.

        The most likely candidates are determined by scoring each candidate word based on its usefulness.
        The score takes into account the frequency of letters in the word and discourages duplicate letters.
        The candidates are then sorted by their score in descending order.

        Args:
            candidates (list[str]): The list of words to consider.
            n (int): The number of most likely candidates to return. Defaults to 10.

        Returns:
            list[str]: A list of the n most likely candidates.
        """
        
        return sorted(candidates, key=self.score_candidate_by_usefulness, reverse=True)[:n]

    def update(self, guess: str, feedback: str) -> None:
        """
        Updates the Solver with a guess and its corresponding feedback.

        The green letters are stored in a map of position to letter,
        the yellow letters are stored in a map of letter to sets of positions they cannot be in,
        and the grey letters are stored in a list.
        The maps are updated based on the feedback.
        """

        for i, char in enumerate(guess):
            if feedback[i] == 'g':
                self.greens[i] = char
                if char in self.yellows:
                    # Remove this position from yellow positions if present
                    if i in self.yellows[char]:
                        self.yellows[char].remove(i)
                    # If no more yellow positions for this char, remove the char key
                    if not self.yellows[char]:
                        del self.yellows[char]
            elif feedback[i] == 'y':
                if char not in self.yellows:
                    self.yellows[char] = set()
                self.yellows[char].add(i)
            elif feedback[i] == 'x':
                if char not in self.greys:
                    self.greys.append(char)


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
    return word

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
        if not all(char in ['g', 'y', 'x'] for char in returned_data):
            print("Please enter valid colours.")
            continue
        if len(returned_data) != args.length:
            print("Please enter data of the correct length.")
            continue
        break

    return returned_data

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

        candidates = solver.candidates(list(WORDS))
        candidates = solver.most_likely_candidates(candidates, args.candidate_number)

        if len(candidates) == 0:
            print("No candidates found. Please revise your input data.")
            return
        print(f"\nHere are {len(candidates)} possible candidates you can try:")
        print(format_candidates(candidates))

if __name__ == "__main__":
    main()
