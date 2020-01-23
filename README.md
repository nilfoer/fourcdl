# 4CDownloader
Tool for downloading files from 4chan.org. Avoids duplicate downloads (optional) by using the MD5 hashes provided by 4chan.

## Download
Download the source code and extract it into a folder where you want the downloaded files to be stored. Then start a shell in that directory and execute:
```batch
> pip install -r requirements.txt
```
This will install all required 3rd-party packages.

## Usage
Start the script using:
```batch
> fourcdl-runner.py watch
```
It will watch your clipboard for copied 4chan thread urls. Once a thread url is copied you need to supply a folder name to which the thread will be downloaded to. You'll also be asked if you want to only download unique files (don't worry you can still download duplicates later).
```
> fourcdl-runner.py watch
Watching clipboard for 4chan thread urls...
14:15:54 - INFO - Viewing thread "B/W Miniseries" No. 3603904. OP:
[Removed output of OP message]
Input the folder name the thread is going to be downloaded to (e.g. "gif_cute", subfolders work too "gif_model/Emily Rudd"):
> p_bw-photos
Only copy unique files? y/n:
> y
Watching clipboard for 4chan file urls...
Copy cmds are: rename_thread, reset_filename, remove_file !
```
Now you can either press `Ctrl+C` and answer `y` to download the whole thread or only unique files if that was previously selected. 

Or you can copy link addresses of 4chan files in this thread (e.g. use `RMB` then `e` on a thumbnail in Chrome). The original filename and and the MD5 hash will be printed. Now you're in append mode and copied text that isn't a 4chan file URL will be appended to the download file name of the file.
```
14:22:00 - INFO - Found file url of file: "p/1579558670830.jpg" Total of 1 files
Orig-fn: 2020-01-20-0008 | MD5: IzisM5jU8PGq+PDZ7n1Wkw==
Not a file URL -> clipboard was appended to filename:
1579558670830_Fomapan 200_ shot on Canonet QL17_ developed in Cinestill Monobath
```
If the file was already downloaded before the following message will appear:
```
Files with matching md5s:
  p_bw-photos\1579558670830_Fomapan 200_ shot on Canonet QL17_ developed in Cinestill Monobath.jpg
14:33:16 - INFO - ALERT!! File with url p/1579558670830.jpg has been downloaded before!
    Copy add_anyway to add file to downloads!
```
You can decide to move on to the next file or copy `add_anyway` to add the file to the download list.

There are three special commands that when copied trigger an action:
- rename_thread: You will be aske to input a new thread folder name.
- reset_filename: File name will be reset to the file name on the 4chan server.
- remove_file: Last copied file will be removed from download list.

Once you want to stop adding files for this thread press `Ctrl+C` **once** then you can copy the URL of another thread url or press `Ctrl+C` **once** again to start downloading.
```
Stopped watching clipboard for 4chan file URLs!
Stopped watching clipboard for 4chan thread URLs!
14:30:40 - INFO - Downloading thread No. 3603904: "B/W Miniseries"
[...]
14:30:42 - INFO - CRC-Check successful!
14:30:42 - INFO - Writing thread export file "p_bw-photos_2020-01-23.txt"
14:30:42 - INFO - Appending md5s!
```
The script automatically verifies downloaded files and saves their MD5 hashes and names in a file with the name `4chan_dl.md5` in the root directory for convenient use with e.g. `md5sum`. Additionally the hashes and file names are saved in a file named `downloaded_files_info.pickle` for internal use. So don't delete these files!

Before starting the download the file `auto-backup.json` is created containing the program state so you can resume from where you left off should the download unexpectedly crash. On crashing a file named `crash-exp.json` is additionally written for the same reason.

To resume after a crash start the script with `fourcdl-runner.py resume` should there be no `crash-exp.json` file and the script crashed while downloading you can use `fourcdl-runner.py resume auto-backup.json`.