import random as rnd
from typing import Tuple

from solver import Solver, WORDS
from wordle import get_feedback

MAX_GUESSES = 6

def play_single_game(answer: str) -> Tuple[bool, int]:
    """
    Plays a single game of Wordle where the bot tries to guess the answer.

    Args:
        answer (str): The word to guess.

    Returns:
        Tuple[bool, int]: (success, number_of_guesses)
    """
    solver = Solver()
    guesses = 0

    print(f"Answer: {answer}")

    while guesses < MAX_GUESSES:
        candidates = solver.candidates(WORDS)
        if not candidates:
            # No candidates left, fail the game
            print("No candidates left to guess. Failing the game.")
            return False, guesses

        # Pick the most likely candidate
        guess = solver.most_likely_candidates(candidates, 1)[0]
        guesses += 1

        print(f"Guess {guesses}: {guess}", end="\t")

        if guess == answer:
            print(f"\nCorrect! Guessed the word in {guesses} guesses.\n")
            return True, guesses

        feedback = get_feedback(guess, answer)
        print(feedback)

        solver.update(guess, feedback)

    print(f"Failed to guess the word within {MAX_GUESSES} guesses.\n")
    return False, guesses

def run_simulation(num_games: int = 1000) -> None:
    """
    Runs multiple games and prints statistics about the bot's performance.

    Args:
        num_games (int): Number of games to simulate.
    """
    total_guesses = 0
    wins = 0
    guess_distribution = {}

    for game_num in range(1, num_games + 1):
        print(f"Game {game_num} starting...")
        answer = rnd.choice(WORDS)
        success, guesses = play_single_game(answer)
        if success:
            wins += 1
            total_guesses += guesses
            guess_distribution[guesses] = guess_distribution.get(guesses, 0) + 1
        else:
            # Count failures as max guesses + 1 for distribution
            guess_distribution[MAX_GUESSES + 1] = guess_distribution.get(MAX_GUESSES + 1, 0) + 1

    print(f"Games played: {num_games}")
    print(f"Games won: {wins}")
    print(f"Win rate: {wins / num_games * 100:.2f}%")
    if wins > 0:
        print(f"Average guesses (wins only): {total_guesses / wins:.2f}")
    print("Guess distribution (number of guesses : count):")
    for guess_count in sorted(guess_distribution.keys()):
        label = f"{guess_count}" if guess_count <= MAX_GUESSES else f">{MAX_GUESSES}"
        print(f"  {label}: {guess_distribution[guess_count]}")

if __name__ == "__main__":
    run_simulation(1000)
