import random as rnd
import argparse

from typing import Tuple

from solver import Solver, WORDS, args
from wordle import get_feedback

# Arguments
# parser = argparse.ArgumentParser()
# parser.add_argument("-g", "--game-number", help="Number of games to play", type=int, default=100)
# args = parser.parse_args()
args.game_number = len(WORDS)

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
            print("No candidates left to guess. Failing the game.\n")
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

def run_simulation(num_games: int = 1000) -> float:
    """
    Runs multiple games and prints statistics about the bot's performance.

    Args:
        num_games (int): Number of games to simulate.

    Returns:
        float: Performance percentage of the bot.
    """
    total_guesses = 0
    wins = 0
    guess_distribution = {}

    answers = rnd.choices(WORDS, k=min(num_games, len(WORDS)))

    for game_num in range(1, num_games + 1):
        print(f"Game {game_num}/{args.game_number} starting...")
        answer = answers[game_num - 1]
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
        print(f"  {label}".ljust(5) + f": {guess_distribution[guess_count]}")

    # Calculate and return performance
    performance = calculate_performance(wins, num_games, total_guesses, MAX_GUESSES)
    return performance

def calculate_performance(wins: int, total_games: int, total_guesses: int, max_guesses: int = MAX_GUESSES) -> float:
    """
    Calculate a percentage performance level of the bot based on win rate and average guesses.

    Args:
        wins (int): Number of games won.
        total_games (int): Total number of games played.
        total_guesses (int): Total guesses made in winning games.
        max_guesses (int): Maximum guesses allowed per game.

    Returns:
        float: Performance percentage (0 to 100).
    """
    if total_games == 0:
        return 0.0

    win_rate = wins / total_games
    if wins == 0:
        avg_guesses = max_guesses + 1  # Penalize for no wins
    else:
        avg_guesses = total_guesses / wins

    # Normalize average guesses to a score between 0 and 1 (lower guesses better)
    guess_score = max(0, (max_guesses + 1 - avg_guesses) / (max_guesses + 1))

    # Weighted performance score: 70% win rate, 30% guess efficiency
    performance = (0.7 * win_rate + 0.3 * guess_score) * 100
    return performance

if __name__ == "__main__":
    performance = run_simulation(args.game_number)
    print(f"Bot performance level: {performance:.2f}%")
