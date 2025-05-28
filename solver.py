import argparse

from typing import Optional, TypeAlias, Literal

Colormap: TypeAlias = dict[str, int]


# Argument Parser
parser = argparse.ArgumentParser()
parser.add_argument("-l", "--length", help="Word length", type=int, default=5)
if __name__ == "__main__":
    parser.add_argument("-c", "--candidate-number", help="Number of candidates to return", type=int, default=10)
args = parser.parse_args()


with open("words.txt", "r") as f:
    WORDS = [word for word in f.read().splitlines() if len(word) == args.length]


class Solver:

    def __init__(self, greens: Optional[dict[str, int]] = None, yellows: Optional[dict[str, int]] = None, greys: Optional[list[str]] = None, length: int = 5):
        """
        Initializes the Solver with optional color maps and word length.

        Args:
            greens (Optional[dict[str, int]], optional): Color map for green letters. Defaults to None.
            yellows (Optional[dict[str, int]], optional): Color map for yellow letters. Defaults to None.
            greys (Optional[list[str]], optional): List of grey letters. Defaults to None.
            length (int, optional): Word length. Defaults to 5.
        """

        self.greens = greens or {}
        self.yellows = yellows or {}
        self.greys = greys or []
        self.length = length

    def filter_by_greys(self, words: list[str]) -> list[str]:
        """
        Returns a list of words that do not contain any grey letters.
        Args:
            words (list[str]): The list of words to filter.
        Returns:
            list[str]: The filtered list of words.
        """
        
        return [word for word in words if all(char not in self.greys for char in word)]

    def is_legal_by_greens(self, word: str) -> bool:
        """
        Checks if a word is legal given the green letters.
        Args:
            word (str): The word to check.
        Returns:
            bool: True if the word is legal, False otherwise.
        """

        # Ensure that all green letters are present
        if sum(1 for char in set(word) if char in self.greens) != len(self.greens):
            return False

        return all(((char in self.greens and self.greens[char] == i) or char not in self.greens) for i, char in enumerate(word))
    
    def filter_by_greens(self, words: list[str]) -> list[str]:
        """
        Returns a list of words that are legal given the green letters.
        Args:
            words (list[str]): The list of words to filter.
        Returns:
            list[str]: The filtered list of words.
        """
        
        return [word for word in words if self.is_legal_by_greens(word)]
        
    def is_legal_by_yellows(self, word: str) -> bool:
        """
        Checks if a word is legal given the yellow letters.
        A word is legal if it contains all yellow letters and they are not in the same position as in the yellow map.
        Args:
            word (str): The word to check.
        Returns:
            bool: True if the word is legal, False otherwise.
        """

        # Ensure that all yellow letters are present
        if sum(1 for char in set(word) if char in self.yellows) != len(self.yellows):
            return False
        
        return all(((char in self.yellows and self.yellows[char] != i) or char not in self.yellows) for i, char in enumerate(word))
    
    def filter_by_yellows(self, words: list[str]) -> list[str]:
        """
        Returns a list of words that are legal given the yellow letters.
        A word is legal if it contains all yellow letters and they are not in the same position as in the yellow map.
        Args:
            words (list[str]): The list of words to filter.
        Returns:
            list[str]: The filtered list of words.
        """
        
        return [word for word in words if self.is_legal_by_yellows(word)]
    
    def candidates(self, words: list[str]) -> list[str]:
        """
        Returns a list of words that are legal given the green and yellow letters.
        A word is legal if it contains all green letters in the same position as in the green map,
        contains all yellow letters but not in the same position as in the yellow map,
        and does not contain any grey letters.
        Args:
            words (list[str]): The list of words to filter.
        Returns:
            list[str]: The filtered list of words.
        """

        candidates = self.filter_by_greys(words)
        candidates = self.filter_by_greens(candidates)
        candidates = self.filter_by_yellows(candidates)

        return candidates

    def score_candidate_by_usefulness(self, candidate: str) -> float:
        """
        Scores a candidate word based on its usefulness.

        The score encourages the use of high frequency letters and discourages duplicate letters in the candidate word.
        
        Args:
            candidate (str): The candidate word to score.
        
        Returns:
            float: The calculated usefulness score for the candidate word.
        """

        # Encourage high frequency letters
        frequency = 'etaonrishdlfcmugypwbvkjxzq'
        score = sum(26 - frequency.index(char) for char in candidate)

        # Discourage duplicate letters
        score += len(set(candidate)) ** 2

        return score

    def most_likely_candidates(self, candidates: list[str], n: int=10) -> list[str]:
        """
        Returns a list of the most likely candidates to be the word.

        The most likely candidates are determined by scoring each candidate word based on its usefulness.
        The score takes into account the frequency of letters in the word and discourages duplicate letters.
        The candidates are then sorted by their score in descending order.

        Args:
            candidates (list[str]): The list of words to consider.
            n (int): The number of most likely candidates to return. Defaults to 10.

        Returns:
            list[str]: A list of the n most likely candidates.
        """
        
        return sorted(candidates, key=self.score_candidate_by_usefulness, reverse=True)[:n]

    def update(self, guess: str, feedback: str) -> None:
        """
        Updates the Solver with a guess and its corresponding feedback.

        The green letters are stored in a map of letter to index,
        the yellow letters are stored in a map of letter to index,
        and the grey letters are stored in a list.
        The maps are updated based on the feedback.
        """

        for i, char in enumerate(guess):
            if feedback[i] == 'g':
                self.greens[char] = i
                if char in self.yellows:
                    del self.yellows[char]
            elif feedback[i] == 'y':
                self.yellows[char] = i
            elif feedback[i] == 'x':
                if char not in self.greys:
                    self.greys.append(char)


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
        word = input("Enter a word you have tried (DONE in all caps to end): ")
        if word == "DONE":
            return False
        
        if not word.isalpha():
            print("Please enter a valid word.")
            continue
        if len(word) != args.length:
            print("Please enter a word of the correct length.")
            continue
        break
    return word

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
        if not all(char in ['g', 'y', 'x'] for char in returned_data):
            print("Please enter valid colours.")
            continue
        if len(returned_data) != args.length:
            print("Please enter data of the correct length.")
            continue
        break

    return returned_data

