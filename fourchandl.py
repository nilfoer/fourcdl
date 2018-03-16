import os
import sys
import time
import logging
import re
import urllib.request
import hashlib
import binascii
import json

from logging.handlers import RotatingFileHandler

import bs4
import pyperclip

ROOTDIR = os.path.dirname(os.path.realpath(__file__))
# CWD = os.getcwd()

logger = logging.getLogger("4chdl")
logger.setLevel(logging.DEBUG)

# create a file handler
# handler = TimedRotatingFileHandler("gwaripper.log", "D", encoding="UTF-8", backupCount=10)
# max 1MB and keep 5 files
handler = RotatingFileHandler(os.path.join(ROOTDIR, "tsuinfo.log"),
                              maxBytes=1048576, backupCount=5, encoding="UTF-8")
handler.setLevel(logging.DEBUG)

# create a logging format
formatter = logging.Formatter(
    "%(asctime)-15s - %(name)-9s - %(levelname)-6s - %(message)s")
# '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
handler.setFormatter(formatter)

# add the handlers to the logger
logger.addHandler(handler)

# create streamhandler
stdohandler = logging.StreamHandler(sys.stdout)
stdohandler.setLevel(logging.INFO)

# create a logging format
formatterstdo = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s", "%H:%M:%S")
stdohandler.setFormatter(formatterstdo)
logger.addHandler(stdohandler)


class ClipboardWatcher:
    """Watches for changes in clipboard that fullfill predicate and get sent to callback

    I create a subclass of threading.Thread, override the methods run and __init__ and create an instance of this class.
    By calling watcher.start() (not run()!), you start the thread.
    To safely stop the thread, I wait for -c (Keyboard-interrupt) and tell the thread to stop itself.
    In the initialization of the class, you also have a parameter pause to control how long to wait between tries.
    by Thorsten Kranz"""
    # predicate ist bedingung ob gesuchter clip content
    # hier beim aufruf in main funktion is_url_but_not_sgasm

    def __init__(self, predicate, callback, txtpath, pause=5.):
        self._predicate = predicate
        if callback is None:
                self._callback = self.add_found
        else:
                self._callback = callback
        self._txtpath = txtpath
        self._found = []
        self._pause = pause
        self._stopping = False

    def run(self):
        recent_value = "" 
        while not self._stopping:
                tmp_value = pyperclip.paste()
                if tmp_value != recent_value:
                        recent_value = tmp_value
                        # if predicate is met
                        if self._predicate(recent_value):
                                # call callback
                                self._callback(recent_value)  # , self._txtpath)
                time.sleep(self._pause)

    def run_single(self, prev_clip_cont):
        # param with prev clip content to avoid matching clip content and then
        # stopping when using run_single
        recent_value = prev_clip_cont
        while not self._stopping:
                tmp_value = pyperclip.paste()
                if tmp_value != recent_value:
                        recent_value = tmp_value
                        # if predicate is met
                        if self._predicate(recent_value):
                                # dont call callback
                                logger.info("File url: %s", recent_value)
                                return recent_value
                time.sleep(self._pause)

    def run_append_found(self):
        recent_value = "" 
        while not self._stopping:
                tmp_value = pyperclip.paste()
                if tmp_value != recent_value:
                        recent_value = tmp_value
                        # if predicate is met
                        if self._predicate(recent_value):
                                # call callback
                                try:
                                    self._found.append(self._callback(recent_value))  # , self._txtpath)
                                except Exception as e:
                                    raise UnexpectedCrash("ClipboardWatcher", self._found, "Unexpected crash while watching clipboard and appending! Program state has been saved, start script with option resume to continue with old state!").with_traceback(e.__traceback__)

                time.sleep(self._pause)

    def add_found(self, item):
            logger.info("Found item: %s", item)
            self._found.append(item)

    def get_found(self):
            return self._found

    def stop(self):
            self._stopping = True

    def copy_to_clip(self, value):
           pyperclip.copy(value) 


def write_to_file(wstring, file_path):
    """
    Writes wstring to filename in dir ROOTDIR

    :param wstring: String to write to file
    :param file_path: File path
    :return: None
    """
    with open(file_path, "w", encoding="UTF-8") as w:
        w.write(wstring)


def append_to_file(wstring, file_path):
    """
    Writes wstring to filename in dir ROOTDIR

    :param wstring: String to write to file
    :param file_path: File path
    :return: None
    """
    with open(file_path, "a", encoding="UTF-8") as w:
        w.write(wstring)


def get_url(url):
    html = None

    # normal urllib user agent is being blocked by tsumino, send normal User-Agent in headers ;old: 'User-Agent': 'Mozilla/5.0'
    req = urllib.request.Request(url, headers={
                                 'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; WOW64; rv:12.0) Gecko/20100101 Firefox/12.0'})
    try:
        site = urllib.request.urlopen(req)
    except urllib.request.HTTPError as err:
        logger.warning("HTTP Error %s: %s: \"%s\"", err.code, err.reason, url)
    else:
        html = site.read().decode('utf-8')
        site.close()
        logger.debug("Getting html done!")

    return html


def get_post_info(postinfo):
    utc = postinfo.select_one("span.dateTime")["data-utc"]
    # select -> find tag using css selectors, select_one only = first match
    post_nr = postinfo.select("span.postNum.desktop a")[1].text
    # doesnt need to be mutable -> use tuple with generator expression
    # (evaluated lazily and won't need to allocate memory for an intermediate list)
    # select link texts removing first 2 symbols(>>)
    # ONLY WORKS WITH JS otherwiese backlinks arent generated -> gen them myself since using
    # sth like selenium or PyQt4 stuff so prob big hit on perf and its not incl in standard lib
    # backlinks = tuple((a.text[2:] for a in postinfo.select("div.backlink a.quotelink")))
    return utc, post_nr, [] 


