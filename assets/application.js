let jobs = [];
let selectedJob = null;
let submitKey = crypto.randomUUID();
const examples = {
  sum: "[12,24,36]",
  sha256: "Your text to hash",
  text_stats: "A useful background task.\nCount these words and lines.",
  json_format: '{"project":"Pocket","ready":true}',
};
function renderJobs() {
  for (const state of ["queued", "running", "succeeded", "dead"])
    $(state + "-count").textContent = jobs.filter(
      (j) => j.status === state,
    ).length;
  const query = $("job-search").value.toLowerCase();
  const filtered = jobs.filter(
    (j) =>
      (!$("job-filter").value || j.status === $("job-filter").value) &&
      (j.id.includes(query) || j.task.includes(query)),
  );
  $("jobs-empty").hidden = filtered.length > 0;
  $("job-rows").innerHTML = filtered
    .map(
      (j) =>
        "<tr><td><strong>" +
        esc(j.task) +
        '</strong><br><span class="mono muted">' +
        esc(j.id.slice(0, 8)) +
        '</span></td><td><span class="status ' +
        esc(j.status) +
        '">' +
        esc(j.status) +
        "</span></td><td>" +
        j.attempts +
        ' / 3</td><td class="muted">' +
        esc(stamp(j.created)) +
        '</td><td><button class="ghost" data-job="' +
        j.id +
        '">Inspect →</button></td></tr>',
    )
    .join("");
}
async function refreshJobs() {
  jobs = await api("/jobs");
  renderJobs();
  if (selectedJob && $("job-detail").open) showJob(selectedJob, false);
}
function showJob(id, open = true) {
  selectedJob = id;
  const job = jobs.find((j) => j.id === id);
  if (!job) return;
  $("job-detail-content").innerHTML =
    '<dl class="detail-list"><dt>ID</dt><dd class="mono">' +
    esc(job.id) +
    "</dd><dt>Status</dt><dd>" +
    esc(job.status) +
    "</dd><dt>Attempts</dt><dd>" +
    job.attempts +
    "</dd><dt>Available</dt><dd>" +
    esc(stamp(job.available)) +
    "</dd></dl><label>Input</label><pre>" +
    esc(job.payload) +
    "</pre><label>Result</label><pre>" +
    esc(job.result ?? "Awaiting execution") +
    "</pre>" +
    (job.error ? "<label>Error</label><pre>" + esc(job.error) + "</pre>" : "");
  $("job-detail-actions").innerHTML =
    job.status === "queued"
      ? '<button class="danger" data-action="cancel">Cancel queued job</button>'
      : ["dead", "cancelled"].includes(job.status)
        ? '<button data-action="retry">Retry job</button>'
        : "";
  if (open) openDialog("job-detail");
}
$("new-job").onclick = () => openDialog("job-dialog");
$("job-task").onchange = () => {
  $("job-payload").value = examples[$("job-task").value];
  submitKey = crypto.randomUUID();
};
$("job-payload").oninput = () => (submitKey = crypto.randomUUID());
$("job-delay").oninput = () => (submitKey = crypto.randomUUID());
$("job-form").onsubmit = async (event) => {
  event.preventDefault();
  $("submit-job").disabled = true;
  try {
    await post("/jobs", {
      task: $("job-task").value,
      payload: $("job-payload").value,
      delay_seconds: Number($("job-delay").value),
      idempotency_key: submitKey,
    });
    submitKey = crypto.randomUUID();
    $("job-dialog").close();
    toast("Job enqueued. Processing will continue in the background.");
    await refreshJobs();
  } catch (error) {
    toast(error.message);
  } finally {
    $("submit-job").disabled = false;
  }
};
$("job-rows").onclick = (event) => {
  const button = event.target.closest("[data-job]");
  if (button) showJob(button.dataset.job);
};
$("job-detail-actions").onclick = async (event) => {
  const button = event.target.closest("[data-action]");
  if (!button) return;
  button.disabled = true;
  try {
    await post("/jobs/" + selectedJob + "/" + button.dataset.action);
    await refreshJobs();
    toast("Job updated");
  } catch (error) {
    toast(error.message);
    button.disabled = false;
  }
};
$("job-search").oninput = renderJobs;
$("job-filter").onchange = renderJobs;
$("refresh-jobs").onclick = () => refreshJobs().catch((e) => toast(e.message));
document.addEventListener("account-ready", () =>
  refreshJobs().catch((e) => toast(e.message)),
);
setInterval(() => {
  if (account && !document.hidden) refreshJobs().catch(() => {});
}, 5000);
