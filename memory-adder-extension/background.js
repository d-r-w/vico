chrome.runtime.onInstalled.addListener(() => {
  chrome.contextMenus.create({
    id: "prysmAddMemory",
    title: "PrysM: Text Memory",
    contexts: ["selection"]
  });
  chrome.contextMenus.create({
    id: "prysmCaptureScreenshot",
    title: "PrysM: Screenshot Memory",
    contexts: ["page", "selection"]
  });
});

chrome.contextMenus.onClicked.addListener((info, tab) => {
  if (!tab?.id) return;

  if (info.menuItemId === "prysmCaptureScreenshot") {
    chrome.tabs.captureVisibleTab(
      tab.windowId,
      { format: "png" },
      (dataUrl) => {
        if (chrome.runtime.lastError) {
          console.error(chrome.runtime.lastError.message);
          return;
        }
        chrome.tabs.sendMessage(tab.id, {
          type: "SHOW_MODAL",
          memoryType: "image",
          data: dataUrl
        });
      }
    );
  } else if (info.menuItemId === "prysmAddMemory" && info.selectionText) {
    chrome.tabs.sendMessage(tab.id, {
      type: "SHOW_MODAL",
      memoryType: "text",
      data: info.selectionText
    });
  }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
  if (message.type === "ADD_MEMORY") {
    // Do not attempt to use async/await here - Manifest V3 does NOT allow it
    sendToPrysm(message.data)
      .then((result) => {
        sendResponse(result);
      })
      .catch((error) => {
        sendResponse({ success: false, error: error.toString() });
      });
    return true; // Indicates async response
  }
});

async function sendToPrysm(memory) {
  const apiUrl = "http://localhost:3000/api/memories";
  try {
    const response = await fetch(apiUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(memory)
    });
    if (!response.ok) {
      throw new Error("Response not ok");
    }
    return { success: true };
  } catch (error) {
    console.error(error);
    return { success: false, error: "Network Error" };
  }
}
