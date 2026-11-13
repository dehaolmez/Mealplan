"""Tek bir 'bugün' kaynağı; testlerde kolayca sabitlenebilir."""

from datetime import date


def today() -> date:
    return date.today()
