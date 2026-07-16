import { useState } from "react";
import { useNavigate } from "react-router";
import { AlertTriangle, ChevronRight, ArrowLeft } from "lucide-react";
import { withdraw, WithdrawalReason, WITHDRAWAL_REASON_LABELS } from "../shared/api/authApi";
import { ApiError } from "../shared/api/client";
import { clearAuth } from "../shared/api/auth";

const cn = (...classes: (string | boolean | undefined)[]) => classes.filter(Boolean).join(" ");

const REASONS = Object.entries(WITHDRAWAL_REASON_LABELS) as [WithdrawalReason, string][];

type Step = "reason" | "confirm";

export default function Withdraw() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("reason");
  const [reason, setReason] = useState<WithdrawalReason | "">("");
  const [reasonDetail, setReasonDetail] = useState("");
  const [feedback, setFeedback] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [agreed, setAgreed] = useState(false);

  const handleWithdraw = async () => {
    if (!reason || !agreed) return;
    setError("");
    setSubmitting(true);
    try {
      await withdraw({
        reason: reason as WithdrawalReason,
        ...(reasonDetail.trim() ? { reason_detail: reasonDetail.trim() } : {}),
        ...(feedback.trim() ? { feedback: feedback.trim() } : {}),
      });
      clearAuth();
      navigate("/", { replace: true });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "탈퇴 처리 중 오류가 발생했습니다.";
      setError(msg);
      setSubmitting(false);
    }
  };

  return (
    <div className="p-6 lg:p-8 max-w-xl">
      <div className="mb-8">
        <button
          onClick={() => navigate(-1)}
          className="flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors mb-4"
        >
          <ArrowLeft size={15} /> 뒤로가기
        </button>
        <div
          className="flex items-center gap-2 text-xs text-muted-foreground mb-2"
          style={{ fontFamily: "JetBrains Mono" }}
        >
          계정 설정 / 회원 탈퇴
        </div>
        <h1 className="text-2xl font-semibold text-foreground mb-1">회원 탈퇴</h1>
        <p className="text-sm text-muted-foreground">탈퇴 전 아래 내용을 꼭 확인해주세요.</p>
      </div>

      {/* Warning box */}
      <div
        className="rounded-xl p-5 mb-6 flex flex-col gap-3"
        style={{ backgroundColor: "rgba(239,68,68,0.05)", border: "1px solid rgba(239,68,68,0.2)" }}
      >
        <div className="flex items-center gap-2">
          <AlertTriangle size={16} style={{ color: "#EF4444" }} />
          <span className="text-sm font-semibold" style={{ color: "#DC2626" }}>
            탈퇴 시 주의사항
          </span>
        </div>
        <ul className="flex flex-col gap-1.5">
          {[
            "모든 건강 프로필 및 기록 데이터가 영구 삭제됩니다.",
            "AI 분석 결과 및 리포트가 삭제됩니다.",
            "진행 중인 챌린지가 모두 종료됩니다.",
            "탈퇴 후 동일 이메일로 재가입이 제한될 수 있습니다.",
          ].map((item) => (
            <li key={item} className="flex items-start gap-2 text-sm" style={{ color: "#7F1D1D" }}>
              <ChevronRight size={13} className="flex-shrink-0 mt-0.5" />
              {item}
            </li>
          ))}
        </ul>
      </div>

      {step === "reason" && (
        <div className="flex flex-col gap-5">
          {/* Reason selection */}
          <div className="flex flex-col gap-2">
            <label className="text-sm font-semibold text-foreground">
              탈퇴 사유를 선택해주세요 <span style={{ color: "#EF4444" }}>*</span>
            </label>
            <div className="flex flex-col gap-2">
              {REASONS.map(([value, label]) => (
                <label
                  key={value}
                  className={cn(
                    "flex items-center gap-3 px-4 py-3 rounded-xl border cursor-pointer transition-all duration-150",
                    reason === value
                      ? "border-primary bg-secondary"
                      : "border-border hover:border-primary/40 hover:bg-muted/50"
                  )}
                >
                  <div
                    className={cn(
                      "w-4 h-4 rounded-full border-2 flex items-center justify-center flex-shrink-0 transition-colors",
                      reason === value ? "border-primary" : "border-muted-foreground/40"
                    )}
                  >
                    {reason === value && (
                      <div
                        className="w-2 h-2 rounded-full"
                        style={{ backgroundColor: "#0D3B6E" }}
                      />
                    )}
                  </div>
                  <input
                    type="radio"
                    name="reason"
                    value={value}
                    className="sr-only"
                    onChange={() => setReason(value)}
                  />
                  <span className="text-sm text-foreground">{label}</span>
                </label>
              ))}
            </div>
          </div>

          {/* Detail */}
          {reason && (
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-foreground">
                상세 사유 <span className="text-muted-foreground font-normal">(선택)</span>
              </label>
              <textarea
                placeholder="불편하셨던 점을 알려주시면 서비스 개선에 도움이 됩니다."
                value={reasonDetail}
                onChange={(e) => setReasonDetail(e.target.value)}
                rows={3}
                className="w-full px-4 py-3 rounded-lg border border-border text-sm bg-background text-foreground outline-none transition-all duration-150 focus:ring-2 focus:ring-primary/20 focus:border-primary resize-none placeholder:text-muted-foreground"
              />
            </div>
          )}

          {/* Feedback */}
          {reason && (
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-foreground">
                서비스 피드백 <span className="text-muted-foreground font-normal">(선택)</span>
              </label>
              <textarea
                placeholder="VitalAI에 바라는 점을 자유롭게 남겨주세요."
                value={feedback}
                onChange={(e) => setFeedback(e.target.value)}
                rows={3}
                className="w-full px-4 py-3 rounded-lg border border-border text-sm bg-background text-foreground outline-none transition-all duration-150 focus:ring-2 focus:ring-primary/20 focus:border-primary resize-none placeholder:text-muted-foreground"
              />
            </div>
          )}

          <button
            onClick={() => setStep("confirm")}
            disabled={!reason}
            className="w-full py-3.5 rounded-lg text-sm font-semibold transition-all hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ backgroundColor: "#EF4444", color: "#fff" }}
          >
            다음 단계
          </button>
          <button
            onClick={() => navigate(-1)}
            className="w-full py-3 rounded-lg text-sm font-medium text-muted-foreground border border-border hover:bg-muted transition-colors"
          >
            취소
          </button>
        </div>
      )}

      {step === "confirm" && (
        <div className="flex flex-col gap-5">
          <div className="bg-white border border-border rounded-xl p-5 flex flex-col gap-3">
            <div className="text-sm font-semibold text-foreground mb-1">탈퇴 정보 확인</div>
            <div className="flex justify-between text-sm">
              <span className="text-muted-foreground">탈퇴 사유</span>
              <span className="font-medium text-foreground">
                {reason ? WITHDRAWAL_REASON_LABELS[reason as WithdrawalReason] : "-"}
              </span>
            </div>
            {reasonDetail && (
              <div className="flex justify-between text-sm">
                <span className="text-muted-foreground flex-shrink-0">상세 사유</span>
                <span className="font-medium text-foreground text-right ml-4">{reasonDetail}</span>
              </div>
            )}
          </div>

          {/* Agreement */}
          <label className="flex items-start gap-3 cursor-pointer">
            <div
              onClick={() => setAgreed(!agreed)}
              className={cn(
                "w-5 h-5 rounded border-2 flex items-center justify-center flex-shrink-0 mt-0.5 transition-colors cursor-pointer",
                agreed ? "border-red-500 bg-red-500" : "border-muted-foreground/40"
              )}
            >
              {agreed && (
                <svg width="10" height="8" viewBox="0 0 10 8" fill="none">
                  <path
                    d="M1 4L3.5 6.5L9 1"
                    stroke="white"
                    strokeWidth="2"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>
              )}
            </div>
            <span className="text-sm text-foreground">
              위 주의사항을 모두 확인했으며, 모든 데이터가 영구적으로 삭제됨에 동의합니다.
            </span>
          </label>

          {error && (
            <div
              className="flex items-center gap-2 px-4 py-3 rounded-lg text-sm"
              style={{
                backgroundColor: "rgba(239,68,68,0.06)",
                border: "1px solid rgba(239,68,68,0.2)",
                color: "#DC2626",
              }}
            >
              <AlertTriangle size={14} className="flex-shrink-0" />
              {error}
            </div>
          )}

          <button
            onClick={handleWithdraw}
            disabled={!agreed || submitting}
            className="w-full py-3.5 rounded-lg text-sm font-semibold transition-all hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed"
            style={{ backgroundColor: "#EF4444", color: "#fff" }}
          >
            {submitting ? (
              <span className="flex items-center justify-center gap-2">
                <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                  <circle
                    className="opacity-25"
                    cx="12"
                    cy="12"
                    r="10"
                    stroke="currentColor"
                    strokeWidth="4"
                  />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                </svg>
                탈퇴 처리 중...
              </span>
            ) : (
              "회원 탈퇴"
            )}
          </button>

          <button
            onClick={() => setStep("reason")}
            className="w-full flex items-center justify-center gap-1.5 py-3 rounded-lg text-sm font-medium text-muted-foreground border border-border hover:bg-muted transition-colors"
          >
            <ArrowLeft size={14} /> 이전 단계
          </button>
        </div>
      )}
    </div>
  );
}