file_size_res_re = re.compile(r".+\.\w{2,5} \(([0-9\.]+ [A-Z]+), (\d+x\d+)\)")
def get_file_info(post):
    filediv = post.select_one("div.file")
    if filediv:
        # select_one("div.fileText").contents: ['File: ', <a href="http://i.4cdn.org/gif/1511722035452.webm" target="_blank">1500927785845.webm</a>, ' (2.8 MB, 1280x720)']
        # -> list -> not accessible like bs4 tag
        # select_one("div.fileText").text: "File: 1500927785845.webm (2.8 MB, 1280x720)"
        filediv_cont = filediv.select_one("div.fileText")
        # file deleted if none
        if filediv_cont:
            file_url = filediv_cont.a["href"]
            # since this is the filename generated by 4ch there wont be additional dots
            file_name_4ch, file_ext = file_url.split("/")[-1].split(".")
            # discard extension of orig fn
            # could contain more than one dot -> use rsplit("delim", max) -> starts splitting from the right-hand-side of the string; by giving it a maximum, you get to split just the right-hand-most occurrence
            # orig fn that are too long will be abreviated in text with (...)
            # long orig fn will be in title attribute of <a>
            try:
                file_name_orig = filediv_cont.a["title"].rsplit(".", 1)[0]
            except KeyError:
                file_name_orig = filediv_cont.a.text.rsplit(".", 1)[0]
            # unpack groups
            file_size, file_res = re.match(file_size_res_re, filediv_cont.text).groups()
            file_thumb = filediv.select_one("img")
            file_info = {
                "file_url": file_url,
                "file_name_4ch": file_name_4ch,
                "file_ext": file_ext,
                "file_name_orig": file_name_orig,
                "file_size": file_size,
                "file_res": file_res,
                "file_thumb_url": file_thumb["src"],
                "file_md5_b64": file_thumb["data-md5"],
                "to_download": False,
                "downloaded": False
            }
            return file_info
        else:
            return None
    else:
        return None


def get_post_msg(post):
    # still tag not text/str
    post_msg = post.select_one("blockquote.postMessage")
    # markup = '<a href="http://example.com/">\nI linked to <i>example.com</i>\n</a>'
    # soup.get_text()
    # u'\nI linked to example.com\n'
    # soup.i.get_text()
    # u'example.com'
    # get_text() and .text (probably same as get_gext()) removes all the tags, so <br> as well and joins them on ""
    # get_text("\n") join the bits of text on "\n" -> same as "\n".join(post_msg.strings)

    # could also extract other links than quotes but since theyre alrdy in the postmsg themself
    # and i probably wont need them in a separate form ill leave it like this
    # dont count cross-thread quotes
    # ex. quotelink: #p11684379, cross-thread quotelink /gif/thread/11673913#p11673913
    # other weird stuff
    # <a href="//boards.4chan.org/t/#s=umblr" class="quotelink">&gt;&gt;&gt;/t/umblr</a>
    quotes = tuple((a["href"].split("#p")[1] for a in post_msg.select("a.quotelink") if a["href"].startswith("#")))
    # NOT removing quotes anymore
    # remove quotes from msg when line starts with ">>", greentext is one ">"
    # regex more secure? r"\>\>\d+ ?(\(OP\))?\n?"
    # or keep one clean and one full msg?
    post_msg = post_msg.get_text("\n")  # .splitlines()
    # The if should be after the for (unless it is in an if-else ternary operator)
    # [y for y in a if y not in b]
    # This would work however:
    # [y if y not in b else other_value for y in a]
    # post_msg = "\n".join([ln for ln in post_msg if not ln.startswith(">>")])
    return quotes, post_msg


def get_op(soup):
    op = soup.select_one("div.post.op")
    subj = op.select_one("span.subject").text
    # second <a> in span with class subject contains thread nr
    thread_nr = op.select("span.postNum.desktop a")[1].text
    utc = op.select_one("span.dateTime")["data-utc"]
    # _ temp var -> discard first return val
    _, post_msg = get_post_msg(op)
    return thread_nr, subj, post_msg, utc


# ich machs jetzt wie ichs von casey(handmade hero) gelernt habe: "always write your usage code first!"
# right now we're writing the platform layer input code even though we dont have
# the game input processing etc written yet -> this code just a first pass that will probably/definitely be rewritten
# since this is just "temporary" code -> tightening it down/optimizing it now would be wasted effort since we need to 
# change it anyway -> premature optimizing is bad
# casey schreibt das meiste auch in die selbe funktion bis er merkt, dass die funktion zu lang/unübersichtlich wird
# oder er der meinung ist ein teil der funktion wird man immer wieder brauchen -> erst dann nimmt er die funktion/teil der funktion
# und teilt sie auf/macht aus ihm eine eigene funktion
def get_thread_from_html(html):
    thread = {}
    soup = bs4.BeautifulSoup(html, "html.parser")
    posts = soup.select_one("div.thread").find_all("div", class_="postContainer")
    thread_nr, subj, op_msg, thread_utc = get_op(soup)
    logger.info("Viewing thread \"%s\" No. %s. OP:\n%s", subj, thread_nr, op_msg)
    folder_name = input("Input the folder name the thread is going to be downloaded to "
            "(e.g. \"gif_cute\", subfolders work too \"gif_model/Emily Rudd\"):\n")
    # write OP entry
    thread["OP"] = {"thread_nr": thread_nr, "subject": subj, "op_post_msg": op_msg, "utc": thread_utc, "folder_name": folder_name}
    for post in posts:
        utc, post_nr, backlinks = get_post_info(post.select_one("div.postInfo.desktop"))
        file_info = get_file_info(post)
        quotes, post_msg = get_post_msg(post)
        post_dict = {
            "utc": utc,
            "post_nr": post_nr,
            "backlinks": backlinks,
            "file_info": file_info,
            "quotes": quotes,
            "post_msg": post_msg
        }
        # add to thread dict
        thread[post_nr] = post_dict
        # also use fileurl if post hast file as key to point to post_dict
        # works since its a mutable: https://stackoverflow.com/questions/10123853/how-do-i-make-a-dictionary-with-multiple-keys-to-one-value
        if file_info:
            thread[file_info["file_url"]] = post_dict
    thread = generate_backlinks(thread)
    return thread


