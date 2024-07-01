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
        [filt.write(x + "\n") for x in subset]

    return os.path.join(ref_data, "filt.txt")


def test_duplicate_fraposa(ref_data, filt_id):
    args = ['fraposa', "--stu_filepref", "dup_test", "dup_test", "--stu_filt_iid", filt_id]
    with pytest.raises(ValueError) as excinfo:
        with patch('sys.argv', args):
            cwd = os.getcwd()
            os.chdir(ref_data)
            main()
            os.chdir(cwd)

    assert "Duplicated sample IIDs detected" in str(excinfo.value)


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


def _fraposa_finished(ref_data):
    fn = ref_data / "example_comm.log"
    with open(fn, 'r') as f:
        if 'FRAPOSA finished' in f.read():
            return True
        else:
            return False


def _expected_outputs(ref_data):
    outputs = ["thousand_comm_U.dat",
               "thousand_comm_V.dat",
               "thousand_comm_mnsd.dat",
               "thousand_comm_s.dat",
               "thousand_comm_vars.dat",
               "thousand_comm.pcs",
               "example_comm.pcs"]
    return [ref_data / x for x in outputs]


def _output_exists(ref_data):
    fns = _expected_outputs(ref_data)
    return all([x.exists() for x in fns])
