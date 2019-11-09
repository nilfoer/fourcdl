import pytest
import os
import time
import shutil
import logging
import urllib.request

from utils import *
from fourcdl.download import download_with_retries_crc, download_thread
from fourcdl.gen_downloaded_files_info import add_file_to_files_info

@pytest.fixture
def setup_thread_for_download(setup_tmpdir):
    tmpdir = setup_tmpdir
    dl_thread_files_path = os.path.join(TESTS_DIR, "dl_thread_files")
    # only needed to do this ONCE now we can just import from import_e.json
    # better to leave it since it only works if the file path of the test files doesnt change
    state_dict = import_json(os.path.join(dl_thread_files_path, "import.json"))
    to_dl, successful_dl_threads = state_dict["dl_multiple_threads"]
    thread, dl_list = to_dl[0]


    b64_of_files_to_dl = set()
    # change file_urls to use file:///
    for k, post_dict in thread.items():
        if k == "OP":
            continue

        file_info_d = post_dict["file_info"]
        # file_info_d can be None
        if file_info_d and file_info_d["to_download"]:
            # CAREFUL download thread doesnt use file_url it uses normal url and prepends https:
            file_info_d["file_url"] = "file:" + urllib.request.pathname2url(os.path.join(dl_thread_files_path,
                f"{file_info_d['dl_filename']}.{file_info_d['file_ext']}"))
            # add md5b64 to later remove them from files info dict since they were added when being downloaded
            b64_of_files_to_dl.add(file_info_d["file_md5_b64"])

    # copy root md5 file
    shutil.copy2(os.path.join(dl_thread_files_path, "4chan_dl.md5"), os.path.join(tmpdir))

    files_info_dict = import_pickle(os.path.join(dl_thread_files_path, "downloaded_files_info_before.pickle"))


    return tmpdir, dl_thread_files_path, thread, dl_list, files_info_dict

    

def test_download_thread(setup_thread_for_download, monkeypatch):
    tmpdir, dl_thread_files_path, thread, dl_list, files_info_dict = setup_thread_for_download
    # just return file_url
    monkeypatch.setattr("fourcdl.download.build_url_to_file", lambda x: x)

    # test every time root md5 and export txt being correct
    # test with one or 2 failed md5s -> check if reported correctly and that havent been added to files_info_dict
    # fail md5 on: 1521372891045_failed_md5
    # test dl fail -> not added to export txt, md5 and files_info_dict
    # on 1521370213050_dl_fail should work by just changing file url since were expceping URLError in download
    thread["v/1521370213050.png"]["file_info"]["file_url"] = "file:" + urllib.request.pathname2url(
            os.path.join(dl_thread_files_path, "file_not_found.jpg"))

    failed_md5 = download_thread(thread, dl_list, files_info_dict, root_dir = tmpdir)
    

    # would take too long to test this seperately so have failed md5s from start
    # only test dl fail seperately since thats quick
    assert(len(failed_md5) == 1)
    # check if files were downloaded/failed and have correct names
    for url in dl_list:
        fn = thread[url]["file_info"]["dl_filename"] + "." + thread[url]["file_info"]["file_ext"]
        isfile = os.path.isfile(os.path.join(tmpdir, "dl_thread_files", fn))

        if url == "v/1521370213050.png":
            # make sure file that had faulty url wasnt downloaded
            assert(not isfile)
        else:
            assert(isfile)

    # vars apparently not allowed to start with numbers
    fchan_dl_md5 = read_file(os.path.join(tmpdir, "4chan_dl.md5"))
    fchan_dl_md5_expected = read_file(os.path.join(dl_thread_files_path, "4chan_dl_after.md5"))
    # we watn download_thread to write wrong md5 (that is in json/thread) to root md5
    # since replacing/deleting is handled by user_handle_failed_md5
    # actual 1369ca2839a2fc8c1bbb11e09f8856e1 *1521372891045_failed_md5.jpg
    # thread 1369ca2839a2fc8c1bbb11e09f88567d <- this should be in root md5
    assert(fchan_dl_md5 == fchan_dl_md5_expected)

    export_txt = read_file(os.path.join(tmpdir, "dl_thread_files", 
        f"dl_thread_files_{time.strftime('%Y-%m-%d')}.txt"))
    export_txt_expected = read_file(os.path.join(dl_thread_files_path, "dl_thread_files_2018-03-18.txt"))
    assert(export_txt == export_txt_expected)

    # CAREFUL
    # downloaded_files_info.pickle only gets written when fourcdl is called as script
    # just use reference that we still have
    files_info_dict_actual = files_info_dict
    files_info_dict_expected = import_pickle(os.path.join(dl_thread_files_path, 
        "downloaded_files_info_after.pickle"))
    assert(files_info_dict_actual == files_info_dict_expected)


