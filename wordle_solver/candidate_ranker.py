# import wordle_solver.candidate_scorers as cs


class CandidateRanker:

    def __init__(self, candidates: list[str], scorer):
        """
        Initializes the CandidateRanker with a scoring function.

        Args:
            scorer (callable, optional): A scoring function to score candidates.
            candidates (list[str]): The list of candidates to rank.
        """
        self.scorer = scorer
        self.candidates = candidates

        # Initialize caches for scoring
        self._letter_counts = {}
        self._total_letters = 0
        self._position_counts = []
        self._letter_presence = {}
        self._total_candidates = 0

        self._calculate_caches()

        scorer_instance = self.scorer(self)
        self.scorer = scorer_instance

    def _calculate_caches(self) -> None:
        """
        Calculate and store caches used for scoring candidates.
        """
        letter_counts = {}
        total_letters = 0
        length = 0
        for word in self.candidates:
            length = len(word)
            for char in word:
                letter_counts[char] = letter_counts.get(char, 0) + 1
                total_letters += 1

        letter_presence = {}
        for word in self.candidates:
            unique_chars = set(word)
            for char in unique_chars:
                letter_presence[char] = letter_presence.get(char, 0) + 1

        position_counts = [{} for _ in range(length)]
        for word in self.candidates:
            if len(word) != length:
                continue
            for i, char in enumerate(word):
                position_counts[i][char] = position_counts[i].get(char, 0) + 1

        self._letter_counts = letter_counts
        self._total_letters = total_letters
        self._position_counts = position_counts
        self._letter_presence = letter_presence
        self._total_candidates = len(self.candidates)

    def most_likely_candidates(self, n: int = -1) -> list[str]:
        """
        Returns a list of the most likely candidates to be the word.

        The most likely candidates are determined by scoring each candidate word using the scorer function.
        The candidates are then sorted by their score in descending order.

        Args:
            candidates (list[str]): The list of words to consider.
            n (int): The number of most likely candidates to return. Defaults to -1, which returns all candidates.

        Returns:
            list[str]: A list of the n most likely candidates.
        """
        self._calculate_caches()

        scored_candidates = [(c, self.scorer.score(c)) for c in self.candidates] # type: ignore
        scored_candidates.sort(key=lambda x: x[1], reverse=True)

        if n == -1:
            return [c[0] for c in scored_candidates]
        else:
            return [c[0] for c in scored_candidates[:n]]
