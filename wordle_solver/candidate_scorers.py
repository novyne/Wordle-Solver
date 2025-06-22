from utils import get_feedback

class DefaultScorer:

    TESTING_ENABLED = True
    STRICT_CANDIDATES = False

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
    STRICT_CANDIDATES = False

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
    STRICT_CANDIDATES = True

    CANDIDATE_HASH_CACHE = {}

    def __init__(self, ranker):
        import threading
        self.ranker = ranker
        self._entropy_cache = {}
        self._db_lock = threading.Lock()

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
        'feedback.db' for future use.

        Args:
            candidate (str): The candidate word to calculate entropy for.

        Returns:
            float: The calculated entropy value representing expected information gain.
        """

        import math
        import hashlib

        from collections import defaultdict

        from utils import conn

        # Cache for feedback results to avoid redundant calculations
        if not hasattr(self, '_feedback_cache'):
            self._feedback_cache = {}

        if tuple(self.candidates) in self.CANDIDATE_HASH_CACHE:
            candidate_set_hash = self.CANDIDATE_HASH_CACHE[tuple(self.candidates)]
        else:
            candidate_set = ",".join(sorted(self.candidates))
            candidate_set_hash = hashlib.sha256(candidate_set.encode()).hexdigest()
            self.CANDIDATE_HASH_CACHE[tuple(self.candidates)] = candidate_set_hash



        # Check in-memory cache first
        cache_key = (candidate, candidate_set_hash)
        if cache_key in self._entropy_cache:
            return self._entropy_cache[cache_key]

        try:
            with self._db_lock:
                cursor = conn.cursor()
                cursor.execute("SELECT entropy FROM entropy WHERE guess=? AND answer IS NULL AND candidate_set_hash=?", (candidate, candidate_set_hash))
                row = cursor.fetchone()
                cursor.close()
                if row is not None and row[0] is not None:
                    self._entropy_cache[cache_key] = row[0]
                    return row[0]
        except Exception as err:
            print(f"Error reading entropy from DB: {err}")

        patterns = defaultdict(int)

        for answer in self.candidates:
            feedback_key = (candidate, answer)
            if feedback_key in self._feedback_cache:
                feedback = self._feedback_cache[feedback_key]
            else:
                feedback = get_feedback(candidate, answer)
                self._feedback_cache[feedback_key] = feedback
            patterns[feedback] += 1

        e = sum(-(p / len(self.candidates)) * math.log2(p / len(self.candidates)) for p in patterns.values())

        try:
            with self._db_lock:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT OR REPLACE INTO entropy (guess, answer, entropy, candidate_set_hash)
                    VALUES (?, NULL, ?, ?)
                """, (candidate, e, candidate_set_hash))
                cursor.close()
        except Exception as ex:
            print(f"Error writing entropy to DB: {ex}")
            raise ex

        self._entropy_cache[cache_key] = e

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
    STRICT_CANDIDATES = False

    def __init__(self, ranker):
        self.ranker = ranker

    def __getattr__(self, name):
        return getattr(self.ranker, name)
    
    def score(self, candidate: str) -> float:
        
        if len(self.candidates) < 250:
            return ReductionScorer(self.ranker).score(candidate) * 1500# + DefaultScorer(self.ranker).score(candidate) * 0.01
        return DefaultScorer(self.ranker).score(candidate)

class StrictHybridScorer:

    TESTING_ENABLED = True
    STRICT_CANDIDATES = True

    def __init__(self, ranker):
        self.ranker = ranker

    def __getattr__(self, name):
        return getattr(self.ranker, name)

    def score(self, candidate: str) -> float:

        if len(self.candidates) < 100:
            return ReductionScorer(self.ranker).score(candidate) * 1500# + DefaultScorer(self.ranker).score(candidate) * 0.01
        return DefaultScorer(self.ranker).score(candidate)