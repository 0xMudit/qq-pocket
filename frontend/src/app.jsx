import { useState, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent } from "@/components/ui/card";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import {
  Shell,
  Field,
  Choice,
  Modal,
  Notice,
  Metrics,
  Status,
  action,
  post,
  date,
  useRecords,
} from "./shared";
import { toast } from "sonner";

const tasks = [
  ["sum", "Sum numbers"],
  ["sha256", "SHA-256 digest"],
  ["text_stats", "Text statistics"],
  ["json_format", "Format JSON"],
];
const samples = {
  sum: "[12,24,36]",
  sha256: "Text to hash",
  text_stats: "Count these words.",
  json_format: '{"ready":true}',
};
const states = ["queued", "running", "succeeded", "dead", "cancelled"];
function Queue() {
  const { rows, error, refresh } = useRecords("/jobs");
  const [open, setOpen] = useState(false),
    [busy, setBusy] = useState(false);
  const [id, setId] = useState(null),
    [query, setQuery] = useState(""),
    [filter, setFilter] = useState("all");
  const [task, setTask] = useState("sum"),
    [payload, setPayload] = useState(samples.sum);
  const key = useRef(crypto.randomUUID());
  const selected = rows.find((job) => job.id === id);
  const visible = rows.filter(
    (job) =>
      (filter === "all" || job.status === filter) &&
      (job.task + " " + job.id).includes(query.toLowerCase()),
  );
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Job queue</h1>
          <p className="text-muted-foreground">
            Schedule work and inspect worker results.
          </p>
        </div>
        <Button onClick={() => setOpen(true)}>Submit job</Button>
      </div>
      <Notice>{error}</Notice>
      <Metrics
        values={states
          .slice(0, 4)
          .map((state) => [
            state === "dead" ? "Dead letter" : state,
            rows.filter((j) => j.status === state).length,
          ])}
      />
      <Card>
        <CardContent className="grid gap-4">
          <div className="flex flex-wrap items-end gap-3">
            <Input
              aria-label="Search jobs"
              placeholder="Search by task or job ID"
              className="max-w-xs"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
            />
            <Choice
              label="Status filter"
              value={filter}
              onChange={setFilter}
              options={[["all", "All statuses"], ...states.map((s) => [s, s])]}
            />
            <Button variant="outline" onClick={refresh}>
              Refresh
            </Button>
          </div>
          <Table>
            <TableHeader>
              <TableRow>
                {["Task", "Status", "Attempts", "Created", ""].map((h) => (
                  <TableHead key={h}>{h}</TableHead>
                ))}
              </TableRow>
            </TableHeader>
            <TableBody>
              {visible.map((j) => (
                <TableRow key={j.id}>
                  <TableCell>
                    <strong>{j.task}</strong>
                    <div className="font-mono text-xs text-muted-foreground">
                      {j.id.slice(0, 8)}
                    </div>
                  </TableCell>
                  <TableCell>
                    <Status>{j.status}</Status>
                  </TableCell>
                  <TableCell>{j.attempts} / 3</TableCell>
                  <TableCell>{date(j.created)}</TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setId(j.id)}
                    >
                      Inspect
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
          {!visible.length && (
            <p className="py-8 text-center text-muted-foreground">
              No matching jobs.
            </p>
          )}
        </CardContent>
      </Card>
      <Modal
        open={open}
        onOpenChange={setOpen}
        title="Submit a job"
        description="Choose a built-in handler and enter its payload."
      >
        <form
          className="grid gap-4"
          onChange={() => {
            key.current = crypto.randomUUID();
          }}
          onSubmit={(event) => {
            event.preventDefault();
            const delay = Number(
              new FormData(event.currentTarget).get("delay"),
            );
            setBusy(true);
            action(async () => {
              try {
                await post("/jobs", {
                  task,
                  payload,
                  delay_seconds: delay,
                  idempotency_key: key.current,
                });
                key.current = crypto.randomUUID();
                setOpen(false);
                await refresh();
                toast.success("Job queued");
              } finally {
                setBusy(false);
              }
            });
          }}
        >
          <Choice
            label="Handler"
            value={task}
            onChange={(value) => {
              setTask(value);
              setPayload(samples[value]);
              key.current = crypto.randomUUID();
            }}
            options={tasks}
          />
          <Field
            id="job-payload"
            label="Payload"
            multiline
            value={payload}
            onChange={(e) => setPayload(e.target.value)}
            required
            maxLength={20000}
          />
          <Field
            id="job-delay"
            name="delay"
            label="Schedule delay (seconds)"
            type="number"
            min={0}
            max={86400}
            defaultValue={0}
            required
          />
          <Button disabled={busy}>Enqueue job</Button>
        </form>
      </Modal>
      <Modal
        open={Boolean(selected)}
        onOpenChange={(value) => {
          if (!value) setId(null);
        }}
        title="Job details"
        description={selected?.id || "Inspect this job."}
      >
        {selected && (
          <div className="grid gap-3">
            <Status>{selected.status}</Status>
            <p>
              Attempts {selected.attempts} / 3 · Available{" "}
              {date(selected.available)}
            </p>
            <Field
              id="input"
              label="Input"
              multiline
              value={selected.payload}
              readOnly
            />
            <Field
              id="result"
              label="Result"
              multiline
              value={selected.result ?? "Awaiting result"}
              readOnly
            />
            <Notice>{selected.error}</Notice>
            {["queued", "dead", "cancelled"].includes(selected.status) && (
              <Button
                variant="outline"
                onClick={() =>
                  action(async () => {
                    await post(
                      "/jobs/" +
                        selected.id +
                        "/" +
                        (selected.status === "queued" ? "cancel" : "retry"),
                    );
                    await refresh();
                  })
                }
              >
                {selected.status === "queued"
                  ? "Cancel queued job"
                  : "Retry job"}
              </Button>
            )}
          </div>
        )}
      </Modal>
    </>
  );
}
export default function App() {
  return <Shell Product={Queue} />;
}
