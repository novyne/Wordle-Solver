import argparse
import random as rnd

from utils import WORDS, get_feedback, format_feedback
from wordle_solver.candidate_scorers import EntropyScorer, OptimisedEntropyScorer, FastEntropyScorer
from wordle_solver.filter import Filter

parser = argparse.ArgumentParser()
parser.add_argument("-d", "--depth", type=int, default=1, help="Depth of the entropy tree")
args = parser.parse_args()

scorer = OptimisedEntropyScorer

SAMPLES = len(WORDS)
words = rnd.sample(WORDS, SAMPLES)
print(f"Reduced words to {SAMPLES} / {len(WORDS)}.\n")

def get_patterns(guess: str, answers: list[str]) -> set[int]:
    """
    Returns a list of patterns for the given guess, comparing it against every answer.
    Args:
        guess (str): The guess word.
        answers (list[str]): The list of answer words.
    Returns:
        set[int]: A list of patterns, where each pattern is represented as an integer.
    """

    patterns = set()
    for answer in answers:
        feedback = get_feedback(guess, answer)
        patterns.add(feedback)

    return patterns

def complete_entropy(filter: Filter, depth: int) -> None:
    if depth == 0:
        candidates = filter.candidates(words)
        s = scorer(candidates)

        print(f"{len(candidates)} / {len(words)}...")
        s.best(show_progress=True)
        return
    
    # Get the best guess to use
    if depth == args.depth:
        best_guess = scorer.FIRST_GUESS
    else:
        best_guess = scorer(filter.candidates(words)).best(show_progress=True)

    # Update a filter with all possible patterns
    answers = filter.strict_candidates(words)
    patterns = get_patterns(best_guess, answers)
    patterns = sorted(list(patterns))
    print(f"Obtained {len(patterns)} patterns for {best_guess}.")

    # Create a new filter for each pattern to simulate every response to the best guess
    for i, pattern in enumerate(patterns, start=1):
        new_filter = Filter(greens=filter.greens.copy(), yellows=filter.yellows.copy(), greys=filter.greys.copy(), length=filter.length)
        new_filter.update(best_guess, pattern)

        print(f"({str(i).zfill(2)}) {format_feedback(pattern)}:",end='\t')

        complete_entropy(new_filter, depth - 1)

complete_entropy(Filter(), args.depth)