"""Pijplijn voor het toetsen van de datakwaliteit van vrijvervalriolering."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("nlriochecker")
except PackageNotFoundError:  # pragma: no cover - alleen zonder installatie
    # Draaien vanuit een broncheckout zonder installatie: er is geen metadata om
    # uit te lezen. Een herkenbaar nummer is beter dan een importfout.
    __version__ = "0.0.0+onbekend"
