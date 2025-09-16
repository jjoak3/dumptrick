import asyncio
import random
from typing import List

from constants import DECK, NUM_ROUNDS, SUIT_ORDER
from enums import GamePhase, TurnPhase
from helpers import get_cards_of_suit, get_rank, parse_card, rotate_index
from models import GameState, Player, Players, Trick


class BotStrategy:
    @staticmethod
    def choose_card(player: "Player", current_trick: "Trick") -> str:
        """
        1. If bot leads trick, play lowest card in hand
        2. If bot can follow leading suit, play lowest card of that suit
        3. If bot cannot follow leading suit, play highest card in hand
        """

        if not current_trick.leading_suit:
            return BotStrategy._get_lowest_card(player.hand)

        cards_of_leading_suit = get_cards_of_suit(
            player.hand, current_trick.leading_suit
        )

        if cards_of_leading_suit:
            return BotStrategy._get_card_of_leading_suit(
                cards_of_leading_suit, current_trick.cards
            )
        else:
            return BotStrategy._get_highest_card(player.hand)

    @staticmethod
    def _get_card_of_leading_suit(cards: List[str], trick_cards: List[str]) -> str:
        lowest_card = min(cards, key=get_rank)

        if not trick_cards:
            return lowest_card

        lowest_trick_card = min(trick_cards, key=get_rank)

        if get_rank(lowest_card) > get_rank(lowest_trick_card):
            return lowest_card

        cards_lower_than_lowest_trick_card = []
        for card in cards:
            if get_rank(card) < get_rank(lowest_trick_card):
                cards_lower_than_lowest_trick_card.append(card)

        return max(cards_lower_than_lowest_trick_card, key=get_rank)

    @staticmethod
    def _get_highest_card(cards: List[str]) -> str:
        def _highest_card_key(card: str) -> tuple[int, int, int]:
            """
            Sorting preference:
            1. Higher rank (dump more dangerous cards first)
            2. Suit with fewer cards (deplete short suits)
            3. Suit with higher total rank (dump from dangerous suits)
            """

            rank, suit = parse_card(card)
            cards_of_suit = get_cards_of_suit(cards, suit)
            cos_count = len(cards_of_suit)
            cos_rank_sum = sum(get_rank(card) for card in cards_of_suit)
            return (rank, -cos_count, cos_rank_sum)

        return max(cards, key=_highest_card_key)

    @staticmethod
    def _get_lowest_card(cards: List[str]) -> str:
        def _lowest_card_key(card: str) -> tuple[int, int, int]:
            """
            Sorting preference:
            1. Lower rank (dump safer cards first)
            2. Suit with fewer cards (deplete short suits)
            3. Suit with lower total rank (dump from safer suits)
            """

            rank, suit = parse_card(card)
            cards_of_suit = get_cards_of_suit(cards, suit)
            cos_count = len(cards_of_suit)
            cos_rank_sum = sum(get_rank(card) for card in cards_of_suit)
            return (rank, cos_count, cos_rank_sum)

        return min(cards, key=_lowest_card_key)


class DeckManager:
    def __init__(self):
        self.deck = DECK.copy()

    def shuffle(self):
        random.shuffle(self.deck)

    def deal_hands(self, players: Players) -> List[List[str]]:
        hand_size = len(self.deck) // len(players)

        for player in players.values():
            player.hand = self.deck[:hand_size]
            self.deck = self.deck[hand_size:]
            player.hand.sort(key=self._get_card_sort_key)

    def _get_card_sort_key(self, card: str) -> tuple[int, int]:
        rank, suit = parse_card(card)
        return (SUIT_ORDER.index(suit), rank)

    def reset(self):
        self.deck = DECK.copy()


