from nanoid import generate


def generate_player_id() -> str:
    return generate(alphabet="0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ", size=4)


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
