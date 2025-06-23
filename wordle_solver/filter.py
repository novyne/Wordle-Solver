from typing import Optional
from wordle_solver import candidate_scorers as cs

from utils import get_feedback

SCORER = cs.HybridScorer
IMPOSSIBLE_PROPORTION_KEPT = 0.4
IMPOSSIBLE_REGARD_RANGE = range(0, 40)

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

        filtered = self.strict_candidates(words)

        if len(filtered) not in IMPOSSIBLE_REGARD_RANGE:
            return filtered

        impossible_candidates = [word for word in words if word not in filtered]

        # Score filtered candidates and get top N
        scored_filtered = [(word, SCORER(filtered).score(word)) for word in filtered]
        scored_filtered.sort(key=lambda x: x[1], reverse=True)
        top_filtered = [word for word, score in scored_filtered[:10]]

        # Letter map of all candidates
        letter_map = {}
        for word in filtered:
            for i, char in enumerate(word):
                letter_map[char] = letter_map.get(char, 0) + 1
        # print(letter_map)
        # print(filtered)

        contribution_score_cache = {}

        def contribution_score(candidate: str) -> float:
            if candidate in contribution_score_cache:
                return contribution_score_cache[candidate]

            if not top_filtered:
                contribution_score_cache[candidate] = 0.0
                return 0.0

            reference = top_filtered[0]

            feedback = get_feedback(candidate, reference)

            temp_filter = Filter(
                greens=self.greens.copy(),
                yellows={k: v.copy() for k, v in self.yellows.items()},
                greys=self.greys.copy(),
                length=self.length
            )

            greens_before = len(temp_filter.greens)
            yellows_before = sum(len(v) for v in temp_filter.yellows.values())
            greys_before = len(temp_filter.greys)

            temp_filter.update(candidate, feedback)

            greens_diff = len(temp_filter.greens) - greens_before
            yellows_diff = sum(len(v) for v in temp_filter.yellows.values()) - yellows_before
            greys_diff = len(temp_filter.greys) - greys_before
            candidate_diff = len(filtered) - len(temp_filter.strict_candidates(filtered))

            # Calculate ratios relative to current counts or 1 to avoid division by zero
            greens_ratio = greens_diff / max(1, len(self.greens))
            yellows_ratio = yellows_diff / max(1, sum(len(v) for v in self.yellows.values()))
            greys_ratio = greys_diff / max(1, len(self.greys))

            # Weighted sum of ratios
            score = 6 * greens_ratio + 3 * yellows_ratio + 0.5 * greys_ratio + candidate_diff

            # Penalise using letters that appear frequently in the map (encourages diversity)
            for char in candidate:
                score -= letter_map.get(char, 0) ** 2
            
            # Exponentially reward based on the number of freq-1 letters in the candidate
            score += sum(1 for char in candidate if letter_map.get(char, 0) == 1) ** 3

            contribution_score_cache[candidate] = score
            return score
        
        scored: list[tuple[str, float]] = [(word, contribution_score(word)) for word in impossible_candidates + filtered]
        scored.sort(key=lambda x: x[1], reverse=True)

        num_to_keep = max(1, int(len(filtered) * IMPOSSIBLE_PROPORTION_KEPT))
        kept_impossible = [word for word, _ in scored[:num_to_keep]]

        # print("Imps:", kept_impossible)

        combined = filtered + kept_impossible

        return sorted(combined)

    def strict_candidates(self, words: list[str]) -> list[str]:
        """
        Return a list of words that could be the answer based on the current state of the filter.
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

    def update(self, guess: str, feedback: int) -> None:
        """
        Updates the Filter with a guess and its corresponding feedback.

        The green letters are stored in a map of position to letter,
        the yellow letters are stored in a map of letter to sets of positions they cannot be in,
        and the grey letters are stored in a set.
        The maps are updated based on the feedback.
        """

        base = 3
        for i, char in enumerate(guess):
            digit = (feedback // (base ** i)) % base
            if digit == 2:  # green
                self.greens[i] = char
                if char in self.yellows:
                    if i in self.yellows[char]:
                        self.yellows[char].remove(i)
                    if not self.yellows[char]:
                        del self.yellows[char]
            elif digit == 1:  # yellow
                if char in self.greys:
                    self.greys.remove(char)
                if char not in self.yellows:
                    self.yellows[char] = set()
                self.yellows[char].add(i)
            elif digit == 0:  # grey
                if char not in self.yellows:
                    self.greys.add(char)
