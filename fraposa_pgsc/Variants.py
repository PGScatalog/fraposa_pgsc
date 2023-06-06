from dataclasses import dataclass
from enum import Enum


class MatchType(Enum):
    # the study variants and reference variants intersect perfectly and are in the same order
    ORDERED = 0
    # the study variants and reference variants intersect perfectly but are not in the same order
    DIFFERENT_ORDER = 1
    # enums below will cause fraposa to explode and terminate ASAP
    DIFFERENT_SIZE = 2
    DIFFERENT_ID = 3


@dataclass
class Variants:
    """
    A class containing variant information that guarantees variant order is the same across reference and study
    variants when the object is instantiated.
    """
    reference_variants: list[str]
    study_variants: list[str]
    match_type: MatchType
    # study_indexes: the order that reference variants appeared in the study variant list
    # used to re-index study genotypes to match the ordered study variants
    study_indexes: list[int]

    def __repr__(self):
        attrs = ["Variants object, containing:",
                 f"Reference variants: {self.reference_variants[0]}, ...",
                 f"Study variants: {self.study_variants[0]}, ...",
                 f"Match type: {self.match_type}",
                 f"Study indexes: {next(iter(self.study_indexes))}, ..."]
        return "\n".join(attrs).strip("\n")

    def __post_init__(self):
        assert self.reference_variants == self.study_variants
