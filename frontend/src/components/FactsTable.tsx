import type { Fact } from "../api";

const LABELS: Record<string, string> = {
  insurer: "Insurer",
  previousInsurer: "Previous insurer",
  businessType: "Business type",
  vehicleClass: "Vehicle class",
  make: "Make",
  model: "Model / variant",
  fuel: "Fuel",
  rto: "RTO",
  cc: "Engine CC",
  manufactureYear: "Manufacture year",
  registrationYear: "Registration year",
  policyType: "Policy type",
  ncb: "NCB %",
  odPremium: "OD premium",
  tpPremium: "TP premium",
  policyStartDate: "Policy start date",
  issueDate: "Issue date",
};

export function FactsTable({ facts }: { facts: Record<string, Fact> }) {
  const names = Object.keys(facts);
  if (names.length === 0)
    return <p className="text-slate-600">No policy facts were extracted.</p>;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b">
            <th className="py-2 pr-3">Fact</th>
            <th className="py-2 pr-3">Value</th>
            <th className="py-2 pr-3">Page</th>
            <th className="py-2 pr-3">Quote</th>
            <th className="py-2 pr-3">Check</th>
            <th className="py-2">Confidence</th>
          </tr>
        </thead>
        <tbody>
          {names.map((n) => {
            const f = facts[n];
            return (
              <tr key={n} className="border-b align-top">
                <th scope="row" className="py-2 pr-3 font-medium">
                  {LABELS[n] ?? n}
                </th>
                <td className="py-2 pr-3">
                  {f.value === null ? "Not found" : String(f.value)}
                </td>
                <td className="py-2 pr-3">{f.page ?? "—"}</td>
                <td className="py-2 pr-3 font-mono text-xs">
                  {f.quote ?? "—"}
                </td>
                <td className="py-2 pr-3">
                  {f.verification.replace(/_/g, " ")}
                </td>
                <td className="py-2">{f.confidence}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
