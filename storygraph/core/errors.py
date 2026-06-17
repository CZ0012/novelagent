"""Shared error types."""


class StoryGraphError(Exception):
    """Base class for project-specific errors."""


class ContractError(StoryGraphError):
    """Raised when a contract invariant is violated."""


class GraphStoreError(StoryGraphError):
    """Graph store error with a contract category."""

    def __init__(self, category: str, message: str):
        super().__init__(message)
        self.category = category

