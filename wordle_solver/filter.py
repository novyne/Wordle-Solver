from typing import Optional
from wordle_solver import candidate_scorers as cs

from utils import get_feedback

SCORER = cs.HybridScorer
IMPOSSIBLE_PROPORTION_KEPT = 0.4
IMPOSSIBLE_REGARD_RANGE = range(0, 40)

class Filter:

    def __init__(self, greens: Optional[dict[str, set[int]]] = None, yellows: Optional[dict[str, set[int]]] = None, greys: Optional[set[str]] = None, length: int = 5):
        """
        Initializes the Filter with optional color maps and word length.

        Args:
            greens (Optional[dict[str, set[int]]], optional): Map of green letters to sets of positions. Defaults to None.
            yellows (Optional[dict[str, set[int]]], optional): Map of yellow letters to positions they cannot be in. Defaults to None.
            greys (Optional[set[str]], optional): Set of grey letters. Defaults to None.
            length (int, optional): Word length. Defaults to 5.
        """

        self.greens = greens or {}
        self.yellows = yellows or {}
        self.greys = greys or set()
        self.length = length

        # New attributes to track min and max counts of letters
        self.min_counts = {}  # letter -> minimum count
        self.max_counts = {}  # letter -> maximum count

    def __str__(self) -> str:
        return f"""
        Greens: {self.greens}
        Yellows: {self.yellows}
        Greys: {self.greys}
        Min counts: {self.min_counts}
        Max counts: {self.max_counts}
        """

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

        This method filters words by:
        - Excluding words containing any grey letters.
        - Ensuring green letters are in the correct positions.
        - Ensuring yellow letters are present but not in forbidden positions.
        - Enforcing min_counts and max_counts for letters.
        """
        filtered = []
        for word in words:
            # Exclude words containing any grey letters
            if any(ch in self.greys for ch in word):
                continue

            # Check green letters: must be in correct positions
            green_valid = True
            for ch, positions in self.greens.items():
                if any(pos >= len(word) or word[pos] != ch for pos in positions):
                    green_valid = False
                    break
            if not green_valid:
                continue

            # Check yellow letters: must be present but not in forbidden positions
            yellow_valid = True
            for ch, forbidden_positions in self.yellows.items():
                # Word must contain at least min_counts[ch] occurrences of ch
                if word.count(ch) < self.min_counts.get(ch, 0):
                    yellow_valid = False
                    break
                # Letter must not be in any forbidden positions
                if any(pos < len(word) and word[pos] == ch for pos in forbidden_positions):
                    yellow_valid = False
                    break
            if not yellow_valid:
                continue

            # Count letters in word
            letter_counts = {}
            for ch in word:
                letter_counts[ch] = letter_counts.get(ch, 0) + 1

            # Enforce min_counts
            if any(letter_counts.get(ch, 0) < min_ct for ch, min_ct in self.min_counts.items()):
                continue

            # Enforce max_counts
            if any(letter_counts.get(ch, 0) > max_ct for ch, max_ct in self.max_counts.items()):
                continue

            filtered.append(word)

        return filtered

    def update(self, guess: str, feedback: int) -> None:
        """
        Fully rewritten update method to update filter state based on guess and feedback.

        Args:
            guess (str): The guessed word.
            feedback (int): Encoded feedback integer with 2 bits per letter:
                            0 = grey, 1 = yellow, 2 = green.

        Updates:
            - self.greens: dict of letter to set of positions confirmed green.
            - self.yellows: dict of letter to set of positions forbidden (yellow positions).
            - self.greys: set of letters confirmed absent.
            - self.min_counts: minimum count of each letter.
            - self.max_counts: maximum count of each letter.
        """
        def get_feedback_color(pos: int) -> int:
            return (feedback >> (2 * pos)) & 0b11

        # Temporary structures to track counts and positions
        green_positions = {}
        yellow_positions = {}
        grey_letters = set()

        green_counts = {}
        yellow_counts = {}
        grey_counts = {}

        # First pass: parse feedback and collect info
        for i, ch in enumerate(guess):
            color = get_feedback_color(i)
            if color == 2:  # green
                green_positions.setdefault(ch, set()).add(i)
                green_counts[ch] = green_counts.get(ch, 0) + 1
            elif color == 1:  # yellow
                yellow_positions.setdefault(ch, set()).add(i)
                yellow_counts[ch] = yellow_counts.get(ch, 0) + 1
            else:  # grey
                grey_counts[ch] = grey_counts.get(ch, 0) + 1

        # Update greens: add positions
        for ch, positions in green_positions.items():
            if ch not in self.greens:
                self.greens[ch] = set()
            self.greens[ch].update(positions)

        # Update yellows: add forbidden positions
        for ch, positions in yellow_positions.items():
            if ch not in self.yellows:
                self.yellows[ch] = set()
            self.yellows[ch].update(positions)

        # Remove any yellow forbidden positions that overlap with green positions
        for ch in green_positions:
            if ch in self.yellows:
                self.yellows[ch].difference_update(self.greens[ch])
                if not self.yellows[ch]:
                    del self.yellows[ch]

        # Update greys: letters that are grey and not green or yellow anywhere in guess
        for ch in grey_counts:
            if ch not in green_positions and ch not in yellow_positions:
                self.greys.add(ch)

        # Remove letters from greys if they appear in greens or yellows
        self.greys.difference_update(self.greens.keys())
        self.greys.difference_update(self.yellows.keys())

        # Update min_counts and max_counts for each letter in guess
        letters_in_guess = set(guess)
        for ch in letters_in_guess:
            green_ct = green_counts.get(ch, 0)
            yellow_ct = yellow_counts.get(ch, 0)
            grey_ct = grey_counts.get(ch, 0)

            min_ct = green_ct + yellow_ct
            max_ct = min_ct if grey_ct > 0 else self.length

            self.min_counts[ch] = max(self.min_counts.get(ch, 0), min_ct)
            self.max_counts[ch] = min(self.max_counts.get(ch, self.length), max_ct)

        # Clean up yellows: remove letters with no forbidden positions and no yellow count
        for ch in list(self.yellows.keys()):
            green_pos_count = len(self.greens.get(ch, set()))
            min_ct = self.min_counts.get(ch, 0)
            max_ct = self.max_counts.get(ch, self.length)
            yellow_pos = self.yellows.get(ch, set())
            yellow_ct = max(min_ct - green_pos_count, 0)

            # Remove yellow if min count <= green count and no forbidden positions and no yellow count
            # OR if max count <= green count (no more yellow occurrences possible)
            if (min_ct <= green_pos_count and not yellow_pos and yellow_ct == 0) or (max_ct <= green_pos_count):
                del self.yellows[ch]
