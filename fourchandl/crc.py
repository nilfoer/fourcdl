import os
import logging
import hashlib
import binascii

logger = logging.getLogger(__name__)


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


def check_4chfile_crc(file_path, md5_b64):
    _, fn = os.path.split(file_path)
    logger.debug("CRC-Checking file \"%s\"!", fn)
    if check_4chan_md5(file_path, md5_b64):
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


