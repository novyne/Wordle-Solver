import hashlib
import heapq
import math
import multiprocessing
import os
import signal
import sqlite3
import threading

from collections import defaultdict, Counter
from functools import lru_cache
from typing import List, Union

from utils import get_feedback, WORDS

from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn, SpinnerColumn

def _best_with_progress(scorer, n=1, show_progress=False, description="Calculating scores...", candidates=None, func=None) -> list[str]:
    """
    Helper function to compute top n candidates with optional rich progress bar.
    Uses scorer.candidates and scorer.score method.
    """
    if candidates is None:
        candidates = scorer.candidates
    if func is None:
        func = scorer.score

    if len(scorer.candidates) == 1:
        return scorer.candidates[0]
    elif len(scorer.candidates) == 0:
        return []

    if not show_progress:
        if n == 1:
            return [max(candidates, key=func)]
        else:
            return [candidate for candidate, score in heapq.nlargest(n, ((c, func(c)) for c in candidates), key=lambda x: x[1])]
    else:
        scores = []
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        TextColumn("{task.fields[current_word]}", justify="right"),
    ) as progress:
        task = progress.add_task(f"[green]{description}", total=len(candidates), current_word="")
        for i, candidate in enumerate(candidates):
            scores.append((candidate, func(candidate)))
            progress.update(task, advance=1, current_word=f"[bright_blue]{candidate}")
        progress.update(task, completed=len(candidates))

        if n == 1:
            return max(scores, key=lambda x: x[1])[0]
        else:
            return [candidate for candidate, score in heapq.nlargest(n, scores, key=lambda x: x[1])]

class IntuitiveScorer:

    """
    Scores candidate words based on static heuristics that consider letter frequency, letter presence,
    positional letter frequency, and uniqueness of letters. This scorer rewards candidates that are likely
    to provide the most information gain by using common letters, letters in common positions, and penalizes
    excessive duplicate letters. It also rewards candidates that share letters with many other candidates,
    encouraging guesses that can eliminate more possibilities.
    """

    TESTING_ENABLED = False
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

    def best(self, n: int = 1, show_progress: bool=False) -> list[str]:
        return _best_with_progress(self, n=n, show_progress=show_progress, description="Calculating Intuitive scores...")

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

    def best(self, n: int = 1, show_progress: bool=False) -> list[str]:
        return _best_with_progress(self, n=n, show_progress=show_progress, description="Calculating Reduction scores...")

