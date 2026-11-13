import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Brand, Notice, Choice, brand } from "./shared";

export function Lab() {
  const [result, setResult] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const [step, setStep] = useState(-1),
    [pace, setPace] = useState("900");
  const steps =
    brand.name === "Pocket"
      ? ["Submit", "Claim", "Execute", "Acknowledge"]
      : brand.name === "Pay"
        ? ["Create intent", "Deduplicate", "Capture", "Reconcile"]
        : ["Receive", "Order", "Reject stale data", "Render"];
  async function run() {
    setBusy(true);
    setStep(-1);
    setError("");
    setResult(null);
    try {
      const response = await fetch("/demo/run", { method: "POST" });
      const data = await response.json();
      if (!response.ok) throw new Error(data.detail || "Unable to run the lab");
      setResult(data);
      window.updateMap?.(data.record.vehicles);
      if (matchMedia("(prefers-reduced-motion: reduce)").matches) {
        setStep(steps.length);
        return;
      }
      for (let index = 0; index < steps.length; index++) {
        setStep(index);
        await new Promise((resolve) => setTimeout(resolve, Number(pace)));
      }
      setStep(steps.length);
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <header className="topbar">
        <Brand />
        <Button asChild variant="outline">
          <a href="/">Back to workspace</a>
        </Button>
      </header>
      <main className="workspace-content">
        <div className="page-heading">
          <div>
            <h1>Engineering lab</h1>
            <p className="text-muted-foreground">
              Run a synthetic scenario and inspect the backend result.
            </p>
          </div>
          <div className="flex items-end gap-3">
            <Choice
              label="Playback pace"
              value={pace}
              onChange={setPace}
              options={[
                ["300", "Quick"],
                ["900", "Normal"],
                ["1800", "Slow"],
              ]}
            />
            <Button disabled={busy} onClick={run}>
              {busy ? "Running…" : "Run the demo"}
            </Button>
          </div>
        </div>
        <Notice>{error}</Notice>
        <Card>
          <CardHeader>
            <CardTitle>Process walkthrough</CardTitle>
          </CardHeader>
          <CardContent className="flex flex-wrap gap-3">
            {steps.map((label, index) => (
              <Badge
                key={label}
                variant={index <= step ? "default" : "outline"}
                aria-current={index === step ? "step" : undefined}
              >
                {label}
              </Badge>
            ))}
          </CardContent>
        </Card>
        {brand.name === "Kashmir" && (
          <Card>
            <CardContent>
              <div
                id="map"
                className="fleet-map"
                aria-label="Synthetic fleet map"
              />
            </CardContent>
          </Card>
        )}
        {result && (
          <Card>
            <CardHeader>
              <CardTitle>{result.title}</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-3">
              <ul className="list-disc pl-5">
                {result.checks.map((check) => (
                  <li key={check}>{check}</li>
                ))}
              </ul>
              <pre className="max-h-96 overflow-auto rounded-md border p-4 text-xs">
                {JSON.stringify(result.record, null, 2)}
              </pre>
            </CardContent>
          </Card>
        )}
        <footer>
          <a href="/docs">API reference ↗</a>
          <a
            href={
              "https://github.com/0xMudit/qq-" +
              brand.name.toLowerCase() +
              "/blob/main/docs/architecture.md"
            }
          >
            Architecture ↗
          </a>
        </footer>
      </main>
    </>
  );
}
