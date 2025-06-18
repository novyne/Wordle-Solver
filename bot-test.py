import random as rnd
import argparse
from typing import Tuple, List
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict
import threading

from solver import Solver, Filter, WORDS, args
from wordle import get_feedback

from rich.progress import Progress, SpinnerColumn, BarColumn, TextColumn, TimeElapsedColumn

args.game_number = len(WORDS) // 50

MAX_GUESSES = 6
PRINT_LOCK = threading.Lock()

def play_single_game(answer: str) -> Tuple[bool, int]:
    """
    Plays a single game of Wordle where the bot tries to guess the answer.

    Args:
        answer (str): The word to guess.

    Returns:
        Tuple[bool, int]: (success, number_of_guesses)
    """
    solver = Solver()
    filter = Filter()
    guesses = 0

    # with PRINT_LOCK:
    #     print(f"Answer: {answer}")

    while guesses < MAX_GUESSES:
        candidates = filter.candidates(WORDS)
        if not candidates:
            # No candidates left, fail the game
            # with PRINT_LOCK:
            #     print("No candidates left to guess. Failing the game.\n")
            return False, guesses

        # Pick the most likely candidate
        guess = solver.most_likely_candidates(candidates, 1)[0]
        guesses += 1

        # with PRINT_LOCK:
        #     print(f"Guess {guesses}: {guess}", end="\t")

        if guess == answer:
            # with PRINT_LOCK:
            #     print(f"\nGuessed {answer} in {guesses} guesses.\n")
            return True, guesses

        feedback = get_feedback(guess, answer)
        # with PRINT_LOCK:
        #     print(feedback)

        filter.update(guess, feedback)

    # with PRINT_LOCK:
    #     print(f"Failed to guess {answer} within {MAX_GUESSES} guesses.\n")
    return False, guesses

def run_simulation(num_games: int = 1000, max_workers: int = 8) -> float:
    """
    Runs multiple games and prints statistics about the bot's performance.

    Args:
        num_games (int): Number of games to simulate.
        max_workers (int): Number of threads to use.

    Returns:
        float: Performance percentage of the bot.
    """
    total_guesses = 0
    wins = 0
    guess_distribution = defaultdict(int)

    answers = rnd.choices(WORDS, k=min(num_games, len(WORDS)))

    if Progress is not None:
        with Progress(
            SpinnerColumn(),
            "[progress.description]{task.description}",
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            "•",
            TimeElapsedColumn(),
        ) as progress:
            task = progress.add_task(f"Running {num_games} games...", total=num_games)

            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_to_game = {executor.submit(play_single_game, answer): idx+1 for idx, answer in enumerate(answers)}

                for future in as_completed(future_to_game):
                    game_num = future_to_game[future]
                    progress.advance(task)
                    # with PRINT_LOCK:
                    #     print(f"Game {game_num}/{args.game_number} completed.")
                    try:
                        success, guesses = future.result()
                    except Exception as exc:
                        with PRINT_LOCK:
                            print(f"Game {game_num} generated an exception: {exc}")
                        success, guesses = False, MAX_GUESSES + 1

                    if success:
                        wins += 1
                        total_guesses += guesses
                        guess_distribution[guesses] += 1
                    else:
                        guess_distribution[MAX_GUESSES + 1] += 1
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_game = {executor.submit(play_single_game, answer): idx+1 for idx, answer in enumerate(answers)}

            for future in as_completed(future_to_game):
                game_num = future_to_game[future]
                with PRINT_LOCK:
                    print(f"Game {game_num}/{args.game_number} completed.")
                try:
                    success, guesses = future.result()
                except Exception as exc:
                    with PRINT_LOCK:
                        print(f"Game {game_num} generated an exception: {exc}")
                    success, guesses = False, MAX_GUESSES + 1

                if success:
                    wins += 1
                    total_guesses += guesses
                    guess_distribution[guesses] += 1
                else:
                    guess_distribution[MAX_GUESSES + 1] += 1

    with PRINT_LOCK:
        print(f"Games played: {num_games}")
        print(f"Games won: {wins}")
        print(f"Win rate: {wins / num_games * 100:.2f}%")
        if wins > 0:
            print(f"Average guesses (wins only): {total_guesses / wins:.2f}")
        print("Guess distribution (number of guesses : count):")
        for guess_count in sorted(guess_distribution.keys()):
            label = f"{guess_count}" if guess_count <= MAX_GUESSES else f">{MAX_GUESSES}"
            print(f"  {label}".ljust(5) + f": {guess_distribution[guess_count]}")

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

    # Weighted performance score: 60% win rate, 40% guess efficiency
    performance = (0.6 * win_rate + 0.4 * guess_score) * 100
    return performance

if __name__ == "__main__":
    performance = run_simulation(args.game_number)
    print(f"Bot performance level: {performance:.2f}%")
