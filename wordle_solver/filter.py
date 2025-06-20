from typing import Optional
from wordle_solver import candidate_scorers as cs
from wordle_solver.candidate_ranker import CandidateRanker

# Constant to select the candidate scorer class to use for ranking impossible candidates
# Use string name to avoid circular import
CANDIDATE_SCORER_CLASS = cs.HybridScorer
IMPOSSIBLE_PROPORTION_KEPT = 0.2

class Filter:

    def __init__(self, greens: Optional[dict[int, str]] = None, yellows: Optional[dict[str, set[int]]] = None, greys: Optional[set[str]] = None, length: int = 5):
        """
        Initializes the Filter with optional color maps and word length.

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

        # Track minimum counts of letters based on feedback
        self.min_counts = {}
        # Track maximum counts of letters based on feedback
        self.max_counts = {}

    def candidates(self, words: list[str]) -> list[str]:
        """
        Returns a list of words that satisfy all constraints: no grey letters,
        green letters in correct positions, yellow letters present but not in bad positions,
        and letter counts satisfy min and max constraints.

        Args:
            words (list[str]): The list of words to filter.

        Returns:
            list[str]: The filtered list of words.
        """

        filtered = []
        impossible_candidates = []

        filtered = self.strict_candidates(words)
        impossible_candidates = [word for word in words if word not in filtered]

        # Use CandidateRanker from solver.py for scoring
        ranker = CandidateRanker(words, scorer=CANDIDATE_SCORER_CLASS)

        # Score impossible candidates
        scored_impossible = [(word, ranker.scorer.score(word)) for word in impossible_candidates]
        scored_impossible.sort(key=lambda x: x[1], reverse=True)

        num_to_keep = max(1, int(len(impossible_candidates) * IMPOSSIBLE_PROPORTION_KEPT))

        kept_impossible = [word for word, score in scored_impossible[:num_to_keep]]

        combined = filtered + kept_impossible

        return sorted(combined)

    def strict_candidates(self, words: list[str]) -> list[str]:
        """
        Returns a list of words that satisfy all constraints strictly: no grey letters allowed,
        green letters in correct positions, yellow letters present but not in bad positions,
        and letter counts satisfy min and max constraints.
        This method does not keep any impossible candidates.

        Args:
            words (list[str]): The list of words to filter.

        Returns:
            list[str]: The strictly filtered list of words.
        """
        filtered = []

        for word in words:
            # Reject words with any grey letters
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
            if not valid:
                continue

            # Check min and max counts
            word_counts = {}
            for c in word:
                word_counts[c] = word_counts.get(c, 0) + 1

            # Check min counts
            for letter, min_count in self.min_counts.items():
                if word_counts.get(letter, 0) < min_count:
                    valid = False
                    break
            if not valid:
                continue

            # Check max counts
            for letter, max_count in self.max_counts.items():
                if word_counts.get(letter, 0) > max_count:
                    valid = False
                    break

            if valid:
                filtered.append(word)

        return sorted(filtered)

    def update(self, guess: str, feedback: str) -> None:
        """
        Updates the Filter with a guess and its corresponding feedback.

        The green letters are stored in a map of position to letter,
        the yellow letters are stored in a map of letter to sets of positions they cannot be in,
        and the grey letters are stored in a set.
        The maps are updated based on the feedback.
        """

        # Count occurrences of letters in guess with feedback
        guess_counts = {}
        green_yellow_counts = {}

        for i, char in enumerate(guess):
            guess_counts[char] = guess_counts.get(char, 0) + 1
            if feedback[i] in ('g', 'y'):
                green_yellow_counts[char] = green_yellow_counts.get(char, 0) + 1

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
                # If the letter has green or yellow elsewhere, set max count to green_yellow_counts
                if char in green_yellow_counts:
                    self.max_counts[char] = green_yellow_counts[char]
                else:
                    self.greys.add(char)

        # Update min_counts for letters with green or yellow feedback
        for char, count in green_yellow_counts.items():
            if char not in self.min_counts or self.min_counts[char] < count:
                self.min_counts[char] = count
