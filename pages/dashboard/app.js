const bridge = window.AstrBotPluginPage;

const state = {
  settingsSchema: {},
  settings: {},
  scripts: [],
  knowledgeEntries: [],
  currentScriptId: "",
};

const els = {
  status: document.getElementById("status"),
  scriptCount: document.getElementById("script-count"),
  scripts: document.getElementById("scripts"),
  scriptSearch: document.getElementById("script-search"),
  newScript: document.getElementById("new-script"),
  scriptForm: document.getElementById("script-form"),
  deleteScript: document.getElementById("delete-script"),
  settingsForm: document.getElementById("settings-form"),
  settingsFields: document.getElementById("settings-fields"),
  exportScripts: document.getElementById("export-scripts"),
  importScripts: document.getElementById("import-scripts"),
  importFilename: document.getElementById("import-filename"),
  importContent: document.getElementById("import-content"),
  knowledgeVisibility: document.getElementById("knowledge-visibility"),
  knowledgeType: document.getElementById("knowledge-type"),
  knowledgeStatus: document.getElementById("knowledge-status"),
  knowledgeList: document.getElementById("knowledge-list"),
};

const scriptFields = {
  title: document.getElementById("script-title"),
  language: document.getElementById("script-language"),
  ruleset_id: document.getElementById("script-ruleset-id"),
  play_mode: document.getElementById("script-play-mode"),
  turn_order_mode: document.getElementById("script-turn-order-mode"),
  theme: document.getElementById("script-theme"),
  summary: document.getElementById("script-summary"),
  background: document.getElementById("script-background"),
  opening_scene: document.getElementById("script-opening"),
  hooks: document.getElementById("script-hooks"),
  tags: document.getElementById("script-tags"),
  gm_notes: document.getElementById("script-notes"),
  rule_nodes: document.getElementById("script-rule-nodes"),
};

const featureFlagKeys = [
  "command_agent_enabled",
  "turn_order_enabled",
  "structured_patch_enabled",
  "dice_requests_enabled",
  "state_patch_enabled",
  "knowledge_enabled",
  "second_pass_resolution_enabled",
];

function showStatus(message, isError = false) {
  els.status.textContent = message;
  els.status.classList.toggle("error", isError);
}

function setActiveTab(tabName) {
  document.querySelectorAll(".tab").forEach((button) => {
    button.classList.toggle("active", button.dataset.tab === tabName);
  });
  document.querySelectorAll(".tab-panel").forEach((panel) => {
    panel.classList.toggle("active", panel.id === `tab-${tabName}`);
  });
}

async function loadDashboard() {
  const data = await bridge.apiGet("dashboard");
  state.settingsSchema = data.settings_schema || {};
  state.settings = data.settings || {};
  state.scripts = data.scripts || [];
  state.knowledgeEntries = data.knowledge_entries || [];
  renderSettings();
  renderScripts();
  renderKnowledge();
  if (state.scripts.length > 0) {
    selectScript(state.scripts[0].script_id);
  } else {
    startNewScript();
  }
}

function renderSettings() {
  els.settingsFields.replaceChildren();
  Object.entries(state.settingsSchema).forEach(([key, definition]) => {
    const row = document.createElement("div");
    row.className = "settings-row";

    const label = document.createElement("label");
    label.className = definition.type === "bool" ? "checkbox-row" : "field";
    label.htmlFor = `setting-${key}`;

    const text = document.createElement("span");
    text.textContent = definition.description || key;

    const input = createSettingInput(key, definition);
    input.id = `setting-${key}`;
    input.name = key;

    if (definition.type === "bool") {
      label.append(input, text);
    } else {
      label.append(text, input);
    }
    row.append(label);

    if (definition.hint) {
      const hint = document.createElement("small");
      hint.textContent = definition.hint;
      row.append(hint);
    }
    els.settingsFields.append(row);
  });
}

