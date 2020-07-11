function markFiles(fid_fnlist) {
    // delete all previous file listings that might exist from prev runs
    for(let n of document.querySelectorAll(".fcdl-file-listing"))
        n.remove();

    Object.keys(fid_fnlist).forEach(function(key) {
        // fids as keys here
        // e.g. f4269593 = id of .file div
        // post divs of form p4269593
        let post_div = document.getElementById("p" + key.slice(1));
        let file_text_container = document.getElementById(key).querySelector(".fileText");
        let file_list = fid_fnlist[key];
        if(file_list == null) {
            post_div.style.background = "#f0c7ae";
        } else {
            let file_listing = document.createElement("div");
            file_listing.classList.add("fcdl-file-listing");
            file_listing.style.backgroundColor = "#fff";
            file_listing.style.padding = "3px 5px";
            file_listing.style.margin = "5px 0";
            file_listing.style.display = "table"; // so we dont take full width of the container
            // only needed for span not div file_listing.appendChild(document.createElement("br"));
            for(let fn of file_list) {
                // append supports multiple DOMStrings or nodes
                file_listing.append(fn, document.createElement("br"));
            }
            file_text_container.append(file_listing);
        }
    });
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
function markFilesReceiver(request, sender, sendResponse) {    
    markFiles(request.uniques);
}

sendIdMd5Info();
browser.runtime.onMessage.addListener(markFilesReceiver);
