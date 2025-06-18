from solver import Solver, Filter, WORDS, args, format_candidates

filter = Filter(length=args.length)
solver = Solver()
candidates = solver.most_likely_candidates(WORDS)

print(f"Top {args.candidate_number} candidates:")
print(format_candidates(candidates[:args.candidate_number]))
print(f"\nBottom {args.candidate_number} candidates:")
print(format_candidates(candidates[-args.candidate_number:]))