import os
import base64
import json
import pickle
import collections
import logging

from fourchandl.crc import md5


logger = logging.getLogger(__name__)

# src: https://stackoverflow.com/questions/8230315/how-to-json-serialize-sets
# by NeilenMarais
class JSONSetEncoder(json.JSONEncoder):
    """Use with json.dumps to allow Python sets to be encoded to JSON

    Example
    -------

    import json

    data = dict(aset=set([1,2,3]))

    encoded = json.dumps(data, cls=JSONSetEncoder)
    decoded = json.loads(encoded, object_hook=json_as_python_set)
    assert data == decoded     # Should assert successfully

    Any object that is matched by isinstance(obj, collections.Set) will
    be encoded, but the decoded value will always be a normal Python set.

    """

    def default(self, obj):
        if isinstance(obj, collections.Set):
            return dict(_set_object=list(obj))
        else:
            return json.JSONEncoder.default(self, obj)

def json_as_python_set(dct):
    """Decode json {'_set_object': [1,2,3]} to set([1,2,3])

    Example
    -------
    decoded = json.loads(encoded, object_hook=json_as_python_set)

    Also see :class:`JSONSetEncoder`

    """
    if '_set_object' in dct:
        return set(dct['_set_object'])
    return dct


VALID_FILE_EXT = ("webm", "gif", "jpg", "png")
DIR_SUBSTR_EXCLUDE = (".git", "_files", "-Dateien", "fourchandl")
def generate_downloaded_files_info(root_dir):
    files_info = {ext: {} for ext in VALID_FILE_EXT}
    for dirpath, dirnames, fnames in os.walk(root_dir):
        # When topdown is true, the caller can modify the dirnames list in-place (e.g., via del or slice assignment), and walk will only recurse into the subdirectories whose names remain in dirnames; this can be used to prune the search...
        # dirs[:] = value modifies dirs in-place. It changes the contents of the list dirs without changing the container. As help(os.walk) mentions, this is needed if you wish to affect the way os.walk traverses the subdirectories. (dirs = value merely reassigns (or "binds") the variable dirs to a new list, without modifying the original dirs
        # exclude website dl files (thumbnails js html etc.)
        dirnames[:] = [d for d in dirnames if not any(ss in d for ss in DIR_SUBSTR_EXCLUDE)]

        for fn in fnames:
            try:
                name, ext = fn.rsplit(".", 1)
            except ValueError:
                # couldnt split at dot from right -> file not relevant
                continue
            if ext not in VALID_FILE_EXT:
                continue

            full_path = os.path.join(dirpath, fn)
            # output in bytes
            fsize = os.path.getsize(full_path)
            # convert binary output of md5 to b64 -> used later to compare it to 4chan md5 which is stored in b64 encoded ascii string
            # -> its byte string/array then
            # A string is already 'decoded', thus the str class has no 'decode' function.Thus:
            # AttributeError: type object 'str' has no attribute 'decode'
            # If you want to decode a byte array and turn it into a string call:

            # the_thing.decode(encoding)
            # If you want to encode a string (turn it into a byte array) call:

            # the_string.encode(encoding)
            # In terms of the base 64 stuff: Using 'base64' as the value for encoding above yields the error:

            # LookupError: unknown encoding: base64

            # You will see that base64 has two very handy functions, namely b64decode and b64encode. b64 decode returns a byte array and b64encode requires a bytes array.

            # To convert a string into it's base64 representation you first need to convert it to bytes. I like utf-8 but use whatever encoding you need...

            # import base64
            # def stringToBase64(s):
            #     return base64.b64encode(s.encode('utf-8'))

            # def base64ToString(b):
            #     return base64.b64decode(b).decode('utf-8')

            # => decode byte string
            md5_b64 = base64.b64encode(md5(full_path, hex=False)).decode("utf-8")

            # could get the fsize in bytes b4 downloading with d=urlopen(url); fsize=d.info()["Content-Length"]
            # could store dupes here to be able to evaluate them later (mb delete..)
            try:
                # dict with extensions -> dict with fsize in bytes (or convert and round?) -> set() of md5_b64 str
                # tried on 300 files and none were the same size, use range/round instead?
                # do i even need fsize since normally the file size is used so you dont have to
                # compare too many files by md5 (needs to be generated) but 4chan has md5s
                # pre-generated for us so the benefit of using size would only be having
                # smaller sets

                # with 5600 files -> only 114 sets with more than one member (->having same fsize)
                # re: "[0-9a-zA-Z/+]+==",
                files_info[ext][fsize].add(md5_b64)
            except KeyError:
                files_info[ext][fsize] = set((md5_b64,))

    return files_info


