import random
import string


ALPHABET = string.ascii_uppercase + string.digits


def generate_code(length: int = 5) -> str:
    return ''.join(random.choice(ALPHABET) for _ in range(length))
