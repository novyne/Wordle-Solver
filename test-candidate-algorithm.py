from solver import CandidateRanker, Filter, WORDS, args, format_candidates

import candidate_scorers as cs

scorer = cs.ReductionScorer

filter = Filter(length=args.length)
scorer = CandidateRanker(WORDS, scorer=scorer)
candidates = scorer.most_likely_candidates()

print(f"Top {args.candidate_number} candidates:")
print(format_candidates(candidates[:args.candidate_number]))
print(f"\nBottom {args.candidate_number} candidates:")
print(format_candidates(candidates[-args.candidate_number:]))
