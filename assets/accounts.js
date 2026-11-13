"use strict";
const $ = (id) => document.getElementById(id);
const esc = (value) =>
  String(value ?? "").replace(
    /[&<>"']/g,
    (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[
        c
      ],
  );
const stamp = (value) =>
  value ? new Date(value * 1000).toLocaleString() : "Never";
const money = (value, currency = "INR") =>
  new Intl.NumberFormat(undefined, { style: "currency", currency }).format(
    value / 100,
  );
let account = null;
let toastTimer;
function toast(message) {
  $("toast").textContent = message;
  $("toast").hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => ($("toast").hidden = true), 6500);
}
async function api(path, options = {}) {
  const response = await fetch("/api" + path, {
    credentials: "same-origin",
    ...options,
    headers: { "Content-Type": "application/json", ...options.headers },
  });
  let data;
  try {
    data = await response.json();
  } catch {
    throw Error("The server returned an unexpected response.");
  }
  if (!response.ok) {
    const detail =
      typeof data.detail === "string"
        ? data.detail
        : Array.isArray(data.detail)
          ? data.detail.map((x) => x.msg).join("; ")
          : "Request failed";
    throw Error(detail);
  }
  return data;
}
const post = (path, data = {}) =>
  api(path, { method: "POST", body: JSON.stringify(data) });
function openDialog(id) {
  $(id).showModal();
}
document.addEventListener("click", (event) => {
  const close = event.target.closest("[data-close]");
  if (close) close.closest("dialog").close();
});
async function copy(value) {
  try {
    await navigator.clipboard.writeText(value);
    toast("Copied to clipboard");
  } catch {
    $("secret-output").value = value;
    openDialog("secret-dialog");
  }
}
function reveal(value) {
  $("secret-output").value = value;
  openDialog("secret-dialog");
}
function enter(user) {
  account = user;
  $("auth-view").hidden = true;
  $("workspace").hidden = false;
  document
    .querySelectorAll("[data-username]")
    .forEach((x) => (x.textContent = user.username));
  $("shared-notice").hidden = user.id !== "demo";
  document.dispatchEvent(new Event("account-ready"));
}
async function login(username, password) {
  const user = await post("/auth/login", { username, password });
  enter(user);
}
$("auth-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const button = $("auth-submit");
  button.disabled = true;
  $("auth-error").textContent = "";
  try {
    const username = $("username").value.trim(),
      password = $("password").value;
    if ($("auth-mode").value === "register")
      await post("/auth/register", { username, password });
    await login(username, password);
  } catch (error) {
    $("auth-error").textContent = error.message;
  } finally {
    button.disabled = false;
  }
});
$("toggle-auth").onclick = () => {
  const register = $("auth-mode").value !== "register";
  $("auth-mode").value = register ? "register" : "login";
  $("auth-title").textContent = register
    ? "Create your workspace"
    : "Welcome back";
  $("auth-submit").textContent = register ? "Create account" : "Sign in";
  $("toggle-auth").textContent = register
    ? "Already have an account? Sign in"
    : "New here? Create an account";
  $("password").autocomplete = register ? "new-password" : "current-password";
};
$("demo-login").onclick = async () => {
  const button = $("demo-login");
  button.disabled = true;
  try {
    const creds = await api("/auth/demo");
    $("username").value = creds.username;
    $("password").value = creds.password;
    await login(creds.username, creds.password);
  } catch (error) {
    $("auth-error").textContent = error.message;
  } finally {
    button.disabled = false;
  }
};
document.querySelectorAll("[data-logout]").forEach(
  (button) =>
    (button.onclick = async () => {
      try {
        await post("/auth/logout");
        location.href = "/";
      } catch (error) {
        toast(error.message);
      }
    }),
);
async function loadKeys() {
  const keys = await api("/auth/keys");
  $("key-list").innerHTML = keys.length
    ? keys
        .map(
          (k) =>
            '<div class="row notice"><span>' +
            esc(k.label) +
            "<br><small>Expires " +
            esc(stamp(k.expires)) +
            '</small></span><button class="danger" data-revoke="' +
            esc(k.digest) +
            '">Revoke</button></div>',
        )
        .join("")
    : "<p>No API keys yet.</p>";
}
document.querySelectorAll("[data-keys]").forEach(
  (button) =>
    (button.onclick = async () => {
      try {
        await loadKeys();
        openDialog("keys-dialog");
      } catch (error) {
        toast(error.message);
      }
    }),
);
$("key-form").onsubmit = async (event) => {
  event.preventDefault();
  try {
    const result = await post("/auth/keys", { label: $("key-label").value });
    reveal(result.token);
    await loadKeys();
    $("key-form").reset();
  } catch (error) {
    toast(error.message);
  }
};
$("key-list").onclick = async (event) => {
  const button = event.target.closest("[data-revoke]");
  if (!button) return;
  try {
    await api("/auth/keys/" + button.dataset.revoke, { method: "DELETE" });
    await loadKeys();
    toast("Key revoked");
  } catch (error) {
    toast(error.message);
  }
};
$("copy-secret").onclick = () => copy($("secret-output").value);
async function boot() {
  if (location.pathname.startsWith("/checkout/")) {
    document.dispatchEvent(new Event("checkout-ready"));
    return;
  }
  try {
    enter(await api("/auth/me"));
  } catch {
    $("auth-view").hidden = false;
    $("workspace").hidden = true;
  }
  try {
    const creds = await api("/auth/demo");
    $("demo-credentials").textContent = creds.username + " / " + creds.password;
  } catch {}
}
document.addEventListener("DOMContentLoaded", boot);
