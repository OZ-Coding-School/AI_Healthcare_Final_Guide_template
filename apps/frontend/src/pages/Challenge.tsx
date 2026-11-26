import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { Target, Calendar, Plus, AlertTriangle, History } from "lucide-react";
import {
  acceptChallenge,
  challengeActionErrorMessage,
  getChallenges,
  isExpired,
  recordChallengeHistory,
  type PersonalChallenge,
} from "../shared/api/challengeApi";
import { ApiError } from "../shared/api/client";
import ChallengeCard from "../shared/components/ChallengeCard";
import ChallengeProgressPanel from "../shared/components/ChallengeProgressPanel";

export default function Challenge() {
  const navigate = useNavigate();
  const [challenges, setChallenges] = useState<PersonalChallenge[] | null>(null);
  const [error, setError] = useState("");
  /** 수락·기록 요청 중인 챌린지 id (중복 클릭 방지) */
  const [busyId, setBusyId] = useState<number | null>(null);
  const [actionError, setActionError] = useState("");

  async function loadChallenges() {
    try {
      setChallenges(await getChallenges());
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "챌린지를 불러오지 못했습니다.");
    }
  }

  useEffect(() => {
    let active = true;
    getChallenges()
      .then((list) => {
        if (active) setChallenges(list);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "챌린지를 불러오지 못했습니다.");
      });
    return () => {
      active = false;
    };
  }, []);

  /** 응답으로 받은 챌린지로 목록의 같은 항목을 바꿉니다. 상세 응답의 histories는 목록에 필요 없어 뺍니다. */
  function replaceChallenge({
    histories: _histories,
    ...updated
  }: PersonalChallenge & { histories?: unknown }) {
    setChallenges((prev) => prev?.map((item) => (item.id === updated.id ? updated : item)) ?? prev);
  }

  async function runAction(
    challengeId: number,
    action: "accept" | "record",
    call: () => Promise<PersonalChallenge>
  ): Promise<boolean> {
    if (busyId !== null) return false;
    setBusyId(challengeId);
    setActionError("");
    try {
      replaceChallenge(await call());
      return true;
    } catch (err) {
      setActionError(challengeActionErrorMessage(action, err));
      // 409·404는 다른 곳에서 상태가 바뀐 경우라 최신 목록을 다시 불러옵니다.
      if (err instanceof ApiError && (err.status === 409 || err.status === 404))
        await loadChallenges();
      return false;
    } finally {
      setBusyId(null);
    }
  }

  const handleAccept = (challengeId: number) =>
    runAction(challengeId, "accept", () => acceptChallenge(challengeId));

  const handleRecord = (challengeId: number, isSuccess: boolean, memo: string) =>
    runAction(challengeId, "record", () =>
      recordChallengeHistory(challengeId, { is_success: isSuccess, memo: memo.trim() || null })
    );

  const list = challenges ?? [];
  const active = list.filter((c) => c.status === "IN_PROGRESS");
  const recommended = list.filter((c) => c.status === "PENDING" && !isExpired(c));
  const finished = list.filter((c) => c.status === "COMPLETED" || c.status === "FAILED");
  const completedCount = list.filter((c) => c.status === "COMPLETED").length;

  return (
    <div className="p-6 lg:p-8 max-w-4xl">
      <div className="mb-8">
        <div
          className="flex items-center gap-2 text-xs text-muted-foreground mb-2"
          style={{ fontFamily: "JetBrains Mono" }}
        >
          건강 챌린지
        </div>
        <h1 className="text-2xl font-semibold text-foreground mb-1">건강 챌린지</h1>
        <p className="text-sm text-muted-foreground">
          AI가 분석한 위험 요인을 기반으로 맞춤 챌린지를 추천합니다.
        </p>
      </div>

      {(error || actionError) && (
        <div className="mb-6 flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
          <AlertTriangle size={15} /> {error || actionError}
        </div>
      )}

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        {[
          { label: "진행 중인 챌린지", value: `${active.length}개`, color: "#0D3B6E" },
          { label: "수락 대기 추천", value: `${recommended.length}개`, color: "#10B981" },
          { label: "완료한 챌린지", value: `${completedCount}개`, color: "#8B5CF6" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white border border-border rounded-xl p-4 text-center">
            <div className="text-2xl font-bold" style={{ fontFamily: "JetBrains Mono", color }}>
              {challenges === null ? "-" : value}
            </div>
            <div className="text-xs text-muted-foreground mt-1">{label}</div>
          </div>
        ))}
      </div>

      {/* Active challenges */}
      <div className="mb-8">
        <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
          <Target size={16} className="text-primary" /> 진행 중인 챌린지
        </h2>
        {active.length > 0 ? (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {active.map((c) => (
              <ChallengeCard
                key={c.id}
                challenge={c}
                action={
                  <ChallengeProgressPanel
                    challenge={c}
                    busy={busyId === c.id}
                    onRecord={(isSuccess, memo) => handleRecord(c.id, isSuccess, memo)}
                  />
                }
              />
            ))}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">진행 중인 챌린지가 없습니다.</p>
        )}
      </div>

      {/* Recommended */}
      <div>
        <h2 className="text-base font-semibold text-foreground mb-1 flex items-center gap-2">
          <Calendar size={16} style={{ color: "#10B981" }} /> AI 추천 챌린지
        </h2>
        <p className="text-xs text-muted-foreground mb-4">
          AI 분석 결과를 기반으로 추천한 챌린지입니다. 수락 기한이 지나면 목록에서 사라집니다.
        </p>
        {challenges === null && !error && (
          <p className="text-sm text-muted-foreground">챌린지를 불러오는 중...</p>
        )}
        {challenges !== null && recommended.length === 0 && (
          <div className="bg-white border border-border rounded-xl p-8 flex flex-col items-center gap-3 text-center">
            <div className="text-sm text-foreground">수락을 기다리는 추천 챌린지가 없습니다.</div>
            <p className="text-xs text-muted-foreground">
              AI 위험도 분석을 완료하면 맞춤 챌린지가 자동으로 추천됩니다.
            </p>
            <button
              onClick={() => navigate("/app/ai/analysis")}
              className="px-4 py-2 rounded-lg text-sm font-semibold text-white"
              style={{ backgroundColor: "#10B981" }}
            >
              AI 위험도 분석하기
            </button>
          </div>
        )}
        <div className="grid sm:grid-cols-2 gap-4">
          {recommended.map((c) => (
            <ChallengeCard
              key={c.id}
              challenge={c}
              action={
                <button
                  onClick={() => handleAccept(c.id)}
                  disabled={busyId !== null}
                  className="flex items-center justify-center gap-2 w-full py-2 rounded-lg text-sm font-medium text-white disabled:opacity-50 disabled:cursor-not-allowed"
                  style={{ backgroundColor: "#10B981" }}
                >
                  <Plus size={14} /> {busyId === c.id ? "시작하는 중..." : "챌린지 시작하기"}
                </button>
              }
            />
          ))}
        </div>
      </div>

      {/* Finished */}
      {finished.length > 0 && (
        <div className="mt-8">
          <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
            <History size={16} style={{ color: "#8B5CF6" }} /> 지난 챌린지
          </h2>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {finished.map((c) => (
              <ChallengeCard
                key={c.id}
                challenge={c}
                action={
                  <ChallengeProgressPanel challenge={c} busy={false} onRecord={async () => false} />
                }
              />
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
