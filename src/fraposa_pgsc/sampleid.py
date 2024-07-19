class SampleID:
    """ A sample ID from a plink fam file, including FID and IID """
    def __init__(self, fid, iid):
        self._fid = fid
        self._iid = iid

    def __repr__(self):
        return f"{self.__class__.__name__}(fid={repr(self.fid)}, iid={repr(self.iid)})"

    @property
    def fid(self):
        if self._fid == "0":  # 0 means missing :)
            return self._iid
        else:
            return self._fid

    @property
    def iid(self):
        return self._iid

    def __hash__(self):
        return hash((self.fid, self.iid))

    def __eq__(self, other):
        if not isinstance(other, SampleID):
            return NotImplemented

        return self.fid == other.fid and self.iid == other.iid
