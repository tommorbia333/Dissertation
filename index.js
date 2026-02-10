// Cognition.run entrypoint.
// This bootstraps required assets and then runs experiment.js.
(function bootstrapCognitionTask() {
  const head = document.head || document.getElementsByTagName("head")[0];

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

    for (const item of requiredScripts) {
      if (!item.ready()) {
        await loadScript(item.src);
      }
    }

    // If experiment logic already ran (e.g. preloaded by host), do not start twice.
    if (typeof getParam === "function") {
      return;
    }

    await loadScript("experiment.js");
  }

  run().catch((error) => {
    console.error("Cognition bootstrap failed:", error);
    document.body.innerHTML = `<pre style="white-space: pre-wrap; color: #b91c1c; font-family: sans-serif;">${String(error)}</pre>`;
  });
})();
