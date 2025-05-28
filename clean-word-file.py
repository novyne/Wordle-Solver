with open("words.txt", "r") as f:
    words = f.read().splitlines()

allowed_words = [word.lower() for word in words if word.isalpha()]

with open("words.txt", "w") as f:
    f.write("\n".join(allowed_words))