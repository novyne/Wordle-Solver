import inspect

from config import WORDS

from wordle_solver import candidate_scorers as cs
from wordle_solver.filter import Filter
from wordle_solver.solver import CandidateRanker

from tests.simulate import play_single_game


scorers = [cls for name, cls in inspect.getmembers(cs, inspect.isclass) if cls.__module__ == cs.__name__ and cls.TESTING_ENABLED]

answer = 'petty'

for scorer in scorers:
    print(f"Scorer: {scorer.__name__}")
    _, guesses = play_single_game(answer, scorer)
    print(f"Guesses: {guesses}")