def export_files_info_pickle(files_info, filename):
    with open(filename, 'wb') as f:
        # Pickle the 'data' dictionary using the highest protocol available.
        pickle.dump(files_info, f, pickle.HIGHEST_PROTOCOL)


def import_files_info_pickle(filename):
    with open(filename, 'rb') as f:
        # The protocol version used is detected automatically, so we do not
        # have to specify it.
        files_info = pickle.load(f)
    return files_info


def export_files_info_json(files_info, filename):
    json_exp_str = json.dumps(files_info, indent=4, sort_keys=True, cls=JSONSetEncoder)
    with open(filename, "w", encoding="UTF-8") as w:
        w.write(json_exp_str)


def import_files_info_json(filename):
    with open(filename, "r", encoding="UTF-8") as f:
        json_str = f.read()

    # json serializes ints that are dict keys as strings (cause thats how it is in js)
    # 1) just us str(fsize) as lookup or convert them to int
    # 2) converting dictionary to a list of [(k1,v1),(k2,v2)] format while encoding it using json, and converting it back to dictionary after decoding it back
    # 3) add option for dict to decoder func:
    # if isinstance(x, dict):
    #         return {int(k):v for k,v in x.items()}
    # 4) use pickle -> better/faster for only python anyways but unsecure, which doesnt matter here since only b64_md5s and int/float sizes will be stored or use YAML
    files_info = json.loads(json_str, object_hook=json_as_python_set)
    return files_info


def adjust_sizes(files_info, div, dec=0):
    result = {}
    for e in VALID_FILE_EXT:
        # using dict comprehension overwrites old values if key was alrdy present
        # -> use normal for loop
        edic = {}
        for size, val in files_info[e].items():
            new_size = size/div if dec is None else round(size/div, dec)
            # val is alrdy set -> union(new set->contains values from both) or assign if key not in dict yet
            try:
                edic[new_size] = edic[new_size] | val
            except KeyError:
                edic[new_size] = val
        result[e] = edic
    return result


SIZE_DIV = 1024*1024
ROUND_DECS = 2
def file_unique(files_info_dict, f_type, size_bytes, md5_b64, add_if_unique=False):
    size = round(size_bytes/SIZE_DIV, ROUND_DECS)

    try:
        unique = md5_b64 not in files_info_dict[f_type][size]
    except KeyError:
        unique = True
    if unique and add_if_unique:
        add_file_to_files_info(files_info_dict, f_type, size_bytes, md5_b64)
    return unique


def file_unique_converted(files_info_dict, f_type, size, md5_b64):
    try:
        unique = md5_b64 not in files_info_dict[f_type][size]
    except KeyError:
        unique = True

    return unique
    
    
def add_file_to_files_info(files_info_dict, f_type, size_bytes, md5_b64):
    size = round(size_bytes/SIZE_DIV, ROUND_DECS)
    try:
        files_info_dict[f_type][size].add(md5_b64)
    except KeyError:
        files_info_dict[f_type][size] = set((md5_b64,))
    logger.debug("Added file with md5_b64 %s to files_info", md5_b64)


# def main():
#     # imports (import fourchandl.blabla) not working when trying to run this as script:
#     # (also doesnt work if i rename fourchandl.fourchandl to something else so module doesnt match package name
#     # Are you by any chance trying to run a module in the package as a script? You can't do that, as that would mean the file is 'imported' as __main__ and has no context of a package.
#     # -> handle all usage of fourchandl as script using -runner.py file (that uses fourchandl.fourchandl main()) or __main__.py in fourchandl folder
# 
#     # go up one dir with ".."
#     module_parent_dir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "..")
#     files_info = generate_downloaded_files_info(module_parent_dir)
#     # files_info = import_files_info_pickle("downloaded_files_info.pickle")
#     # export_files_info_json(files_info, "downloaded_files_info.json")
#     files_info = adjust_sizes(files_info, SIZE_DIV, dec=ROUND_DECS)
#     export_files_info_pickle(files_info, "downloaded_files_info.pickle")
#     # for e in VALID_FILE_EXT:
#     #     print(e, len(files_info[e].keys()))
# 
# if __name__ == "__main__":
#     main()
