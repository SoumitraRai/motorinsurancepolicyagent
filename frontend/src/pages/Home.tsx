import { UploadDrop } from "../components/UploadDrop";
import { useUpload } from "../upload";

/** The start screen beside the run list: one large drop target and what a run produces. */
export function Home() {
  const upload = useUpload();
  return (
    <div className="space-y-6">
      <header className="max-w-[60ch] space-y-2">
        <h2 className="text-2xl font-semibold tracking-tight">
          Rate a motor policy
        </h2>
        <p className="text-ink-soft">
          Upload a policy PDF. The agent reads it, resolves the OD and TP
          brokerage from the insurer's grid, and prints a rate schedule with the
          PDF page and grid cell behind every number. When the grid doesn't
          cover the policy, it says why instead of guessing.
        </p>
      </header>
      <UploadDrop
        large
        onUpload={upload.start}
        busy={upload.busy}
        serverError={upload.serverError}
      />
      <p className="text-sm text-ink-muted">
        Supported grids: Go Digit, HDFC ERGO, Reliance and Tata AIG. Open any
        earlier run from the list.
      </p>
    </div>
  );
}
