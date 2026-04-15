interface BadgeIconProps {
  badgeType: string;
  size?: "sm" | "md";
  showTooltip?: boolean;
}

const BADGE_MAP: Record<string, { emoji: string; label: string; bg: string }> = {
  street_detective: { emoji: "\uD83D\uDD0D", label: "Street Detective", bg: "#e8f0fe" },
  night_owl: { emoji: "\uD83E\uDD89", label: "Night Owl", bg: "#ede7f6" },
  explorer: { emoji: "\uD83E\uDDED", label: "Explorer", bg: "#e0f2f1" },
  time_keeper: { emoji: "\u23F3", label: "Time Keeper", bg: "#fff8e1" },
  pioneer: { emoji: "\uD83C\uDFF4", label: "Pioneer", bg: "#fce4ec" },
};

const DEFAULT_BADGE = { emoji: "\u2B50", label: "Badge", bg: "#f5f5f5" };

function BadgeIcon({ badgeType, size = "sm", showTooltip = true }: BadgeIconProps) {
  const badge = BADGE_MAP[badgeType] || DEFAULT_BADGE;
  const px = size === "md" ? 36 : 24;
  const fontSize = size === "md" ? "1rem" : "0.75rem";

  return (
    <span
      className="badge-icon"
      title={showTooltip ? badge.label : undefined}
      style={{
        width: px,
        height: px,
        fontSize,
        background: badge.bg,
      }}
    >
      {badge.emoji}
    </span>
  );
}

export default BadgeIcon;
export { BADGE_MAP };
