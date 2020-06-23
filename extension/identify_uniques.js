function markUniqueFiles(file_ids) {
    for (var fid of file_ids) {
        // change bgcolor of div with fid to red
        document.getElementById(fid).style.background = "#ffc29c";
    }
}

function getAllMD5B64() {
    // get array of [div file id, file size in kb or mb, md5_b64]
    var result = [];
    var divs = document.getElementsByClassName("file");
    // 4chan-x may add Spoiler info in parens with file size
    var size_re = /^(?:File: )?(.+) \((?:Spoiler, )?([\d\.]+ [KMB]+),/;
    
    for (var d of divs) {
        var file_id = d.id;
        var file_info_str = d.getElementsByClassName("file-info")
        if (file_info_str.length > 0) {
            file_info_str = file_info_str[0].innerText;
        } else {
            // file was deleted
            continue;
        }
        // use regex pattern
        var match = size_re.exec(file_info_str);
        var file_size_str = match[2];
        var file_name = match[1];
        // use css selector to get to img then get md5
        var md5_b64 = d.querySelector("a.fileThumb > img").getAttribute("data-md5");
        result.push([file_id, file_name, file_size_str, md5_b64])
    }
    return result;
}

function sendIdMd5Info() {
    file_info_array = getAllMD5B64()
    browser.runtime.sendMessage({
        title: "from identify_uniques.js",
        file_info: file_info_array
    });
}

// If we want send messages back from the content script to the background page,  we would use runtime.sendMessage()
function markUniquesReceiver(request, sender, sendResponse) {    
    markUniqueFiles(request.uniques);
}

sendIdMd5Info();
browser.runtime.onMessage.addListener(markUniquesReceiver);
