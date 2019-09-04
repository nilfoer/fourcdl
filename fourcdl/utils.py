import logging
import urllib.request

logger = logging.getLogger(__name__)

def write_to_file(wstring, file_path):
    """
    Writes wstring to file_path

    :param wstring: String to write to file
    :param file_path: File path
    :return: None
    """
    with open(file_path, "w", encoding="UTF-8") as w:
        w.write(wstring)


def append_to_file(wstring, file_path):
    """
    Appends wstring to file_path

    :param wstring: String to write to file
    :param file_path: File path
    :return: None
    """
    with open(file_path, "a", encoding="UTF-8") as w:
        w.write(wstring)


def get_url(url):
    html = None

    try:
        site = urllib.request.urlopen(url)
    except urllib.request.HTTPError as err:
        logger.warning("HTTP Error %s: %s: \"%s\"", err.code, err.reason, url)
    else:
        html = site.read().decode('utf-8')
        site.close()
        logger.debug("Getting html done!")

    return html


def sanitize_fn(name):
    return "".join(c if c.isalnum() or c in (' ', '_', "-", "(", ")") else "_" for c in name).strip()


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
