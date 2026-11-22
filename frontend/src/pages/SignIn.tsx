import { useState, type FormEvent } from "react";

export function SignIn({
  signIn,
}: {
  signIn: (email: string, password: string) => Promise<void>;
}) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email, password);
    } catch {
      setError("Email or password is wrong. Try again.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <form
      onSubmit={submit}
      aria-labelledby="signin-h"
      className="w-full max-w-md overflow-hidden rounded-lg border border-guard bg-sheet shadow-[0_1px_2px_rgba(28,36,64,0.06),0_8px_24px_-12px_rgba(28,36,64,0.18)]"
    >
      <div
        className="guard-band h-10 border-b border-guard"
        aria-hidden="true"
      />
      <div className="space-y-5 p-6 sm:p-8">
        <div className="space-y-1">
          <h2 id="signin-h" className="text-2xl font-semibold tracking-tight">
            Sign in
          </h2>
          <p className="text-ink-muted">
            Use the reviewer login sent with the submission.
          </p>
        </div>
        <label className="block">
          <span className="block text-sm font-semibold">Email</span>
          <input
            type="email"
            autoComplete="username"
            required
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="field"
          />
        </label>
        <label className="block">
          <span className="block text-sm font-semibold">Password</span>
          <input
            type="password"
            autoComplete="current-password"
            required
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="field"
          />
        </label>
        {error && (
          <p role="alert" className="text-sm font-medium text-refuse">
            {error}
          </p>
        )}
        <button type="submit" disabled={busy} className="btn-primary w-full">
          {busy ? "Signing in…" : "Sign in"}
        </button>
      </div>
    </form>
  );
}
