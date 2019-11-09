import logging
import re

import bs4

from fourcdl.post import get_post_msg, get_post_info, get_file_info

logger = logging.getLogger(__name__)


def get_op(soup):
    op = soup.select_one("div.post.op")
    subj = op.select_one("span.subject").text
    # second <a> in span with class subject contains thread nr
    thread_nr = op.select("span.postNum.desktop a")[1].text
    utc = op.select_one("span.dateTime")["data-utc"]
    # _ temp var -> discard first return val
    _, post_msg = get_post_msg(op)
    return thread_nr, subj, post_msg, utc


FILE_URL_TO_KEY = re.compile(r"^(https?:)?\/\/[a-z0-9]+\.(4cdn|4chan)\.org\/")
def get_key_from_furl(url):
    return re.sub(FILE_URL_TO_KEY, "", url)


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
    # write OP entry
    thread["OP"] = {"thread_nr": thread_nr, "subject": subj, "op_post_msg": op_msg, "utc": thread_utc, "folder_name": None}
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
            # since files may be on different servers remove main domain part
            # (https://i.4cdn.org/ or https://is2.4chan.org/)
            file_url_key = get_key_from_furl(file_info["file_url"])
            thread[file_url_key] = post_dict
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


thread_re = re.compile(r"https?:\/\/boards\.(4chan|4channel)\.org\/[a-z]+\/thread\/\d+")
def is_4ch_thread_url(url):
    if re.match(thread_re, url):
        return True
    else:
        return False