def generate_backlinks(thread_dict):
    """Generates backlinks to posts based on the quotes in post_dicts of thread_dict

    :param thread_dict: Dict containing keys of postnrs and fileurls with post_dict as values"""
    for key, post_dict in thread_dict.items():
        if "/" in key:
            # key is fileurl
            continue
        elif key == "OP":
            continue
        else:
            for quotenr in post_dict["quotes"]:
                # append postnr of quotING post to quotED posts backlink list
                thread_dict[quotenr]["backlinks"].append(post_dict["post_nr"])
    return thread_dict


def is_sauce_request(post_dict):
    kw = ["sauce", "source", "src", "name", "more", "link", "full"]
    # if any element of test for kw in post_msg is true
    if any(w in post_dict["post_msg"].lower() for w in kw):
        return True
    else:
        return False


def build_msg_backlinks_str(thread, post_dict, max_level=3):
    """Build string of post msg and indented backlinks descending max_level
    :param thread: thread dict
    :param post_dict: post dict
    :param max_level: max level to descend and add backlinks to str, 0 being post msg and 1 direct backlinks"""

    str_lines = []
    # print msg of post with file -> some ppl post src with file
    if post_dict["post_msg"]:
        str_lines.append(post_dict["post_msg"])
    else:
        str_lines.append("No post message!")

    # build backlinks str recursively
    recursive_get_backlinks_str(thread, post_dict, 1, str_lines, max_level)

    return "\n".join(str_lines)


def recursive_get_backlinks_str(thread, post_dict, cur_lvl, output, max_lvl=3):
    """Build backlink str recursively by walking through every backlink and if it has
       backlinks as well call this function again with cur_lvl advanced by one...
       Backlink lines get indented by 5 * cur_lvl to the right and will be appended to
       ouput
       :param thread: thread dict
       :param post_dict: post_dict
       :param cur_lvl: current level of backlink, 0 being starting post that function was first called on
       :param ouput: list to append lines to
       :param max_lvl: how many levels of backlinks get collected"""

    for backlink in post_dict["backlinks"]:
        backlink_post_dict = thread[backlink]
        # append msg of backlink first so order is correct
        if backlink_post_dict["post_msg"]:
            # add separator
            output.append(f"  {'__________':>{10+5*cur_lvl}}")
            # post msg can contain newlines -> make sure 2nd backlinks are padded on
            # newlines as well
            for line in backlink_post_dict["post_msg"].splitlines():
                padding = len(line) + 5 * cur_lvl
                # build str with line padded right to padding nr of chars
                output.append(f"> {line:>{padding}}")
        # only get backlinks if next lvl is still in bounds of max_lvl
        if backlink_post_dict["backlinks"] and (cur_lvl+1 <= max_lvl):
            # dont collect backlinks for posts that have no msg and have a file
            if (not backlink_post_dict["post_msg"] and backlink_post_dict["file_info"]):
                continue
            recursive_get_backlinks_str(thread, backlink_post_dict, cur_lvl+1, output, max_lvl)


def build_rel_backlinks_str(thread, post_dict):
    prints = []
    # print msg of post with file -> some ppl post src with file
    if post_dict["post_msg"]:
        prints.append(post_dict["post_msg"])
    for backlink in post_dict["backlinks"]:
        backlink_post_dict = thread[backlink]
        if backlink_post_dict["post_msg"]:
            is_sauce_req = is_sauce_request(backlink_post_dict)
            # also print that since some ppl use the keywords when posting src
            # -> find more elaborate filter for is_sauce_request?
            prints.append("> {:>{padding}}".format(backlink_post_dict["post_msg"], padding=len(backlink_post_dict["post_msg"])+5))
            if is_sauce_req:
                for backlink_2nd in backlink_post_dict["backlinks"]:
                    # post msg can contain newlines -> make sure 2nd backlinks are padded on
                    # newlines as well
                    for line in thread[backlink_2nd]["post_msg"].splitlines():
                        # insert nr of chars to pad string with kwarg of format func itself
                        prints.append("> {:>{padding}}".format(line, padding=len(line)+10))
            # else clause only needed if we dont print all direct backlinks incl sauce req
            # else:
            #    prints.append("> {:>{padding}}".format(backlink_post_dict["post_msg"], padding=len(backlink_post_dict["post_msg"])+10))
    # if prints:
    #     logger.info("Direct backlinks and replies to src requests:\n%s", "\n".join(prints))
    # else:
    #     logger.info("No backlinks matching criteria!")
    return "\n".join(prints)


def build_export_str(thread, dl_list):
    exp_str_lines = []
    # to continue f string on next line put f in front of it on the following lines as well
    exp_str_lines.append(f"Thread No. {thread['OP']['thread_nr']}: \"{thread['OP']['subject']}\", "
            f"UTC_{thread['OP']['utc']}\n\tSaved to: {thread['OP']['folder_name']}\nOP: \"{thread['OP']['op_post_msg']}\"\n")
    for url in dl_list:
        post_dict = thread[url]
        file_inf = post_dict["file_info"]
        exp_str_lines.append(f"File: \"{file_inf['dl_filename']}.{file_inf['file_ext']}\", {file_inf['file_size']}, {file_inf['file_res']}, "
                f"MD5_b64: \"{file_inf['file_md5_b64']}\", Original filename: \"{file_inf['file_name_orig']}\"\nMessages and Backlinks (indented):")
        exp_str_lines.append(build_msg_backlinks_str(thread, post_dict, max_level=3))
        exp_str_lines.append("\n")
    return "\n".join(exp_str_lines)


