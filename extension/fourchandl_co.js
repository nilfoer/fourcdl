function onResponse(response) {
  console.log("Received " + response); // these msgs only appear when debugging the addon with the addon-debugger
  // -> about:debugging -> check enable addon debugging and click on debug for your addon
}

function onError(error) {
  console.log(`Error: ${error}`);
}

/*
On a click on the browser action, send the app a message.
*/
browser.browserAction.onClicked.addListener(() => {
  console.log("Sending:  ping");
  var sending = browser.runtime.sendNativeMessage(
    "fourchandl",
    "ping");
  sending.then(onResponse, onError);
});