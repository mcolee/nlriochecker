"""Uitzonderingen van de pijplijn."""


class GwswPijplijnFout(Exception):
    """Basisfout van de pijplijn; de CLI vertaalt deze naar een nette melding."""


class RapportFormaatFout(GwswPijplijnFout):
    """Een detailrapport heeft niet het verwachte formaat."""


class RapportPaarFout(GwswPijplijnFout):
    """Het aangeboden rapportenpaar voldoet niet aan de harde eisen."""
