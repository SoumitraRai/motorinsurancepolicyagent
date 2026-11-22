import { useState, type FormEvent } from "react";

const NAMES: Record<string, string> = {
  fuel: "Fuel",
  business_type: "Business type (new, renewal or rollover)",
  policy_start_date: "Policy start date (YYYY-MM-DD)",
  rto: "RTO code",
  cc: "Engine CC",
};

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
      aria-labelledby="clarify-h"
      className="rounded-sm border border-warn/40 bg-warn-tint p-5"
    >
      <h2 id="clarify-h" className="text-lg font-semibold">
        Add the missing facts
      </h2>
      <p className="mt-1 max-w-[75ch] text-sm text-ink-soft">
        The rate depends on these facts, which the policy didn't show clearly.
        Rerunning starts a new run marked “reviewer-supplied fact”; this run
        stays unchanged.
      </p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        {facts.map((f) => (
          <label key={f} className="block">
            <span className="block text-sm font-semibold">{NAMES[f] ?? f}</span>
            <input
              className="field"
              value={values[f] ?? ""}
              onChange={(e) => setValues({ ...values, [f]: e.target.value })}
            />
          </label>
        ))}
      </div>
      <button type="submit" disabled={busy} className="btn-primary mt-4">
        {busy ? "Starting the rerun…" : "Rerun with these facts"}
      </button>
    </form>
  );
}
