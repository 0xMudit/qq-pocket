const config = JSON.parse(document.getElementById("demo-config").textContent);
const byId = (id) => document.getElementById(id);
const reducedMotion = window.matchMedia(
  "(prefers-reduced-motion: reduce)",
).matches;
let running = false;
let lastResult = null;
let lastDuration = 0;
const stages = [...document.querySelectorAll(".stage")];
function status(message) {
  byId("status").textContent = message;
}
function renderResult(data, duration) {
  byId("resulttitle").textContent = data.title;
  byId("checks").replaceChildren(
    ...data.checks.map((check) => {
      const item = document.createElement("li");
      item.textContent = check;
      return item;
    }),
  );
  byId("result").textContent = JSON.stringify(data.record, null, 2);
  byId("latency").textContent = duration.toFixed(0) + " ms";
  byId("outcome").textContent =
    config.kind === "pay"
      ? data.record.balance === 0
        ? "Balanced"
        : "Review"
      : config.kind === "fleet"
        ? data.record.vehicles.length + " vehicles"
        : data.record.status;
  byId("guarantee").textContent =
    config.kind === "pay"
      ? data.record.entries.length + " entries"
      : config.kind === "fleet"
        ? "Stale rejected"
        : data.record.attempts + " attempt(s)";
  if (window.updateMap) window.updateMap(data.record.vehicles);
}
async function replay(data) {
  byId("trace-mode").textContent = "Explaining returned evidence";
  for (let index = 0; index < stages.length; index++) {
    stages.forEach((stage, i) => {
      stage.classList.toggle("active", i === index);
      stage.classList.toggle("done", i < index);
    });
    byId("progress").style.width = (index + 1) * 25 + "%";
    byId("trace-description").textContent = config.steps[index].description;
    if (!reducedMotion) {
      stages[index].animate(
        [
          { transform: "translateY(5px)", opacity: 0.5 },
          { transform: "translateY(0)", opacity: 1 },
        ],
        { duration: 350, easing: "ease-out" },
      );
      await new Promise((resolve) =>
        setTimeout(resolve, Number(byId("speed").value)),
      );
    }
  }
  stages.forEach((stage) => {
    stage.classList.remove("active");
    stage.classList.add("done");
  });
  byId("trace-mode").textContent = "Walkthrough complete";
}
async function execute(useCached = false) {
  if (running) return;
  running = true;
  byId("run").disabled = true;
  byId("replay").disabled = true;
  try {
    if (!useCached) {
      status("Executing the backend scenario…");
      byId("trace-mode").textContent = "Waiting for API response";
      const start = performance.now();
      const response = await fetch("/demo/run", {
        method: "POST",
        signal: AbortSignal.timeout(30000),
      });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Request failed");
      lastDuration = performance.now() - start;
      lastResult = data;
      renderResult(data, lastDuration);
    }
    status(
      "Backend complete. Playing an explanatory walkthrough of the result.",
    );
    await replay(lastResult);
    status(
      "Verified response · " +
        new Date().toLocaleTimeString() +
        " · replay does not make another request",
    );
  } catch (error) {
    status(
      error.name === "TimeoutError"
        ? "The request timed out. Try again shortly."
        : error.message,
    );
    byId("trace-mode").textContent = "Request did not complete";
  } finally {
    running = false;
    byId("run").disabled = false;
    byId("replay").disabled = !lastResult;
  }
}
byId("run").addEventListener("click", () => execute());
byId("replay").addEventListener("click", () => execute(true));
if (!reducedMotion)
  document.querySelector(".intro").animate(
    [
      { opacity: 0, transform: "translateY(14px)" },
      { opacity: 1, transform: "translateY(0)" },
    ],
    { duration: 700, easing: "ease-out" },
  );