function createSettingInput(key, definition) {
  const value = state.settings[key] ?? definition.default ?? "";
  if (definition.type === "text") {
    const input = document.createElement("textarea");
    input.rows = 6;
    input.value = value;
    return input;
  }
  if (definition.type === "int") {
    const input = document.createElement("input");
    input.type = "number";
    input.step = "1";
    input.value = value;
    return input;
  }
  if (definition.type === "bool") {
    const input = document.createElement("input");
    input.type = "checkbox";
    input.checked = value === true || value === 1 || value === "true";
    return input;
  }
  const input = document.createElement("input");
  input.value = value;
  return input;
}

function renderScripts() {
  const query = els.scriptSearch.value.trim().toLowerCase();
  const scripts = state.scripts.filter((script) => {
    const text = `${script.title} ${script.theme} ${(script.tags || []).join(" ")}`;
    return text.toLowerCase().includes(query);
  });
  els.scriptCount.textContent = `${state.scripts.length} 个剧本`;
  els.scripts.replaceChildren();
  if (scripts.length === 0) {
    const empty = document.createElement("p");
    empty.textContent = "暂无匹配剧本。";
    empty.className = "empty";
    els.scripts.append(empty);
    return;
  }
  scripts.forEach((script) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "script-item";
    button.classList.toggle("active", script.script_id === state.currentScriptId);
    button.addEventListener("click", () => selectScript(script.script_id));

    const title = document.createElement("strong");
    title.textContent = script.title || "未命名剧本";
    const meta = document.createElement("span");
    meta.textContent = `${script.language || "zh"} · ${playModeLabel(script.play_mode)} · ${rulesetLabel(script.ruleset_id)} · ${turnOrderModeLabel(script.turn_order_mode)} · ${script.theme || script.title || ""}`;
    button.append(title, meta);
    els.scripts.append(button);
  });
}

function playModeLabel(mode) {
  if (mode === "simple") {
    return "简易";
  }
  if (mode === "custom") {
    return "自定义";
  }
  return "进阶";
}

function rulesetLabel(rulesetId) {
  return rulesetId === "coc7_lite" ? "CoC 7e Lite" : "d20 Lite";
}

function turnOrderModeLabel(mode) {
  return mode === "soft" ? "玩家软顺序" : "LLM 主持";
}

function renderKnowledge() {
  const visibility = els.knowledgeVisibility.value;
  const type = els.knowledgeType.value;
  const status = els.knowledgeStatus.value;
  const entries = state.knowledgeEntries.filter((entry) => {
    if (visibility && entry.visibility !== visibility) {
      return false;
    }
    if (type && entry.type !== type) {
      return false;
    }
    if (status && entry.status !== status) {
      return false;
    }
    return true;
  });
  els.knowledgeList.replaceChildren();
  if (entries.length === 0) {
    const empty = document.createElement("p");
    empty.textContent = "暂无匹配战役记忆。";
    empty.className = "empty";
    els.knowledgeList.append(empty);
    return;
  }
  entries.forEach((entry) => {
    const item = document.createElement("article");
    item.className = "knowledge-item";

    const title = document.createElement("strong");
    title.textContent = entry.title || entry.text || entry.id || "未命名记忆";
    const meta = document.createElement("span");
    meta.textContent = `${entry.type || "-"} · ${entry.visibility || "-"} · ${entry.status || "-"}`;
    const body = document.createElement("span");
    body.textContent = entry.summary || entry.detail || entry.text || "";

    item.append(title, meta);
    if (body.textContent) {
      item.append(body);
    }
    els.knowledgeList.append(item);
  });
}

