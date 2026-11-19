import type { ReactNode } from "react";
import { Activity, CalendarDays, Flame, Repeat, Target, type LucideIcon } from "lucide-react";
import { formatRounds, type ChallengeType, type PersonalChallenge } from "../api/challengeApi";
import { formatDate } from "../utils/format";

const TYPE_STYLES: Record<ChallengeType, { icon: LucideIcon; color: string }> = {
  DAILY: { icon: Flame, color: "#F59E0B" },
  WEEKLY: { icon: Activity, color: "#10B981" },
  MONTHLY: { icon: CalendarDays, color: "#8B5CF6" },
  COUNT_BASED: { icon: Repeat, color: "#06B6D4" },
};

const FALLBACK_STYLE = { icon: Target, color: "#0D3B6E" };

export default function ChallengeCard({
  challenge,
  action,
}: {
  challenge: PersonalChallenge;
  /** 카드 하단 버튼 영역 (수락·기록 등) */
  action?: ReactNode;
}) {
  const { icon: Icon, color } = TYPE_STYLES[challenge.challenge_type] ?? FALLBACK_STYLE;
  const rounds = formatRounds(challenge);
  const basis = [...new Set(challenge.basis.map((item) => item.display_name))];

  return (
    <div className="bg-white border border-border rounded-xl p-5 flex flex-col gap-3">
      <div className="flex items-start gap-3">
        <div
          className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0"
          style={{ backgroundColor: `${color}15` }}
        >
          <Icon size={20} style={{ color }} />
        </div>
        <div className="min-w-0">
          <div className="font-semibold text-foreground text-sm">{challenge.title}</div>
          <div className="text-xs text-muted-foreground mt-0.5 leading-relaxed">
            {challenge.description}
          </div>
        </div>
      </div>

      <div className="flex flex-wrap gap-1.5">
        <span
          className="text-[11px] font-medium px-2 py-0.5 rounded-full"
          style={{ backgroundColor: `${color}12`, color }}
        >
          {challenge.challenge_type_label}
          {rounds ? ` · ${rounds}` : ""}
        </span>
        {challenge.target_diseases.map((disease) => (
          <span
            key={disease.model_type}
            className="text-[11px] font-medium px-2 py-0.5 rounded-full bg-muted text-muted-foreground"
          >
            {disease.disease_name}
          </span>
        ))}
      </div>

      {challenge.expected_effect && (
        <p className="text-xs text-foreground leading-relaxed">{challenge.expected_effect}</p>
      )}

      {basis.length > 0 && (
        <div
          className="text-[11px] px-2.5 py-1.5 rounded-lg"
          style={{
            backgroundColor: "rgba(13,59,110,0.05)",
            color: "#0D3B6E",
            fontFamily: "JetBrains Mono",
          }}
        >
          추천 근거: {basis.join(" · ")}
        </div>
      )}

      <div className="text-[11px] text-muted-foreground" style={{ fontFamily: "JetBrains Mono" }}>
        {challenge.status === "PENDING"
          ? `수락 기한 ${formatDate(challenge.expired_at)}`
          : `${challenge.status_label}${challenge.joined_at ? ` · ${formatDate(challenge.joined_at)} 시작` : ""}`}
      </div>

      {action}
    </div>
  );
}