class EntropyScorer:

    """
    Optimized EntropyScorer that precomputes feedback cache using multiprocessing to speed up entropy calculations.
    Reduces redundant feedback computations and batches DB writes to improve performance.
    """

    TESTING_ENABLED = True
    STRICT_CANDIDATES = True
    FIRST_GUESS = "soare"

    CANDIDATE_HASH_CACHE = {}

    @staticmethod
    def _compute_feedback_for_entropy(args):
        candidate, answer = args
        return (candidate, answer, get_feedback(candidate, answer))

    def __init__(self, candidates: list[str]):

        self.candidates = candidates
        self._entropy_cache = {}
        self._db_lock = threading.Lock()

        # Ensure feedback directory exists
        feedback_dir = os.path.join(os.getcwd(), "feedback")
        if not os.path.exists(feedback_dir):
            os.makedirs(feedback_dir)

        # Initialize persistent DB connection in feedback directory
        db_path = os.path.join(feedback_dir, "feedback.db")
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")  # Enable WAL for concurrency
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute("CREATE TABLE IF NOT EXISTS entropy (guess TEXT, answer TEXT, entropy REAL, candidate_set_hash TEXT, PRIMARY KEY (guess, answer, candidate_set_hash));")
        self._conn.commit()

        # Cache for feedback results to avoid redundant calculations
        self._feedback_cache = {}

        # Cache candidate set hash once per instance
        candidate_set = ",".join(sorted(self.candidates))
        self._candidate_set_hash = hashlib.sha256(candidate_set.encode()).hexdigest()

        # Precompute feedback cache using multiprocessing pool
        self.precompute_feedback_cache()

    def precompute_feedback_cache(self):
        """
        Precompute and cache feedback for all candidate-answer pairs using multiprocessing to speed up entropy calculations.
        Optimized to reduce multiprocessing overhead by chunking tasks and minimizing pickling.
        """

        pairs = [(candidate, answer) for candidate in self.candidates for answer in self.candidates]

        def chunked_map(func, data, chunk_size=1000):
            results = []
            try:
                with multiprocessing.Pool() as pool:
                    for i in range(0, len(data), chunk_size):
                        chunk = data[i:i+chunk_size]
                        results.extend(pool.map(func, chunk))
            except Exception as e:
                print(f"Exception in multiprocessing pool: {e}")
                with self._db_lock:
                    try:
                        self._conn.commit()
                        self._conn.close()
                    except Exception as ex:
                        print(f"Error during DB cleanup after multiprocessing exception: {ex}")
                raise
            return results

        results = chunked_map(self._compute_feedback_for_entropy, pairs, chunk_size=5000)

        for candidate, answer, feedback in results:
            self._feedback_cache[(candidate, answer)] = feedback

    def entropy(self, candidate: str) -> float:
        """
        Calculate the entropy of a candidate word based on the distribution of feedback patterns
        it produces against all remaining candidate answers.

        Entropy is a measure of the expected information gain from guessing the candidate word.
        Higher entropy indicates a guess that is expected to reduce the candidate space more effectively.

        This method uses a cached feedback map to avoid recalculating entropy for
        candidates that have been scored before. If the entropy is not cached, it computes the
        distribution of feedback patterns by comparing the candidate against all possible answers,
        calculates the entropy from this distribution, and writes the updated entropy back to
        'feedback.db' for future use.

        Args:
            candidate (str): The candidate word to calculate entropy for.

        Returns:
            float: The calculated entropy value representing expected information gain.
        """

        cache_key = (candidate, self._candidate_set_hash)
        if cache_key in self._entropy_cache:
            return self._entropy_cache[cache_key]

        # Use DB connection with lock for thread safety
        with self._db_lock:
            cursor = self._conn.cursor()
            try:
                cursor.execute("SELECT entropy FROM entropy WHERE guess=? AND answer=? AND candidate_set_hash=?", (candidate, "", self._candidate_set_hash))
                row = cursor.fetchone()
                if row is not None and row[0] is not None:
                    self._entropy_cache[cache_key] = row[0]
                    cursor.close()
                    return row[0]
            except Exception as e:
                print(f"Error reading entropy from DB: {e}")
                cursor.close()

        patterns = defaultdict(int)

        for answer in self.candidates:
            feedback = self._feedback_cache.get((candidate, answer))
            if feedback is None:
                feedback = get_feedback(candidate, answer)
                self._feedback_cache[(candidate, answer)] = feedback
            patterns[feedback] += 1

        e = sum(-(p / len(self.candidates)) * math.log2(p / len(self.candidates)) for p in patterns.values())

        # Batch insert/update entropy in DB without immediate commit
        with self._db_lock:
            cursor = self._conn.cursor()
            try:
                cursor.execute("""
                    INSERT OR REPLACE INTO entropy (guess, answer, entropy, candidate_set_hash)
                    VALUES (?, ?, ?, ?)
                """, (candidate, "", e, self._candidate_set_hash))
            except Exception as ex:
                print(f"Error writing entropy to DB: {ex}")
            cursor.close()

        self._entropy_cache[cache_key] = e

        return e

    def best(self, n: int = 1, show_progress: bool=False) -> list[str]:
        try:
            best = _best_with_progress(self, n=n, show_progress=show_progress, description="Calculating Entropy scores...", candidates=WORDS, func=self.entropy)
            self._conn.commit()
            return best
        except Exception as e:
            print(f"Exception in best(): {e}")
            print("Terminated")
            with self._db_lock:
                self._conn.commit()
                self._conn.close()
            raise

    def _handle_termination(self, signum, frame):
        print(f"Received termination signal ({signum}). Committing and closing DB.")
        with self._db_lock:
            try:
                self._conn.commit()
                self._conn.close()
            except Exception as e:
                print(f"Error during DB cleanup on termination: {e}")
        print("Terminated")

    def __del__(self):
        try:
            self._conn.commit()
            self._conn.close()
        except Exception:
            pass
    
