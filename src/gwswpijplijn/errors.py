"""Uitzonderingen van de pijplijn."""


class PipelineError(Exception):
    """Basisfout van de pijplijn; de CLI vertaalt deze naar een nette melding."""


class ReportFormatError(PipelineError):
    """Een detailrapport heeft niet het verwachte formaat."""


class ReportPairError(PipelineError):
    """Het aangeboden rapportenpaar voldoet niet aan de harde eisen."""


class ConfigError(PipelineError):
    """Het configbestand met de dekkingmapping ontbreekt of is ongeldig."""


class ComparisonError(PipelineError):
    """De twee aangeboden nulmetingen zijn niet vergelijkbaar."""
