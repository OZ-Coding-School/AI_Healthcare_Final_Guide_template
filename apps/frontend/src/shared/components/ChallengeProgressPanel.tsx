import { useState } from "react";
import { Check, X } from "lucide-react";
import {
  HISTORY_MEMO_MAX_LENGTH,
  roundPeriodLabel,
  type PersonalChallenge,
} from "../api/challengeApi";

/**
 * 수락한 챌린지 카드 하단의 진행률과 현재 회차 기록 영역입니다.
 * 완료 기준: 주기형은 기간이 끝날 때 목표의 80% 이상 성공, 횟수형은 30일 안에 목표 횟수 달성 (백엔드 판정)
 */
export default function ChallengeProgressPanel({
  challenge,
  busy,
  onRecord,
}: {
  challenge: PersonalChallenge;
  busy: boolean;
  onRecord: (isSuccess: boolean, memo: string) => Promise<boolean>;
}) {
  const [memo, setMemo] = useState("");
  const progress = challenge.progress;
  if (!progress) return null;

  const percent = Math.min(100, Math.round((progress.success_count / progress.total_rounds) * 100));
  const requiredPercent = Math.round((progress.required_success / progress.total_rounds) * 100);
  const period = roundPeriodLabel(challenge.challenge_type);
  const inProgress = challenge.status === "IN_PROGRESS";

  async function submit(isSuccess: boolean) {
    if (await onRecord(isSuccess, memo)) setMemo("");
  }

  return (
    <div className="flex flex-col gap-2 border-t border-border pt-3">
      <div className="flex items-center justify-between text-[11px] text-muted-foreground">
        <span>
          성공 <strong className="text-foreground">{progress.success_count}</strong>/
          {progress.total_rounds}회 · 완료 기준 {progress.required_success}회
        </span>
        {inProgress && <span style={{ fontFamily: "JetBrains Mono" }}>~{progress.ends_on}</span>}
      </div>

      <div className="relative h-2 rounded-full bg-muted overflow-hidden" aria-hidden>
        <div
          className="h-full rounded-full"
          style={{ width: `${percent}%`, backgroundColor: "#10B981" }}
        />
        <div
          className="absolute top-0 h-full w-px bg-foreground/40"
          style={{ left: `${requiredPercent}%` }}
          title="완료 기준"
        />
      </div>

      {inProgress && progress.can_record && (
        <div className="flex flex-col gap-2">
          <div className="text-xs font-medium text-foreground">
            {period} 기록 · {progress.current_round}회차
          </div>
          <textarea
            value={memo}
            onChange={(event) => setMemo(event.target.value)}
            maxLength={HISTORY_MEMO_MAX_LENGTH}
            rows={2}
            placeholder="메모 (선택) 예: 저녁 식후 30분 걸었어요"
            className="w-full resize-none rounded-lg border border-border px-3 py-2 text-xs focus:outline-none focus:ring-1 focus:ring-primary"
            disabled={busy}
          />
          <div className="flex gap-2">
            <button
              onClick={() => submit(true)}
              disabled={busy}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2 text-sm font-medium text-white disabled:opacity-50"
              style={{ backgroundColor: "#10B981" }}
            >
              <Check size={14} /> 성공했어요
            </button>
            <button
              onClick={() => submit(false)}
              disabled={busy}
              className="flex flex-1 items-center justify-center gap-1.5 rounded-lg border border-border py-2 text-sm font-medium text-muted-foreground disabled:opacity-50"
            >
              <X size={14} /> 못했어요
            </button>
          </div>
        </div>
      )}

      {inProgress && !progress.can_record && (
        <p className="text-xs text-muted-foreground">
          {period} 기록을 마쳤습니다. 다음 회차에 다시 기록해주세요.
        </p>
      )}

      {challenge.status === "COMPLETED" && (
        <p className="text-xs font-medium" style={{ color: "#8B5CF6" }}>
          챌린지를 완료했습니다!
        </p>
      )}
      {challenge.status === "FAILED" && (
        <p className="text-xs text-muted-foreground">
          완료 기준에 닿지 못해 종료되었습니다. 새 분석으로 다른 챌린지를 추천받아 보세요.
        </p>
      )}
    </div>
  );
}