function selectScript(scriptId) {
  const script = state.scripts.find((item) => item.script_id === scriptId);
  if (!script) {
    startNewScript();
    return;
  }
  state.currentScriptId = script.script_id;
  scriptFields.title.value = script.title || "";
  scriptFields.language.value = script.language || "zh";
  scriptFields.ruleset_id.value = script.ruleset_id || "d20_lite";
  scriptFields.play_mode.value = script.play_mode || "advanced";
  scriptFields.turn_order_mode.value = script.turn_order_mode || "llm_gm";
  scriptFields.theme.value = script.theme || "";
  scriptFields.summary.value = script.summary || "";
  scriptFields.background.value = script.background || "";
  scriptFields.opening_scene.value = script.opening_scene || "";
  scriptFields.hooks.value = (script.hooks || []).join("\n");
  scriptFields.tags.value = (script.tags || []).join(", ");
  scriptFields.gm_notes.value = script.gm_notes || "";
  scriptFields.rule_nodes.value = formatRuleNodes(script.rule_nodes || []);
  applyFeatureFlags(script.feature_flags || defaultFeatureFlags(scriptFields.play_mode.value));
  updateFeatureFlagVisibility();
  els.deleteScript.disabled = false;
  renderScripts();
}

function startNewScript() {
  state.currentScriptId = "";
  Object.values(scriptFields).forEach((field) => {
    field.value = "";
  });
  scriptFields.language.value = "zh";
  scriptFields.ruleset_id.value = "d20_lite";
  scriptFields.play_mode.value = "advanced";
  scriptFields.turn_order_mode.value = "llm_gm";
  scriptFields.rule_nodes.value = "[]";
  applyFeatureFlags(defaultFeatureFlags("advanced"));
  updateFeatureFlagVisibility();
  els.deleteScript.disabled = true;
  renderScripts();
}

function collectScriptPayload() {
  const payload = {
    title: scriptFields.title.value.trim(),
    language: scriptFields.language.value,
    ruleset_id: scriptFields.ruleset_id.value,
    play_mode: scriptFields.play_mode.value,
    turn_order_mode: scriptFields.turn_order_mode.value,
    theme: scriptFields.theme.value.trim(),
    summary: scriptFields.summary.value.trim(),
    background: scriptFields.background.value.trim(),
    opening_scene: scriptFields.opening_scene.value.trim(),
    hooks: splitLines(scriptFields.hooks.value),
    gm_notes: scriptFields.gm_notes.value.trim(),
    tags: splitTags(scriptFields.tags.value),
    rule_nodes: parseRuleNodes(scriptFields.rule_nodes.value),
    feature_flags: collectFeatureFlags(),
  };
  if (state.currentScriptId) {
    payload.script_id = state.currentScriptId;
  }
  return payload;
}

function defaultFeatureFlags(mode) {
  const enabled = mode !== "simple";
  return Object.fromEntries(featureFlagKeys.map((key) => [key, enabled]));
}

function featureFlagInputs() {
  return Array.from(document.querySelectorAll("[data-feature-flag]"));
}

function applyFeatureFlags(flags) {
  const values = flags || {};
  const defaults = defaultFeatureFlags(scriptFields.play_mode.value || "advanced");
  featureFlagInputs().forEach((input) => {
    const key = input.dataset.featureFlag;
    input.checked = values[key] ?? defaults[key] ?? true;
  });
}

function collectFeatureFlags() {
  const flags = {};
  featureFlagInputs().forEach((input) => {
    flags[input.dataset.featureFlag] = input.checked;
  });
  return flags;
}

function updateFeatureFlagVisibility() {
  const fieldset = document.getElementById("script-feature-flags");
  fieldset.hidden = scriptFields.play_mode.value !== "custom";
}

function splitLines(value) {
  return value
    .split(/\r?\n/)
    .map((item) => item.trim().replace(/^[-*+]\s*/, ""))
    .filter(Boolean);
}

