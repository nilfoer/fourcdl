import pytest
import os
import logging
import urllib.request

from utils import *
from fourchandl.fourchandl import download_with_retries_crc

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
