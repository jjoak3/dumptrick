from nanoid import generate
import re
from typing import List


def generate_player_id() -> str:
    return generate(alphabet="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", size=4)


def get_cards_of_suit(cards: List[str], suit: str) -> List[str]:
    return [card for card in cards if get_suit(card) == suit]


def get_rank(card: str) -> int:
    return parse_card(card)[0]


def get_suit(card: str) -> str:
    return parse_card(card)[1]


def is_higher_rank(card_a: str, card_b: str) -> bool:
    if not card_a:
        return False

    if not card_b:
        return True

    card_a_rank, card_a_suit = parse_card(card_a)
    card_b_rank, card_b_suit = parse_card(card_b)

    if card_a_suit != card_b_suit:
        return False

    return card_a_rank > card_b_rank


def parse_card(card: str) -> tuple[int, str]:
    rank = card[:-1]
    suit = card[-1]

    if rank == "A":
        rank = "14"
    elif rank == "K":
        rank = "13"
    elif rank == "Q":
        rank = "12"
    elif rank == "J":
        rank = "11"

    return int(rank), suit


def rotate_index(index: int, length: int) -> int:
    return (index + 1) % length


def sanitize_for_log(value: str) -> str:
    """
    Sanitize string values for safe logging by removing control characters.
    
    Prevents log injection attacks by removing:
    - ASCII control characters (0x00-0x1F, 0x7F-0x9F)
    - Unicode line separator (U+2028)
    - Unicode paragraph separator (U+2029)
    
    Args:
        value: The string value to sanitize
        
    Returns:
        Sanitized string safe for logging
    """
    if not isinstance(value, str):
        return str(value)
    # Remove ASCII control characters, Unicode line/paragraph separators
    return re.sub(r'[\x00-\x1F\x7F-\x9F\u2028\u2029]', '', value)
