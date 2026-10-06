/* Loaded before every other script and written in ES5, so it still runs on WebViews too old for
   the console. It fills in the one newer DOM method the console relies on and, when the engine
   cannot parse modern syntax at all, replaces the blank page with instructions to update WebView.
   (Strings are bilingual here: i18n.js may not run on such a WebView.) */
(function () {
  "use strict";

  // Element.replaceChildren arrived in Chromium 86; the console calls it everywhere.
  var owners = [window.Element, window.Document, window.DocumentFragment];
  for (var i = 0; i < owners.length; i++) {
    var proto = owners[i] && owners[i].prototype;
    if (proto && typeof proto.replaceChildren !== "function") {
      proto.replaceChildren = function () {
        while (this.lastChild) this.removeChild(this.lastChild);
        if (arguments.length) this.append.apply(this, arguments);
      };
    }
  }

  // Optional chaining and nullish coalescing (Chromium 80) are the newest syntax the scripts use.
  var modern = true;
  try { new Function("var a = null; return a?.b ?? 1;")(); } catch (error) { modern = false; }
  window.AgentConsoleSupported = modern;
  if (modern) return;

  var match = /Chrome\/(\d+)/.exec(navigator.userAgent || "");
  var version = match ? match[1] : "?";
  var chinese = /^zh/i.test(navigator.language || "");
  var title = chinese ? "系统 WebView 版本过旧" : "System WebView is too old";
  var body = chinese
    ? "这台手机的 WebView 内核是 Chrome " + version + "，Agent Workspace 需要 80 或更新版本。请在应用商店更新“Android System WebView”（部分手机叫“WebView 组件”），然后重新打开本应用。"
    : "This phone's WebView is Chrome " + version + "; Agent Workspace needs 80 or newer. Update \"Android System WebView\" from your app store, then reopen the app.";
  var button = chinese ? "更新 WebView" : "Update WebView";

  function show() {
    var panel = document.createElement("div");
    panel.setAttribute("role", "alert");
    panel.style.cssText = "position:fixed;top:0;right:0;bottom:0;left:0;z-index:2147483647;padding:48px 24px;" +
      "background:#fff;color:#18201e;font:16px/1.6 sans-serif;overflow:auto";
    var heading = document.createElement("h1");
    heading.style.cssText = "font-size:20px;margin:0 0 12px";
    heading.textContent = title;
    var text = document.createElement("p");
    text.textContent = body;
    panel.appendChild(heading);
    panel.appendChild(text);
    if (window.AndroidBridge && typeof window.AndroidBridge.openWebViewUpdate === "function") {
      var action = document.createElement("button");
      action.type = "button";
      action.textContent = button;
      action.style.cssText = "margin-top:16px;padding:12px 20px;font-size:16px";
      action.onclick = function () { window.AndroidBridge.openWebViewUpdate(); };
      panel.appendChild(action);
    }
    document.body.appendChild(panel);
  }
  if (document.body) show(); else document.addEventListener("DOMContentLoaded", show);
})();
