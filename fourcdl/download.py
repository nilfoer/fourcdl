import os
import time
import urllib.request
import logging

from fourcdl.crc import check_4chfile_crc, append_to_md5_file
from fourcdl.gen_downloaded_files_info import add_file_to_files_info
from fourcdl.thread import get_key_from_furl, build_export_str
from fourcdl.utils import append_to_file, sanitize_fn, UnexpectedCrash
logger = logging.getLogger(__name__)


def download(url, dl_path):
    """
    Will download the file to dl_path, return True on success

    :param curfnr: Current file number
    :param maxfnr: Max files to download
    :return: Current file nr(int)
    """
    # get head (everythin b4 last part of path ("/" last -> tail empty, filename or dir(without /) -> tail)) of path; no slash in path -> head empty
    dirpath, fn = os.path.split(dl_path)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)

    try:
        _, headers = urllib.request.urlretrieve(url, dl_path)  # reporthook=prog_bar_dl)
    except urllib.request.HTTPError as err:
        # catch this more detailed first then broader one (HTTPError is subclass of URLError)
        logger.warning("HTTP Error %s: %s: \"%s\"", err.code, err.reason, url)
        return False, None
    except urllib.request.URLError as err:
        logger.warning("URL Error %s: \"%s\"", err.reason, url)
        return False, None
    else:
        return True, headers


def download_in_chunks(url, filename):
    # get head (everythin b4 last part of path ("/" last -> tail empty, filename or dir(without /) -> tail)) of path; no slash in path -> head empty
    dirpath, fn = os.path.split(filename)
    if dirpath:
        os.makedirs(dirpath, exist_ok=True)

    # urlretrieve uses block-size of 8192
    # Before response.read() is called, the contents are not downloaded.
    with urllib.request.urlopen(url) as response:
        meta = response.info()
        reported_file_size = int(meta["Content-Length"])
        # by Alex Martelli
        # Experiment a bit with various CHUNK sizes to find the "sweet spot" for your requirements
        # CHUNK = 16 * 1024
        file_size_dl = 0
        chunk_size = 8192
        with open(filename, 'wb') as w:
            while True:
                chunk = response.read(chunk_size)
                if not chunk:
                    break

                # not chunk_size since the last chunk will probably not be of size chunk_size
                file_size_dl += len(chunk)
                w.write(chunk)

    # from urlretrieve doc: urlretrieve() will raise ContentTooShortError when it detects that the amount of data available was less than the expected amount (which is the size reported by a Content-Length header). This can occur, for example, when the download is interrupted.
    # The Content-Length is treated as a lower bound: if there’s more data to read, urlretrieve reads more data, but if less data is available, it raises the exception.
    if file_size_dl < reported_file_size:
        logger.warning("Downloaded file's size is samller than the reported size for "
                       "\"%s\"", url)
        return False, file_size_dl
    else:
        return True, file_size_dl


def download_with_retries_crc(url, dl_path, md5_b64, retries=1):
    dl_success = None
    md5_match = None
    n = 0
    # both dl_.. md5_.. None -> we didnt try dling yet or n <= retries -> were still in our range of allowed retries
    # but keep trying till we reach retries since md5 has to match
    while ((md5_match is None and dl_success is None) or n <= retries) and md5_match is not True:
        if md5_match is not None or dl_success is not None:
            logger.warning("Download failed: either md5 didnt match or there were connection problems! -> Retrying!")

        dl_success, headers = download(url, dl_path)
        if dl_success:
            md5_match = check_4chfile_crc(dl_path, md5_b64)
        n += 1

    return dl_success, md5_match, headers


# build url to file so we dont use the specified server in the file_url
# but the faster i.4cdn.org
def build_url_to_file(file_url, server="i.4cdn.org"):
    return f"https://{server}/{get_key_from_furl(file_url)}"


def get_url_file_size(url):
    """Returns file size in bytes that is reported in Content-Length Header"""
    with urllib.request.urlopen(url) as response:
        reported_file_size = int(response.info()["Content-Length"])
    return reported_file_size


