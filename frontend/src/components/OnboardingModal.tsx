import { useState } from "react";
import apiClient from "../api/client";

const ONBOARDED_KEY = "duvarsanat_onboarded";

type ProfileType = "photographer" | "artist" | "explorer";

interface ProfileOption {
  type: ProfileType;
  icon: string;
  label: string;
  description: string;
}

const OPTIONS: ProfileOption[] = [
  {
    type: "photographer",
    icon: "\uD83D\uDCF7",
    label: "I photograph street art",
    description: "Photographer",
  },
  {
    type: "artist",
    icon: "\uD83C\uDFA8",
    label: "I create street art",
    description: "Artist",
  },
  {
    type: "explorer",
    icon: "\uD83D\uDEB6",
    label: "I explore and appreciate",
    description: "Explorer",
  },
];

interface OnboardingModalProps {
  onComplete: () => void;
}

function OnboardingModal({ onComplete }: OnboardingModalProps) {
  const [saving, setSaving] = useState(false);

  async function handleSelect(profileType: ProfileType) {
    if (saving) return;
    setSaving(true);

    try {
      await apiClient.patch("/api/users/me", { profile_type: profileType });
    } catch {
      // Non-critical -- still mark onboarding as complete
    }

    localStorage.setItem(ONBOARDED_KEY, "true");
    setSaving(false);
    onComplete();
  }

  return (
    <div className="onboarding-overlay">
      <div className="onboarding-modal">
        <h2 className="onboarding-title">Welcome to DuvarSanat!</h2>
        <p className="onboarding-subtitle">What brings you here?</p>

        <div className="onboarding-options">
          {OPTIONS.map((opt) => (
            <button
              key={opt.type}
              className="onboarding-card"
              onClick={() => handleSelect(opt.type)}
              disabled={saving}
            >
              <span className="onboarding-icon">{opt.icon}</span>
              <span className="onboarding-label">{opt.label}</span>
              <span className="onboarding-desc">({opt.description})</span>
            </button>
          ))}
        </div>

        <p className="onboarding-footnote">
          You can always change this later in settings.
        </p>
      </div>
    </div>
  );
}

export default OnboardingModal;