def append_to_md5_file(thread, dl_list):  #, thread_folder, sanitized_folder_name):
    final_str_ln = []
    for url in dl_list:
        md5hex = convert_b64str_to_hex(thread[url]["file_info"]["file_md5_b64"])
        # one central md5 file now so its easiert to transfer -> write subfolder(s)
        final_str_ln.append(f"{md5hex} *{thread['OP']['folder_name']}/{thread[url]['file_info']['dl_filename']}.{thread[url]['file_info']['file_ext']}")
    # The first (normpath) strips off any trailing slashes, the second (basename) gives you the last part of the path. 
    # Using only basename gives everything after the last slash, which could be ''
    # md5_path = os.path.join(thread_folder, f"{os.path.basename(os.path.normpath(thread_folder)}.md5")
    # md5_path = os.path.join(thread_folder, f"{sanitized_folder_name}.md5")
    logger.info("Appending md5s!") # to \"%s.md5\"", sanitized_folder_name)
    with open("4chan_dl.md5", "a", encoding="UTF-8") as f:
        # add newline so next append starts on new line
        f.write("\n".join(final_str_ln) + "\n")


thread_re = re.compile(r"https?:\/\/boards\.4chan\.org\/[a-z]+\/thread\/\d+")
def is_4ch_thread_url(url):
    if re.match(thread_re, url):
        return True
    else:
        return False


file_url_4ch_re = re.compile(r"(https?:)?\/\/i\.4cdn\.org\/[a-z]+\/(\d+)\.(\w+)")
def is_4ch_file_url(url):
    if re.match(file_url_4ch_re, url):
        return True
    else:
        return False

def get_new_clipboard(recent):
    """Check clipboard for new contents and returns it if its doesnt match the content of recent
    :param recent: recent content we dont want to count as new clipboard content"""
    try:
        while True:
            tmp_value = pyperclip.paste()
            if tmp_value != recent:
                return tmp_value
            time.sleep(0.1)
    except KeyboardInterrupt:
        raise # reraise exception and handle it in outer scope 


remove_https_re = re.compile("^https?:")
def watch_for_file_urls(thread, prev_dl_list=None):
    """Watch clip for 4chan file urls, once url is found the original filename is copied to
    clipboard and post info with backlinks and backlinks to source requests are printed
    :param thread: thread dict, post_nr and file urls as keys to post_dict"""
    running = True
    # continue with imported dl_list if present
    if prev_dl_list:
        dl_list = prev_dl_list
    else:
        dl_list = []

    print("Watching clipboard for 4chan file urls...")
    recent_value = None
    file_post_dict = None
    while running:
        try:
            recent_value = get_new_clipboard(recent_value)
        except KeyboardInterrupt:
            if file_post_dict:
                # also report final fn on interrupt
                logger.info("File will be downloaded as \"%s.%s\"", file_post_dict["file_info"]["dl_filename"], file_post_dict["file_info"]["file_ext"])
            elif not dl_list:
                whole = input("No file urls copied! Download all file urls in thread: y/n?\n")
                if whole == "y":
                    all_file_urls_thread = []
                    for u in thread.keys():
                        if "/" in u:
                            all_file_urls_thread.append(u)
                            thread[u]["file_info"]["to_download"] = True
                            # set dl_filename, append orig fn
                            thread[u]["file_info"]["dl_filename"]= f"{thread[u]['file_info']['file_name_4ch']}_{thread[u]['file_info']['file_name_orig']}"

                    return all_file_urls_thread
            print("Stopped watching clipboard for 4chan file urls!")
            running = False
        # must be executed if the try clause does not raise an exception
        # so we dont process the file_url from b4 when we stop watching clip
        else:
            if is_4ch_file_url(recent_value):
                # remove https?: from start of url, better to use address without http/https since the copies differ with/without 4chan x
                file_url = re.sub(remove_https_re, "", recent_value)
                # file_url alrdy processed? -> skip.. or use as possibility to rename -> to rename just get rid of this if
                # if file_url not in dl_list:
                # report on final filename if there was a prev file
                if file_post_dict:
                    logger.info("File will be downloaded as \"%s.%s\"", file_post_dict["file_info"]["dl_filename"], file_post_dict["file_info"]["file_ext"])
                if file_url in dl_list:
                    logger.info("File name of %s has been RESET!!!", file_url.split("/")[-1])

                try:
                    file_post_dict = thread[file_url]
                except KeyError:
                    file_post_dict = None
                    print(f"File of url \"{file_url}\" was not found in the thread!")
                # only proceed if file_url is in dict/thread
                else:
                    # append file_url (without http part) of file post to dl list and set to_download
                    dl_list.append(file_url)
                    file_post_dict["file_info"]["to_download"] = True
                    # set dl_filename 
                    file_post_dict["file_info"]["dl_filename"]= file_post_dict['file_info']['file_name_4ch']
                    logger.info("Found file url of file: \"%s\"", file_url.replace("//i.4cdn.org/", ""))
                # else:
                #     print(f"SKIPPED: File of url \"{file_url}\" was already added to the list!")

            elif recent_value == "rename_thread":
                # option to set new folder name when rename_thread is copied
                folder_name = input("Input new folder name:\n")
                thread["OP"]["folder_name"] = folder_name
                print(f"Renamed thread folder to {folder_name}")
                
            elif file_post_dict:
                # sanitize filename for windows, src: https://stackoverflow.com/questions/7406102/create-sane-safe-filename-from-any-unsafe-string by wallyck
                # if after for..in is part of comprehension syntax <-> if..else b4 for..in is pythons equivalent of ternary operator
                # only keep chars if theyre alphanumerical (a-zA-Z0-9) or in the tuple (' ', '_'), replace rest with _
                # reset file name to 4ch name when reset_filename is copied
                if recent_value == "reset_filename":
                    file_post_dict["file_info"]["dl_filename"]= file_post_dict['file_info']['file_name_4ch']
                    print("Filename has been reset!")
                elif recent_value == "remove_file":
                    logger.info("Removing file with filename \"%s\" from download list", file_post_dict["file_info"]["dl_filename"])
                    file_url = file_post_dict["file_info"]["file_url"]
                    # remove only removes first item
                    try:
                        # keep removing until remove returns error -> no element x left
                        while True:
                            dl_list.remove(file_url)
                    except ValueError:
                        logger.debug("Removed all occurences of %s in dl_list", file_url)

                    file_post_dict["file_info"]["to_download"] = False
                    # dl_filename key only gets created once added to dls -> remove it
                    del file_post_dict["file_info"]["dl_filename"]
                    file_post_dict = None
                else:
                    sanitized_clip = sanitize_fn(recent_value)

                    dl_filename = f"{file_post_dict['file_info']['dl_filename']}_{sanitized_clip}"
                    file_post_dict["file_info"]["dl_filename"] = dl_filename
                    print(f"Not a file url -> clipboard was appended to filename: \"{dl_filename}\"")

    # since were working on thread directly and its a mutable type(dict) we dont have
    # to return (but mb more readable)
    # create set to remove duplicates, back to list -> json serializable
    return list(set(dl_list))


