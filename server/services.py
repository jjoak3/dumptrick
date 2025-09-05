import random
from typing import List

from constants import DECK, SUIT_ORDER
from enums import GamePhase, TurnPhase
from helpers import parse_card, rotate_index
from models import GameState, Player, Players, Trick


class BotStrategy:
    @staticmethod
    def choose_card(player: "Player", current_trick: "Trick") -> str:
        cards_matching_leading_suit = []
        for card in player.hand:
            card_suit = parse_card(card)[1]
            if card_suit == current_trick.leading_suit:
                cards_matching_leading_suit.append(card)

        if cards_matching_leading_suit:
            return min(cards_matching_leading_suit, key=parse_card)
        else:
            return max(player.hand, key=parse_card)


class DeckManager:
    def __init__(self):
        self.deck = DECK.copy()

    def shuffle(self):
        random.shuffle(self.deck)

    def deal_hands(self, num_players: int) -> List[List[str]]:
        hand_size = len(self.deck) // num_players
        hands = []

        for _ in range(num_players):
            hand = self.deck[:hand_size]
            self.deck = self.deck[hand_size:]
            hand.sort(key=self._get_card_sort_key)
            hands.append(hand)

        return hands

    def _get_card_sort_key(self, card: str) -> tuple[int, int]:
        rank, suit = parse_card(card)
        return (SUIT_ORDER.index(suit), rank)

    def reset(self):
        self.deck = DECK.copy()


class GameFlow:
    def __init__(self, game_state: "GameState", players: "Players"):
        self.game_state = game_state
        self.players = players
        self.bot_strategy = BotStrategy()
        self.deck_manager = DeckManager()

    def start_game(self):
        self.players.fill_openings_with_bots()

        self.game_state.game_phase = GamePhase.IN_PROGRESS
        self._setup_new_round()

    def _setup_new_round(self):
        self._set_turn_order()

        self.deck_manager.reset()
        self.deck_manager.shuffle()
        hands = self.deck_manager.deal_hands(len(self.players))

        for i, player in enumerate(self.players.values()):
            player.hand = hands[i]

    def _set_turn_order(self):
        self.game_state.turn_order = list(self.players.keys())

    async def play_card(self, player: "Player", card: str) -> bool:
        if not self._is_valid_play(player, card):
            return False

        player.hand.remove(card)
        self.game_state.discard_pile.append(card)
        self.game_state.current_trick.update(card, player.player_id)
        self.game_state.turn_phase = TurnPhase.TURN_COMPLETE

        return True

    def _is_valid_play(self, player: "Player", card: str) -> bool:
        if card not in player.hand:
            return False

        played_suit = parse_card(card)[1]
        leading_suit = self.game_state.current_trick.leading_suit

        if (
            leading_suit
            and player.has_suit_in_hand(leading_suit)
            and played_suit != leading_suit
        ):
            return False

        return True

    def advance_turn(self):
        self.game_state.turn_order_index = rotate_index(
            self.game_state.turn_order_index,
            len(self.game_state.turn_order),
        )
        self.game_state.turn_phase = TurnPhase.NOT_STARTED

        if self._is_trick_over():
            self._advance_trick()

        if self._is_round_over():
            self._advance_round()

    def _is_trick_over(self) -> bool:
        return self.game_state.turn_order_index == self.game_state.trick_start_index

    def _is_round_over(self) -> bool:
        for player in self.players.values():
            if player.hand:
                return False
        return True

    def _advance_trick(self):
        self.game_state.current_trick.cards = self.game_state.discard_pile.copy()
        self.game_state.discard_pile.clear()

        if self._is_round_over():
            self.game_state.current_trick.is_last_trick = True

        winner_id = self.game_state.current_trick.winner
        if not winner_id:
            return
        if winner_id not in self.players:
            return

        winner = self.players.get(winner_id)
        winner.take_trick(self.game_state.current_trick)

        self.game_state.turn_order_index = self.game_state.turn_order.index(winner_id)
        self.game_state.trick_start_index = self.game_state.turn_order_index

        self.game_state.current_trick = Trick()

    def _advance_round(self):
        self.game_state.current_round += 1
        ScoreCalculator.set_round_scores(self.players, self.game_state.current_round)

        if self.game_state.current_round >= 5:
            return self._complete_game()

        self.game_state.round_start_index = rotate_index(
            self.game_state.round_start_index, len(self.game_state.turn_order)
        )
        self.game_state.turn_order_index = self.game_state.round_start_index
        self.game_state.trick_start_index = self.game_state.round_start_index

        self._setup_new_round()
        self.players.clear_tricks()

    def _complete_game(self):
        self.game_state.game_phase = GamePhase.GAME_COMPLETE
        ScoreCalculator.set_winners(self.players)


class ScoreCalculator:
    @staticmethod
    def set_round_scores(players: "Players", current_round: int):
        for player in players.values():
            score = ScoreCalculator.calculate_round_score(player, current_round)
            player.scores.append(score)

    @staticmethod
    def calculate_round_score(player: "Player", round_number: int) -> int:
        score = 0

        score += ScoreCalculator.calculate_card_count_penalty(player.tricks)
        if round_number >= 2:
            score += ScoreCalculator.calculate_hearts_penalty(player.tricks)
        if round_number >= 3:
            score += ScoreCalculator.calculate_queens_penalty(player.tricks)
        if round_number >= 4:
            score += ScoreCalculator.calculate_ks_penalty(player.tricks)
        if round_number >= 5:
            score += ScoreCalculator.calculate_last_trick_penalty(player.tricks)

        return score

    @staticmethod
    def calculate_card_count_penalty(tricks: List["Trick"]) -> int:
        return sum(len(trick.cards) for trick in tricks)

    @staticmethod
    def calculate_hearts_penalty(tricks: List["Trick"]) -> int:
        penalty = 0

        for trick in tricks:
            for card in trick.cards:
                if parse_card(card)[1] == "H":
                    penalty += 10

        return penalty

    @staticmethod
    def calculate_queens_penalty(tricks: List["Trick"]) -> int:
        penalty = 0

        for trick in tricks:
            for card in trick.cards:
                if card in ["QC", "QD", "QH", "QS"]:
                    penalty += 25

        return penalty

    @staticmethod
    def calculate_ks_penalty(tricks: List["Trick"]) -> int:
        penalty = 0

        for trick in tricks:
            if "KS" in trick.cards:
                penalty += 50

        return penalty

    @staticmethod
    def calculate_last_trick_penalty(tricks: List["Trick"]) -> int:
        penalty = 0

        for trick in tricks:
            if trick.is_last_trick:
                penalty += 100

        return penalty

    @staticmethod
    def set_winners(players: "Players"):
        if not players:
            return

        score_totals = {}
        for player_id, player in players.items():
            score_totals[player_id] = sum(player.scores)

        if not score_totals:
            return

        lowest_score = min(score_totals.values())

        for player_id, player_score in score_totals.items():
            if player_score == lowest_score:
                players.get(player_id).is_winner = True
