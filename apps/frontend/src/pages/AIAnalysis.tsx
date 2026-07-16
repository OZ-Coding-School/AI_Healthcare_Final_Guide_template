import { useState } from "react";
import { Brain, Zap, AlertTriangle, CheckCircle, ChevronRight, RefreshCw } from "lucide-react";

function RiskGauge({ label, value, color, risk }: { label: string; value: number; color: string; risk: string }) {
  const r = 52;
  const circumference = Math.PI * r;
  const strokeDash = (value / 100) * circumference;
  return (
    <div className="flex flex-col items-center gap-3">
      <svg width="130" height="78" viewBox="0 0 130 78">
        <path d={`M 13 65 A ${r} ${r} 0 0 1 117 65`} fill="none" stroke="#E2E8F0" strokeWidth="11" strokeLinecap="round" />
        <path d={`M 13 65 A ${r} ${r} 0 0 1 117 65`} fill="none" stroke={color} strokeWidth="11" strokeLinecap="round" strokeDasharray={`${strokeDash} ${circumference}`} />
        <text x="65" y="60" textAnchor="middle" fontSize="20" fontWeight="700" fill="#0B1628" fontFamily="JetBrains Mono">{value}%</text>
      </svg>
      <div className="text-center">
        <div className="text-sm font-medium px-3 py-1 rounded-full" style={{ backgroundColor: `${color}12`, color }}>{risk}</div>
        <div className="text-sm text-muted-foreground font-medium mt-1.5">{label}</div>
      </div>
    </div>
  );
}

const FACTORS = [
  { label: "복부 비만", level: 78, color: "#EF4444", impact: "매우 높음", src: "프로필·월별" },
  { label: "공복혈당 수치", level: 62, color: "#F59E0B", impact: "높음", src: "혈당·검진" },
  { label: "신체활동 부족", level: 55, color: "#F59E0B", impact: "보통", src: "월별기록" },
  { label: "가족력 (당뇨)", level: 45, color: "#8B5CF6", impact: "보통", src: "프로필" },
  { label: "수면 품질", level: 28, color: "#10B981", impact: "낮음", src: "월별기록" },
];

