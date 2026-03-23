class BotError(Exception):
    """Base bot exception."""


class NotFound(BotError):
    pass


class InvalidStateTransition(BotError):
    pass
