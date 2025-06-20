import random as rnd

from wordle_solver.filter import Filter
from config import WORDS, args

def get_feedback(guess: str, answer: str) -> str:
    """
    Returns a string of feedback colors for the guess compared to the answer.
    'g' for green, 'y' for yellow, 'x' for grey.
    """
    feedback = ['x'] * len(guess)
    answer_chars: list[str | None] = list(answer)

    # First pass for greens
    for i, char in enumerate(guess):
        if char == answer[i]:
            feedback[i] = 'g'
            answer_chars[i] = None  # Remove matched char

    # Second pass for yellows
    for i, char in enumerate(guess):
        if feedback[i] == 'x' and char in answer_chars:
            feedback[i] = 'y'
            answer_chars[answer_chars.index(char)] = None  # Remove matched char

    return ''.join(feedback)

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

def update_filter_with_feedback(filter: Filter, guess: str, feedback: str) -> None:

    for i, char in enumerate(guess):
        if feedback[i] == 'g':
            filter.greens[i] = char
            if char in filter.yellows:
                # Remove this position from yellow positions if present
                if i in filter.yellows[char]:
                    filter.yellows[char].remove(i)
                # If no more yellow positions for this char, remove the char key
                if not filter.yellows[char]:
                    del filter.yellows[char]
        elif feedback[i] == 'y':
            if char not in filter.yellows:
                filter.yellows[char] = set()
            filter.yellows[char].add(i)
        elif feedback[i] == 'x':
            if char not in filter.greys:
                filter.greys.add(char)

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

        update_filter_with_feedback(filter, guess, feedback)

def main():
    play()

if __name__ == "__main__":
    main()
