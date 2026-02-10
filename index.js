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
      { src: "dist/plugin-instructions.js", ready: () => typeof jsPsychInstructions !== "undefined" },
      { src: "dist/plugin-survey-html-form.js", ready: () => typeof jsPsychSurveyHtmlForm !== "undefined" },
      { src: "dist/plugin-survey-likert.js", ready: () => typeof jsPsychSurveyLikert !== "undefined" },
      { src: "dist/plugin-call-function.js", ready: () => typeof jsPsychCallFunction !== "undefined" },
      { src: "plugin-causal-pair-scale.js", ready: () => typeof jsPsychCausalPairScale !== "undefined" }
    ];

    if (isCognitionHost) {
      // In Cognition editor mode, dependencies should be configured via jsPsych version + External JS/CSS.
      await waitFor(
        () => requiredScripts.every((item) => item.ready()),
        2500
      );
    } else {
      // Local/static fallback: load missing scripts from repository paths.
      for (const item of requiredScripts) {
        if (!item.ready()) {
          await loadScript(item.src);
        }
      }
    }

    const missingDependencies = requiredScripts
      .filter((item) => !item.ready())
      .map((item) => item.src);

    if (missingDependencies.length > 0) {
      const details = isCognitionHost
        ? `Cognition did not preload required files: ${missingDependencies.join(", ")}. Add them under External JS/CSS (or use GitHub deployment).`
        : `Failed to load required files: ${missingDependencies.join(", ")}.`;
      showSetupError("Experiment setup is incomplete.", details);
      throw new Error(details);
    }

    // If experiment logic already ran (e.g. preloaded by host), do not start twice.
    if (typeof getParam === "function") {
      return;
    }

    if (isCognitionHost) {
      const experimentReady = await waitFor(() => typeof getParam === "function", 2500);
      if (!experimentReady) {
        const details =
          "Add experiment.js to External JS/CSS, or paste experiment.js directly into Task Code.";
        showSetupError("Experiment script is missing.", details);
        throw new Error(details);
      }
      return;
    }

    await loadScript("experiment.js");
  }

  run().catch((error) => {
    console.error("Cognition bootstrap failed:", error);
    document.body.innerHTML = `<pre style="white-space: pre-wrap; color: #b91c1c; font-family: sans-serif;">${String(error)}</pre>`;
  });
})();
