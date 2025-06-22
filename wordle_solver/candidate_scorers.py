from utils import get_feedback

class DefaultScorer:

    TESTING_ENABLED = False

    def __init__(self, ranker):
        self.ranker = ranker

    def __getattr__(self, name):
        return getattr(self.ranker, name)

    def score(self, candidate: str) -> float:
        """
        Default scoring function for a candidate word based on its usefulness using static heuristics.

        The score encourages the use of high frequency letters and letters present in many candidates.
        It also gives a positional bonus for letters in common positions.
        Duplicate letters are penalized but less harshly to allow some repetition.
        The score rewards candidates with more unique letters to maximize information gain.
        Additionally, it rewards candidates that share letters with many other candidates, encouraging elimination of more candidates.

        Args:
            candidate (str): The candidate word to score.

        Returns:
            float: The calculated usefulness score for the candidate word.
        """

        def positional_letter_bonus(candidate: str, position_counts_cache: list[dict[str, int]]) -> float:
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

        score = 0.0
        unique_letters = set(candidate)

        for char in unique_letters:
            freq = self._letter_counts.get(char, 0) / self._total_letters if self._total_letters > 0 else 0
            presence = self._letter_presence.get(char, 0) / self._total_candidates if self._total_candidates > 0 else 0
            # Weight frequency and presence, frequency weighted higher
            score += (freq * 70 + presence * 40)

        # Penalize duplicate letters less harshly
        duplicate_count = len(candidate) - len(unique_letters)
        score -= 20 * duplicate_count ** 1.5

        # Add positional letter frequency bonus using cached counts, weighted more
        score += positional_letter_bonus(candidate, self._position_counts) * 7.5

        # Add bonus for sharing letters with many other candidates
        shared_letter_bonus = 0
        for char in unique_letters:
            shared_letter_bonus += self._letter_presence.get(char, 0)
        # Normalize and weight the shared letter bonus
        score += (shared_letter_bonus / self._total_candidates) * 100

        return score

class ReductionScorer:

    """Scores purely based on how many candidates can be eliminated with a given guess."""

    TESTING_ENABLED = False

    def __init__(self, ranker):
        self.ranker = ranker
    
    def __getattr__(self, name):
        return getattr(self.ranker, name)
    
    def score(self, candidate: str) -> float:

        from wordle_solver.filter import Filter

        # Collect a letter map of remaining candidates and reward candidates that use letters with lower frequencies
        letter_map = {}
        score = 0

        # Averaging of remaining candidates
        total_remaining = 0
        candidates = self.ranker.candidates
        num_candidates = len(candidates)
        if num_candidates == 0:
            return 0.0

        for answer in candidates:
            feedback = get_feedback(candidate, answer)
            filter = Filter(length=len(candidate))
            filter.update(candidate, feedback)
            filtered_candidates = filter.strict_candidates(candidates)
            total_remaining += len(filtered_candidates)

            # Collect letter frequencies
            for i, char in enumerate(answer):
                letter_map[char] = letter_map.get(char, 0) + 1

        
        # Normalise letter frequencies
        for char in letter_map:
            letter_map[char] = letter_map[char] / num_candidates

        # Penalise candidates that use letters with higher frequencies
        for char in candidate:
            score -= letter_map.get(char, 0) ** 2
            score += sum(1 for char in candidate if letter_map.get(char, 0) == 1) ** 2 # Reward candidates that use 1-freq letters

        average_remaining = total_remaining / num_candidates
        # Return negative average remaining to rank candidates that reduce more higher
        return -average_remaining * 100 + score

class EntropyScorer:

    TESTING_ENABLED = True

    def __init__(self, ranker):
        self.ranker = ranker

    def __getattr__(self, name):
        return getattr(self.ranker, name)
    
    def entropy(self, candidate: str) -> float:
        """
        Calculate the entropy of a candidate word based on the distribution of feedback patterns
        it produces against all remaining candidate answers.

        Entropy is a measure of the expected information gain from guessing the candidate word.
        Higher entropy indicates a guess that is expected to reduce the candidate space more effectively.

        This method uses a cached feedback map (FEEDBACK_MAP) to avoid recalculating entropy for
        candidates that have been scored before. If the entropy is not cached, it computes the
        distribution of feedback patterns by comparing the candidate against all possible answers,
        calculates the entropy from this distribution, and writes the updated entropy back to
        'feedback_map.json' for future use.

        Args:
            candidate (str): The candidate word to calculate entropy for.

        Returns:
            float: The calculated entropy value representing expected information gain.
        """

        import math
        import json

        from collections import defaultdict

        from utils import FEEDBACK_MAP

        if candidate in FEEDBACK_MAP and "ENTROPY" in FEEDBACK_MAP[candidate]:
            return FEEDBACK_MAP[candidate]["ENTROPY"]

        patterns = defaultdict(int)

        for answer in self.candidates:
            feedback = get_feedback(candidate, answer)
            patterns[feedback] += 1

        e = sum(-(p / self._total_candidates) * math.log2(p / self._total_candidates) for p in patterns.values())

        # Cache the calculated entropy in the feedback map and write to file for persistence
        FEEDBACK_MAP.setdefault(candidate, {})["ENTROPY"] = e
        with open('feedback_map.json', 'w') as f:
            json.dump(FEEDBACK_MAP, f, indent=4, sort_keys=True)

        return e

    def score(self, candidate: str) -> float:
        """
        Score a candidate word by its entropy value, representing the expected information gain
        from guessing this word.

        Args:
            candidate (str): The candidate word to score.

        Returns:
            float: The entropy score of the candidate.
        """
        return self.entropy(candidate)


class HybridScorer:

    TESTING_ENABLED = True

    def __init__(self, ranker):
        self.ranker = ranker

    def __getattr__(self, name):
        return getattr(self.ranker, name)
    
    def score(self, candidate: str) -> float:
        
        if len(self.candidates) < 250:
            return ReductionScorer(self.ranker).score(candidate) * 1500# + DefaultScorer(self.ranker).score(candidate) * 0.01
        return DefaultScorer(self.ranker).score(candidate)

class StrictHybridScorer:

    TESTING_ENABLED = False

    def __init__(self, ranker):
        self.ranker = ranker

    def __getattr__(self, name):
        return getattr(self.ranker, name)

    def score(self, candidate: str) -> float:

        if len(self.candidates) < 100:
            return ReductionScorer(self.ranker).score(candidate) * 1500# + DefaultScorer(self.ranker).score(candidate) * 0.01
        return DefaultScorer(self.ranker).score(candidate)