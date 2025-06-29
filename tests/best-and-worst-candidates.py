from utils import WORDS, args, format_candidates

from wordle_solver.filter import Filter
import wordle_solver.candidate_scorers as cs

scorer = cs.EntropyScorer

candidates = scorer(WORDS).best(-1, show_progress=True)

print(f"Top {args.candidate_number} candidates:")
print(format_candidates(candidates[:args.candidate_number]))
print(f"\nBottom {args.candidate_number} candidates:")
print(format_candidates(candidates[-args.candidate_number:]))
