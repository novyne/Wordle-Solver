import inspect
import random as rnd

from wordle_solver import candidate_scorers as cs
from utils import WORDS
from tests.simulate import play_single_game


scorers = [cls for name, cls in inspect.getmembers(cs, inspect.isclass) if cls.__module__ == cs.__name__ and cls.TESTING_ENABLED]

def test_scorer(scorer):
    print(f"Scorer: {scorer.__name__}")
    success, guesses = play_single_game(answer, scorer, display_guesses=True)
    if not success:
        print("\nFAILED!")
    else:
        print(f"\nGuesses: {guesses}")
    print("\n")

def main() -> None:
    print(f"\nANSWER: {answer}\n\n")

    for scorer in scorers:
        test_scorer(scorer)

if __name__ == "__main__":
    answer = rnd.choice(WORDS)
    main()