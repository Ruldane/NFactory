"""Response shapes shared across routes."""

from pydantic import BaseModel


class Page[T](BaseModel):
    items: list[T]
    total: int
    limit: int
    offset: int


class Items[T](BaseModel):
    """An unpaginated list, wrapped so fields can be added later without breaking clients."""

    items: list[T]
