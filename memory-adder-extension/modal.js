function injectModalStyles() {
  if (document.getElementById("prysm-styles")) return;
  const style = document.createElement("style");
  style.id = "prysm-styles";
  style.textContent = `
    @import url('https://fonts.googleapis.com/css2?family=Roboto+Mono:wght@400;500&display=swap');
    .prysm-overlay {
      position: fixed;
      top: 0;
      left: 0;
      width: 100vw;
      height: 100vh;
      background: rgba(0, 0, 0, 0.5);
      display: flex;
      align-items: center;
      justify-content: center;
      z-index: 10000;
    }
    .prysm-modal {
      background: #fff;
      border-radius: 8px;
      padding: 20px;
      width: 90%;
      max-width: 400px;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.2);
      animation: prysmFadeIn 0.3s ease-out;
      font-family: 'Roboto Mono', monospace;
    }
    .prysm-textarea {
      width: 100%;
      height: 300px;
      padding: 10px;
      border: 1px solid #ccc;
      border-radius: 4px;
      resize: vertical;
      margin-bottom: 15px;
      font-size: 1em;
      box-sizing: border-box;
      color: black;
      font-family: inherit;
      background-color: rgb(215 228 240);
    }
    .prysm-buttons {
      text-align: right;
    }
    .prysm-button {
      padding: 10px 15px;
      border: none;
      border-radius: 4px;
      cursor: pointer;
      font-size: 1em;
      transition: background-color 0.2s ease;
      margin-left: 10px;
      font-family: inherit;
    }
    .prysm-button.save {
      background-color: #4CAF50;
      color: #fff;
    }
    .prysm-button.save:hover {
      background-color: #45A049;
    }
    .prysm-button.cancel {
      background-color: #f44336;
      color: #fff;
    }
    .prysm-button.cancel:hover {
      background-color: #e53935;
    }
    @keyframes prysmFadeIn {
      from { opacity: 0; transform: scale(0.9); }
      to { opacity: 1; transform: scale(1); }
    }
  `;
  document.head.appendChild(style);
}

function showMemoryModal(content, type) {
  injectModalStyles();

  const overlay = document.createElement("div");
  overlay.className = "prysm-overlay";

  const modal = document.createElement("div");
  modal.className = "prysm-modal";

  let contentElement;
  if (type === "image") {
    contentElement = document.createElement("img");
    contentElement.src = content;
    contentElement.style.display = "block";
    contentElement.style.maxWidth = "100%";
    contentElement.style.maxHeight = "300px";
    contentElement.style.marginBottom = "15px";
  } else {
    contentElement = document.createElement("textarea");
    contentElement.className = "prysm-textarea";
    contentElement.value = content;
    setTimeout(() => contentElement.focus(), 0);
  }
  modal.appendChild(contentElement);

  const buttonsDiv = document.createElement("div");
  buttonsDiv.className = "prysm-buttons";

  const saveButton = document.createElement("button");
  saveButton.className = "prysm-button save";
  saveButton.textContent = "Save Memory";
  buttonsDiv.appendChild(saveButton);

  const cancelButton = document.createElement("button");
  cancelButton.className = "prysm-button cancel";
  cancelButton.textContent = "Cancel";
  buttonsDiv.appendChild(cancelButton);

  modal.appendChild(buttonsDiv);
  overlay.appendChild(modal);
  document.body.appendChild(overlay);

  cancelButton.addEventListener("click", () => overlay.remove());

  saveButton.addEventListener("click", () => {
    const memory = type === "image" ? null : contentElement.value;
    const media = type === "image" ? content : null;
    chrome.runtime.sendMessage(
      { type: "ADD_MEMORY", data: { memory, media } },
      (response) => {
        if (response?.success) {
          overlay.remove();
        } else {
          const originalText = saveButton.textContent;
          saveButton.textContent = "Error Saving";
          saveButton.style.backgroundColor = "#e53935";
          saveButton.disabled = true;
          setTimeout(() => {
            saveButton.textContent = originalText;
            saveButton.style.backgroundColor = "#4CAF50";
            saveButton.disabled = false;
          }, 5000);
        }
      }
    );
  });

  return overlay;
}

chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
  if (request.type === "SHOW_MODAL") {
    showMemoryModal(request.data, request.memoryType);
    sendResponse({ success: true });
  }
});