def sanitize_fn(name):
    return "".join(c if c.isalnum() or c in (' ', '_', "-", "(", ")") else "_" for c in name).strip()


def watch_for_file_urls_cw(thread):
    """Watch clip for 4chan file urls, once url is found the original filename is copied to
    clipboard and post info with backlinks and backlinks to source requests are printed
    :param thread: thread dict, post_nr and file urls as keys to post_dict"""
    running = True
    watcher = ClipboardWatcher(is_4ch_file_url, None, ROOTDIR, 0.1)

    print("Watching clipboard for 4chan file urls...")
    file_url_recent = None
    while running:
        file_url = None
        try:
            # run_single returns found val matching predciate after first match
            file_url = watcher.run_single(file_url_recent)
        except KeyboardInterrupt:
            watcher.stop()
            print("Stopped watching clipboard for 4chan file urls!")
            running = False
        if file_url:
            # remove https?: from start of url
            # file_url = re.sub(remove_https_re, "", file_url)
            post_dict = thread[file_url]
            logger.info("Found file url of file: \"%s\"", file_url.replace("http://i.4cdn.org/", ""))
            orig_fn = post_dict["file_info"]["file_name_orig"]
            pyperclip.copy(orig_fn) 
            logger.info("Copied original filename to clipboard: %s", orig_fn)
            # print_rel_backlinks(thread, post_dict)
            file_url_recent = file_url


def process_4ch_thread(url):
    html = get_url(url)
    # with open("4chtest.html", "r", encoding="UTF-8") as f:
    #     html = f.read()
    thread = get_thread_from_html(html)
    try:
        dl_list = watch_for_file_urls(thread)
    except Exception as e:
        # i dont rly need dl_list since im setting to_download and dl_filename in mutable dict thats contained inside thread dict
        # instead of using raise UnexpectedCrash from e (gets rid of traceback) use with_traceback
        raise UnexpectedCrash("process_4ch_thread", thread, "Unexpected crash while processing 4ch thread! Program state has been saved, start script with option resume to continue with old state!").with_traceback(e.__traceback__)
    return thread, dl_list


def md5(fname, hex=True):
    # construct a hash object by calling the appropriate constructor function
    hash_md5 = hashlib.md5()
    # open file in read-only byte-mode
    with open(fname, "rb") as f:
        # only read in chunks of size 4096 bytes
        for chunk in iter(lambda: f.read(4096), b""):
            # update it with the data by calling update() on the object
            # as many times as you need to iteratively update the hash
            hash_md5.update(chunk)
    # get digest out of the object by calling digest() (or hexdigest() for hex-encoded string)
    if hex:
        return hash_md5.hexdigest()
    else:
        return hash_md5.digest()


def check_4chan_md5(filename, md5_base64):
    # either convert all md5 when reading posts or convert when checking file -> latter more
    # efficient since were not downloading all files

    # ch_md5_decoded = base64.b64decode(ch_md5)
    # either use  binascii.unhexlify to Return the binary data represented by the hexadecimal string
    # then binascii.a2b_base64(string) -> Convert a block of base64 data back to binary and return
    # the binary data then compare the binary datas
    # return binascii.unhexlify(md5(filname)) == binascii.a2b_base64(md5_base64)
    # shorter: use binary output with digest() and compare to binary of converted b64 str
    return md5(filename, hex=False) == binascii.a2b_base64(md5_base64)

    # OR use base64.b64decode() -> Decode the Base64 encoded bytes-like object or ASCII string s 
    # and return the decoded bytes and compare binary md5 (using .digest())
    # print(base64.b16encode(base64.b64decode(ch_md5)), md5(fn, hex=False))

    # also possible to convert base64 representation of md5 to bytes using binascii.a2b_base64(string)
    # or base64.b64decode(ch_md5) and then convert to hex using binascii.hexlify(data) or 
    # base64.b16encode BUT CAREFUL: funcs in base64 module only operate with uppercase hexadecimal 
    # letters, whereas the functions in binascii work with either case    
    # important to note that the output produced by the encoding functions is always a byte string.
    # To coerce it to Unicode for output, you may need to add an extra decoding step -> .decode("ascii")
    # print(base64.b16encode(base64.b64decode(ch_md5)).decode("ascii").lower(), md5(fn))
    # print(binascii.hexlify(binascii.a2b_base64(ch_md5)).decode("ascii"), md5(fn))


def convert_b64str_to_hex(b64_str):
    return binascii.hexlify(binascii.a2b_base64(b64_str)).decode("ascii")
    
