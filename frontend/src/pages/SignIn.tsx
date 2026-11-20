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
      className="mx-auto max-w-sm space-y-4"
      aria-labelledby="signin-h"
    >
      <h2 id="signin-h" className="text-lg font-semibold">
        Sign in
      </h2>
      <label className="block">
        <span className="block text-sm font-medium">Email</span>
        <input
          type="email"
          autoComplete="username"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          className="mt-1 min-h-11 w-full rounded border border-slate-300 px-2"
        />
      </label>
      <label className="block">
        <span className="block text-sm font-medium">Password</span>
        <input
          type="password"
          autoComplete="current-password"
          required
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          className="mt-1 min-h-11 w-full rounded border border-slate-300 px-2"
        />
      </label>
      {error && (
        <p role="alert" className="text-sm text-rose-800">
          {error}
        </p>
      )}
      <button
        type="submit"
        disabled={busy}
        className="min-h-11 w-full rounded bg-sky-700 font-medium text-white disabled:opacity-60"
      >
        Sign in
      </button>
    </form>
  );
}
