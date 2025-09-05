from enum import auto, Enum


class PlayerType(Enum):
    BOT = auto()
    HUMAN = auto()


class GamePhase(Enum):
    NOT_STARTED = auto()
    IN_PROGRESS = auto()
    GAME_COMPLETE = auto()


class RoundPhase(Enum):
    NOT_STARTED = auto()
    IN_PROGRESS = auto()
    ROUND_COMPLETE = auto()


class TrickPhase(Enum):
    NOT_STARTED = auto()
    IN_PROGRESS = auto()
    TRICK_COMPLETE = auto()


class TurnPhase(Enum):
    NOT_STARTED = auto()
    IN_PROGRESS = auto()
    TURN_COMPLETE = auto()
