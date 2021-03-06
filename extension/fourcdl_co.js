// this is the background_script
// Content scripts and background scripts can't directly access each other's state. However, they can communicate by sending messages. One end sets up a message listener, and the other end can then send it a message.

// then()
/* The Promise API proposes the following:
Each asynchronous task will return a promise object.
Each promise object will have a then function that can take two arguments, a success handler and an error handler.
The success or the error handler in the then function will be called only once, after the asynchronous task finishes.
The then function will also return a promise, to allow chaining multiple calls.
Each handler (success or error) can return a value, which will be passed to the next function as an argument, in the chain of promises.
If a handler returns a promise (makes another asynchronous request), then the next handler (success or error) will be called only after that request is finished.
*/
function messageTab(msg, tabs) {
    // use tabs.sendMessage() to send a message to the content scripts loaded into that tab
    browser.tabs.sendMessage(tabs[0].id, {
        uniques: msg
    });
}

/* use trick to pass more params to chained then: https://stackoverflow.com/questions/32912459/promises-pass-additional-parameters-to-then-chain
Perhaps the most straightforward answer is:

P.then(function(data) { return doWork('text', data); });
Or, since this is tagged ecmascript-6, using arrow functions:

P.then(data => doWork('text', data));

OR 

You can use Function.prototype.bind to create a new function with a value passed to its first argument, like this

P.then(doWork.bind(null, 'text'))
and you can change doWork to,

function doWork(text, data) {
  consoleToLog(data);
}
Now, text will be actually 'text' in doWork and data will be the value resolved by the Promise
*/
function sendResponseToActiveTab(msg) {    
    console.log("To conentjs: " + msg);
    // use tabs.query() to get the currently active tab
    var querying = browser.tabs.query({
        active: true,
        currentWindow: true
    });
    // use trick to pass more params to chained then; data is here the value resolved by the Promise from querying
    querying.then(function(data) { return messageTab(msg, data); });
}

function sendNativeMsg(req) {
    console.log("From conentjs: " + req.file_info);
    var sending = browser.runtime.sendNativeMessage(
        "fourcdl",
        req.file_info);
    sending.then(onResponse, onError);
}

function onResponse(response) {    
    // these msgs only appear when debugging the addon with the addon-debugger
    // -> about:debugging -> check enable addon debugging and click on debug for your addon
    console.log("Received " + response);
    sendResponseToActiveTab(response);
}

function onError(error) {
  console.log(`Error: ${error}`);
}

/*
On a click on the browser action, send the app a message.
*/
/**
Since tabs.executeScript() is an asynchronous function, and to ensure we send message only after listener has been 
added in "page-eater.js", we use onExecuted which will be called after "page-eater.js" executed
*/
browser.browserAction.onClicked.addListener(() => {
    // start content_script identify_uniques.js when icon in the toolbar is clicked
    // irrelevant: Since tabs.executeScript() is an asynchronous function since we are waiting to here back from the conent script
    browser.tabs.executeScript({
      file: "identify_uniques.js"
    });
});
// wait for content script to send msg
browser.runtime.onMessage.addListener(sendNativeMsg);