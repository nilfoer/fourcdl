function markUniqueFiles(file_ids) {
    for (var fid of file_ids) {
        // change bgcolor of div with fid to red
        document.getElementById(fid).style.background = "red";
    }
}

function getAllMD5B64() {
    // get array of [div file id, file size in kb or mb, md5_b64]
    var result = [];
    var divs = document.getElementsByClassName("file");
    var size_re = /^.*  \(([\d\.]+ [KMB]+),/;
    
    for (var d of divs) {
        var file_id = d.id;
        var file_info_str = d.getElementsByClassName("file-info")[0].innerText;
        // use regex pattern
        var match = size_re.exec(file_info_str);
        // get caputre grp 1
        var file_size_str = match[1];
        // use css selector to get to img then get md5
        var md5_b64 = d.querySelector("a.fileThumb > img").getAttribute("data-md5");
        result.push([file_id, file_size_str, md5_b64])
    }
    return result;
}

function sendIdMd5Info() {
    id_fs_md5b64_array = getAllMD5B64()
    browser.runtime.sendMessage({
        title: "from identify_uniques.js",
        id_fs_md5b64: id_fs_md5b64_array
    });
    document.body.textContent = "";
    var sent = document.createElement('p');
    sent.textContent = id_fs_md5b64_array;
    document.body.appendChild(sent);
}

// If we want send messages back from the content script to the background page,  we would use runtime.sendMessage()
function markUniquesReceiver(request, sender, sendResponse) {    
    var recieved = document.createElement('p');
    recieved.textContent = request.replacement;
    document.body.appendChild(recieved);
}

sendIdMd5Info();
browser.runtime.onMessage.addListener(markUniquesReceiver);