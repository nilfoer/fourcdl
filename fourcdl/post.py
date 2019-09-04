import logging
import re

logger = logging.getLogger(__name__)

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

            # make sure were using https later when downloading by prepending https
            # both http and https work: https is obv. preferred
            # but continue to use url without https? as keys in success_dl list etc.
            file_url = f"https:{file_url}"

            file_info = {
                "file_url": file_url,
                "file_name_4ch": file_name_4ch,
                "file_ext": file_ext,
                "file_name_orig": file_name_orig,
                "file_size": file_size,
                "file_res": file_res,
                "file_thumb_url": f"https:{file_thumb['src']}",
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


file_url_4ch_re = re.compile(r"(https?:)?\/\/[a-z0-9]+\.(4cdn|4chan)\.org\/[a-z]+\/(\d+)\.[\w\d]+")
def is_4ch_file_url(url):
    if re.match(file_url_4ch_re, url):
        return True
    else:
        return False

