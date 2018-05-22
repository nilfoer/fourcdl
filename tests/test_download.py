import pytest
import os
import time
import shutil
import logging
import urllib.request

from utils import *
from fourchandl.fourchandl import download_with_retries_crc, download_thread
from fourchandl.gen_downloaded_files_info import add_file_to_files_info

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

    # copy downloaded_files_info
    shutil.copy2(os.path.join(dl_thread_files_path, "downloaded_files_info_before.pickle"),
            os.path.join(tmpdir, "downloaded_files_info.pickle"))
    files_info_dict = import_pickle(os.path.join(tmpdir, "downloaded_files_info.pickle"))

    # only needed to do this once to get .pickle then we can import
    # # load files_info_dict
    # files_info_dict = import_pickle(os.path.join(dl_thread_files_path, "downloaded_files_info.pickle"))
    # # files are alrdy in this dict -> remove them
    # # i could also convert the size and get the ext when iterating over thread to chang file_urls
    # # but just to make sure theyre not in there -> remove them this expensive way
    # for ext in ("jpg", "png"):
    #     # accessing dict with d[key] causes key to be hashed to access value
    #     # -> for large dicts ...
    #     ext_d = files_info_dict[ext]
    #     for md5_d in ext_d.values():
    #         # remove all b64str that belong to the files we want download_thread to dl
    #         md5_d = md5_d - b64_of_files_to_dl

    # export_pickle(files_info_dict, os.path.join(dl_thread_files_path, "downloaded_files_info_before.pickle"))

    # code for "manually" adding the correct files to files_info_dict
    # only needed once since then we can import the pickle, same for above (removing files)
    # for url in dl_list:
    #     if url in ("//i.4cdn.org/v/1521370213050.png", "//i.4cdn.org/v/1521372891045.jpg"):
    #         continue

    #     fd = thread[url]["file_info"]
    #     f_type = fd["file_ext"]
    #     size_bytes = os.path.getsize(os.path.join(dl_thread_files_path, 
    #         f"{fd['dl_filename']}.{f_type}"))
    #     md5_b64 = fd["file_md5_b64"]
    #     add_file_to_files_info(files_info_dict, f_type, size_bytes, md5_b64)
    # export_pickle(files_info_dict, os.path.join(dl_thread_files_path, "downloaded_files_info_after.pickle"))


    return tmpdir, dl_thread_files_path, thread, dl_list, files_info_dict

    

def test_download_thread(setup_thread_for_download, monkeypatch):
    tmpdir, dl_thread_files_path, thread, dl_list, files_info_dict = setup_thread_for_download
    # just return file_url
    monkeypatch.setattr("fourchandl.fourchandl.build_url_to_file", lambda x: x)

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

    files_info_dict_actual = import_pickle(os.path.join(tmpdir, "downloaded_files_info.pickle"))
    files_info_dict_expected = import_pickle(os.path.join(dl_thread_files_path, 
        "downloaded_files_info_after.pickle"))
    assert(files_info_dict_actual == files_info_dict_expected)


def test_download_with_retries_crc(setup_tmpdir, caplog, monkeypatch):
    caplog.set_level(logging.DEBUG)
    tmpdir = setup_tmpdir
    # print below works when: import fourchandl.fourchandl
    # print(fourchandl.fourchandl.download)
    dl_path = os.path.join(tmpdir, "test.download")

    # to dl file with urlretrieve i need to prepend file:/// (was only using 2 slashe b4 -> didnt work)
    # -> now i dont need to monkey patch download for these tests
    # def dl_local(src, dst):
    #     shutil.copy2(src, dst)
    #     return True, {}
    # monkeypatch.setattr("fourchandl.fourchandl.download", dl_local)
    # convert windows path C:\\blabla\\file.txt to url like C:/blabla/file.txt with pathname2url
    file_to_dl = "file:" + urllib.request.pathname2url(os.path.join(TESTS_DIR, "download_with_retries_files", "1521370139210.png"))
    # correct md5b64 gUkUw0o1n7cI+w0x8LWj2w==
    dl_success, md5_match, headers = download_with_retries_crc(file_to_dl, dl_path, "gUkUw0o1n7cI+w0x8LWj2w==")
    assert(dl_success)
    assert(md5_match)
    # test logging output
    assert caplog.record_tuples == [
        ('fourchandl.crc', logging.DEBUG, 'CRC-Checking file "test.download"!'),
        ('fourchandl.crc', logging.DEBUG, 'MD5-Check   "test.download" OK'),
    ]
    # clear logging records
    caplog.clear()

    # test with wrong md5
    dl_success, md5_match, headers = download_with_retries_crc(file_to_dl, dl_path, "gUkUw0o1n7cI+w0x8LWjff==")
    assert(dl_success)
    assert(not md5_match)
    assert caplog.record_tuples == [
        ('fourchandl.crc', logging.DEBUG, 'CRC-Checking file "test.download"!'),
        ('fourchandl.crc', logging.WARNING, 'MD5-Check   "test.download" FAILED'),
        ('fourchandl.fourchandl', logging.WARNING, 'Download failed: either md5 didnt match or there were connection problems! -> Retrying!'),
        ('fourchandl.crc', logging.DEBUG, 'CRC-Checking file "test.download"!'),
        ('fourchandl.crc', logging.WARNING, 'MD5-Check   "test.download" FAILED'),
    ]
    caplog.clear()

    # download now always returns False
    monkeypatch.setattr("fourchandl.fourchandl.download", lambda x,y: (False, {}))

    dl_success, md5_match, headers = download_with_retries_crc(file_to_dl, dl_path, "gUkUw0o1n7cI+w0x8LWjff==")
    assert(not dl_success)
    assert(md5_match is None)
    assert caplog.record_tuples == [
        ('fourchandl.fourchandl', logging.WARNING, 'Download failed: either md5 didnt match or there were connection problems! -> Retrying!'),
    ]

    caplog.clear()
    # 2 retries
    dl_success, md5_match, headers = download_with_retries_crc(file_to_dl, dl_path, "gUkUw0o1n7cI+w0x8LWjff==", retries=2)
    assert(not dl_success)
    assert(md5_match is None)
    assert caplog.record_tuples == [
        ('fourchandl.fourchandl', logging.WARNING, 'Download failed: either md5 didnt match or there were connection problems! -> Retrying!'),
        ('fourchandl.fourchandl', logging.WARNING, 'Download failed: either md5 didnt match or there were connection problems! -> Retrying!')
    ]