def receive_input_data() -> tuple[dict[str, int], dict[str, int], list[str]]:
    """
    Prompts the user to enter the data for each word tried.

    The function continually prompts the user to enter the word and its corresponding colour data until the user
    indicates completion with "DONE". The word data is validated to ensure it only contains valid colours (g, y, x)
    and matches the specified length.

    Returns:
        tuple[dict[str, int], dict[str, int], list[str]]: A tuple containing the green letters, yellow letters and grey letters.
    """

    greens = {}
    yellows = {}
    greys = []
    
    while True:

        word = receive_word()
        if word is False:
            return greens, yellows, greys
        
        returned_data = receive_word_data()

        for i, char in enumerate(word):
            if returned_data[i] == 'g':
                greens[char] = i
                if char in yellows:
                    del yellows[char]

            elif returned_data[i] == 'y':
                yellows[char] = i
            elif returned_data[i] == 'x':
                greys.append(char)

def format_candidates(candidates: list[str]) -> list[str]:
    return [f"{word} ({i+1})" for i, word in enumerate(candidates)]


def main():

    greens, yellows, greys = receive_input_data()

    solver = Solver(greens, yellows, greys, args.length)

    candidates = solver.candidates(WORDS)
    candidates = solver.most_likely_candidates(candidates, args.candidate_number)

    if len(candidates) == 0:
        print("No candidates found. Please revise your input data.")
        return
    print(f"Here are {len(candidates)} possible candidates you can try:")
    print("\n".join(format_candidates(candidates)))

if __name__ == "__main__":
    main()