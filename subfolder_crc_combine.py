# combine crc files in subfolders into one file in root
import os

ROOTDIR = os.getcwd()
md5_contents = []
for dirpath, dirnames, filenames in os.walk(ROOTDIR):
    md5_files = [fn for fn in filenames if ".md5" in fn]
    for md5_f in md5_files:
        # dirnames and filenames just basenames -> join with dirpath
        # (rel path from start dir of os.walk)
        with open(os.path.join(dirpath, md5_f), "r", encoding="UTF-8") as f:
            cont = f.read()
        cont_rel = []
        for ln in cont.strip().splitlines():
            md5, fname = ln.split(" *", 1)
            # force use of forward slashes for linux compatablity
            relpath = os.path.relpath(dirpath, ROOTDIR).replace('\\', '/')
            cont_rel.append(f"{md5} *{relpath}/{fname}")
        md5_contents.extend(cont_rel)
md5_contents.append("") # append empty line so we end on newline

with open(os.path.join(ROOTDIR, "4chan_dl.md5"), "w", encoding="UTF-8") as f:
    f.write("\n".join(md5_contents))

# tested 2017-12-25 on 4cha with 1057 md5 lines (counted by searching for * in all opened md5 files in notepad++) -> also 1057 lines in generated md5 file
