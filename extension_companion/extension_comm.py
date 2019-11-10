#!/usr/bin/python -u

# new src: https://github.com/mdn/webextensions-examples/tree/master/native-messaging
# old src: https://developer.mozilla.org/en-US/docs/Mozilla/Add-ons/WebExtensions/Native_messaging
# !!! example from ^^ didnt work -> uses python2
# On the application side, you use standard input to receive messages and standard output to send them.
# Each message is serialized using JSON, UTF-8 encoded and is preceded with a 32-bit value containing the message length in native byte order.
# The maximum size of a single message from the application is 1 MB. The maximum size of a message sent to the application is 4 GB.

# Note that running python with the `-u` flag is required on Windows,
# in order to ensure that stdin and stdout are opened in binary, rather
# than text, mode.

import json
import sys
import struct
import os

from fourcdl.gen_downloaded_files_info import file_unique_converted, import_files_info_pickle, convert_4chan_file_size

DOWNLOADED_FILES_INFO_PATH = r"N:\_archive\test\4c\downloaded_files_info.pickle"
ROOTDIR = os.path.abspath(os.path.dirname(__file__))

# If the native application sends any output to stderr, the browser will redirect it to the browser console.
# -> use this for debugging

# Python 3.x version
# Read a message from stdin and decode it.
def getMessage():
    rawLength = sys.stdin.buffer.read(4)
    if len(rawLength) == 0:
        sys.exit(0)
    messageLength = struct.unpack('@I', rawLength)[0]
    message = sys.stdin.buffer.read(messageLength).decode('utf-8')
    return json.loads(message)

# Encode a message for transmission,
# given its content.
def encodeMessage(messageContent):
    encodedContent = json.dumps(messageContent).encode('utf-8')
    encodedLength = struct.pack('@I', len(encodedContent))
    return {'length': encodedLength, 'content': encodedContent}

# Send an encoded message to stdout
def sendMessage(encodedMessage):
    sys.stdout.buffer.write(encodedMessage['length'])
    sys.stdout.buffer.write(encodedMessage['content'])
    sys.stdout.buffer.flush()

def main():
    # TODO(moe): change to connection-based so we dont have to always reimport a 7mb+ file
    downloaded_files_info = import_files_info_pickle(DOWNLOADED_FILES_INFO_PATH)
    sys.stderr.write("Loaded files info pickle!")
    while True:
        receivedMessage = getMessage()
        # data in stdout has to follow nativeMessaging protocol so for debugging write to stderr
        # stderr output is printed in Firefox Menu -> Web-Dev -> Browser Console, not the debugging console of the extension
        if isinstance(receivedMessage, list):
            sys.stderr.write("Received list")
            uniques = []
            for fid, fname, fsize_str, md5 in receivedMessage:
                converted = convert_4chan_file_size(fsize_str)
                f_type = fname.strip().rsplit(".", 1)[1]
                if file_unique_converted(downloaded_files_info, f_type, converted, md5):
                    uniques.append(fid)
            sendMessage(encodeMessage(uniques))
        elif receivedMessage:
            sys.stderr.write("Received unexpected:", receivedMessage)
            # sendMessage(encodeMessage(["Received: ", receivedMessage]))