def test_download_with_retries_crc(setup_tmpdir, caplog, monkeypatch):
    caplog.set_level(logging.DEBUG)
    tmpdir = setup_tmpdir
    # print below works when: import fourcdl.fourcdl
    # print(fourcdl.fourcdl.download)
    dl_path = os.path.join(tmpdir, "test.download")

    # to dl file with urlretrieve i need to prepend file:/// (was only using 2 slashe b4 -> didnt work)
    # -> now i dont need to monkey patch download for these tests
    # def dl_local(src, dst):
    #     shutil.copy2(src, dst)
    #     return True, {}
    # monkeypatch.setattr("fourcdl.fourcdl.download", dl_local)
    # convert windows path C:\\blabla\\file.txt to url like C:/blabla/file.txt with pathname2url
    file_to_dl = "file:" + urllib.request.pathname2url(os.path.join(TESTS_DIR, "download_with_retries_files", "1521370139210.png"))
    # correct md5b64 gUkUw0o1n7cI+w0x8LWj2w==
    dl_success, md5_match, headers = download_with_retries_crc(file_to_dl, dl_path, "gUkUw0o1n7cI+w0x8LWj2w==")
    assert(dl_success)
    assert(md5_match)
    # test logging output
    assert caplog.record_tuples == [
        ('fourcdl.crc', logging.DEBUG, 'MD5-Check   "test.download" OK'),
    ]
    # clear logging records
    caplog.clear()

    # test with wrong md5
    dl_success, md5_match, headers = download_with_retries_crc(file_to_dl, dl_path, "gUkUw0o1n7cI+w0x8LWjff==")
    assert(dl_success)
    assert(not md5_match)
    assert caplog.record_tuples == [
        ('fourcdl.crc', logging.WARNING, 'MD5-Check   "test.download" FAILED'),
        ('fourcdl.download', logging.WARNING, 'Download failed: either md5 didnt match or there were connection problems! -> Retrying!'),
        ('fourcdl.crc', logging.WARNING, 'MD5-Check   "test.download" FAILED'),
    ]
    caplog.clear()

    # download now always returns False
    monkeypatch.setattr("fourcdl.download.download", lambda x,y: (False, {}))

    dl_success, md5_match, headers = download_with_retries_crc(file_to_dl, dl_path, "gUkUw0o1n7cI+w0x8LWjff==")
    assert(not dl_success)
    assert(md5_match is None)
    assert caplog.record_tuples == [
        ('fourcdl.download', logging.WARNING, 'Download failed: either md5 didnt match or there were connection problems! -> Retrying!'),
    ]

    caplog.clear()
    # 2 retries
    dl_success, md5_match, headers = download_with_retries_crc(file_to_dl, dl_path, "gUkUw0o1n7cI+w0x8LWjff==", retries=2)
    assert(not dl_success)
    assert(md5_match is None)
    assert caplog.record_tuples == [
        ('fourcdl.download', logging.WARNING, 'Download failed: either md5 didnt match or there were connection problems! -> Retrying!'),
        ('fourcdl.download', logging.WARNING, 'Download failed: either md5 didnt match or there were connection problems! -> Retrying!')
    ]