class OptimisedEntropyScorer:
    """
    Highly optimized entropy scorer with improved caching, reduced DB operations,
    and better multiprocessing efficiency for calculating word entropy in word games.
    
    Features:
    - Precomputed feedback cache with efficient multiprocessing
    - LRU caching for frequently used entropy calculations
    - Batched DB operations with WAL mode for concurrency
    - Reduced memory footprint with optimized data structures
    - Thread-safe operations with proper locking
    - Better error handling and resource management
    """

    TESTING_ENABLED = True
    STRICT_CANDIDATES = True
    FIRST_GUESS = "soare"

    def __init__(self, candidates: List[str]):
        """Initialize with a list of candidate words."""
        self.candidates = sorted(candidates)  # Sorting for consistent hashing
        self._feedback_cache = {}
        self._db_lock = threading.Lock()
        self._init_database()
        self._candidate_set_hash = self._hash_candidate_set()
        self._precompute_thread = threading.Thread(target=self._precompute_feedback_cache, daemon=True)
        self._precompute_thread.start()

        # Precompute letter frequency counts for quick_entropy_upper_bound optimization
        self._letter_counts = Counter()
        self._total_letters = 0
        for word in self.candidates:
            unique_letters = set(word)
            self._letter_counts.update(unique_letters)
            self._total_letters += len(unique_letters)

    def _init_database(self):
        """Initialize the SQLite database connection with optimized settings."""
        feedback_dir = os.path.join(os.getcwd(), "feedback")
        os.makedirs(feedback_dir, exist_ok=True)
        
        db_path = os.path.join(feedback_dir, "feedback.db")
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA synchronous=NORMAL;")
        self._conn.execute("""
            CREATE TABLE IF NOT EXISTS entropy (
                guess TEXT,
                answer TEXT,
                entropy REAL,
                candidate_set_hash TEXT,
                PRIMARY KEY (guess, answer, candidate_set_hash)
            );
        """)
        self._conn.commit()

    def _hash_candidate_set(self) -> str:
        """Generate a consistent hash for the current candidate set."""
        candidate_str = ",".join(self.candidates)
        return hashlib.sha256(candidate_str.encode()).hexdigest()

    @staticmethod
    def _compute_feedback_pair(args):
        """Static method for multiprocessing feedback calculations."""
        candidate, answer = args
        return (candidate, answer, get_feedback(candidate, answer))

    def _precompute_feedback_cache(self):
        """Precompute feedback for all candidate pairs using efficient multiprocessing."""
        # Use a generator expression instead of a full list to reduce startup time
        def pair_generator():
            for c in self.candidates:
                for a in self.candidates:
                    yield (c, a)
        pairs = pair_generator()
        
        # Process in chunks to balance memory and CPU usage
        chunk_size = 100
        
        try:
            with multiprocessing.Pool() as pool:
                results = pool.imap_unordered(
                    self._compute_feedback_pair,
                    pairs,
                    chunksize=chunk_size
                )
                # Update the feedback cache incrementally to reduce memory usage
                for candidate, answer, feedback in results:
                    self._feedback_cache[(candidate, answer)] = feedback
        except Exception as e:
            print(f"Exception in multiprocessing pool: {e}")
            with self._db_lock:
                try:
                    self._conn.commit()
                    self._conn.close()
                except Exception as ex:
                    print(f"Error during DB cleanup after multiprocessing exception: {ex}")
            raise

    @lru_cache(maxsize=5000)
    def entropy(self, candidate: str, threshold: float = -1.0) -> float:
        """
        Calculate the entropy of a candidate word with caching at multiple levels.
        Supports early stopping if entropy cannot exceed the given threshold.
        
        Args:
            candidate (str): The candidate word to calculate entropy for.
            threshold (float): Early stopping threshold. If partial entropy plus max possible remaining entropy
                               is less than or equal to this, stop calculation early.
        
        Returns:
            float: The calculated entropy value or a value less than or equal to threshold if early stopped.
        """
        
        # Check database cache only if no threshold or threshold is very low (to avoid false positives)
        if threshold < 0:
            with self._db_lock:
                cursor = self._conn.cursor()
                try:
                    cursor.execute("""
                        SELECT entropy FROM entropy 
                        WHERE guess=? AND answer=? AND candidate_set_hash=?
                    """, (candidate, "", self._candidate_set_hash))
                    if (row := cursor.fetchone()):
                        return row[0]
                except Exception as e:
                    print(f"DB read error: {e}")
                finally:
                    cursor.close()

        # Calculate entropy from feedback patterns with early stopping
        total = len(self.candidates)
        entropy = 0.0
        total_answers = 0

        pattern_counts = defaultdict(int)
        pattern_probs = {}
        entropy_contribs = {}

        for answer in self.candidates:
            with threading.Lock():
                feedback = self._feedback_cache.get((candidate, answer))
            if feedback is None:
                feedback = get_feedback(candidate, answer)
                with threading.Lock():
                    self._feedback_cache[(candidate, answer)] = feedback

            old_count = pattern_counts[feedback]
            new_count = old_count + 1
            pattern_counts[feedback] = new_count
            total_answers += 1

            # Update probabilities and entropy contributions incrementally
            old_prob = pattern_probs.get(feedback, 0)
            new_prob = new_count / total_answers
            pattern_probs[feedback] = new_prob

            # Calculate new entropy contribution for this pattern
            new_entropy_contrib = -new_prob * math.log2(new_prob) if new_prob > 0 else 0

            # Calculate old entropy contribution for this pattern
            old_entropy_contrib = entropy_contribs.get(feedback, 0)

            # Update entropy by removing old contribution and adding new contribution
            entropy += new_entropy_contrib - old_entropy_contrib

            # Store new entropy contribution
            entropy_contribs[feedback] = new_entropy_contrib

            # Adjust other pattern probabilities due to total_answers change
            for pattern, count in pattern_counts.items():
                if pattern != feedback:
                    old_p = pattern_probs.get(pattern, 0)
                    new_p = count / total_answers
                    if old_p != new_p:
                        old_ec = entropy_contribs.get(pattern, 0)
                        new_ec = -new_p * math.log2(new_p) if new_p > 0 else 0
                        entropy += new_ec - old_ec
                        pattern_probs[pattern] = new_p
                        entropy_contribs[pattern] = new_ec

            # Early stopping check: if entropy so far plus max possible remaining entropy < threshold, stop
            max_possible_entropy = math.log2(total)  # Max entropy if all patterns equally likely
            if threshold >= 0 and entropy + (max_possible_entropy * (total - total_answers) / total) <= threshold:
                # Return a value less than or equal to threshold to indicate early stop
                return threshold - 0.0001

        # Cache result in database if no threshold or threshold < 0
        if threshold < 0:
            with self._db_lock:
                cursor = self._conn.cursor()
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO entropy 
                        (guess, answer, entropy, candidate_set_hash)
                        VALUES (?, ?, ?, ?)
                    """, (candidate, "", entropy, self._candidate_set_hash))
                    self._conn.commit()
                except Exception as e:
                    print(f"DB write error: {e}")
                finally:
                    cursor.close()

        return entropy

    def quick_entropy_upper_bound(self, candidate: str) -> float:
        """
        Quick heuristic to estimate an upper bound on entropy for a candidate.
        Uses distribution of letter frequencies in candidate set to estimate max entropy.
        """
        # Use precomputed letter frequency counts
        freqs = []
        unique_letters = set(candidate)
        for letter in unique_letters:
            freq = self._letter_counts.get(letter, 0) / self._total_letters if self._total_letters > 0 else 0
            freqs.append(freq)

        # Estimate entropy upper bound as sum of -p*log2(p) for letter frequencies
        entropy_bound = 0.0
        for p in freqs:
            if p > 0:
                entropy_bound -= p * math.log2(p)

        # Scale by number of unique letters to approximate entropy
        entropy_bound *= len(unique_letters)
        return entropy_bound

    def best(self, n: int = 1, show_progress: bool = False) -> list[str]:
        """
        Find the top n candidates with highest entropy using early elimination optimization.
        
        Args:
            n: Number of top candidates to return
            show_progress: Whether to display progress information
            
        Returns:
            List of top candidates or single string if n=1
        """
        best_entropy = -1.0
        candidates_scores = []

        if len(self.candidates) == 1:
            return self.candidates

        if not show_progress:
            for candidate in WORDS:
                upper_bound = self.quick_entropy_upper_bound(candidate)
                if upper_bound <= best_entropy:
                    # Skip full entropy calculation if upper bound is not better
                    continue
                score = self.entropy(candidate, threshold=best_entropy)
                if score > best_entropy:
                    best_entropy = score
                candidates_scores.append((candidate, score))
        
        else:
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                TextColumn("{task.fields[current_word]}", justify="right"),
            ) as progress:
                
                task = progress.add_task("[green]Calculating Entropy scores...", total=len(WORDS), current_word="")
                for candidate in WORDS:
                    upper_bound = self.quick_entropy_upper_bound(candidate)
                    if upper_bound <= best_entropy:
                        # Skip full entropy calculation if upper bound is not better
                        progress.update(task, advance=1, current_word=f"[bright_blue]{candidate} (skipped)")
                        continue
                    score = self.entropy(candidate, threshold=best_entropy)
                    if score > best_entropy:
                        best_entropy = score
                    candidates_scores.append((candidate, score))
                    progress.update(task, advance=1, current_word=f"[bright_blue]{candidate}")

        # Ensure DB changes are committed asynchronously
        self._async_commit()

        # Get top n candidates by score
        candidates_scores.sort(key=lambda x: x[1], reverse=True)
        if n == 1:
            return candidates_scores[0][0]
        else:
            return [candidate for candidate, score in candidates_scores[:n]]
  
    def _async_commit(self):
        """Commit the database in a separate thread."""

        def commit_thread_func():
            with self._db_lock:
                try:
                    self._conn.commit()
                except Exception as e:
                    print(f"DB async commit error: {e}")

        thread = threading.Thread(target=commit_thread_func)
        thread.daemon = True
        thread.start()

    def __enter__(self):
        """Support context manager protocol for resource management."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up resources when exiting context."""
        self.close()

    def close(self):
        """Explicit cleanup method for resource management."""
        with self._db_lock:
            print("Committing DB connection...")
            self._conn.commit()
            self._conn.close()
        # Clear caches
        self.entropy.cache_clear()
        self._feedback_cache.clear()

    def __del__(self):
        """Destructor for fallback cleanup."""
        self.close()