def download(url, dl_path):
    """
    Will download the file to dl_path, return True on success

    :param curfnr: Current file number
    :param maxfnr: Max files to download
    :return: Current file nr(int)
    """
    # get head (everythin b4 last part of path ("/" last -> tail empty, filename or dir(without /) -> tail)) of path
    os.makedirs(os.path.split(dl_path)[0], exist_ok=True)

    try:
        urllib.request.urlretrieve(url, dl_path)  # reporthook=prog_bar_dl)
    except urllib.request.HTTPError as err:
        logger.warning("HTTP Error {}: {}: \"{}\"".format(err.code, err.reason, url))
        return False
    else:
        return True


def cli_yes_no(question_str):
    ans = input(f"{question_str} y/n:\n")
    while True:
        if ans == "n":
            return False
        elif ans == "y":
            return True
        else:
            ans = input(f"\"{ans}\" was not a valid answer, type in \"y\" or \"n\":\n")


def download_thread(thread, dl_list, overwrite=False, retries=1):
    # keep list of successful dls so we only export those in export str
    success_dl = []
    logger.info("Downloading thread No. %s: \"%s\"", thread["OP"]["thread_nr"], thread["OP"]["subject"])
    thread_folder_name = thread["OP"]["folder_name"]
    thread_folder = os.path.join(ROOTDIR, thread_folder_name)
    nr_files_thread = len(dl_list)
    cur_nr = 1
    failed_md5 = []
    for url in dl_list:
        dl_path = os.path.join(thread_folder, f"{thread[url]['file_info']['dl_filename']}.{thread[url]['file_info']['file_ext']}")
        if not os.path.isfile(dl_path) or overwrite:
            # add https part to url, since both http and https work: https is obv. preferred
            # but continue to use url without https? as keys in success_dl list etc.
            furl = f"https:{url}"
            logger.info("Downloading: \"%s\", File %s of %s", furl, cur_nr, nr_files_thread)
            # print(f"Downloading: {url}..., File {cur_nr} of {nr_files_thread}")
            try:
                md5_match = None
                n = 0
                while (md5_match is None or n <= retries) and md5_match is not True:
                    if md5_match is not None:
                        logger.warning("Download failed: either md5 didnt match or there were connection problems! -> Retrying!")

                    if download(furl, dl_path):
                        md5_match = check_4chfile_crc(thread[url]["file_info"], thread_folder)
                    n += 1
                if not md5_match:
                    failed_md5.append(url)
                # we even keep files with failed md5 -> user hast to check them manually first if theyre worth keeping or useless
                success_dl.append(url)
            except Exception as e:
                raise UnexpectedCrash("download_thread", (thread, dl_list), "Unecpected crash while downloading! Program state has been saved, start script with option resume to continue with old state!").with_traceback(e.__traceback__)
        else:
            logger.warning("File already exists, url \"%s\" has been skipped!", url)
        cur_nr += 1

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
    append_to_md5_file(thread, success_dl)  #, thread_folder, sanitized_folder_name)

    return failed_md5


def check_4chfile_crc(file_dict, thread_folder):
    fn = f"{file_dict['dl_filename']}.{file_dict['file_ext']}"
    logger.debug("CRC-Checking file \"%s\"!", fn)
    if check_4chan_md5(os.path.join(thread_folder, fn), file_dict['file_md5_b64']):
        logger.debug("MD5-Check   \"%s\" OK", fn)
        return True
    else:
        logger.warning("MD5-Check   \"%s\" FAILED", fn)
        return False


def check_thread_files_crc(thread, success_dl, thread_folder):
    logger.info("CRC-Checking files!")
    failed_md5 = []
    for url in success_dl:
        fn = f"{thread[url]['file_info']['dl_filename']}.{thread[url]['file_info']['file_ext']}"
        if check_4chan_md5(os.path.join(thread_folder, fn), thread[url]['file_info']['file_md5_b64']):
            logger.debug("MD5-Check   \"%s\" OK", fn)
        else:
            logger.warning("MD5-Check   \"%s\" FAILED", fn)
            failed_md5.append(url)
    if not failed_md5:
        logger.info("CRC-Check successful, all files match corresponding MD5s!")
    else:
        fmd5str = '\n'.join(failed_md5)
        write_to_file(f"Failed MD5s of Thread No. {thread['OP']['thread_nr']}:\n"
                      f"{fmd5str}", os.path.join(thread_folder, "FAILED_MD5.txt"))
        logger.warning("The following files failed CRC-Check:\n%s", fmd5str)

    return failed_md5


def watch_clip_for_4ch_threads():
    """Watch clip for 4chan thread urls, once url is found process_4ch_thread is called,
    returned thread dicts and dl_links (which also are the keys of files to dl in thread dict)
    are appended to internal found list of ClipboardWatcher. After KeyboardInterrupt we
    assign that list to to_dl"""
    to_dl = []
    watcher = ClipboardWatcher(is_4ch_thread_url, process_4ch_thread, ROOTDIR, 0.1)
    try:
        print("Watching clipboard for 4chan thread urls...")
        watcher.run_append_found()
    except KeyboardInterrupt:
        watcher.stop()
        to_dl = watcher.get_found()
        print("Stopped watching clipboard!")
    except Exception:
        # wont be able to add any info since we crashed while info was still in ClipWatcher
        # just reraise so we can handle in outermost scope
        raise

    try:
        dl_multiple_threads(to_dl)
    except Exception:
        raise


def read_from_file(file_path):
    with open(file_path, "r", encoding="UTF-8") as f:
        contents = f.read()
    return contents
    

def export_state_from_dict(program_state):
    # readability indent=4, sort_keys=True
    json_exp_str = json.dumps(program_state, indent=4, sort_keys=True)
    write_to_file(json_exp_str, "crash-exp.json")


def import_state():
    """State list contains tuple(s) of (thread, dl_list) pairs"""
    json_imp = read_from_file("crash-exp.json")
    state = json.loads(json_imp)
    return state


