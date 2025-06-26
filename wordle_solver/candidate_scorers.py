import heapq

from utils import get_feedback

class IntuitiveScorer:

    """
    Scores candidate words based on static heuristics that consider letter frequency, letter presence,
    positional letter frequency, and uniqueness of letters. This scorer rewards candidates that are likely
    to provide the most information gain by using common letters, letters in common positions, and penalizes
    excessive duplicate letters. It also rewards candidates that share letters with many other candidates,
    encouraging guesses that can eliminate more possibilities.
    """

    TESTING_ENABLED = True
    STRICT_CANDIDATES = False
    FIRST_GUESS = "tares"

    def __init__(self, candidates: list[str]):
        self.candidates = candidates
        self._caches_calculated = False

    def _calculate_caches(self) -> None:
        """
        Calculate and store caches used for scoring candidates.
        """
        if self._caches_calculated:
            return

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

        self._caches_calculated = True

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

        self._calculate_caches()

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

    def best(self, n: int = 1) -> list[str] | str:
        if n == 1:
            return max(self.candidates, key=self.score)
        else:
            return [candidate for candidate, score in heapq.nlargest(n, ((c, self.score(c)) for c in self.candidates), key=lambda x: x[1])]

class ReductionScorer:

    """
    Scores candidate words based on their ability to reduce the candidate set size.
    This scorer simulates the filtering effect of each guess against all remaining candidates,
    rewarding guesses that eliminate the most candidates on average. It also penalizes guesses
    that use letters with higher frequencies among remaining candidates, encouraging guesses
    that target less common letters to maximize reduction.
    """

    TESTING_ENABLED = False
    STRICT_CANDIDATES = False
    def __init__(self, candidates: list[str]):
        self.candidates = candidates

    def score(self, candidate: str) -> float:

        from wordle_solver.filter import Filter

        # Collect a letter map of remaining candidates and reward candidates that use letters with lower frequencies
        letter_map = {}
        score = 0

        # Averaging of remaining candidates
        total_remaining = 0
        candidates = self.candidates
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

    def best(self, n: int = 1) -> list[str] | str:
        if n == 1:
            return max(self.candidates, key=self.score)
        else:
            return [candidate for candidate, score in heapq.nlargest(n, ((c, self.score(c)) for c in self.candidates), key=lambda x: x[1])]