RETRIES = 1
def download_4chan_file_url(url, dl_path, file_dict, files_info_dict, thread,
                            overwrite=False, retries=RETRIES):
    dl_success, md5_match = None, None

    file_loc = os.path.join(thread["OP"]["folder_name"],
                            f"{file_dict['dl_filename']}.{file_dict['file_ext']}")

    if not os.path.isfile(dl_path) or overwrite:
        dl_success, md5_match, headers = download_with_retries_crc(url, dl_path, 
                file_dict["file_md5_b64"], retries=retries)

        # WARNING only added if md5_match even if we decide to keep the file
        # removing md5_b64 later from files_info_dict also wouldnt work since we might have downloaded
        # that file before then removing it would be wrong
        if dl_success and md5_match:
            add_file_to_files_info(files_info_dict, file_dict["file_ext"], 
                    int(headers["Content-Length"]), file_dict["file_md5_b64"],
                    file_loc)
        else:
            logger.warning("Download of %s failed after %s tries - File was skipped!", url, 
                    retries+1)
    else:
        logger.warning("File already exists, url \"%s\" has been skipped!", url)

    return dl_success, md5_match


def download_thread(thread, dl_list, files_info_dict, root_dir, overwrite=False):
    # keep list of successful dls so we only export those in export str
    success_dl = []
    logger.info("Downloading thread No. %s: \"%s\"", thread["OP"]["thread_nr"], thread["OP"]["subject"])
    thread_folder_name = thread["OP"]["folder_name"]
    thread_folder = os.path.join(root_dir, thread_folder_name)
    nr_files_thread = len(dl_list)
    cur_nr = 1
    failed_md5 = []
    for url in dl_list:
        file_dict = thread[url]["file_info"]
        dl_path = os.path.join(thread_folder, f"{file_dict['dl_filename']}.{file_dict['file_ext']}")
        # TODO(moe): when downloading from better server fails, try the one in file_url
        # file_url = file_dict["file_url"]
        # have to derive url from file_url in dict otherwise we lose ability
        # to use local file:/// urls for tests, and i wanna get rid of dl_list eventually
        file_url = build_url_to_file(file_dict["file_url"])

        logger.info("Downloading: \"%s\", File %s of %s", url, cur_nr, nr_files_thread)
        try:
            dl_success, md5_match = download_4chan_file_url(file_url, dl_path, file_dict,
                                                            files_info_dict, thread,
                                                            overwrite=overwrite)

            if dl_success:
                # we even keep files with failed md5 -> user hast to check them manually first if theyre worth keeping or useless
                success_dl.append(url)
                if not md5_match:
                    failed_md5.append(url)
            cur_nr += 1

        except Exception as e:
            raise UnexpectedCrash("download_thread", (thread, dl_list), "Unexpected crash while downloading! Program state has been saved, start script with option resume to continue with old state!").with_traceback(e.__traceback__)

    if failed_md5:
        thread["failed_md5"] = failed_md5
        logger.warning("There were the following files with failed CRC-Checks in Thread No. %s: \"%s\"\n%s",
                       thread["OP"]["thread_nr"], thread["OP"]["subject"], "\n".join(thread["failed_md5"]))
    else:
        logger.info("CRC-Check successful!")


    # build exp str and append (so we dont overwrite) to txt file
    exp_str = build_export_str(thread, success_dl)
    # sanitize thread_folder_name so it wont throw an exception when it includes a subdir
    # e.g. gif_model/Emily Rudd_TIME.txt -> tries to write to Emily Rudd_TIME.txt in subfolder gif_model of folder gif_model
    sanitized_folder_name = sanitize_fn(thread_folder_name)

    exp_txt_filename = f"{sanitized_folder_name}_{time.strftime('%Y-%m-%d')}.txt"
    logger.info("Writing thread export file \"%s\"", exp_txt_filename)
    append_to_file(exp_str, os.path.join(thread_folder, exp_txt_filename))

    # append md5 of downloaded files to md5 file in cwd (old: named thread_folder_name.md5)
    append_to_md5_file(thread, success_dl, root_dir)  #, thread_folder, sanitized_folder_name)

    return failed_md5
