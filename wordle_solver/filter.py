from typing import Optional

class Filter:

    def __init__(self, greens: Optional[dict[int, str]] = None, yellows: Optional[dict[str, set[int]]] = None, greys: Optional[set[str]] = None, length: int = 5):
        """
        Initializes the Filter with optional color maps and word length.

        Args:
            greens (Optional[dict[int, str]], optional): Map of position to green letter. Defaults to None.
            yellows (Optional[dict[str, set[int]]], optional): Map of yellow letters to positions they cannot be in. Defaults to None.
            greys (Optional[set[str]], optional): Set of grey letters. Defaults to None.
            length (int, optional): Word length. Defaults to 5.
        """

        self.greens = greens or {}
        self.yellows = yellows or {}
        self.greys = greys or set()
        self.length = length

    def filter_candidates(self, words: list[str]) -> list[str]:
        """
        Returns a list of words that satisfy all constraints: no grey letters,
        green letters in correct positions, yellow letters present but not in bad positions.

        Args:
            words (list[str]): The list of words to filter.

        Returns:
            list[str]: The filtered list of words.
        """

        filtered = []
        for word in words:
            # Check greys
            if any(char in self.greys for char in word):
                continue
            # Check greens
            if any(word[pos] != letter for pos, letter in self.greens.items()):
                continue
            # Check yellows
            valid = True
            for letter, bad_positions in self.yellows.items():
                if letter not in word:
                    valid = False
                    break
                if any(word[pos] == letter for pos in bad_positions):
                    valid = False
                    break
            if valid:
                filtered.append(word)
        return sorted(filtered)

    def candidates(self, words: list[str]) -> list[str]:
        """
        Returns a list of words that are legal given the green and yellow letters,
        and do not contain any grey letters.

        Args:
            words (list[str]): The list of words to filter.

        Returns:
            list[str]: The filtered list of words.
        """
        return self.filter_candidates(words)

    def update(self, guess: str, feedback: str) -> None:
        """
        Updates the Filter with a guess and its corresponding feedback.

        The green letters are stored in a map of position to letter,
        the yellow letters are stored in a map of letter to sets of positions they cannot be in,
        and the grey letters are stored in a set.
        The maps are updated based on the feedback.
        """

        for i, char in enumerate(guess):
            if feedback[i] == 'g':
                self.greens[i] = char
                if char in self.yellows:
                    if i in self.yellows[char]:
                        self.yellows[char].remove(i)
                    if not self.yellows[char]:
                        del self.yellows[char]
            elif feedback[i] == 'y':
                if char not in self.yellows:
                    self.yellows[char] = set()
                self.yellows[char].add(i)
            elif feedback[i] == 'x':
                self.greys.add(char)
