import inspect
from wordle_solver import candidate_scorers as cs

scorers = [cls for name, cls in inspect.getmembers(cs, inspect.isclass) if cls.__module__ == cs.__name__]

print(scorers)