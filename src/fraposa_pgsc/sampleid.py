from dataclasses import dataclass


@dataclass(frozen=True)
class SampleID:
    """ A sample ID from a plink fam/psam file, including FID and IID """
    FID: str
    IID: str