class GameEngine:
    def __init__(self):
        self.game_state = GameState()
        self.players = Players()
        self.bot_strategy = BotStrategy()
        self.deck_manager = DeckManager()

    async def handle_action(self, action: str, data: dict = {}):
        if action == "update_name":
            await self._update_name(data["player_id"], data["name"])

        elif action == "start_game":
            await self._start_game()

        elif action == "play_card":
            await self._play_card(data["player_id"], data["card"])

        elif action == "reset_game":
            await self.reset_game()

    async def _update_name(self, player_id: str, new_name: str):
        self.players[player_id].name = new_name.strip()

        await self._broadcast_state()

    async def _broadcast_state(self):
        await self.players.broadcast(
            {
                "game_state": self.game_state.to_dict(),
                "players": self.players.to_dict(),
            }
        )

    async def _start_game(self):
        self.players.add_bots()

        self._set_up_new_round()
        self.game_state.game_phase = GamePhase.IN_PROGRESS

        await self._broadcast_state()

    def _set_up_new_round(self):
        self._set_turn_order()

        self.deck_manager.reset()
        self.deck_manager.shuffle()
        self.deck_manager.deal_hands(self.players)

    def _set_turn_order(self):
        self.game_state.turn_order = list(self.players.keys())

    async def _play_card(self, player_id: str, card: str):
        player = self.players[player_id]

        if not self._is_valid_play(player, card):
            return

        player.hand.remove(card)
        self.game_state.discard_pile.append(card)

        self.game_state.current_trick.update(card, player_id)
        self.game_state.turn_phase = TurnPhase.TURN_COMPLETE

        await self._broadcast_state()

        await self._end_turn()

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

    async def _end_turn(self):
        await asyncio.sleep(0.5)

        self.game_state.current_turn_index = rotate_index(
            self.game_state.current_turn_index,
            len(self.game_state.turn_order),
        )
        self.game_state.turn_phase = TurnPhase.NOT_STARTED

        if self._is_trick_over():
            await self._end_trick()

        if self._is_round_over():
            self._end_round()

        await self._broadcast_state()

        if self._is_bot_turn():
            await self._play_bot_turn(self.game_state.current_player_id)

    def _is_trick_over(self) -> bool:
        return self.game_state.current_turn_index == self.game_state.trick_start_index

    async def _end_trick(self):
        current_trick = self.game_state.current_trick

        current_trick.cards = self.game_state.discard_pile.copy()
        self.game_state.discard_pile.clear()

        if self._is_round_over():
            current_trick.is_last_trick = True

        current_round = self.game_state.current_round
        card_scores = ScoreCalculator.get_card_scores(current_trick, current_round)

        winner = self.players.get(current_trick.winner_id)
        winner.take_trick(current_trick)

        await self._animate_card_scores(card_scores)

        winner.update_scores(current_round, sum(card_scores))

        winner_index = self.game_state.turn_order.index(current_trick.winner_id)
        self.game_state.current_turn_index = winner_index
        self.game_state.trick_start_index = winner_index

        self.game_state.current_trick = Trick()

    async def _animate_card_scores(self, card_scores: List[int]):
        for count, _ in enumerate(card_scores, 1):
            await self.players.broadcast({"card_scores": card_scores[:count]})
            await asyncio.sleep(0.25)

        await asyncio.sleep(0.5)
        await self.players.broadcast({"card_scores": []})

    def _is_round_over(self) -> bool:
        return all(not player.hand for player in self.players.values())

    def _end_round(self):
        if self._is_game_over():
            return self._end_game()

        self.game_state.current_round += 1

        self.game_state.round_start_index = rotate_index(
            self.game_state.round_start_index, len(self.game_state.turn_order)
        )
        self.game_state.current_turn_index = self.game_state.round_start_index
        self.game_state.trick_start_index = self.game_state.round_start_index

        self._set_up_new_round()
        self.players.clear_tricks()

    def _is_game_over(self) -> bool:
        return self.game_state.current_round >= NUM_ROUNDS

    def _end_game(self):
        self.game_state.game_phase = GamePhase.GAME_COMPLETE
        ScoreCalculator.set_winners(self.players)

    def _is_bot_turn(self) -> bool:
        return self.players.get(self.game_state.current_player_id).is_bot()

    async def _play_bot_turn(self, bot_id: str):
        if self.game_state.game_phase != GamePhase.IN_PROGRESS:
            return

        card = self.bot_strategy.choose_card(
            self.players.get(bot_id),
            self.game_state.current_trick,
        )

        await self._play_card(bot_id, card)

    async def reset_game(self):
        self.game_state.reset()
        self.players.reset()

        await self._broadcast_state()


class ScoreCalculator:
    @staticmethod
    def get_card_scores(trick: "Trick", current_round: int) -> List[int]:
        card_scores = []

        for card in trick.cards:
            card_suit = parse_card(card)[1]
            card_score = 0

            if current_round >= 1:
                card_score += 1
            if current_round >= 2 and card_suit == "H":
                card_score += 10
            if current_round >= 3 and card in ["QC", "QD", "QH", "QS"]:
                card_score += 25
            if current_round >= 4 and card == "KS":
                card_score += 50

            card_scores.append(card_score)

        if current_round >= 5 and trick.is_last_trick:
            card_scores.append(100)

        return card_scores

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
