/**
 * ScrubSync AI brand mark: an "S" monogram assembled from waveform segments
 * (voice sampled into the letter) inside a rounded gradient tile.
 * Pure inline SVG — scales crisply from favicon size to hero size.
 */
export function Logo({ className = "" }: { className?: string }) {
  // Open double-curve "S", stroked (not filled) so the dashes read as samples.
  const sPath =
    "M31 15.5 C31 12.5 27 11 23 11 C17 11 14 13.5 14 17 C14 20.5 18 22 24 23 " +
    "C30 24 34 25.5 34 29 C34 32.5 31 35 25 35 C21 35 17 33.5 15.5 31";

  return (
    <svg
      viewBox="0 0 48 48"
      className={className}
      role="img"
      aria-label="ScrubSync AI logo"
    >
      <defs>
        <linearGradient id="ssStroke" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#22d3ee" />
          <stop offset="100%" stopColor="#34d399" />
        </linearGradient>
        <linearGradient id="ssTile" x1="0" y1="0" x2="1" y2="1">
          <stop offset="0%" stopColor="#0b1a24" />
          <stop offset="100%" stopColor="#06120f" />
        </linearGradient>
      </defs>

      {/* Rounded tile */}
      <rect
        x="1.5"
        y="1.5"
        width="45"
        height="45"
        rx="12"
        fill="url(#ssTile)"
        stroke="url(#ssStroke)"
        strokeWidth="2"
      />

      {/* Faint continuous S for legibility underneath */}
      <path
        d={sPath}
        fill="none"
        stroke="url(#ssStroke)"
        strokeWidth="3.2"
        strokeLinecap="round"
        opacity="0.14"
      />

      {/* Bright, segmented S — the "waveform samples" that form the letter */}
      <path
        d={sPath}
        fill="none"
        stroke="url(#ssStroke)"
        strokeWidth="3.2"
        strokeLinecap="round"
        strokeDasharray="2.6 3.6"
      />
    </svg>
  );
}
