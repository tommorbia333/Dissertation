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

  async function loadScriptFromCandidates(label, candidateSources) {
    const failures = [];
    for (const source of candidateSources) {
      try {
        await loadScript(source);
        return source;
      } catch (error) {
        failures.push(`${source}: ${error && error.message ? error.message : String(error)}`);
      }
    }
    const details = `${label} could not be loaded from any candidate path (${candidateSources.join(", ")}).`;
    const cause = failures.length > 0 ? ` Attempts: ${failures.join(" | ")}` : "";
    throw new Error(`${details}${cause}`);
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
      ? errorLike.message
      : String(errorLike);
    const details = [
      `<strong>${escapeHtml(contextLabel)}</strong>`,
      `<span>${escapeHtml(message)}</span>`,
      stack ? `<pre style="margin-top:10px;white-space:pre-wrap;font-size:12px;line-height:1.4;">${escapeHtml(stack)}</pre>` : ""
    ].join("<br>");
    showSetupError("A runtime error occurred.", details);
  }

  window.addEventListener("error", (event) => {
    const location = event.filename
      ? `${event.filename}:${event.lineno || 0}:${event.colno || 0}`
      : "unknown location";
    const context = `Uncaught error at ${location}`;
    showRuntimeError(event.error || event.message || "Unknown script error", context);
  });

  window.addEventListener("unhandledrejection", (event) => {
    showRuntimeError(event.reason || "Unhandled promise rejection", "Unhandled promise rejection");
  });

  async function run() {
    ensureStylesheet("dist/jspsych.css");
    ensureStylesheet("style.css");

    const requiredScripts = [
      { src: "dist/jspsych.js", ready: () => typeof initJsPsych === "function" },
      { src: "dist/plugin-html-button-response.js", ready: () => typeof jsPsychHtmlButtonResponse !== "undefined" },
      { src: "dist/plugin-instructions.js", ready: () => typeof jsPsychInstructions !== "undefined" },
      { src: "dist/plugin-survey-html-form.js", ready: () => typeof jsPsychSurveyHtmlForm !== "undefined" },
      { src: "dist/plugin-survey-likert.js", ready: () => typeof jsPsychSurveyLikert !== "undefined" },
      { src: "dist/plugin-call-function.js", ready: () => typeof jsPsychCallFunction !== "undefined" },
      { src: "plugin-causal-pair-scale.js", ready: () => typeof jsPsychCausalPairScale !== "undefined" }
    ];

    // Load missing scripts from repository paths in order.
    for (const item of requiredScripts) {
      if (!item.ready()) {
        await loadScript(item.src);
      }
    }

    const missingDependencies = requiredScripts
      .filter((item) => !item.ready())
      .map((item) => item.src);

    if (missingDependencies.length > 0) {
      const details = `Failed to load required files: ${missingDependencies.join(", ")}.`;
      showSetupError("Experiment setup is incomplete.", details);
      throw new Error(details);
    }

    // If experiment logic already ran (e.g. preloaded by host), do not start twice.
    if (typeof getParam === "function") {
      return;
    }

    const experimentScriptCandidates = [
      "experiment.js",
      "./experiment.js",
      "Experiment/experiment.js",
      "jsPsych/experiment.js"
    ];
    await loadScriptFromCandidates("experiment.js", experimentScriptCandidates);

    if (typeof getParam !== "function") {
      const details =
        "Loaded experiment.js but getParam() was not defined. Ensure experiment.js is the expected file.";
      showSetupError("Experiment script did not initialize.", details);
      throw new Error(details);
    }
  }

  run().catch((error) => {
    console.error("Cognition bootstrap failed:", error);
    showRuntimeError(error, "Bootstrap failure");
  });
})();
