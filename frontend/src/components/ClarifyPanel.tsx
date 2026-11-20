import { useState, type FormEvent } from "react";

/** Shown only for `ambiguous` runs that name the facts that would settle them (spec SR25). */
export function ClarifyPanel({
  facts,
  onSubmit,
  busy,
}: {
  facts: string[];
  onSubmit: (values: Record<string, string>) => void;
  busy: boolean;
}) {
  const [values, setValues] = useState<Record<string, string>>({});
  function submit(e: FormEvent) {
    e.preventDefault();
    const filled = Object.fromEntries(
      Object.entries(values).filter(([, v]) => v.trim() !== ""),
    );
    if (Object.keys(filled).length > 0) onSubmit(filled);
  }
  return (
    <form
      onSubmit={submit}
      className="space-y-3 rounded border border-violet-300 bg-violet-50 p-4"
    >
      <h2 className="font-semibold">Add the missing facts</h2>
      <p className="text-sm">
        This starts a new run marked “reviewer-supplied fact”. This run stays
        unchanged.
      </p>
      {facts.map((f) => (
        <label key={f} className="block text-sm">
          <span className="block font-medium">{f}</span>
          <input
            className="mt-1 min-h-11 w-full rounded border border-slate-300 px-2"
            value={values[f] ?? ""}
            onChange={(e) => setValues({ ...values, [f]: e.target.value })}
          />
        </label>
      ))}
      <button
        type="submit"
        disabled={busy}
        className="min-h-11 rounded bg-violet-800 px-4 font-medium text-white disabled:opacity-60"
      >
        Rerun with these facts
      </button>
    </form>
  );
}
