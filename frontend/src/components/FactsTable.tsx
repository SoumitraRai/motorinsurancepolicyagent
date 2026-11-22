import type { Fact } from "../api";

export const LABELS: Record<string, string> = {
  insurer: "Insurer",
  previousInsurer: "Previous insurer",
  businessType: "Business type",
  vehicleClass: "Vehicle class",
  make: "Make",
  model: "Model / variant",
  fuel: "Fuel",
  rto: "RTO",
  rtoLocation: "RTO location",
  registrationNumber: "Registration number",
  cc: "Engine CC",
  manufactureYear: "Manufacture year",
  registrationYear: "Registration year",
  policyType: "Policy type",
  ncb: "NCB %",
  previousNcb: "Previous NCB %",
  odPremium: "OD premium",
  tpPremium: "TP premium",
  netPremium: "Net premium",
  policyStartDate: "Policy start date",
  issueDate: "Issue date",
  gvw: "Gross vehicle weight",
  seatingCapacity: "Seating capacity",
  bodyType: "Body type",
  addOns: "Add-on covers",
  cpaCover: "CPA cover",
  cngLpgKitValue: "CNG / LPG kit value",
  odTermYears: "OD term (years)",
  segment: "Segment",
  tppdRestricted: "TPPD restricted",
};

export const CHECK: Record<string, string> = {
  text_layer: "Text layer",
  verified_both: "Both OCR engines",
  verified_one: "One OCR engine",
  unverified: "Not verified",
  derived: "Derived",
  reviewer_supplied: "Reviewer supplied",
  not_found: "Not found",
};

function shown(f: Fact): string {
  if (f.value === null) return "Not found";
  return Array.isArray(f.value) ? f.value.join(", ") : String(f.value);
}

/** The facts read from the policy, as numbered schedule fields, each beside the quote it came from. */
export function FactsTable({ facts }: { facts: Record<string, Fact> }) {
  const names = Object.keys(facts).sort(
    (a, b) => Number(facts[a].value === null) - Number(facts[b].value === null),
  );
  if (names.length === 0)
    return <p className="text-ink-muted">No policy facts were extracted.</p>;
  return (
    <dl className="grid gap-x-10 lg:grid-cols-2">
      {names.map((n, i) => {
        const f = facts[n];
        const missing = f.value === null;
        return (
          <div
            key={n}
            className="grid grid-cols-[2.25rem_minmax(0,9.5rem)_minmax(0,1fr)] gap-x-3 gap-y-1 border-b border-rule py-3"
          >
            <span className="tabular font-mono text-[0.8125rem] text-serial">
              {String(i + 1).padStart(2, "0")}
            </span>
            <dt className="font-semibold">{LABELS[n] ?? n}</dt>
            <dd className={missing ? "text-ink-muted" : ""}>{shown(f)}</dd>
            {f.quote && (
              <dd className="col-start-3 rounded-sm bg-quote px-2 py-1 font-mono text-[0.8125rem] leading-snug text-ink-soft [overflow-wrap:anywhere]">
                {f.quote}
              </dd>
            )}
            {!missing && (
              <dd className="col-start-3 text-[0.8125rem] text-ink-muted">
                {[
                  f.page ? `Page ${f.page}` : null,
                  CHECK[f.verification] ?? f.verification,
                  `${f.confidence} confidence`,
                ]
                  .filter(Boolean)
                  .join(" · ")}
              </dd>
            )}
          </div>
        );
      })}
    </dl>
  );
}
