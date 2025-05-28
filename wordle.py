import random as rnd

from solver import Solver, WORDS

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

def validate_guess(guess: str, solver: Solver) -> bool:
    if not guess.isalpha():
        print("Please enter a valid word.")
        return False
    if len(guess) != solver.length:
        print("Please enter a word of the correct length.")
        return False
    if guess not in WORDS:
        print("Please enter a valid word.")
        return False
    return True

def update_solver_with_feedback(solver: Solver, guess: str, feedback: str) -> None:

    for i, char in enumerate(guess):
        if feedback[i] == 'g':
            solver.greens[i] = char
            if char in solver.yellows:
                # Remove this position from yellow positions if present
                if i in solver.yellows[char]:
                    solver.yellows[char].remove(i)
                # If no more yellow positions for this char, remove the char key
                if not solver.yellows[char]:
                    del solver.yellows[char]
        elif feedback[i] == 'y':
            if char not in solver.yellows:
                solver.yellows[char] = set()
            solver.yellows[char].add(i)
        elif feedback[i] == 'x':
            if char not in solver.greys:
                solver.greys.append(char)

def get_user_guess() -> str:
    return input("Guess a word:\t")

def play() -> None:
    answer = rnd.choice(list(WORDS))
    solver = Solver()

    while True:
        guess = get_user_guess()
        if guess == "exit":
            return
        if not validate_guess(guess, solver):
            continue

        if guess == answer:
            print("You win!")
            return

        feedback = get_feedback(guess, answer)
        print("Feedback:\t" + feedback)

        update_solver_with_feedback(solver, guess, feedback)

def main():
    play()

if __name__ == "__main__":
    main()
