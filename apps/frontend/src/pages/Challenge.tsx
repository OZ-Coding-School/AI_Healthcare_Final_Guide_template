import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { Target, Calendar, Plus, AlertTriangle } from "lucide-react";
import { getChallenges, isExpired, type PersonalChallenge } from "../shared/api/challengeApi";
import ChallengeCard from "../shared/components/ChallengeCard";

export default function Challenge() {
  const navigate = useNavigate();
  const [challenges, setChallenges] = useState<PersonalChallenge[] | null>(null);
  const [error, setError] = useState("");

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

  const list = challenges ?? [];
  const active = list.filter((c) => c.status === "IN_PROGRESS");
  const recommended = list.filter((c) => c.status === "PENDING" && !isExpired(c));
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

      {error && (
        <div className="mb-6 flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
          <AlertTriangle size={15} /> {error}
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
              <ChallengeCard key={c.id} challenge={c} />
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
                  disabled
                  title="챌린지 수락 API가 준비되면 사용할 수 있습니다."
                  className="flex items-center justify-center gap-2 w-full py-2 rounded-lg text-sm font-medium text-white opacity-50 cursor-not-allowed"
                  style={{ backgroundColor: "#10B981" }}
                >
                  <Plus size={14} /> 챌린지 시작하기 (준비 중)
                </button>
              }
            />
          ))}
        </div>
      </div>
    </div>
  );
}