class EntropyScorer:

    """
    Scores candidate words based on the entropy of feedback patterns they produce against all remaining candidates.
    Entropy measures the expected information gain from a guess, with higher entropy indicating a guess that
    is expected to reduce the candidate space more effectively. This scorer uses caching and a database to
    store entropy values for efficiency, and calculates entropy by simulating feedback distributions for each guess.
    """

    TESTING_ENABLED = True
    STRICT_CANDIDATES = True
    FIRST_GUESS = "soare"

    CANDIDATE_HASH_CACHE = {}

    def __init__(self, candidates: list[str]):
        import threading

        self.candidates = candidates
        self._entropy_cache = {}
        self._db_lock = threading.Lock()
    
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
        import traceback
        import sqlite3
        import os
        from collections import defaultdict
        from utils import get_feedback

        # Cache for feedback results to avoid redundant calculations
        if not hasattr(self, '_feedback_cache'):
            self._feedback_cache = {}

        # Get candidate set hash
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

        # Create a new connection per call to avoid threading issues
        db_path = os.path.join(os.getcwd(), "feedback.db")
        conn = sqlite3.connect(db_path, check_same_thread=False)

        try:
            cursor = conn.cursor()
            candidate_set_hash_str = str(candidate_set_hash) if candidate_set_hash is not None else ""
            candidate_str = str(candidate) if candidate is not None else ""
            try:
                cursor.execute("SELECT entropy FROM entropy WHERE guess=? AND answer=? AND candidate_set_hash=?", (candidate_str, "", candidate_set_hash_str))
            except Exception as e:
                print(f"Error executing SELECT with params: guess={candidate_str}, answer='', candidate_set_hash={candidate_set_hash_str}")
                traceback.print_exc()
                raise e
            row = cursor.fetchone()
            cursor.close()
            if row is not None and row[0] is not None:
                self._entropy_cache[cache_key] = row[0]
                conn.close()
                return row[0]
        except Exception as err:
            print(f"Error reading entropy from DB: {err}")
            traceback.print_exc()
            conn.close()

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
            cursor = conn.cursor()
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO entropy (guess, answer, entropy, candidate_set_hash)
                    VALUES (?, ?, ?, ?)
                """, (candidate_str, "", e, candidate_set_hash_str))
            except Exception as e:
                print(f"Error executing INSERT with params: guess={candidate_str}, answer='', entropy={e}, candidate_set_hash={candidate_set_hash_str}")
                traceback.print_exc()
                raise e
            conn.commit()
            cursor.close()
            conn.close()
        except Exception as ex:
            print(f"Error writing entropy to DB: {ex}")
            traceback.print_exc()
            conn.close()

        self._entropy_cache[cache_key] = e

        return e

    def best(self, n: int = 1) -> list[str] | str:

        from utils import WORDS

        if len(self.candidates) == 1:
            return self.candidates[0]
        elif len(self.candidates) == 0:
            return []
        if n == 1:
            return max(WORDS, key=self.entropy)
        else:
            return [candidate for candidate, score in heapq.nlargest(n, ((c, self.entropy(c)) for c in WORDS), key=lambda x: x[1])]

class FastEntropyScorer:

    """
    Similar to EntropyScorer, but only computes entropy for candidates rather than for all WORDS.
    This scorer is optimized for performance by limiting entropy calculations to the current candidate set.
    """

    TESTING_ENABLED = True
    STRICT_CANDIDATES = True
    FIRST_GUESS = "soare"

    def __init__(self, candidates: list[str]):
        self.candidates = candidates
    
    def best(self, n: int = 1) -> list[str] | str:
        es = EntropyScorer(self.candidates)

        if len(self.candidates) == 1:
            return self.candidates[0]
        elif len(self.candidates) == 0:
            return []
        if n == 1:
            return max(self.candidates, key=es.entropy)
        else:
            return [candidate for candidate, score in heapq.nlargest(n, ((c, es.entropy(c)) for c in self.candidates), key=lambda x: x[1])]

class HybridScorer:

    """
    Combines scoring strategies by using ReductionScorer for smaller candidate sets and IntuitiveScorer: otherwise.
    This hybrid approach aims to balance the benefits of candidate reduction and heuristic scoring for better performance.
    """

    TESTING_ENABLED = True
    STRICT_CANDIDATES = False
    FIRST_GUESS = "tares"

    def __init__(self, candidates: list[str]):
        self.candidates = candidates
    
    def score(self, candidate: str) -> float:
        
        if len(self.candidates) < 250:
            return ReductionScorer(self.candidates).score(candidate) * 1500# + IntuitiveScorer:(self.candidates).score(candidate) * 0.01
        return IntuitiveScorer(self.candidates).score(candidate)

    def best(self, n: int = 1) -> list[str] | str:
        if n == 1:
            return max(self.candidates, key=self.score)
        else:
            return [candidate for candidate, score in heapq.nlargest(n, ((c, self.score(c)) for c in self.candidates), key=lambda x: x[1])]

class StrictHybridScorer:

    """
    Similar to HybridScorer but enforces strict candidate filtering.
    Uses ReductionScorer for smaller candidate sets and IntuitiveScorer: otherwise.
    """

    TESTING_ENABLED = True
    STRICT_CANDIDATES = True
    FIRST_GUESS = "tares"

    def __init__(self, candidates: list[str]):
        self.candidates = candidates

    def score(self, candidate: str) -> float:

        if len(self.candidates) < 100:
            return ReductionScorer(self.candidates).score(candidate) * 1500# + IntuitiveScorer:(self.candidates).score(candidate) * 0.01
        return IntuitiveScorer(self.candidates).score(candidate)

    def best(self, n: int = 1) -> list[str] | str:
        if n == 1:
            return max(self.candidates, key=self.score)
        else:
            return [candidate for candidate, score in heapq.nlargest(n, ((c, self.score(c)) for c in self.candidates), key=lambda x: x[1])]
