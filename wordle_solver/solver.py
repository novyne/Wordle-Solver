from typing import Literal

import wordle_solver.candidate_scorers as cs
from wordle_solver.filter import Filter
from config import args, WORDS, format_candidates


class CandidateRanker:

    def __init__(self, candidates: list[str], scorer=None):
        """
        Initializes the CandidateRanker with a scoring function.

        Args:
            scorer (callable, optional): A scoring function to score candidates. Defaults to None.
            candidates (list[str]): The list of candidates to rank.
        """
        self.scorer = scorer or cs.DefaultScorer
        self.candidates = candidates

        # Initialize caches for scoring
        self._letter_counts = {}
        self._total_letters = 0
        self._position_counts = []
        self._letter_presence = {}
        self._total_candidates = 0

        self._calculate_caches()

        scorer_instance = self.scorer(self)
        self.scorer = scorer_instance

    def _calculate_caches(self) -> None:
        """
        Calculate and store caches used for scoring candidates.
        """
        letter_counts = {}
        total_letters = 0
        length = 0
        for word in self.candidates:
            length = len(word)
            for char in word:
                letter_counts[char] = letter_counts.get(char, 0) + 1
                total_letters += 1

        letter_presence = {}
        for word in self.candidates:
            unique_chars = set(word)
            for char in unique_chars:
                letter_presence[char] = letter_presence.get(char, 0) + 1

        position_counts = [{} for _ in range(length)]
        for word in self.candidates:
            if len(word) != length:
                continue
            for i, char in enumerate(word):
                position_counts[i][char] = position_counts[i].get(char, 0) + 1

        self._letter_counts = letter_counts
        self._total_letters = total_letters
        self._position_counts = position_counts
        self._letter_presence = letter_presence
        self._total_candidates = len(self.candidates)

    def most_likely_candidates(self, n: int = -1) -> list[str]:
        """
        Returns a list of the most likely candidates to be the word.

        The most likely candidates are determined by scoring each candidate word using the scorer function.
        The candidates are then sorted by their score in descending order.

        Args:
            candidates (list[str]): The list of words to consider.
            n (int): The number of most likely candidates to return. Defaults to -1, which returns all candidates.

        Returns:
            list[str]: A list of the n most likely candidates.
        """
        self._calculate_caches()

        scored_candidates = [(c, self.scorer.score(c)) for c in self.candidates] # type: ignore
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        if n == -1:
            return [c[0] for c in scored_candidates]
        else:
            return [c[0] for c in scored_candidates[:n]]


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

def update_filter_from_input(filter: Filter) -> Filter:
    """
    Continually prompts the user to enter a word and its corresponding colour data and updates the filter.

    Continually prompts the user to enter a word and its corresponding colour data until the user enters "DONE".
    The data is validated and used to update the filter.

    Args:
        filter (Filter): The filter to be updated.

    Returns:
        Filter: The updated filter.
    """

    while True:

        word = receive_word()
        if word is False:
            return filter
        
        returned_data = receive_word_data()

        filter.update(word, returned_data)


def main():

    filter = Filter()
    
    scorer = cs.HybridScorer

    while True:
        filter = update_filter_from_input(filter)

        candidates = filter.candidates(WORDS)
        candidate_ranker = CandidateRanker(candidates, scorer)

        candidates = candidate_ranker.most_likely_candidates(args.candidate_number)

        if len(candidates) == 0:
            print("No candidates found. Please revise your input data.\nSolver has been reset.")
            filter = Filter()
            continue
        elif len(candidates) == 1:
            print(f"The word is: {candidates[0]}")
            return
        print(f"\nHere are {len(candidates)} possible candidates you can try:")
        print(format_candidates(candidates))

if __name__ == "__main__":
    main()
