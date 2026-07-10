const status = document.getElementById("status");

document.getElementById("explain").addEventListener("click", async () => {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  status.classList.remove("err");
  status.textContent = "Starting…";
  chrome.runtime.sendMessage({ type: "explain", tabUrl: tab?.url || "" }, (res) => {
    if (res?.error) { status.classList.add("err"); status.textContent = res.error; return; }
    status.textContent = `Opening explainer for arXiv:${res.id}…`;
    setTimeout(() => window.close(), 600);
  });
});

document.getElementById("opts").addEventListener("click", () => chrome.runtime.openOptionsPage());
document.getElementById("demo").addEventListener("click", () =>
  chrome.tabs.create({ url: chrome.runtime.getURL("viewer.html?demo=1") }));

// preflight: warn early if no model configured
chrome.storage.local.get("config").then(({ config }) => {
  if (!config?.model) {
    status.textContent = "No model configured yet — open Settings, or try the demo.";
  }
});
