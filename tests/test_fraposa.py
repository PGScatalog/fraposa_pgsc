import os
from distutils.dir_util import copy_tree
from unittest.mock import patch

import pytest

from fraposa_pgsc.fraposa_runner import main


@pytest.fixture(scope="session")
def ref_data(tmp_path_factory):
    fn = tmp_path_factory.mktemp("data")
    copy_tree("tests/data/", str(fn))
    return fn.resolve()


def test_fraposa(ref_data):
    args: list[str] = ['fraposa', "--stu_filepref", "example_comm", "thousand_comm"]

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