function splitTags(value) {
  return value
    .split(/[,，、]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function formatRuleNodes(ruleNodes) {
  return JSON.stringify(ruleNodes || [], null, 2);
}

function parseRuleNodes(value) {
  const text = value.trim();
  if (!text) {
    return [];
  }
  const parsed = JSON.parse(text);
  if (Array.isArray(parsed)) {
    return parsed.filter((item) => item && typeof item === "object" && !Array.isArray(item));
  }
  if (parsed && typeof parsed === "object") {
    return [parsed];
  }
  throw new Error("检定节点必须是 JSON 对象或对象数组。");
}

async function saveScript(event) {
  event.preventDefault();
  const payload = collectScriptPayload();
  if (!payload.title) {
    showStatus("剧本标题不能为空。", true);
    scriptFields.title.focus();
    return;
  }
  const result = await bridge.apiPost("scripts/save", { script: payload });
  await refreshScripts(result.script.script_id);
  showStatus("剧本已保存。");
}

async function deleteCurrentScript() {
  if (!state.currentScriptId) {
    return;
  }
  const confirmed = window.confirm("删除后无法从 WebGUI 恢复，确认删除这个剧本？");
  if (!confirmed) {
    return;
  }
  await bridge.apiPost("scripts/delete", { script_id: state.currentScriptId });
  await refreshScripts("");
  showStatus("剧本已删除。");
}

async function refreshScripts(selectedId) {
  const data = await bridge.apiGet("scripts");
  state.scripts = data.scripts || [];
  renderScripts();
  if (selectedId) {
    selectScript(selectedId);
  } else if (state.scripts.length > 0) {
    selectScript(state.scripts[0].script_id);
  } else {
    startNewScript();
  }
}

async function saveSettings(event) {
  event.preventDefault();
  const payload = {};
  els.settingsFields.querySelectorAll("[name]").forEach((input) => {
    payload[input.name] = input.type === "checkbox" ? input.checked : input.value;
  });
  const result = await bridge.apiPost("settings/save", payload);
  state.settings = result.settings || {};
  renderSettings();
  showStatus("设置已保存。");
}

async function importScripts() {
  const content = els.importContent.value.trim();
  if (!content) {
    showStatus("导入内容不能为空。", true);
    els.importContent.focus();
    return;
  }
  const result = await bridge.apiPost("scripts/import", {
    filename: els.importFilename.value.trim(),
    content,
  });
  const imported = result.scripts || [];
  await refreshScripts(imported[0]?.script_id || "");
  showStatus(`已导入 ${imported.length} 个剧本。`);
}

async function exportScripts() {
  await bridge.download("scripts/export", {}, "scenario_scripts.json");
  showStatus("剧本 JSON 已导出。");
}

function bindEvents() {
  document.querySelectorAll(".tab").forEach((button) => {
    button.addEventListener("click", () => setActiveTab(button.dataset.tab));
  });
  els.scriptSearch.addEventListener("input", renderScripts);
  els.newScript.addEventListener("click", startNewScript);
  scriptFields.play_mode.addEventListener("change", () => {
    applyFeatureFlags(defaultFeatureFlags(scriptFields.play_mode.value));
    updateFeatureFlagVisibility();
  });
  els.scriptForm.addEventListener("submit", (event) => runAction(() => saveScript(event)));
  els.deleteScript.addEventListener("click", () => runAction(deleteCurrentScript));
  els.settingsForm.addEventListener("submit", (event) => runAction(() => saveSettings(event)));
  els.importScripts.addEventListener("click", () => runAction(importScripts));
  els.exportScripts.addEventListener("click", () => runAction(exportScripts));
  els.knowledgeVisibility.addEventListener("change", renderKnowledge);
  els.knowledgeType.addEventListener("change", renderKnowledge);
  els.knowledgeStatus.addEventListener("change", renderKnowledge);
}

async function runAction(action) {
  try {
    showStatus("处理中...");
    await action();
  } catch (error) {
    showStatus(error.message || "操作失败。", true);
  }
}

async function boot() {
  if (!bridge) {
    showStatus("当前页面没有 AstrBot bridge，无法连接插件后端。", true);
    return;
  }
  bindEvents();
  await bridge.ready();
  await loadDashboard();
  showStatus("已加载。");
}

boot().catch((error) => {
  showStatus(error.message || "页面加载失败。", true);
});
