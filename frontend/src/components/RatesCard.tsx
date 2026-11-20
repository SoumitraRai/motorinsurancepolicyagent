import type { Rate } from "../api";
import { rateText } from "./rates";

function One({ name, rate }: { name: "OD" | "TP"; rate: Rate | undefined }) {
  return (
    <div className="rounded border border-slate-200 p-4">
      <p className="text-xl font-semibold">{`${name} ${rateText(rate)}`}</p>
      {rate?.reason && (
        <p className="mt-1 text-sm text-slate-700">{rate.reason}</p>
      )}
      {rate?.gridCitation && (
        <p className="mt-1 font-mono text-xs text-slate-600">
          {rate.gridCitation}
        </p>
      )}
    </div>
  );
}

export function RatesCard({ od, tp }: { od?: Rate; tp?: Rate }) {
  return (
    <section aria-labelledby="rates-h" className="grid gap-3 sm:grid-cols-2">
      <h2 id="rates-h" className="sr-only">
        Rates
      </h2>
      <One name="OD" rate={od} />
      <One name="TP" rate={tp} />
    </section>
  );
}