# Default parameter values are evaluated when the function definition is executed. This means that the expression is evaluated once, when the function is defined, and that same “pre-computed” value is used for each call. This is especially important to understand when a default parameter is a mutable object, such as a list or a dictionary: if the function modifies the object (e.g. by appending an item to a list), the default value is in effect modified.
# Lists are a mutable objects; you can change their contents. The correct way to get a default list (or dictionary, or set) is to create it at run time instead, inside the function
# dont use test(a, b=[]) since all funcs calls will use the same list do it like below
def dl_multiple_threads(to_dl, successful_dl_threads=None, overwrite=False):
    if successful_dl_threads is None:
        successful_dl_threads = []

    for thread, dl_list in to_dl:
        # only dl if it wasnt downloaded successfuly b4 crash
        # could also use set functionality and build the difference? but this is fine since there wont be more >5 threads
        if thread["OP"]["thread_nr"] not in successful_dl_threads:
            try:
                # only start dl if file urls were copied from clipboard
                if dl_list:
                    download_thread(thread, dl_list, overwrite=overwrite)
                    successful_dl_threads.append(thread["OP"]["thread_nr"])
            except Exception as e:
                    raise UnexpectedCrash("dl_multiple_threads", (to_dl, successful_dl_threads), "Unexpected crash while downloading multiple 4ch threads! Program state has been saved, start script with option resume to continue with old state!").with_traceback(e.__traceback__)
    # assume all are downloaded
    for thread, _ in to_dl:
        try:
            user_handle_failed_md5(thread, thread["failed_md5"])
        except KeyError:
            continue


def user_handle_failed_md5(thread, failed_md5):
    with open("4chan_dl.md5", "r", encoding="UTF-8") as f:
        root_md5_file = f.read()

    # we already warned b4
    print("Files with failed CRC that you want to keep will get their original md5 (in root md5 file) replaced "
          "by their actual md5, but their original md5 will be stored in 'kept_failed_md5_files.md5'\n"
          "It is recommended to check the files manually -> if the play/look ok -> keep them")
    # cant use \ in {} of f-strings -> either use chr(10) to get \n or assign to var nl="\n" and use that or join b4hand and assign to var
    # nested f-strings dont work somehow if they contain the usage of quotation marks
    i_failed_names = "\n".join((f'({i}) {thread[url]["file_info"]["dl_filename"]}' for i, url in enumerate(failed_md5)))
    keep = input(f"Type in the indexes seperated by \",\" of files to keep in Thread No. {thread['OP']['thread_nr']} "
                 f"with failed CRC-Checks: \"{thread['OP']['subject']}\"\n{i_failed_names}\n")
    keep = [int(i) for i in keep.split(",")]
    kept_failed_lns = []
    for i, url in enumerate(failed_md5):
        file_info = thread[url]["file_info"]
        thread_folder_name = thread["OP"]["folder_name"]
        fn = f"{file_info['dl_filename']}.{file_info['file_ext']}"
        orig_md5 = convert_b64str_to_hex(file_info['file_md5_b64'])

        # check if we want to keep file
        if i in keep:
            actual_md5 = md5(os.path.join(thread_folder_name, fn))
            # replace orig md5 in root md5 file with actual md5
            # WARNING dont only replace orig_md5 since md5 might be in root md5 alrdy (since we dont check for dupes when downloading)
            # -> use md5 *path instead
            # STRING->IMMUTABLE => replace returns the new string with replaced substring -> need to reassign it
            root_md5_file = root_md5_file.replace(f"{orig_md5} *{thread_folder_name}/{fn}", f"{actual_md5} *{thread_folder_name}/{fn}", 1)
            kept_failed_lns.append(f"{orig_md5} *{thread_folder_name}/{fn}")
        else:
            logger.info("Removing \"%s\" from folder and root md5 file", fn)
            os.remove(os.path.join(thread["OP"]["folder_name"], fn))
            root_md5_file = root_md5_file.replace(f"{orig_md5} *{thread_folder_name}/{fn}\n", "", 1)

    if kept_failed_lns:
        append_to_file("\n".join(kept_failed_lns) + "\n", "kept_failed_md5_files.md5")

    with open("4chan_dl.md5", "w", encoding="UTF-8") as w:
        w.write(root_md5_file)