export default function AIAnalysis() {
  const [analyzing, setAnalyzing] = useState(false);
  const [analyzed, setAnalyzed] = useState(true);

  const runAnalysis = async () => {
    setAnalyzing(true);
    setAnalyzed(false);
    await new Promise((r) => setTimeout(r, 2000));
    setAnalyzing(false);
    setAnalyzed(true);
  };

  return (
    <div className="p-6 lg:p-8 max-w-4xl">
      <div className="mb-8 flex items-start justify-between">
        <div>
          <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2" style={{ fontFamily: "JetBrains Mono" }}>AI / AI 위험도 분석</div>
          <h1 className="text-2xl font-semibold text-foreground mb-1">AI 위험도 분석</h1>
          <p className="text-sm text-muted-foreground">축적된 건강 데이터를 기반으로 당뇨병·고혈압 발생 위험도를 예측합니다.</p>
        </div>
        <button
          onClick={runAnalysis}
          disabled={analyzing}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-60 flex-shrink-0"
          style={{ backgroundColor: "#10B981" }}
        >
          <RefreshCw size={14} className={analyzing ? "animate-spin" : ""} />
          {analyzing ? "분석 중..." : "재분석"}
        </button>
      </div>

      {analyzing && (
        <div className="bg-white border border-border rounded-xl p-10 flex flex-col items-center gap-4 mb-6">
          <div className="w-14 h-14 rounded-full flex items-center justify-center animate-pulse" style={{ backgroundColor: "rgba(16,185,129,0.1)" }}>
            <Brain size={26} style={{ color: "#10B981" }} />
          </div>
          <div className="text-sm font-medium text-foreground">AI가 건강 데이터를 분석하고 있습니다...</div>
          <div className="text-xs text-muted-foreground" style={{ fontFamily: "JetBrains Mono" }}>건강프로필 · 월별기록 6개월 · 2024 검진결과 분석 중</div>
          <div className="w-48 h-1.5 bg-muted rounded-full overflow-hidden">
            <div className="h-full rounded-full animate-pulse" style={{ width: "70%", backgroundColor: "#10B981" }} />
          </div>
        </div>
      )}

      {analyzed && !analyzing && (
        <div className="flex flex-col gap-5">
          {/* Data source notice */}
          <div className="flex items-center gap-3 px-4 py-3 rounded-lg border text-sm" style={{ backgroundColor: "rgba(13,59,110,0.04)", borderColor: "rgba(13,59,110,0.12)", color: "#0D3B6E" }}>
            <CheckCircle size={15} />
            <span>분석 기준: 건강프로필 + 월별기록 6개월 + 2024년 건강검진 결과</span>
            <span className="ml-auto text-xs text-muted-foreground" style={{ fontFamily: "JetBrains Mono" }}>2025.01.14 분석</span>
          </div>

          {/* Gauges */}
          <div className="bg-white border border-border rounded-xl p-8 flex justify-around">
            <RiskGauge label="당뇨병" value={68} color="#F59E0B" risk="주의 필요" />
            <div className="w-px bg-border self-stretch" />
            <RiskGauge label="고혈압" value={31} color="#10B981" risk="정상 범위" />
          </div>

          {/* Risk factors */}
          <div className="bg-white border border-border rounded-xl overflow-hidden">
            <div className="px-6 py-4 border-b border-border">
              <h3 className="font-semibold text-foreground">위험 요인 분석</h3>
              <p className="text-xs text-muted-foreground mt-1">각 요인이 위험도에 기여하는 정도입니다.</p>
            </div>
            <div className="p-6 flex flex-col gap-4">
              {FACTORS.map(({ label, level, color, impact, src }) => (
                <div key={label}>
                  <div className="flex items-center justify-between mb-2">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium text-foreground">{label}</span>
                      <span className="text-[10px] text-muted-foreground" style={{ fontFamily: "JetBrains Mono" }}>{src}</span>
                    </div>
                    <span className="text-xs font-semibold" style={{ fontFamily: "JetBrains Mono", color }}>{impact}</span>
                  </div>
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div className="h-full rounded-full transition-all" style={{ width: `${level}%`, backgroundColor: color }} />
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* AI opinion */}
          <div className="rounded-xl p-5" style={{ backgroundColor: "#FFF7ED", border: "1px solid rgba(245,158,11,0.2)" }}>
            <div className="flex items-center gap-2 mb-3">
              <AlertTriangle size={15} style={{ color: "#D97706" }} />
              <span className="text-sm font-semibold" style={{ color: "#92400E" }}>AI 종합 의견</span>
            </div>
            <p className="text-sm leading-relaxed" style={{ color: "#78350F" }}>
              복부 비만과 공복혈당이 주요 위험 요인으로 확인되었습니다. 특히 당뇨 가족력이 있어 혈당 관리가 중요합니다. 저탄수화물 식단과 유산소 운동 챌린지를 3개월 꾸준히 수행하면 당뇨병 위험도를 약 30% 낮출 수 있습니다.
            </p>
          </div>

          {/* CTA to report */}
          <div className="flex items-center justify-between p-5 bg-white border border-border rounded-xl hover:shadow-sm transition-shadow cursor-pointer">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: "rgba(13,59,110,0.07)" }}>
                <Zap size={18} className="text-primary" />
              </div>
              <div>
                <div className="text-sm font-semibold text-foreground">AI 건강리포트 확인하기</div>
                <div className="text-xs text-muted-foreground">이 분석 결과를 기반으로 리포트가 생성되었습니다.</div>
              </div>
            </div>
            <ChevronRight size={16} className="text-muted-foreground" />
          </div>
        </div>
      )}
    </div>
  );
}
