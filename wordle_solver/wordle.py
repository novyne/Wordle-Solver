import random as rnd

from wordle_solver.filter import Filter
from utils import WORDS, args, get_feedback

def validate_guess(guess: str, filter: Filter) -> bool:
    if not guess.isalpha():
        print("Please enter a valid word.")
        return False
    if len(guess) != filter.length:
        print("Please enter a word of the correct length.")
        return False
    if guess not in WORDS:
        print("Please enter a valid word.")
        return False
    return True

def get_user_guess() -> str:
    return input("Guess a word:\t")

def play() -> None:
    answer = rnd.choice(list(WORDS))
    filter = Filter(length=args.length)

    while True:
        guess = get_user_guess()
        if guess == "exit":
            return
        if not validate_guess(guess, filter):
            continue

        if guess == answer:
            print("You win!")
            return

        feedback = get_feedback(guess, answer)
        print("Feedback:\t" + feedback)

        filter.update(guess, feedback)

def main():
    play()

if __name__ == "__main__":
    main()
