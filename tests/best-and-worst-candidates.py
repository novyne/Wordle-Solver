from utils import WORDS, args, format_candidates

from wordle_solver.candidate_ranker import CandidateRanker
from wordle_solver.filter import Filter
import wordle_solver.candidate_scorers as cs

scorer = cs.ReductionScorer

filter = Filter(length=args.length)
scorer = CandidateRanker(WORDS, scorer=scorer)
candidates = scorer.most_likely_candidates()

print(f"Top {args.candidate_number} candidates:")
print(format_candidates(candidates[:args.candidate_number]))
print(f"\nBottom {args.candidate_number} candidates:")
print(format_candidates(candidates[-args.candidate_number:]))
