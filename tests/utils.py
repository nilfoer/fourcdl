import pytest
import os
import shutil
import json


TESTS_DIR = os.path.dirname(os.path.realpath(__file__))

def read_file(fn):
    with open(fn, "r", encoding="UTF-8") as f:
        return f.read()


def write_file_str(fn, s):
    with open(fn, "w", encoding="UTF-8") as w:
        w.write(s)


def import_json(fn):
    json_str = read_file(fn)
    return json.loads(json_str)


def export_json(fn, obj):
    json_str = json.dumps(files_info, indent=4, sort_keys=True)
    write_file_str(fn, json_str)
    
@pytest.fixture
def setup_tmpdir():
    tmpdir = os.path.join(TESTS_DIR, "tmp")
    os.makedirs(tmpdir)

    yield tmpdir
    # del dir and contents after test is done
    shutil.rmtree(tmpdir)
