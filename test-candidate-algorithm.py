from solver import Solver, WORDS, args, format_candidates

solver = Solver(length=args.length)
candidates = solver.most_likely_candidates(WORDS)

print(f"Top {args.candidate_number} candidates:")
print(format_candidates(candidates[:args.candidate_number]))
print(f"\nBottom {args.candidate_number} candidates:")
print(format_candidates(candidates[-args.candidate_number:]))