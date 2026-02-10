// Cognition.run entrypoint.
// This bootstraps required assets and then runs experiment.js.
(function bootstrapCognitionTask() {
  const head = document.head || document.getElementsByTagName("head")[0];
  let hasShownFatalError = false;

  function ensureStylesheet(href) {
    const existing = document.querySelector(`link[rel="stylesheet"][href="${href}"]`);
    if (existing) return;
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = href;
    head.appendChild(link);
  }

  function loadScript(src) {
    return new Promise((resolve, reject) => {
      const existing = document.querySelector(`script[src="${src}"]`);
      if (existing) {
        if (existing.dataset.loaded === "true") {
          resolve();
          return;
        }
        existing.addEventListener("load", () => resolve(), { once: true });
        existing.addEventListener("error", () => reject(new Error(`Failed to load ${src}`)), { once: true });
        return;
      }

      const script = document.createElement("script");
      script.src = src;
      script.async = false;
      script.onload = () => {
        script.dataset.loaded = "true";
        resolve();
      };
      script.onerror = () => reject(new Error(`Failed to load ${src}`));
      head.appendChild(script);
    });
  }

  function replaceBodyHtml(html) {
    if (document.body) {
      document.body.innerHTML = html;
      return;
    }
    document.addEventListener(
      "DOMContentLoaded",
      () => {
        document.body.innerHTML = html;
      },
      { once: true }
    );
  }

  function escapeHtml(text) {
    return String(text)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  function showSetupError(title, details) {
    hasShownFatalError = true;
    const detailsHtml = details
      ? `<p style="margin-top:8px;font-size:14px;line-height:1.45;">${details}</p>`
      : "";
    replaceBodyHtml(`
      <div style="max-width:760px;margin:40px auto;padding:18px 20px;border:1px solid #fecaca;border-radius:10px;background:#fef2f2;color:#7f1d1d;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
        <h2 style="margin:0 0 8px 0;font-size:20px;">${title}</h2>
        ${detailsHtml}
      </div>
    `);
  }

  function showRuntimeError(errorLike, contextLabel) {
    if (hasShownFatalError) return;
    const stack =
      errorLike && typeof errorLike === "object" && "stack" in errorLike
        ? errorLike.stack
        : null;
    const message = errorLike && typeof errorLike === "object" && "message" in errorLike