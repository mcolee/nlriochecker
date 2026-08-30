"""Uitzonderingen van de pijplijn."""


class PipelineError(Exception):
    """Basisfout van de pijplijn; de CLI vertaalt deze naar een nette melding."""


class ReportFormatError(PipelineError):
    """Een detailrapport heeft niet het verwachte formaat."""


class NulmetingError(PipelineError):
    """De aangeboden SHACL-rapporten vormen samen geen geldige nulmeting."""


class ConfigError(PipelineError):
    """Het configbestand met de dekkingmapping ontbreekt of is ongeldig."""


class ComparisonError(PipelineError):
    """De twee aangeboden nulmetingen zijn niet vergelijkbaar."""


class StudyAreaError(PipelineError):
    """Het studiegebied ontbreekt, is onleesbaar of staat in een ander stelsel."""


class CoverageError(PipelineError):
    """De dekkingmapping loopt uit de pas met het checkregister."""


class OpdrachtError(PipelineError):
    """Het verzoek zelf kan niet: een onbekende keuze of een vlag zonder houvast."""
