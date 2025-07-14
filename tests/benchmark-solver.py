import cProfile
import time
import random
import statistics

from wordle_solver.candidate_scorers import *
from wordle_solver.filter import Filter
from utils import WORDS

SOLVER = OptimisedEntropyScorer

def test_scorer_speed(TESTS: int = 10):
    """
    Test the speed of SOLVER for the FIRST GUESS over TESTS number of tests.
    Chooses answers randomly and times how long it takes for the first guess.
    Averages the results and produces statistics.
    Shows progress bar during the entropy scoring.
    """
    timings = []

    for i in range(TESTS):
        answer = random.choice(WORDS)
        filter = Filter()
        filter.update(SOLVER.FIRST_GUESS, get_feedback(SOLVER.FIRST_GUESS, answer))
        candidates = filter.strict_candidates(WORDS) if SOLVER.STRICT_CANDIDATES else filter.candidates(WORDS)

        # Test header
        print(f"""
        {i+1}/{TESTS}
        Answer: {answer}
        First guess: {SOLVER.FIRST_GUESS}
        #Candidates: {len(candidates)}/{len(WORDS)}
        """)

        scorer = SOLVER(candidates)
        start_time = time.perf_counter()
        first_guess = scorer.best(n=1, show_progress=False)
        end_time = time.perf_counter()
        elapsed = end_time - start_time
        timings.append(elapsed)
        
        # Test footer
        print(f"""
        First guess: {first_guess}
        Time: {elapsed:.4f} seconds
        """)

    avg_time = statistics.mean(timings)
    min_time = min(timings)
    max_time = max(timings)
    stddev_time = statistics.stdev(timings) if len(timings) > 1 else 0.0

    print("\nSpeed Test Statistics for OptimisedEntropyScorer (First Guess):")
    print(f"Number of tests: {TESTS}")
    print(f"Average time: {avg_time:.4f} seconds")
    print(f"Minimum time: {min_time:.4f} seconds")
    print(f"Maximum time: {max_time:.4f} seconds")
    print(f"Standard deviation: {stddev_time:.4f} seconds")

answer = random.choice(WORDS)
filter = Filter()
filter.update(SOLVER.FIRST_GUESS, get_feedback(SOLVER.FIRST_GUESS, answer))
candidates = filter.strict_candidates(WORDS) if SOLVER.STRICT_CANDIDATES else filter.candidates(WORDS)

def test_entropy_speed(TESTS: int = 10):
    """
    Test the speed of SOLVER for the ENTROPY over TESTS number of tests.
    Chooses answers randomly and times how long it takes for the entropy.
    Averages the results and produces statistics.
    """
    timings = []

    TESTS = min(TESTS, len(WORDS))

    scorer = SOLVER(candidates)
    guesses = random.sample(WORDS, TESTS)

    for i in range(TESTS):
        guess = guesses[i]

        # Test header
        print(f"""
        {i+1}/{TESTS}
        Entropy for: {guess}
        #Candidates: {len(candidates)}/{len(WORDS)}
        """)

        start_time = time.perf_counter()
        scorer.entropy(guess)
        end_time = time.perf_counter()
        elapsed = end_time - start_time
        timings.append(elapsed)

if __name__ == "__main__":
    cProfile.run("test_entropy_speed(1000)",sort="tottime")
    cProfile.run("test_scorer_speed(10)",sort="tottime")
