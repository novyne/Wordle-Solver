import inspect

from wordle_solver import candidate_scorers as cs

from tests.simulate import play_single_game


scorers = [cls for name, cls in inspect.getmembers(cs, inspect.isclass) if cls.__module__ == cs.__name__ and cls.TESTING_ENABLED]

answer = 'petty'

for scorer in scorers:
    print(f"\n\nScorer: {scorer.__name__}")
    success, guesses = play_single_game(answer, scorer, display_guesses=True)
    if not success:
        print("FAILED!")
    else:
        print(f"Guesses: {guesses}")