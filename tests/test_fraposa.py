import csv
import os
import shutil
from unittest.mock import patch

import pandas as pd
import pytest

from fraposa_pgsc.fraposa_runner import main


@pytest.fixture(scope="session")
def ref_data(tmp_path_factory):
    fn = tmp_path_factory.mktemp("data")
    shutil.copytree("tests/data/", str(fn), dirs_exist_ok=True)
    return fn.resolve()


@pytest.fixture(scope="session")
def filt_id(ref_data):
    df = pd.read_table(os.path.join(ref_data, "example_comm.fam"), header=None)
    subset: list[str] = df[0].to_list()[:100]
    with open(os.path.join(ref_data, "filt.txt"), "w") as filt:
        # fake bim format: FID \t IID \t ...
        [filt.write(x + "\t" + x + "\n") for x in subset]

    return os.path.join(ref_data, "filt.txt")


@pytest.fixture
def duplicate_fid(ref_data, tmp_path_factory):
    fn = tmp_path_factory.mktemp("baddata")
    shutil.copytree("tests/data", str(fn), dirs_exist_ok=True)
    with open(fn / "dup_test.fam", "rt") as f:
        lines = list(csv.reader(f, delimiter="\t"))

    for x in lines:
        # reset FIDs so they share duplicated IDs
        x[0] = "samp001"

    with open(fn / "dup_test.fam", "wt") as f:
        csv.writer(f, delimiter="\t").writerows(lines)

    return fn.resolve()


def test_bad_duplicate_fraposa(duplicate_fid, filt_id):
    """ Duplicate IIDs will fail if they're duplicated in an FID too """
    args = ['fraposa', "--stu_filepref", "dup_test", "thousand_comm", "--stu_filt_iid", filt_id]
    with pytest.raises(ValueError) as excinfo:
        with patch('sys.argv', args):
            cwd = os.getcwd()
            os.chdir(duplicate_fid)
            main()
            os.chdir(cwd)

    assert "duplicated FID + IID" in str(excinfo.value)


def test_duplicate_fraposa(ref_data, filt_id):
    """ Duplicate IIDs will pass if FIDs are distinct """
    args = ['fraposa', "--stu_filepref", "dup_test", "thousand_comm", "--stu_filt_iid", filt_id]
    with patch('sys.argv', args):
        cwd = os.getcwd()
        os.chdir(ref_data)
        main()
        os.chdir(cwd)

    assert _fraposa_finished(ref_data, stu_prefix="dup_test"), "FRAPOSA did not finish in log"
    assert _output_exists(ref_data, stu_prefix="dup_test"), "Missing output files"


@pytest.mark.parametrize("args", [
    ['fraposa', "--stu_filepref", "example_comm", "thousand_comm"],
    ['fraposa', "--stu_filepref", "example_comm", "thousand_comm", "--stu_filt_iid", "filt.txt"]
])
def test_fraposa(ref_data, filt_id, args):
    with patch('sys.argv', args):
        cwd = os.getcwd()
        os.chdir(ref_data)
        main()
        os.chdir(cwd)

    assert _fraposa_finished(ref_data), "FRAPOSA did not finish in log"
    assert _output_exists(ref_data), "Missing output files"


def _fraposa_finished(ref_data, stu_prefix="example_comm"):
    fn = ref_data / f"{stu_prefix}.log"
    with open(fn, 'r') as f:
        if 'FRAPOSA finished' in f.read():
            return True
        else:
            return False


def _expected_outputs(ref_data, stu_prefix="example_comm"):
    outputs = ["thousand_comm_U.dat",
               "thousand_comm_V.dat",
               "thousand_comm_mnsd.dat",
               "thousand_comm_s.dat",
               "thousand_comm_vars.dat",
               "thousand_comm.pcs",
               f"{stu_prefix}.pcs"]
    return [ref_data / x for x in outputs]


def _output_exists(ref_data, stu_prefix="example_comm"):
    fns = _expected_outputs(ref_data, stu_prefix)
    return all([x.exists() for x in fns])