class SimpleEntropyScorer:

    """
    Similar to EntropyScorer, but does not include any optimisations.
    """

    TESTING_ENABLED = True
    STRICT_CANDIDATES = True
    FIRST_GUESS = "soare"

    def __init__(self, candidates: list[str]):
        self.candidates = candidates

    def entropy(self, candidate: str) -> float:
        """
        Calculate the entropy of a candidate word based on the distribution of feedback patterns
        it produces against all remaining candidate answers.

        This method does not use any optimizations and computes feedback on the fly.

        Args:
            candidate (str): The candidate word to calculate entropy for.

        Returns:
            float: The calculated entropy value representing expected information gain.
        """
        from collections import defaultdict
        import math
        from utils import get_feedback

        patterns = defaultdict(int)
        total = len(self.candidates)

        for answer in self.candidates:
            feedback = get_feedback(candidate, answer)
            patterns[feedback] += 1

        entropy = 0.0
        for count in patterns.values():
            p = count / total
            entropy -= p * math.log2(p)

        return entropy
    
    def best(self, n: int = 1, show_progress: bool = False) -> list[str]:
        return _best_with_progress(self, n=n, show_progress=show_progress, description="Calculating Entropy scores...", func=self.entropy, candidates=WORDS)
            
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

    def best(self, n: int = 1, show_progress: bool=False) -> list[str]:
        es = OptimisedEntropyScorer(self.candidates)
        best = _best_with_progress(self, n=n, show_progress=show_progress, description="Calculating Fast Entropy scores...", func=es.entropy)
        es._conn.commit()
        return best

class HybridScorer:

    """
    Combines scoring strategies by using ReductionScorer for smaller candidate sets and IntuitiveScorer: otherwise.
    This hybrid approach aims to balance the benefits of candidate reduction and heuristic scoring for better performance.
    """

    TESTING_ENABLED = False
    STRICT_CANDIDATES = False
    FIRST_GUESS = "tares"

    def __init__(self, candidates: list[str]):
        self.candidates = candidates

    def score(self, candidate: str) -> float:

        if len(self.candidates) < 250:
            return ReductionScorer(self.candidates).score(candidate) * 1500# + IntuitiveScorer:(self.candidates).score(candidate) * 0.01
        return IntuitiveScorer(self.candidates).score(candidate)

    def best(self, n: int = 1, show_progress: bool=False) -> list[str]:
        return _best_with_progress(self, n=n, show_progress=show_progress, description="Calculating Hybrid scores...")

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

    def best(self, n: int = 1, show_progress: bool=False) -> list[str]:
        return _best_with_progress(self, n=n, show_progress=show_progress, description="Calculating Strict Hybrid scores...")
