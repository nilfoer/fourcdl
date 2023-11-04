import os
import sys
import time
import logging
import urllib.request
import json
import re

import pyperclip

from fourcdl.logging_setup import configure_logging
from fourcdl.gen_downloaded_files_info import file_unique_converted, import_files_info_pickle, export_files_info_pickle, generate_downloaded_files_info, convert_4chan_file_size
from fourcdl.crc import md5, convert_b64str_to_hex
from fourcdl.threading import download_thread_threaded
from fourcdl.thread import get_key_from_furl, get_thread_from_html, is_4ch_thread_url
from fourcdl.post import is_4ch_file_url
from fourcdl.utils import sanitize_fn, get_url, write_to_file, append_to_file, UnexpectedCrash
from fourcdl.autocomplete import init_autocomplete

logger = logging.getLogger(__name__)

# os.path.dirname(os.path.realpath(__file__))
# CWD = os.getcwd()

# normal urllib user agent is being blocked by tsumino
# set user agent to use with urrlib
opener = urllib.request.build_opener()
opener.addheaders = [('User-agent', 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:12.0) Gecko/20100101 Firefox/12.0')]
# ...and install it globally so it can be used with urlretrieve/open
urllib.request.install_opener(opener)

DOWNLOAD_THREAD_FUNC = download_thread_threaded
PYPERCLIP_ACCESS_ERROR_SLEEP = 5


def get_new_clipboard(recent):
    """Check clipboard for new contents and returns it if its doesnt match the content of recent
    :param recent: recent content we dont want to count as new clipboard content"""
    times_slept_for_clip_access = 0
    try:
        while True:
            try:
                tmp_value = pyperclip.paste()
            except pyperclip.PyperclipWindowsException:
                # except pyperclip.PyperclipWindowsException which gets raised when the user
                # e.g. locks the computer and we pyperclip can't access the clipboard
                if times_slept_for_clip_access == 0:
                    print("Couldn't read from clipboard! This might be due to the computer "
                          "being in the locking screen.")
                times_slept_for_clip_access += 1
                # write this on the same line so we don't spam the console by using the
                # carriage return ('\r') character to return to the start of the line without
                # advancing to the next line
                print(f"Trying again in {PYPERCLIP_ACCESS_ERROR_SLEEP} seconds... "
                      f"x{times_slept_for_clip_access}", end='\r')
                time.sleep(PYPERCLIP_ACCESS_ERROR_SLEEP)
            if tmp_value != recent:
                return tmp_value
            time.sleep(0.1)
    except KeyboardInterrupt:
        return None


def get_all_file_urls_thread(thread, unique_only, files_info_dict):
    all_file_urls_thread = []
    for u in thread.keys():
        if "/" in u:
            if unique_only:
                size = convert_4chan_file_size(thread[u]["file_info"]["file_size"])
                # if not unique/not alrdy dled -> skip
                if not file_unique_converted(files_info_dict,
                        thread[u]["file_info"]["file_ext"], size,
                        thread[u]["file_info"]["file_md5_b64"]):
                    continue
            all_file_urls_thread.append(u)
            thread[u]["file_info"]["to_download"] = True
            # set dl_filename, append orig fn
            thread[u]["file_info"]["dl_filename"]= f"{thread[u]['file_info']['file_name_4ch']}_{thread[u]['file_info']['file_name_orig']}"

    return all_file_urls_thread


def watch_for_file_urls(thread, files_info_dict, prev_dl_list=None):
    """Watch clip for 4chan file urls
    :param thread: thread dict, post_nr and file urls as keys to post_dict"""
    running = True
    # continue with imported dl_list if present
    if prev_dl_list:
        dl_list = set(prev_dl_list)
    else:
        dl_list = set()
    unique_only = thread["OP"]["unique_only"]

    print("Watching clipboard for 4chan file urls...")
    print("Copy cmds are: rename_thread, reset_filename, remove_file, toggle_use_orig_fn,"
          " reset_to_4ch_fn !")
    recent_value = None
    file_post_dict = None
    use_orig_filename = False
    while running:
        recent_value = get_new_clipboard(recent_value)
        # None -> caught a user interrupt
        if recent_value is None:
            # we had a current file
            if file_post_dict:
                if file_post_dict["file_info"]["to_download"]:
                    logger.info("File will be downloaded as \"%s.%s\"\n",
                                file_post_dict["file_info"]["dl_filename"],
                                file_post_dict["file_info"]["file_ext"])
                elif not file_post_dict["file_info"]["unique"]:
                    file_url = get_key_from_furl(file_post_dict["file_info"]["file_url"])
                    logger.info("File \"%s\" wasn't unique and therefore was NOT added "
                                "to the download list!\n",
                                file_post_dict["file_info"]["file_name_orig"])
                    # remove on set raises KeyError when item not present -> discard(x) doesnt
                    dl_list.remove(file_url)

                    # dl_filename key only gets created once added to dls -> remove it
                    del file_post_dict["file_info"]["dl_filename"]
            elif not dl_list:
                whole = input("No file urls copied! Download all file urls in thread: y/n?\n")

                if whole == "y":
                    return get_all_file_urls_thread(thread, unique_only, files_info_dict)

            print("Stopped watching clipboard for 4chan file URLs!")
            running = False
        else:
            if is_4ch_file_url(recent_value):
                # remove https?: from start of url, better to use address
                # without http/https since the copies differ with/without 4chan x
                # -> or just make sure that its https: by replacing match with https:
                # better remove whole main domain part since files might be on different servers
                # but we always want to dl from i.4cdn.org later since its faster
                # (as stated by 4chan x)
                file_url = get_key_from_furl(recent_value)

                # report on final filename if there was a prev file
                if file_post_dict:
                    if file_post_dict["file_info"]["to_download"]:
                        logger.info("File will be downloaded as \"%s.%s\"\n",
                                    file_post_dict["file_info"]["dl_filename"],
                                    file_post_dict["file_info"]["file_ext"])
                    elif not file_post_dict["file_info"]["unique"]:
                        # TODO(moe): this seems complicated -> better to not use dl_list at all and just work
                        # with to_dl in dict etc.
                        file_url_old = get_key_from_furl(file_post_dict["file_info"]["file_url"])
                        # may have removed file alrdy so use orig-fn oder 4ch fn
                        logger.info("File \"%s\" wasn't unique and therefore was NOT "
                                    "added to the download list!\n",
                                    file_post_dict["file_info"]["file_name_orig"])
                        # remove on set raises KeyError when item not present -> discard(x) doesnt
                        # might have removed file with remove_file alrdy -> use discard
                        dl_list.discard(file_url_old)

                        # dl_filename key only gets created once added to dls -> remove it
                        # might have removed dl_filename with cmd remove_file
                        try:
                            del file_post_dict["file_info"]["dl_filename"]
                        except KeyError:
                            pass
                if file_url in dl_list:
                    logger.info("RESET file name of \"%s\"!!!", file_url.split("/")[-1])

                file_post_dict = add_file_url_to_downloads(file_url, thread, dl_list,
                                                           files_info_dict, unique_only,
                                                           use_orig_filename=use_orig_filename)
            elif recent_value.strip() == "rename_thread":
                # option to set new folder name when rename_thread is copied
                thread["OP"]["folder_name"] = cli_folder_name("Input new folder name:\n")
                print(f"Renamed thread folder to {thread['OP']['folder_name']}")
            elif recent_value.strip() == "toggle_use_orig_fn":
                # option to set new folder name when rename_thread is copied
                use_orig_filename = not use_orig_filename
                print(f"Append original filename by default: {use_orig_filename}")
            elif file_post_dict:
                file_post_dict = modify_current_file(file_post_dict, dl_list, recent_value,
                                                     use_orig_filename=use_orig_filename)

    # since were working on thread directly and its a mutable type(dict) we dont have
    # to return (but mb more readable)
    # to list -> json serializable
    return list(dl_list)


ARTIST_NAMES_RE = (
        re.compile(r"by(?:-|_)((\w+)(?:-|_)(?:.$)?)"),
        re.compile(r"^([-_A-Za-z0-9]+?)(?:_|-)\d{4,}(?:_|-)"),
        re.compile(r"^\d{4,}_([-_A-Za-z0-9]+)_"),
        re.compile(r"^\d{4,}-([-_A-Za-z0-9]+)-"),
        re.compile(r"\d{4,}\.([-_A-Za-z0-9]+)_"),
)


def add_file_url_to_downloads(file_url, thread, dl_list, files_info_dict,
                              unique_only, use_orig_filename=False):
    try:
        file_post_dict = thread[file_url]
    except KeyError:
        file_post_dict = None
        print(f"ERROR: File of URL \"{file_url}\" was deleted or is not from this thread!")
    # only proceed if file_url is in dict/thread
    else:
        # add file_url (without http part) of file post to dl list and set to_download
        dl_list.add(file_url)
        file_post_dict["file_info"]["to_download"] = True
        file_post_dict["file_info"]["dl_filename"] = file_post_dict['file_info']['file_name_4ch']

        logger.info("Found file url of file: \"%s\" Total of %s files",
                    file_url, len(dl_list))
        print("Orig-fn:", file_post_dict["file_info"]["file_name_orig"], "|",
              "MD5:", file_post_dict["file_info"]["file_md5_b64"])

        if use_orig_filename:
            file_post_dict["file_info"]["dl_filename"] = (
                f"{file_post_dict['file_info']['file_name_4ch']}_"
                f"{file_post_dict['file_info']['file_name_orig']}")
            print(f"Appended original filename: {file_post_dict['file_info']['dl_filename']}")
        else:
            file_post_dict["file_info"]["dl_filename"] = (
                    file_post_dict['file_info']['file_name_4ch'])
            # look for possible artist names in the orig fn
            orig_fn = file_post_dict['file_info']['file_name_orig']

            possible_artist_names = []
            for regexpr in ARTIST_NAMES_RE:
                for match in regexpr.finditer(orig_fn):
                    possible_artist_names.extend(match.groups())

            if possible_artist_names:
                possible_artist_names_str = "\n".join(possible_artist_names)
                print(f"Possible artist(s) found:\n{possible_artist_names_str}")

        if unique_only:
            # cant use get_url_file_size here since it might take multiple seconds
            # use value available in 4chan file_info
            size = convert_4chan_file_size(file_post_dict["file_info"]["file_size"])
            # if not unique/not alrdy dled -> alert user and set to not dl
            if not file_unique_converted(files_info_dict,
                    file_post_dict["file_info"]["file_ext"], size,
                    file_post_dict["file_info"]["file_md5_b64"],
                    print_flist=True):
                file_post_dict["file_info"]["unique"] = False
                file_post_dict["file_info"]["to_download"] = False
                logger.info("ALERT!! File with url %s has been downloaded before!\n"
                            "    Copy add_anyway to add file to downloads!", file_url)
            else:
                file_post_dict["file_info"]["unique"] = True

    return file_post_dict


def modify_current_file(file_post_dict, dl_list, cmd, use_orig_filename=False):
    # sanitize filename for windows, src: https://stackoverflow.com/questions/7406102/create-sane-safe-filename-from-any-unsafe-string by wallyck
    # if after for..in is part of comprehension syntax <-> if..else b4 for..in is pythons equivalent of ternary operator
    # only keep chars if theyre alphanumerical (a-zA-Z0-9) or in the tuple (' ', '_'), replace rest with _
    # reset file name to 4ch name when reset_filename is copied
    cmd = cmd.strip()
    if cmd == "reset_filename":
        if use_orig_filename:
            file_post_dict["file_info"]["dl_filename"] = (
                f"{file_post_dict['file_info']['file_name_4ch']}_"
                f"{file_post_dict['file_info']['file_name_orig']}")
        else:
            file_post_dict["file_info"]["dl_filename"] = (
                    file_post_dict['file_info']['file_name_4ch'])
        print("Filename has been reset to ", file_post_dict['file_info']['dl_filename'])
    elif cmd == "reset_to_4ch_fn":
        file_post_dict["file_info"]["dl_filename"] = (
                file_post_dict['file_info']['file_name_4ch'])
        print("Filename has been reset to ", file_post_dict['file_info']['dl_filename'])
    elif cmd == "add_anyway":
        file_post_dict["file_info"]["to_download"] = True
        logger.info("File \"%s\" WAS added to download_list even though it wasnt unique!",
                    file_post_dict["file_info"]["dl_filename"])
    elif cmd == "remove_file":
        logger.info("Removing file with filename \"%s\" from download list",
                    file_post_dict["file_info"]["dl_filename"])
        file_url = get_key_from_furl(file_post_dict["file_info"]["file_url"])
        # remove on set raises KeyError when item not present -> discard(x) doesnt
        dl_list.remove(file_url)

        file_post_dict["file_info"]["to_download"] = False
        # dl_filename key only gets created once added to dls -> remove it
        del file_post_dict["file_info"]["dl_filename"]
        # this caused a crash since this was assigning None to the local var
        # instead of the var in outer scope (watch_for_file_urls)
        # still assumes we have a current file -> copy non-furl -> crash since
        # fname key doesnt exist -> fix: return local var and assign in outer scope
        file_post_dict = None
        logger.info("New total file count: %s\n", len(dl_list))
    else:
        sanitized_clip = sanitize_fn(cmd)

        dl_filename = f"{file_post_dict['file_info']['dl_filename']}_{sanitized_clip}"
        file_post_dict["file_info"]["dl_filename"] = dl_filename
        print(f"Not a file URL -> clipboard was appended to filename:\n{dl_filename}")

    return file_post_dict


def process_4ch_thread(url, files_info_dict):
    html = get_url(url)
    thread = get_thread_from_html(html)
    thread["OP"]["folder_name"] = cli_folder_name(
            "Input the folder name the thread is going to be downloaded to "
            "(e.g. \"gif_cute\", subfolders work too \"gif_model/Emily Rudd\""
            "):\n")
    thread["OP"]["unique_only"] = cli_yes_no("Only copy unique files?")
    try:
        dl_list = watch_for_file_urls(thread, files_info_dict)
    except Exception as e:
        # i dont rly need dl_list since im setting to_download and dl_filename
        # in mutable dict thats contained inside thread dict
        # instead of using raise UnexpectedCrash from e (gets rid of traceback) use with_traceback
        raise UnexpectedCrash("process_4ch_thread", thread,
                              "Unexpected crash while processing 4ch thread! Program state has been"
                              " saved, start script with option resume to continue with old state!"
                              ).with_traceback(e.__traceback__)
    return thread, dl_list


def cli_folder_name(msg):
    while True:
        folder_name = input(msg).strip()
        if any(c in ':?*"<>|' for c in folder_name):
            print("Invalid character in folder name! Banned characters: ?:*\"<>|")
        else:
            logger.debug("Folder name is \"%s\"", folder_name)
            return folder_name


def cli_yes_no(question_str):
    ans = input(f"{question_str} y/n:\n")
    while True:
        if ans == "n":
            return False
        elif ans == "y":
            return True
        else:
            ans = input(f"\"{ans}\" was not a valid answer, type in \"y\" or \"n\":\n")


def watch_clip_for_4ch_threads(files_info_dict, root_dir):
    """Watch clip for 4chan thread urls, once url is found process_4ch_thread is called,
    returned thread dicts and dl_links (which also are the keys of files to dl in thread dict)
    are appended to to_dl."""
    to_dl = []
    print("Watching clipboard for 4chan thread urls...")
    recent_value = None
    while True:
        recent_value = get_new_clipboard(recent_value)
        if recent_value is None:
            print("Stopped watching clipboard for 4chan thread URLs!")
            break
        elif is_4ch_thread_url(recent_value):
            try:
                to_dl.append(process_4ch_thread(recent_value, files_info_dict))
            except Exception as e:
                raise UnexpectedCrash(
                        "watch_clip_for_4ch_threads", to_dl,
                        "Unexpected crash while watching clipboard and appending! "
                        "Program state has been saved, start script with option resume "
                        "to continue with old state!"
                        ).with_traceback(e.__traceback__)
            else:
                # backup after every thread
                export_state_from_dict(
                    {"dl_multiple_threads": (to_dl, [])}, os.path.join(root_dir, "auto-backup.json"))

    # write state before downloading as safety measure against running into a dead lock
    # due to a threaded dl worker crashing or a user hitting Ctrl-C twice and interrupting
    # the download
    export_state_from_dict({"dl_multiple_threads": (to_dl, [])}, os.path.join(root_dir, "auto-backup.json"))

    dl_multiple_threads(to_dl, files_info_dict, root_dir)


def read_from_file(file_path):
    with open(file_path, "r", encoding="UTF-8") as f:
        contents = f.read()
    return contents


def export_state_from_dict(program_state, filepath):
    # readability indent=4, sort_keys=True
    json_exp_str = json.dumps(program_state, indent=4, sort_keys=True)
    write_to_file(json_exp_str, filepath)


def import_state(filepath):
    """State list contains tuple(s) of (thread, dl_list) pairs"""
    json_imp = read_from_file(filepath)
    state = json.loads(json_imp)
    return state


# Default parameter values are evaluated when the function definition is executed. This means that the expression is evaluated once, when the function is defined, and that same “pre-computed” value is used for each call. This is especially important to understand when a default parameter is a mutable object, such as a list or a dictionary: if the function modifies the object (e.g. by appending an item to a list), the default value is in effect modified.
# Lists are a mutable objects; you can change their contents. The correct way to get a default list (or dictionary, or set) is to create it at run time instead, inside the function
# dont use test(a, b=[]) since all funcs calls will use the same list do it like below
def dl_multiple_threads(to_dl, files_info_dict, root_dir, successful_dl_threads=None, overwrite=False):
    if successful_dl_threads is None:
        successful_dl_threads = []

    for thread, dl_list in to_dl:
        # only dl if it wasnt downloaded successfuly b4 crash
        # could also use set functionality and build the difference? but this is fine since there wont be more >5 threads
        if thread["OP"]["thread_nr"] not in successful_dl_threads:
            try:
                # only start dl if file urls were copied from clipboard
                if dl_list:
                    DOWNLOAD_THREAD_FUNC(thread, dl_list, files_info_dict, root_dir, overwrite=overwrite)
                    successful_dl_threads.append(thread["OP"]["thread_nr"])
            except Exception as e:
                    raise UnexpectedCrash("dl_multiple_threads", (to_dl, successful_dl_threads), "Unexpected crash while downloading multiple 4ch threads! Program state has been saved, start script with option resume to continue with old state!").with_traceback(e.__traceback__)
    # assume all are downloaded
    for thread, _ in to_dl:
        try:
            user_handle_failed_md5(thread, thread["failed_md5"], root_dir)
        except KeyError:
            continue


def user_handle_failed_md5(thread, failed_md5, root_dir):
    root_md5_path = os.path.join(root_dir, "4chan_dl.md5")
    with open(root_md5_path, "r", encoding="UTF-8") as f:
        root_md5_file = f.read()

    # we already warned b4
    print("Files with failed CRC that you want to keep will get their original md5 (in root md5 file) replaced "
          "by their actual md5, but their original md5 will be stored in 'kept_failed_md5_files.md5'\n"
          "It is recommended to check the files manually -> if they play/look ok -> keep them")
    # cant use \ in {} of f-strings -> either use chr(10) to get \n or assign to var nl="\n" and use that or join b4hand and assign to var
    # nested f-strings dont work somehow if they contain the usage of quotation marks
    i_failed_names = "\n".join((f'({i}) {thread[url]["file_info"]["dl_filename"]}' for i, url in enumerate(failed_md5)))
    keep = input(f"Type in the indexes seperated by \",\" of files to keep in Thread No. {thread['OP']['thread_nr']} "
                 f"with failed CRC-Checks: \"{thread['OP']['subject']}\"\n{i_failed_names}\n")
    keep = [int(i) for i in keep.split(",")] if keep else []
    kept_failed_lns = []
    for i, url in enumerate(failed_md5):
        file_info = thread[url]["file_info"]
        thread_folder_name = thread["OP"]["folder_name"]
        fn = f"{file_info['dl_filename']}.{file_info['file_ext']}"
        orig_md5 = convert_b64str_to_hex(file_info['file_md5_b64'])

        # check if we want to keep file
        if i in keep:
            actual_md5 = md5(os.path.join(root_dir, thread_folder_name, fn))
            # replace orig md5 in root md5 file with actual md5
            # WARNING dont only replace orig_md5 since md5 might be in root md5 alrdy (since we dont check for dupes when downloading)
            # -> use md5 *path instead
            # STRING->IMMUTABLE => replace returns the new string with replaced substring -> need to reassign it
            root_md5_file = root_md5_file.replace(f"{orig_md5} *{thread_folder_name}/{fn}", f"{actual_md5} *{thread_folder_name}/{fn}", 1)
            kept_failed_lns.append(f"{orig_md5} *{thread_folder_name}/{fn}")
        else:
            logger.info("Removing \"%s\" from folder and root md5 file", fn)
            os.remove(os.path.join(root_dir, thread["OP"]["folder_name"], fn))
            root_md5_file = root_md5_file.replace(f"{orig_md5} *{thread_folder_name}/{fn}\n", "", 1)

    if kept_failed_lns:
        append_to_file("\n".join(kept_failed_lns) + "\n", os.path.join(root_dir, "kept_failed_md5_files.md5"))

    with open(root_md5_path, "w", encoding="UTF-8") as w:
        w.write(root_md5_file)


def resume_from_state_dict(state_dict, files_info_dict, root_dir):
    # TODO copy inline comments into docstr
    # four possible keys in state dict 
    # "download_thread" contains one/or only alrdy processed thread
    # "watch_clip_for_4ch_threads" contains alrdy processed threads and dl_lists, crashed while process_4ch_thread so while watch_for_file_urls
    # "process_4ch_thread" contains latest thread, no dl_list since it crashed while watching for urls b4 returning it
    # "dl_multiple_threads" contains one/multiple already processed threads and dl_lists, saved cause crashed while downloading

    # be CAREFUL where we raise UnexpectedCrash or reraise since that (or reraising UnexpectedCrash)
    # will lead to crash-exp.json to be overwritten and we might have crashed again b4 being done
    # wont be bad if we still collect all the necessary info
    # not raising UnexpectedCrash -> export state wont be called -> nothing happens
    # we dont need to reraise for UnexpectedCrash to reach outmost scope, no matter where we raise it unless we except it (and then dont reraise it) it will reach outmost scope and it will be caught and state will get exported
    keys = state_dict.keys()
    if "dl_multiple_threads" in keys:
        # crashed while downloading multiple threads, all fns and dl_lists alrdy created -> error has to be fixed manually in code/json, supply alrdy successfuly download threads b4 crash as optional argument so they wont get downloaded again (-> duplicates in exp txt and md5)
        logger.info("Continuing with download of multiple threads!")
        to_dl, successful_dl_threads = state_dict["dl_multiple_threads"]
        # overwrite old since they might be corrupt
        dl_multiple_threads(to_dl, files_info_dict, root_dir, successful_dl_threads=successful_dl_threads,
                overwrite=True)

    elif "watch_clip_for_4ch_threads" in keys:
        # was inside watch_clip_for_4ch_threads b4 crash -> continue with watching for urls for latest thrad (use key "process_4ch_thread") then dl all
        # last item in this list isnt actually the thread we working on b4 the crash
        to_dl = state_dict["watch_clip_for_4ch_threads"]

        try:
            last_thread = state_dict["process_4ch_thread"]
        except KeyError:
            # crashed b4 starting process_4ch_thread
            pass
        else:
            # no dl_list saved use to_download vals to recreate it
            last_dl_list = recreate_dl_list(last_thread)

            logger.info("Start watching for 4ch_file_urls for latest thread \"%s\" -> will be "
                        "downloaded with the previously processed threads afterwards!",
                        last_thread["OP"]["thread_nr"])
            # dont try to raise UnexpectedCrash here unless we'd just supply
            # to_dl again for crash point "watch_clip_for_4ch_threads"
            # -> few copies we have to do again dont matter?
            last_dl_list = watch_for_file_urls(last_thread, files_info_dict, prev_dl_list=last_dl_list)
            to_dl.append((last_thread, last_dl_list))

        logger.info("Continuing with download of multiple threads!")
        # here we can reraise (NO! -> dont need to reraise to catch exception in outer scope, only if we wanted to raise new type of Exception (UnexpectedCrash) or add information to the Exception) due to successful thread dls
        # nothing was downloaded b4 crash
        dl_multiple_threads(to_dl, files_info_dict, root_dir)

    elif "process_4ch_thread" in keys:
        # 1) single option -> continue with watch file urls
        # 2) from "watch_clip_for_4ch_threads": "watch_clip_for_4ch_threads"->true, a) continue to watch for file urls for thread(latest) then dl latest+rest from watch_clip_for_4ch_threads or b) dl(latest) + rest right away
        # 2) alrdy account for when reaching this point (cause of elif "watch_clip_for_4ch_threads"..)

        last_thread = state_dict["process_4ch_thread"]

        logger.info("Found single thread with no dl_list -> recreating it and starting to watch for 4ch_file_urls again!")
        # no dl_list saved use to_download vals to recreate it
        # multiple if statements (and for..in allowed in comprehension) -> stack them after each other
        last_dl_list = recreate_dl_list(last_thread)
        # dont reraise here
        last_dl_list = watch_for_file_urls(last_thread, files_info_dict, prev_dl_list=last_dl_list)

        # just single thread need to reraise since dl_list complete and we land in "download_thread" next resume -> tested OK
        # reraising uneccessary see above
        # nothing dled b4 crash
        DOWNLOAD_THREAD_FUNC(last_thread, last_dl_list, files_info_dict, root_dir)
        try:
            user_handle_failed_md5(last_thread, last_thread["failed_md5"], root_dir)
        except KeyError:
            pass

    elif "download_thread" in keys:
        # 1) single opt: probably fix error manually -> re-dl
        # 2) from dl_multiple_threads: also have to fix error -> re-dl with rest
        # 2) alrdy accounted for cause of elif "dl_multiple_threads"..
        thread, dl_list = state_dict["download_thread"]

        logger.info("Found failed download -> trying to re-download, old files will be overwritten!")
        # ovewrite since file dled b4/at crash might be corrupt
        DOWNLOAD_THREAD_FUNC(thread, dl_list, files_info_dict, root_dir, overwrite=True)
        try:
            user_handle_failed_md5(thread, thread["failed_md5"], root_dir)
        except KeyError:
            pass


def recreate_dl_list(thread):
    result = []
    for k, post_dict in thread.items():
        if "/" in k:
            try:
                if post_dict["file_info"]["to_download"]:
                    result.append(get_key_from_furl(post_dict["file_info"]["file_url"]))
            except KeyError:
                pass

    return result


def main():
    # set ROOTDIR to loc we were called from (path from terminal -> getcwd())
    # better use dir of script, since we might not want to write our files at terminals cwd
    # ROOTDIR = os.getcwd()
    # sys.argv[0] is path to script -> which is fchdl-runner.py (but might be __main__.py as well)
    ROOTDIR = os.path.dirname(os.path.realpath(sys.argv[0]))
    # -> removed __main__.py so fourcdl can only be started as script via fchdl-runner.py

    # dont use clipwatch but use thread url as argv -> have to wait for imports when new thread
    cmd_line_arg1 = sys.argv[1]
    if cmd_line_arg1 == "watch":
        # check if we have a generated files info pickle
        if not os.path.isfile("downloaded_files_info.pickle"):
            files_info_dict = generate_downloaded_files_info(ROOTDIR)
        else:
            files_info_dict = import_files_info_pickle(
                        os.path.join(ROOTDIR, "downloaded_files_info.pickle"))

        # setup sub-folder auto-complete
        init_autocomplete(files_info_dict)

        try:
            watch_clip_for_4ch_threads(files_info_dict, ROOTDIR)
        except UnexpectedCrash as e:
            export_files_info_pickle(files_info_dict, os.path.join(ROOTDIR, "downloaded_files_info.pickle"))
            export_state_from_dict(e.program_state, os.path.join(ROOTDIR, "crash-exp.json"))
            # here we really need to except and reraise since we want to export information in-between but still want the program to end with the traceback
            raise
    elif cmd_line_arg1 == "resume":
        files_info_dict = import_files_info_pickle(os.path.join(ROOTDIR, "downloaded_files_info.pickle"))
        # setup sub-folder auto-complete
        init_autocomplete(files_info_dict)

        state_json_name = os.path.join(ROOTDIR, "crash-exp.json") if len(sys.argv) < 3 else sys.argv[2]
        state = import_state(state_json_name)
        # we just catch UnexpectedCrash here and then export state so resume_from_state_dict
        # handles when UnexpectedCrash gets raised or reraised(when we except it and raise it again to e.g. add information) to here (have to be careful since we might overwrite old state export that wasnt properly downloaded yet)
        try:
            resume_from_state_dict(state, files_info_dict, ROOTDIR)
        except UnexpectedCrash as e:
            export_files_info_pickle(files_info_dict, os.path.join(ROOTDIR, "downloaded_files_info.pickle"))
            export_state_from_dict(e.program_state, os.path.join(ROOTDIR, "crash-exp.json"))
            raise
    elif cmd_line_arg1 == "gen_info":
        files_info_dict = generate_downloaded_files_info(ROOTDIR)

    # always write udated files_info after script is done
    export_files_info_pickle(files_info_dict, os.path.join(ROOTDIR, "downloaded_files_info.pickle"))


if __name__ == "__main__":
    main()
