/**
 * VerifiedBadge - small purple checkmark icon indicating a verified artist.
 * Shows a tooltip on hover: "Verified artist".
 */
function VerifiedBadge() {
  return (
    <span className="verified-badge" title="Verified artist">
      <svg
        width="18"
        height="18"
        viewBox="0 0 24 24"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-label="Verified artist"
      >
        <circle cx="12" cy="12" r="11" fill="#7c3aed" />
        <path
          d="M7 12.5L10.5 16L17 9"
          stroke="white"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        />
      </svg>
    </span>
  );
}

export default VerifiedBadge;
