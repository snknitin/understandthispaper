const $ = (id) => document.getElementById(id);
const DEFAULT_BASE = { anthropic: "https://api.anthropic.com", openai: "https://openrouter.ai/api/v1" };

chrome.storage.local.get("config").then(({ config }) => {
  if (!config) return;
  $("provider").value = config.provider || "anthropic";
  $("baseUrl").value = config.baseUrl || "";
  $("model").value = config.model || "";
  $("apiKey").value = config.apiKey || "";
});

$("provider").addEventListener("change", () => {
  $("baseUrl").placeholder = DEFAULT_BASE[$("provider").value];
});

$("save").addEventListener("click", async () => {
  const config = {
    provider: $("provider").value,
    baseUrl: $("baseUrl").value.trim() || DEFAULT_BASE[$("provider").value],
    model: $("model").value.trim(),
    apiKey: $("apiKey").value.trim(),
  };
  await chrome.storage.local.set({ config });
  $("saved").textContent = "saved ✓";
  setTimeout(() => ($("saved").textContent = ""), 2000);
});
