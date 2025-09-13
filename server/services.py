import asyncio
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
            self._update_name(data["player_id"], data["name"])

        elif action == "start_game":
            self._start_game()

        elif action == "play_card":
            self._play_card(data["player_id"], data["card"])

        elif action == "end_turn":
            await asyncio.sleep(0.5)
            self._end_turn()

        elif action == "play_bot_turn":
            self._play_bot_turn(data["bot_id"])

        elif action == "end_game":
            self._end_game()

        await self.players.broadcast(
            {
                "game_state": self.game_state.to_dict(),
                "players": self.players.to_dict(),
            }
        )

    def _update_name(self, player_id: str, new_name: str):
        self.players[player_id].name = new_name.strip()

    def _start_game(self):
        self.players.add_bots()

        self._set_up_new_round()
        self.game_state.game_phase = GamePhase.IN_PROGRESS

    def _set_up_new_round(self):
        self._set_turn_order()

        self.deck_manager.reset()
        self.deck_manager.shuffle()
        self.deck_manager.deal_hands(self.players)

    def _set_turn_order(self):
        self.game_state.turn_order = list(self.players.keys())

    def _play_card(self, player_id: str, card: str):
        player = self.players[player_id]

        if not self._is_valid_play(player, card):
            return

        player.hand.remove(card)
        self.game_state.discard_pile.append(card)

        self.game_state.current_trick.update(card, player)
        self.game_state.turn_phase = TurnPhase.TURN_COMPLETE

        asyncio.create_task(self.handle_action("end_turn"))

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

    def _end_turn(self):
        self.game_state.current_turn_index = rotate_index(
            self.game_state.current_turn_index,
            len(self.game_state.turn_order),
        )
        self.game_state.turn_phase = TurnPhase.NOT_STARTED

        if self._is_trick_over():
            self._end_trick()

        if self._is_round_over():
            self._end_round()

        if self._is_bot_turn():
            asyncio.create_task(
                self.handle_action(
                    "play_bot_turn", {"bot_id": self.game_state.current_player_id}
                )
            )

    def _is_trick_over(self) -> bool:
        return self.game_state.current_turn_index == self.game_state.trick_start_index

    def _end_trick(self):
        current_trick = self.game_state.current_trick

        current_trick.cards = self.game_state.discard_pile.copy()
        self.game_state.discard_pile.clear()

        if self._is_round_over():
            current_trick.is_last_trick = True

        current_trick.winner.take_trick(current_trick)

        winner_index = self.game_state.turn_order.index(current_trick.winner.player_id)
        self.game_state.current_turn_index = winner_index
        self.game_state.trick_start_index = winner_index

        self.game_state.current_trick = Trick()

    def _is_round_over(self) -> bool:
        return all(not player.hand for player in self.players.values())

    def _end_round(self):
        self.game_state.current_round += 1
        ScoreCalculator.set_round_scores(self.players, self.game_state.current_round)

        if self._is_game_over():
            return self._complete_game()

        self.game_state.round_start_index = rotate_index(
            self.game_state.round_start_index, len(self.game_state.turn_order)
        )
        self.game_state.current_turn_index = self.game_state.round_start_index
        self.game_state.trick_start_index = self.game_state.round_start_index

        self._set_up_new_round()
        self.players.clear_tricks()

    def _is_game_over(self) -> bool:
        return self.game_state.current_round >= 5

    def _complete_game(self):
        self.game_state.game_phase = GamePhase.GAME_COMPLETE
        ScoreCalculator.set_winners(self.players)

    def _is_bot_turn(self) -> bool:
        return self.players.get(self.game_state.current_player_id).is_bot()

    def _play_bot_turn(self, bot_id: str):
        card = self.bot_strategy.choose_card(
            self.players.get(bot_id),
            self.game_state.current_trick,
        )

        asyncio.create_task(
            self.handle_action("play_card", {"player_id": bot_id, "card": card})
        )

    def _end_game(self):
        self.game_state.reset()
        self.players.reset()


class ScoreCalculator:
    @staticmethod
    def set_round_scores(players: "Players", current_round: int):
        for player in players.values():
            score = ScoreCalculator._calculate_round_score(player, current_round)
            player.scores.append(score)

    def _calculate_round_score(player: "Player", round_number: int) -> int:
        score = 0

        score += ScoreCalculator._calculate_card_count_penalty(player.tricks)
        if round_number >= 2:
            score += ScoreCalculator._calculate_hearts_penalty(player.tricks)
        if round_number >= 3:
            score += ScoreCalculator._calculate_queens_penalty(player.tricks)
        if round_number >= 4:
            score += ScoreCalculator._calculate_ks_penalty(player.tricks)
        if round_number >= 5:
            score += ScoreCalculator._calculate_last_trick_penalty(player.tricks)

        return score

    def _calculate_card_count_penalty(tricks: List["Trick"]) -> int:
        return sum(len(trick.cards) for trick in tricks)

    def _calculate_hearts_penalty(tricks: List["Trick"]) -> int:
        penalty = 0

        for trick in tricks:
            for card in trick.cards:
                if parse_card(card)[1] == "H":
                    penalty += 10

        return penalty

    def _calculate_queens_penalty(tricks: List["Trick"]) -> int:
        penalty = 0

        for trick in tricks:
            for card in trick.cards:
                if card in ["QC", "QD", "QH", "QS"]:
                    penalty += 25

        return penalty

    def _calculate_ks_penalty(tricks: List["Trick"]) -> int:
        penalty = 0

        for trick in tricks:
            if "KS" in trick.cards:
                penalty += 50

        return penalty

    def _calculate_last_trick_penalty(tricks: List["Trick"]) -> int:
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
