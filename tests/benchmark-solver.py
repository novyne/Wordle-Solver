import cProfile
import random as rnd

from wordle_solver import candidate_scorers as cs
from wordle_solver.filter import Filter
from utils import WORDS, get_feedback, format_feedback

SCORER = cs.EntropyScorer

guess = "soare"
answer = rnd.choice(WORDS)

feedback = get_feedback(guess, answer)

filter = Filter()
filter.update(guess, feedback)
candidates = filter.strict_candidates(WORDS)

print(f"Reduced candidates to {len(candidates)} / {len(WORDS)} after receiving feedback {format_feedback(feedback)} from guess {guess}")

cProfile.run("SCORER(candidates).entropy(guess)", sort="tottime")