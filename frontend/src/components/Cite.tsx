/**
 * A citation rendered byte-for-byte. Only a significant run of spaces and the word on each side of it
 * (a sheet name such as '4W  RTO') is kept unbreakable, so no space can vanish at a line end while the
 * rest of a long path still wraps.
 */
export function Cite({
  text,
  className = "",
}: {
  text: string;
  className?: string;
}) {
  const parts = text.split(/(\S+ {2,}\S+)/g);
  return (
    <span className={`cite ${className}`}>
      {parts.map((p, i) =>
        i % 2 === 1 ? (
          <span key={i} className="whitespace-pre">
            {p}
          </span>
        ) : (
          p
        ),
      )}
    </span>
  );
}

/** The page number in a policy citation ("policy.pdf · page 3" → 3). */
export function citedPage(text: string): number | undefined {
  const m = / · page (\d+)\b/.exec(text);
  return m ? Number(m[1]) : undefined;
}
