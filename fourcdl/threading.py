import os
import time
import logging
from threading import Thread, current_thread
from queue import Queue

from fourcdl.gen_downloaded_files_info import add_file_to_files_info
from fourcdl.download import download_with_retries_crc, build_url_to_file
from fourcdl.crc import append_to_md5_file
from fourcdl.thread import build_export_str
from fourcdl.utils import append_to_file, sanitize_fn

logger = logging.getLogger(__name__)

NUMBER_OF_THREADS = 3
DL_WORKER_SLEEP = 1

RETRIES = 1
def download_4chan_file_url_threaded(dl_queue, downloaded_queue, nr_files_thread):
    thread_name = current_thread().name
    while True:
        # will block on the statement .get() until the queue has something to return, so it
        # is safe to start the threads before there is anything in the queue
        i, url, dl_path, file_dict, thread, overwrite = dl_queue.get()
        if i is None:
            # stop signal
            break

        dl_success, md5_match = None, None
        # TODO(moe): when downloading from better server fails, try the one in file_url
        # file_url = file_dict["file_url"]
        # have to derive url from file_url in dict otherwise we lose ability
        # to use local file:/// urls for tests, and i wanna get rid of dl_list eventually
        file_url = build_url_to_file(file_dict["file_url"])
        file_loc = os.path.join(thread["OP"]["folder_name"],
                                f"{file_dict['dl_filename']}.{file_dict['file_ext']}")

        if not os.path.isfile(dl_path) or overwrite:
            logger.info("%s: Downloading: \"%s\", File %s of %s", thread_name, file_url, i, nr_files_thread)
            dl_success, md5_match, headers = download_with_retries_crc(file_url, dl_path,
                                                                       file_dict["file_md5_b64"],
                                                                       retries=RETRIES)
            # download_thread_threaded needs normal url to access file_dict from thread
            # otherwise we get a key error
            # url: aco/1567501767995.jpg file_url: https://i.4cdn.org/aco/1567501767995.jpg
            downloaded_queue.put((url, dl_success, md5_match, int(headers["Content-Length"]), file_loc))
            if not dl_success:
                logger.warning("Download of %s failed after %s tries - File was skipped!", url, RETRIES+1)

        else:
            logger.warning("File already exists, url \"%s\" has been skipped!", url)
            # still put a task in the downloaded_queue so nr of processed items match
            # which is needed to properly terminate the threads
            downloaded_queue.put((url, dl_success, md5_match, None, file_loc))
        dl_queue.task_done()
        time.sleep(DL_WORKER_SLEEP)


def download_thread_threaded(thread, dl_list, files_info_dict, root_dir, overwrite=False):
    logger.info("Downloading thread No. %s: \"%s\"", thread["OP"]["thread_nr"], thread["OP"]["subject"])
    thread_folder_name = thread["OP"]["folder_name"]
    thread_folder = os.path.join(root_dir, thread_folder_name)
    nr_files_thread = len(dl_list)
    failed_md5 = []
    dl_queue = Queue()
    downloaded_queue = Queue()
    print("** Queueing downloads! **")
    for i, url in enumerate(dl_list):
        file_dict = thread[url]["file_info"]
        dl_path = os.path.join(thread_folder, f"{file_dict['dl_filename']}.{file_dict['file_ext']}")

        dl_queue.put((i+1, url, dl_path, file_dict, thread, overwrite))

    print("** Starting DL jobs! **")
    dl_threads = []
    for i in range(NUMBER_OF_THREADS):
        t = Thread(
                name=f"DL-Worker {i}", target=download_4chan_file_url_threaded,
                args=(dl_queue, downloaded_queue, nr_files_thread)
                )
        dl_threads.append(t)
        t.start()

    # keep list of successful dls so we only export those in export str
    success_dl = []
    to_process = len(dl_list)
    processed = 0
    # main thread handles adding files to files info dict since even though dicts are thread-safe
    # for single operations i dont want to rely on it
    while processed < to_process:
        processed += 1
        # file_loc is relative to fourcdl root dir so its not the same as dl_path
        url, dl_success, md5_match, file_size, file_loc = downloaded_queue.get()
        if dl_success:
            # we even keep files with failed md5 -> user hast to check them
            # manually first if theyre worth keeping or useless
            success_dl.append(url)
            if not md5_match:
                failed_md5.append(url)
        # WARNING only added if md5_match even if we decide to keep the file
        # removing md5_b64 later from files_info_dict also wouldnt work since we might have downloaded
        # that file before then removing it would be wrong
        if dl_success and md5_match:
            file_dict = thread[url]["file_info"]
            add_file_to_files_info(files_info_dict, file_dict["file_ext"], file_size,
                                   file_dict["file_md5_b64"], file_loc)
            logger.debug("Added file %s to files_info_dict!", file_loc)
        downloaded_queue.task_done()
        print(f"~~ PROCESSED {processed} of {to_process} ~~")
        time.sleep(0.1)

    # stop worker thread
    for _ in range(NUMBER_OF_THREADS):
        dl_queue.put((None,)*6)
    for t in dl_threads:
        print(f"** Waiting on thread {t.name} **")
        t.join()

    print("** Done! **")

    # TODO(m): do we  still need to except unexpected crashes and what happens if a thread crashes and we dont reach the needed nr of processed items?
    # try:
    #     dl_success, md5_match = download_4chan_file_url(file_url, dl_path, file_dict,
    #                                                     files_info_dict, thread,
    #                                                     overwrite=overwrite)

    #     if dl_success:
    #         # we even keep files with failed md5 -> user hast to check them manually first if theyre worth keeping or useless
    #         success_dl.append(url)
    #         if not md5_match:
    #             failed_md5.append(url)
    #     cur_nr += 1

    # except Exception as e:
    #     raise UnexpectedCrash("download_thread", (thread, dl_list), "Unexpected crash while downloading! Program state has been saved, start script with option resume to continue with old state!").with_traceback(e.__traceback__)

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
