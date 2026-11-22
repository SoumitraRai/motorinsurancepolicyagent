import { useRef, useState, type DragEvent } from "react";

export const MAX_BYTES = 25 * 1024 * 1024;

function problem(file: File): string | null {
  const isPdf =
    file.type === "application/pdf" || file.name.toLowerCase().endsWith(".pdf");
  if (!isPdf) return "Upload a PDF file. This file is not a PDF.";
  if (file.size > MAX_BYTES)
    return "This file is over 25 MB. Upload a smaller PDF.";
  return null;
}

export function UploadDrop({
  onUpload,
  busy,
  serverError,
  large = false,
}: {
  onUpload: (file: File) => void;
  busy: boolean;
  serverError?: string | null;
  large?: boolean;
}) {
  const [error, setError] = useState<string | null>(null);
  const [over, setOver] = useState(false);
  const input = useRef<HTMLInputElement>(null);

  function take(file: File | undefined) {
    if (!file) return;
    const p = problem(file);
    setError(p);
    if (!p) onUpload(file);
  }

  function drop(e: DragEvent<HTMLDivElement>) {
    e.preventDefault();
    setOver(false);
    take(e.dataTransfer.files[0]);
  }

  const message = error ?? serverError ?? null;
  return (
    <div>
      <div
        onDragOver={(e) => {
          e.preventDefault();
          setOver(true);
        }}
        onDragLeave={() => setOver(false)}
        onDrop={drop}
        className={`flex flex-col gap-2 rounded-sm border border-dashed transition-colors duration-150 ${
          large ? "min-h-56 items-center justify-center p-8 text-center" : "p-3"
        } ${over ? "border-guard bg-guard-tint" : "border-rule-strong bg-sheet"}`}
      >
        <button
          type="button"
          disabled={busy}
          onClick={() => input.current?.click()}
          className={`btn-primary ${large ? "" : "w-full"}`}
        >
          {busy ? "Uploading…" : "Upload a policy PDF"}
        </button>
        <span className="text-sm text-ink-muted">
          Or drag a file here. PDF only, up to 25 MB and 200 pages.
        </span>
        <input
          ref={input}
          type="file"
          accept="application/pdf,.pdf"
          aria-label="Policy PDF"
          className="sr-only"
          tabIndex={-1}
          disabled={busy}
          onChange={(e) => {
            take(e.target.files?.[0]);
            e.target.value = "";
          }}
        />
      </div>
      {message && (
        <p role="alert" className="mt-2 text-sm font-medium text-refuse">
          {message}
        </p>
      )}
    </div>
  );
}
