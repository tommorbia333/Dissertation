// Cognition.run entrypoint.
// This bootstraps required assets and then runs experiment.js.
(function bootstrapCognitionTask() {
  const head = document.head || document.getElementsByTagName("head")[0];
  const isCognitionHost = /(^|\.)cognition\.run$/i.test(window.location.hostname);

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

  function waitFor(checkFn, timeoutMs = 2000, pollMs = 50) {
    const start = performance.now();
    return new Promise((resolve) => {
      const tick = () => {
        if (checkFn()) {
          resolve(true);
          return;
        }
        if (performance.now() - start >= timeoutMs) {
          resolve(false);
          return;
        }
        setTimeout(tick, pollMs);
      };
      tick();
    });
  }

  function showSetupError(title, details) {
    const detailsHtml = details
      ? `<p style="margin-top:8px;font-size:14px;line-height:1.45;">${details}</p>`
      : "";
    document.body.innerHTML = `
      <div style="max-width:760px;margin:40px auto;padding:18px 20px;border:1px solid #fecaca;border-radius:10px;background:#fef2f2;color:#7f1d1d;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
        <h2 style="margin:0 0 8px 0;font-size:20px;">${title}</h2>
        ${detailsHtml}
      </div>
    `;
  }

  async function run() {
    ensureStylesheet("dist/jspsych.css");
    ensureStylesheet("style.css");

    const requiredScripts = [
      { src: "dist/jspsych.js", ready: () => typeof initJsPsych === "function" },
      { src: "dist/plugin-html-button-response.js", ready: () => typeof jsPsychHtmlButtonResponse !== "undefined" },
      { src: "