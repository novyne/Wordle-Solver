from typing import Literal

import wordle_solver.candidate_scorers as cs
from wordle_solver.filter import Filter
from utils import args, WORDS, format_candidates, intify_feedback


def receive_word() -> str | Literal[False]:
    """
    Prompts the user to enter a word and returns it if valid.

    Continually prompts the user to enter the most recent word tried until a valid word is entered
    or the user types "DONE" to indicate completion. The word is validated to ensure it only contains
    alphabetic characters and matches the specified length.

    Returns:
        str: The valid word entered by the user.
        Literal[False]: If the user indicates completion with "DONE".
    """

    while True:
        word = input("\nEnter a word you have tried (DONE in all caps to end): ")
        if word == "DONE":
            return False
        
        if not word.isalpha():
            print("Please enter a valid word.")
            continue
        if len(word) != args.length:
            print("Please enter a word of the correct length.")
            continue
        if word not in WORDS:
            print("Please enter a valid word. (Not in word list)")
            continue
        break
    return word.lower()

def receive_word_data() -> str:
    """
    Prompts the user to enter the colour of each letter in the word and returns the result.

    Continually prompts the user to enter the colour of each letter in the word until valid data is entered.
    The data is validated to ensure it only contains valid colours (g, y, x) and matches the specified length.

    Returns:
        str: The valid colour data entered by the user.
    """
    
    while True:
        returned_data = input("Enter the colour of each letter (g for green, y for yellow, x for grey): ")
        if not all(char.lower() in ['g', 'y', 'x'] for char in returned_data):
            print("Please enter valid colours.")
            continue
        if len(returned_data) != args.length:
            print("Please enter data of the correct length.")
            continue
        break

    return returned_data.lower()

def update_filter_from_input(filter: Filter) -> Filter:
    """
    Continually prompts the user to enter a word and its corresponding colour data and updates the filter.

    Continually prompts the user to enter a word and its corresponding colour data until the user enters "DONE".
    The data is validated and used to update the filter.

    Args:
        filter (Filter): The filter to be updated.

    Returns:
        Filter: The updated filter.
    """

    while True:

        word = receive_word()
        if word is False:
            return filter
        
        returned_data = receive_word_data()

        filter.update(word, intify_feedback(returned_data))


def main():

    filter = Filter()
    
    scorer = cs.EntropyScorer

    while True:
        filter = update_filter_from_input(filter)

        candidates = filter.candidates(WORDS)
        candidates = scorer().best(candidates, args.candidate_number)

        if len(candidates) == 0:
            print("No candidates found. Please revise your input data.\nSolver has been reset.")
            filter = Filter()
            continue
        elif len(candidates) == 1:
            print(f"The word is: {candidates[0]}")
            return
        print(f"\nHere are {len(candidates)} possible candidates you can try:")
        print(format_candidates(candidates))

if __name__ == "__main__":
    main()
