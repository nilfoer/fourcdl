import pytest
import os
import shutil

from utils import *
from fourchandl.crc import md5
from fourchandl.fourchandl import user_handle_failed_md5


@pytest.fixture
def setup_thread_for_handled_failed_md5():
    # create tmp dir myself since pytest fixture tmpdir usees weird tmpdir.mkdir("..") methods
    # and it will be created in tmp dir loc of system which i also dont want (and not immediately deleted as well!!)
    tmpdir = os.path.join(TESTS_DIR, "temp_test_failed_md5")
    os.makedirs(tmpdir)
    failed_md5_files_path = os.path.join(TESTS_DIR, "failed_md5_files")
    state_dict = import_json(os.path.join(failed_md5_files_path, "crash-exp.json"))
    to_dl, successful_dl_threads = state_dict["dl_multiple_threads"]
    thread, dl_list = to_dl[0]
    # fourchandl now uses https://.. as key but these tests are still valid since
    # the json still uses these all over and nothing gets dled here
    thread["failed_md5"] = ["//i.4cdn.org/v/1521370213050.png", "//i.4cdn.org/v/1521370986708.jpg",
            "//i.4cdn.org/v/1521372959414.png"]

    # use "" as last join to make sure tmpdir_failed_md5 ends in os.sep so it gets treated as 
    # dir path and not as file path -> copy2 used it as filename before (but only when dir didnt exist yet -> worked when dir existed)
    tmpdir_failed_md5 = os.path.join(tmpdir, "failed_md5_files", "")
    # need to create path for shutil copy2
    os.makedirs(tmpdir_failed_md5)
    # set up root_dir and subdir with files
    for fn in os.listdir(failed_md5_files_path):
        if fn.endswith(".md5"):
            shutil.copy2(os.path.join(failed_md5_files_path, fn), tmpdir)
            continue
        elif fn.rsplit(".",1)[-1] not in ("jpg", "png", "gif", "webm"):
            continue
        shutil.copy2(os.path.join(failed_md5_files_path, fn), tmpdir_failed_md5)

    yield thread, tmpdir, tmpdir_failed_md5
    # code after yield runs after test
    shutil.rmtree(tmpdir)


def test_user_handle_failed_md5(setup_thread_for_handled_failed_md5, monkeypatch):
    thread, tmpdir, tmpdir_failed_md5 = setup_thread_for_handled_failed_md5

    # As The Compiler suggested, pytest has a new monkeypatch fixture for this. A monkeypatch object can alter an attribute in a class or a value in a dictionary, and then restore its original value at the end of the test.
    # In this case, the built-in input function is a value of python's __builtins__ dictionary, so we can alter it like so:
    # monkeypatch the "input" function, so that it returns "0,2".
    # This simulates the user entering "0,2" in the terminal:
    monkeypatch.setattr('builtins.input', lambda x: "0,2")

    user_handle_failed_md5(thread, thread["failed_md5"], tmpdir)


    for fn in [fn for fn in os.listdir(os.path.join(TESTS_DIR, "failed_md5_files")) if fn.rsplit()[-1] in ("jpg", "png", "gif")]:
        if "_del" in fn:
            assert(not os.path.isfile(os.path.join(tmpdir_failed_md5, fn)))
        else:
            assert(os.path.isfile(os.path.join(tmpdir_failed_md5, fn)))

    # since i edited the md5 b64 str in the json to not match the downloaded files these shouldnt
    # the actual md5s
    kept_failed_md5 = read_file(os.path.join(tmpdir, "kept_failed_md5_files.md5"))
    kept_failed_md5_expected = "d388569ddf18ee0f2bf542140126fe7d *failed_md5_files/1521370213050_failed_keep.png\n59698bb6bf4bb9b2918247ea8738157d *failed_md5_files/1521372959414_failed_keep.png\n"
    assert(kept_failed_md5 == kept_failed_md5_expected)

    root_md5_file = read_file(os.path.join(tmpdir, "4chan_dl.md5"))
    root_md5_file_expected = "554a3ef2da2ba6edd7ab5c1d6b533ee6 *g_tw/1520537586480.webm\n13c9f8bb29bae0a7c21e1f0f53121bf4 *g_tw/1520534816168.webm\neee268e8c0e2993a146f9162fe1c0892 *g_tw/1520556227609.webm\na4f099b0a61e4837c235c550e65d8cb6 *g_tw/1520461949084.webm\nf8bee6cab2236a3281fc3898ed31bb9d *g_tw/1520557864639.webm\n9a59e1417d2f00b7a1f1df6d3a00b810 *g_tw/1520562505142.webm\n1837e99f815a7dabf2e7e0a8c976c4a1 *g_tw/1520620298548.webm\neb2842e6b13e13ddc4758d4e05a5c1ee *g_tw/1520558881500.webm\nb30f5a2490ace196f5e99f10e6b9b50f *g_tw/1520620029765.webm\nd388569ddf18ee0f2bf542140126fe9a *failed_md5_files/1521370213050_failed_keep.png\n1369ca2839a2fc8c1bbb11e09f8856e1 *failed_md5_files/1521372891045.jpg\n967de5dd8439da03725e6bfa645cbcb0 *failed_md5_files/1521370944283.jpg\n59698bb6bf4bb9b2918247ea87381545 *failed_md5_files/1521372959414_failed_keep.png\n814914c34a359fb708fb0d31f0b5a3db *failed_md5_files/1521370139210.png\n"
    print(repr(root_md5_file))
    assert(root_md5_file == root_md5_file_expected)

    for ln in root_md5_file.splitlines():
        # test keep files md5 and one additional to make sure user_handle_failed_md5 didnt screw up
        # integrity of root_md5_file
        if not "_keep" in ln or not "1521370944283.jpg" in ln:
            continue
        md5hex, fpath = ln.split(" *")
        assert(md5(os.path.join(tmpdir, fpath)) == md5hex)

    


