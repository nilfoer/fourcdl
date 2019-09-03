import os.path

# could also use importlib for this
try:
    import readline
except ImportError:
    # windows doesn't have readline since its gnu only
    try:
        import pyreadline as readline
    except ImportError:
        readline = None  # needed otherwise NameError


def init_autocomplete(files_info_dict):
    if not readline:
        # neither readline nor pyreadline could be imported
        print("Couldn't import readline or pyreadline(windows alternative to python's "
              "stdlib readline!)\nAutocompleting sub-dirs won't be available!")
        return

    dirs = set()
    # files_info_dict is {file_ext: {size: {md5: [fname, fname...]}}}
    for _, size_md5_dict in files_info_dict.items():
        for _, md5_fnames_dict in size_md5_dict.items():
            for _, fname_list in md5_fnames_dict.items():
                dirs.update([os.path.dirname(fname) for fname in fname_list])

    cmpl = create_list_completer(dirs)

    readline.set_completer_delims('\t')
    readline.parse_and_bind("tab: complete")

    readline.set_completer(cmpl)


def create_list_completer(compl_list):
    """
    from: https://gist.github.com/iamatypeofwalrus/5637895
    This is a closure that creates a method that autocompletes from
    the given list.

    Since the autocomplete function can't be given a list to complete from
    a closure is used to create the listCompleter function with a list to complete
    from.
    """
    def list_completer(text, state):
        """
        from set_completer doc:
        The completer function is called as function(text, state), for state in
        0, 1, 2, …, until it returns a non-string value. It should return the
        next possible completion starting with text.
        """
        line = readline.get_line_buffer()

        if not line:
            return [item + " " for item in compl_list][state]

        else:
            return [item + " " for item in compl_list if item.startswith(line)][state]

    return list_completer