def resume_from_state_dict(state_dict):
    # TODO copy inline comments into docstr
    # four possible keys in state dict 
    # "download_thread" contains one/or only alrdy processed thread
    # "ClipboardWatcher" contains alrdy processed threads and dl_lists, crashed while process_4ch_thread so while watch_for_file_urls
    # "process_4ch_thread" contains latest thread, no dl_list since it crashed while watching for urls b4 returning it
    # "dl_multiple_threads" contains one/multiple already processed threads and dl_lists, saved cause crashed while downloading

    # be CAREFUL where we raise UnexpectedCrash or reraise since that (or reraising UnexpectedCrash)
    # will lead to crash-exp.json to be overwritten and we might have crashed again b4 being done
    # wont be bad if we still collect all the necessary info
    # not raising UnexpectedCrash or not reraising UnexpectedCrash -> wont make it to outer scope where export state would be called -> nothing happens
    keys = state_dict.keys()
    if "dl_multiple_threads" in keys:
        # crashed while downloading multiple threads, all fns and dl_lists alrdy created -> error has to be fixed manually in code/json, supply alrdy successfuly download threads b4 crash as optional argument so they wont get downloaded again (-> duplicates in exp txt and md5)
        logger.info("Continuing with download of multiple threads!")
        to_dl, successful_dl_threads = state_dict["dl_multiple_threads"]
        # reraise here since we might have succesfully downloaded a thread
        try:
            # overwrite old since they might be corrupt
            dl_multiple_threads(to_dl, successful_dl_threads, overwrite=True)
        except Exception:
            raise

    elif "ClipboardWatcher" in keys:
        # was inside watch_clip_for_4ch_threads b4 crash -> continue with watching for urls for latest thrad (use key "process_4ch_thread") then dl all
        # last item in this list isnt actually the thread we working on b4 the crash
        to_dl = state_dict["ClipboardWatcher"]

        try:
            last_thread = state_dict["process_4ch_thread"]
        except KeyError:
            # crashed b4 starting process_4ch_thread
            pass
        else:
            # no dl_list saved use to_download vals to recreate it
            # multiple if statements (and for..in allowed in comprehension) -> stack them after each other
            last_dl_list = recreate_dl_list(last_thread)

            logger.info("Start watching for 4ch_file_urls for latest thread \"%s\" -> will be downloaded with the previously processed threads afterwards!", last_thread["OP"]["thread_nr"])
            # dont try to raise UnexpectedCrash here unless we just supply to_dl again for crash point "ClipboardWatcher" -> few copies we have to do again dont matter?
            last_dl_list = watch_for_file_urls(last_thread, prev_dl_list=last_dl_list)
            to_dl.append((last_thread, last_dl_list))

        logger.info("Continuing with download of multiple threads!")
        # here we can reraise due to successful thread dls
        try:
            # nothing was downloaded b4 crash
            dl_multiple_threads(to_dl)
        except Exception:
            raise

    elif "process_4ch_thread" in keys:
        # 1) single option -> continue with watch file urls
        # 2) as callback in ClipboardWatcher: "ClipboardWatcher"->true, a) continue to watch for file urls for thread(latest) then dl latest+rest from ClipboardWatcher or b) dl(latest) + rest right away
        # 2) alrdy account for when reaching this point (cause of elif "ClipboardWatcher"..)

        last_thread = state_dict["process_4ch_thread"]

        logger.info("Found single thread with no dl_list -> recreating it and starting to watch for 4ch_file_urls again!")
        # no dl_list saved use to_download vals to recreate it
        # multiple if statements (and for..in allowed in comprehension) -> stack them after each other
        last_dl_list = recreate_dl_list(last_thread)
        # dont reraise here
        last_dl_list = watch_for_file_urls(last_thread, prev_dl_list=last_dl_list)

        # just single thread need to reraise since dl_list complete and we land in "download_thread" next resume -> tested OK
        try:
            # nothing dled b4 crash
            download_thread(last_thread, last_dl_list)
            try:
                user_handle_failed_md5(last_thread, last_thread["failed_md5"])
            except KeyError:
                pass
        except Exception:
            raise

    elif "download_thread" in keys:
        # 1) single opt: probably fix error manually -> re-dl
        # 2) from dl_multiple_threads: also have to fix error -> re-dl with rest
        # 2) alrdy accounted for cause of elif "dl_multiple_threads"..
        thread, dl_list = state_dict["download_thread"]

        logger.info("Found failed download -> trying to re-download, old files will be overwritten!")
        # no need to reraise since well just land here again with the same info anyways
        # ovewrite since file dled b4/at crash might be corrupt
        download_thread(thread, dl_list, overwrite=True)
        try:
            user_handle_failed_md5(thread, thread["failed_md5"])
        except KeyError:
            pass


def recreate_dl_list(thread):
    result = []
    for k, post_dict in thread.items():
        if "//" in k:
            try:
                if post_dict["file_info"]["to_download"]:
                    result.append(post_dict["file_info"]["file_url"])
            except KeyError:
                pass

    return result


class UnexpectedCrash(Exception):
    # have dict as class var shared over all instances so we can access dict with all info
    # in outermost scope
    program_state = {}

    def __init__(self, func_name, func_state, *args, **kwargs):
        # Call the base class constructor with the parameters it needs, in python 3 you dont need to do super(Exception, self) anymore
        # first arg is normally msg
        super().__init__(*args, **kwargs)
        # program_state is a class var so we have to access it with ClassName.classvar
        # self.classvar obv creates an instance var of that name and "overwrites" classvar
        # same happens when trying to assign to it from somewhere else (when non-mutable type)
        # class Test: a = 1; a = Test(); a.a = 2 -> Test.a will still be 1 only a.a is 2
        # but it will work with a mutable type (when not assigning but using funcs on that var)
        # class Test: a = []; a = Test(); a.a.append(2); Test.a will have a = [2]
        # when this gets reraised every time its basically just the same as adding the state to
        # a global var (here UnexpectedCrash)
        UnexpectedCrash.program_state[func_name] = func_state 


def main():
    # dont use clipwatch but use thread url as argv -> have to wait for imports when new thread
    cmd_line_arg1 = sys.argv[1]
    if cmd_line_arg1.startswith("http"):
        try:
            thread, dl_list = process_4ch_thread(cmd_line_arg1)
            if dl_list:
                download_thread(thread, dl_list)
            try:
                user_handle_failed_md5(thread, thread["failed_md5"])
            except KeyError:
                pass
        except UnexpectedCrash as e:
            export_state_from_dict(e.program_state)
            raise
    elif cmd_line_arg1 == "watch":
        try:
            watch_clip_for_4ch_threads()
        except UnexpectedCrash as e:
            export_state_from_dict(e.program_state)
            raise
    elif cmd_line_arg1 == "resume":
        state = import_state()
        # we just catch UnexpectedCrash here and then export state so resume_from_state_dict
        # handles when UnexpectedCrash gets raised or reraised to here (have to be careful since we might overwrite old state export that wasnt properly downloaded yet)
        try:
            resume_from_state_dict(state)
        except UnexpectedCrash as e:
            export_state_from_dict(e.program_state)
            raise


if __name__ == "__main__":
    main()
    # md5 b64 test
    # print(check_4chan_md5("4chtest_files/1511725708046.webm", "Omr1x0rvF/zt4RqJcNYarA=="))
    # import pprint
    # with open("test.txt", "w", encoding="UTF-8") as f:
    #     pprint.pprint(thread, stream=f)
    
