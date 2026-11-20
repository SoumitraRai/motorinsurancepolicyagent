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
}: {
  onUpload: (file: File) => void;
  busy: boolean;
  serverError?: string | null;
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
        className={`flex min-h-24 flex-col items-center justify-center gap-2 rounded border-2 border-dashed p-4 text-center ${over ? "border-sky-600 bg-sky-50" : "border-slate-300"}`}
      >
        <button
          type="button"
          disabled={busy}
          onClick={() => input.current?.click()}
          className="min-h-11 rounded bg-sky-700 px-4 font-medium text-white hover:bg-sky-800 focus:outline-none focus:ring-2 focus:ring-sky-600 focus:ring-offset-2 disabled:opacity-60"
        >
          {busy ? "Uploading…" : "Upload a policy PDF"}
        </button>
        <span className="text-sm text-slate-600">
          Or drag a file here. PDF only, up to 25 MB and 60 pages.
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
        <p role="alert" className="mt-2 text-sm text-rose-800">
          {message}
        </p>
      )}
    </div>
  );
}
