import { Layers3 } from "lucide-react";
import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Alert, AlertDescription } from "@/components/ui/alert";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Separator } from "@/components/ui/separator";
import { Toaster } from "@/components/ui/sonner";
import { toast } from "sonner";

export const brand = {
  name: "Pocket",
  mark: "Q",
  dark: true,
  heading: "Background jobs, under control.",
  description: "Submit and schedule work, then inspect its results.",
};
export async function api(path, method = "GET", data) {
  const response = await fetch("/api" + path, {
    method,
    headers: data === undefined ? {} : { "Content-Type": "application/json" },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  const result = await response.json().catch(() => null);
  if (!response.ok)
    throw new Error(
      typeof result?.detail === "string"
        ? result.detail
        : result?.detail?.map((item) => item.msg).join("; ") ||
            "Request failed",
    );
  return result;
}
export const post = (path, data = {}) => api(path, "POST", data);
export const date = (value) =>
  value ? new Date(value * 1000).toLocaleString() : "Never";
export const money = (value, currency) =>
  new Intl.NumberFormat(undefined, { style: "currency", currency }).format(
    value / 100,
  );
export function useRecords(path, delay = 5000) {
  const [rows, setRows] = useState([]);
  const [error, setError] = useState("");
  async function refresh() {
    try {
      setRows(await api(path));
      setError("");
    } catch (error) {
      setError(error.message);
    }
  }
  useEffect(() => {
    refresh();
    const id = setInterval(() => {
      if (!document.hidden) refresh();
    }, delay);
    return () => clearInterval(id);
  }, [path, delay]);
  return { rows, error, refresh };
}
export async function action(callback) {
  try {
    await callback();
  } catch (error) {
    toast.error(error.message);
  }
}
export function Notice({ children }) {
  return children ? (
    <Alert>
      <AlertDescription>{children}</AlertDescription>
    </Alert>
  ) : null;
}
export function Status({ children }) {
  return (
    <Badge variant="outline" className="status" data-state={children}>
      {children}
    </Badge>
  );
}
export function Field({ label, multiline, ...props }) {
  const control = multiline ? <Textarea {...props} /> : <Input {...props} />;
  return (
    <div className="grid gap-2">
      <Label htmlFor={props.id}>{label}</Label>
      {control}
    </div>
  );
}
export function Choice({ label, value, onChange, options }) {
  return (
    <div className="grid gap-2">
      <Label>{label}</Label>
      <Select value={value} onValueChange={onChange}>
        <SelectTrigger aria-label={label} className="w-full">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          {options.map(([id, title]) => (
            <SelectItem key={id} value={id}>
              {title}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}
export function Modal({ title, description, open, onOpenChange, children }) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90dvh] overflow-auto">
        <DialogHeader>
          <DialogTitle>{title}</DialogTitle>
          <DialogDescription>{description}</DialogDescription>
        </DialogHeader>
        {children}
      </DialogContent>
    </Dialog>
  );
}
export function Metrics({ values }) {
  return (
    <div className="metric-grid">
      {values.map(([title, value]) => (
        <Card key={title} className="gap-2 py-4">
          <CardHeader>
            <CardTitle className="text-sm text-muted-foreground">
              {title}
            </CardTitle>
          </CardHeader>
          <CardContent className="text-3xl font-semibold">{value}</CardContent>
        </Card>
      ))}
    </div>
  );
}
export function Secret({ value, close }) {
  return (
    <Modal
      title="Copy your token"
      description="This token is shown once. Keep it private."
      open={Boolean(value)}
      onOpenChange={(open) => {
        if (!open) close();
      }}
    >
      <Textarea aria-label="Token" readOnly value={value} />
      <Button
        onClick={() =>
          action(async () => {
            await navigator.clipboard.writeText(value);
            toast.success("Copied");
          })
        }
      >
        Copy token
      </Button>
    </Modal>
  );
}
export function Shell({ Product, Checkout }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(true);
  const checkout = location.pathname.startsWith("/checkout/");
  useEffect(() => {
    if (checkout) return;
    api("/auth/me")
      .then(setUser)
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [checkout]);
  return (
    <>
      <Toaster theme={brand.dark ? "dark" : "light"} />
      {checkout && Checkout ? (
        <Checkout />
      ) : loading ? (
        <main className="center">Loading workspace…</main>
      ) : user ? (
        <Workspace
          user={user}
          Product={Product}
          logout={() =>
            action(async () => {
              await post("/auth/logout");
              setUser(null);
            })
          }
        />
      ) : (
        <Login onLogin={setUser} />
      )}
    </>
  );
}
function Login({ onLogin }) {
  const [register, setRegister] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [demo, setDemo] = useState(null);
  useEffect(() => {
    api("/auth/demo")
      .then(setDemo)
      .catch(() => {});
  }, []);
  async function login(credentials, create = false) {
    setBusy(true);
    setError("");
    try {
      if (create) await post("/auth/register", credentials);
      onLogin(await post("/auth/login", credentials));
    } catch (error) {
      setError(error.message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="auth">
      <aside>
        <Brand />
        <div>
          <h1>{brand.heading}</h1>
          <p>{brand.description}</p>
        </div>
        <a href="/lab">System design lab ↗</a>
      </aside>
      <section>
        <Card className="w-full max-w-sm">
          <CardHeader>
            <CardTitle className="text-2xl">
              {register ? "Create an account" : "Sign in"}
            </CardTitle>
          </CardHeader>
          <CardContent className="grid gap-4">
            <form
              className="grid gap-4"
              onSubmit={(event) => {
                event.preventDefault();
                login(
                  Object.fromEntries(new FormData(event.currentTarget)),
                  register,
                );
              }}
            >
              <Field
                id="username"
                label="Username"
                name="username"
                autoComplete="username"
                minLength={3}
                maxLength={40}
                required
              />
              <Field
                id="password"
                label="Password"
                type="password"
                name="password"
                autoComplete={register ? "new-password" : "current-password"}
                minLength={12}
                maxLength={128}
                required
              />
              <Notice>{error}</Notice>
              <Button disabled={busy}>
                {register ? "Create account" : "Sign in"}
              </Button>
            </form>
            <Button variant="ghost" onClick={() => setRegister(!register)}>
              {register ? "Back to sign in" : "Create an account"}
            </Button>
            <Separator />
            <Button
              variant="outline"
              disabled={!demo || busy}
              onClick={() =>
                login({ username: demo.username, password: demo.password })
              }
            >
              Explore the demo workspace
            </Button>
            {demo && (
              <p className="text-xs text-muted-foreground">
                Shared demo ·{" "}
                <code>
                  {demo.username} / {demo.password}
                </code>
              </p>
            )}
          </CardContent>
        </Card>
      </section>
    </main>
  );
}
export function Brand() {
  return (
    <div className="brand">
      <span aria-hidden="true">
        <Layers3 />
      </span>{" "}
      QQ {brand.name}
    </div>
  );
}
function Workspace({ user, Product, logout }) {
  const [keysOpen, setKeysOpen] = useState(false);
  const [keys, setKeys] = useState([]);
  const [secret, setSecret] = useState("");
  const [busy, setBusy] = useState(false);
  const load = async () => setKeys(await api("/auth/keys"));
  return (
    <div className="workspace">
      <header className="topbar">
        <Brand />
        <nav>
          <span>{user.username}</span>
          <Button
            size="sm"
            variant="outline"
            onClick={() =>
              action(async () => {
                await load();
                setKeysOpen(true);
              })
            }
          >
            API keys
          </Button>
          <Button size="sm" variant="ghost" onClick={logout}>
            Sign out
          </Button>
        </nav>
      </header>
      <main className="workspace-content">
        {user.id === "demo" && (
          <Notice>Shared demo workspace. Use synthetic data only.</Notice>
        )}
        <Product />
      </main>
      <footer>
        <a href="/docs">API reference ↗</a>
        <a href="/lab">System design ↗</a>
      </footer>
      <Modal
        title="API keys"
        description="Send an API key as an Authorization: Bearer header. Keys expire after 30 days."
        open={keysOpen}
        onOpenChange={setKeysOpen}
      >
        <form
          className="grid gap-3"
          onSubmit={(event) => {
            event.preventDefault();
            const form = event.currentTarget;
            const label = new FormData(form).get("label");
            setBusy(true);
            action(async () => {
              try {
                const key = await post("/auth/keys", { label });
                form.reset();
                setKeysOpen(false);
                setSecret(key.token);
              } finally {
                setBusy(false);
              }
            });
          }}
        >
          <Field
            id="key-label"
            name="label"
            label="Key label"
            required
            maxLength={60}
          />
          <Button disabled={busy}>Create API key</Button>
        </form>
        {keys.map((key) => (
          <div
            className="flex items-center justify-between gap-3"
            key={key.digest}
          >
            <span>{key.label}</span>
            <Button
              size="sm"
              variant="outline"
              onClick={() =>
                action(async () => {
                  await api("/auth/keys/" + key.digest, "DELETE");
                  await load();
                })
              }
            >
              Revoke
            </Button>
          </div>
        ))}
      </Modal>
      <Secret value={secret} close={() => setSecret("")} />
    </div>
  );
}
