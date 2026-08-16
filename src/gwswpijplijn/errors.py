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


class DatasetError(PipelineError):
    """De OroX-dataset ontbreekt, is onleesbaar of bevat geen toetsbare objecten."""


class StudyAreaError(PipelineError):
    """Het studiegebied ontbreekt, is onleesbaar of staat in een ander stelsel."""
