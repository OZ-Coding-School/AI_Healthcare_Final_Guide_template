import { FileText, Download, ChevronRight } from "lucide-react";

const REPORTS = [
  {
    id: 1,
    date: "2025.01.14",
    diabetes: 68,
    hypertension: 31,
    highlight: "복부 비만·공복혈당 주의",
    isNew: true,
  },
  {
    id: 2,
    date: "2024.10.22",
    diabetes: 72,
    hypertension: 38,
    highlight: "신체활동 부족 고위험",
    isNew: false,
  },
  {
    id: 3,
    date: "2024.07.15",
    diabetes: 75,
    hypertension: 42,
    highlight: "혈당·혈압 복합 위험",
    isNew: false,
  },
];

function RiskPill({ value, label }: { value: number; label: string }) {
  const color = value >= 70 ? "#EF4444" : value >= 50 ? "#F59E0B" : "#10B981";
  return (
    <div className="flex items-center gap-1.5 text-xs" style={{ fontFamily: "JetBrains Mono" }}>
      <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
      <span className="text-muted-foreground">{label}</span>
      <span className="font-semibold" style={{ color }}>
        {value}%
      </span>
    </div>
  );
}

export default function AIReport() {
  return (
    <div className="p-6 lg:p-8 max-w-3xl">
      <div className="mb-8">
        <div
          className="flex items-center gap-2 text-xs text-muted-foreground mb-2"
          style={{ fontFamily: "JetBrains Mono" }}
        >
          AI / AI 건강리포트
        </div>
        <h1 className="text-2xl font-semibold text-foreground mb-1">AI 건강리포트</h1>
        <p className="text-sm text-muted-foreground">
          AI 위험도 분석 결과를 기반으로 생성된 리포트를 조회합니다.
        </p>
      </div>

      <div className="flex flex-col gap-4">
        {REPORTS.map((report) => (
          <div
            key={report.id}
            className="bg-white border border-border rounded-xl overflow-hidden hover:shadow-sm transition-shadow cursor-pointer"
          >
            <div className="px-5 py-5 flex items-center justify-between">
              <div className="flex items-start gap-4">
                <div
                  className="w-11 h-11 rounded-xl flex items-center justify-center flex-shrink-0"
                  style={{ backgroundColor: "rgba(13,59,110,0.07)" }}
                >
                  <FileText size={20} className="text-primary" />
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-semibold text-foreground text-sm">AI 건강리포트</span>
                    {report.isNew && (
                      <span
                        className="text-[10px] font-semibold px-2 py-0.5 rounded-full"
                        style={{
                          fontFamily: "JetBrains Mono",
                          backgroundColor: "rgba(16,185,129,0.1)",
                          color: "#10B981",
                        }}
                      >
                        NEW
                      </span>
                    )}
                  </div>
                  <div
                    className="text-xs text-muted-foreground mb-2"
                    style={{ fontFamily: "JetBrains Mono" }}
                  >
                    {report.date}
                  </div>
                  <div className="flex items-center gap-4">
                    <RiskPill value={report.diabetes} label="당뇨" />
                    <RiskPill value={report.hypertension} label="고혈압" />
                  </div>
                  <div className="text-xs text-muted-foreground mt-1.5">{report.highlight}</div>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  className="p-2 rounded-lg hover:bg-muted text-muted-foreground hover:text-foreground transition-colors"
                  onClick={(e) => e.stopPropagation()}
                >
                  <Download size={15} />
                </button>
                <ChevronRight size={16} className="text-muted-foreground" />
              </div>
            </div>

            {/* Latest report preview */}
            {report.isNew && (
              <div className="border-t border-border mx-5 pt-4 pb-5">
                <div
                  className="text-xs font-semibold text-muted-foreground mb-3 uppercase tracking-wide"
                  style={{ fontFamily: "JetBrains Mono" }}
                >
                  핵심 인사이트
                </div>
                <div className="grid sm:grid-cols-2 gap-2">
                  {[
                    { icon: "🔴", text: "복부 비만이 당뇨 위험도에 가장 크게 기여" },
                    { icon: "🟡", text: "공복혈당 118mg/dL — 전당뇨 범위 진입" },
                    { icon: "🟢", text: "혈압은 정상 범위를 유지 중" },
                    { icon: "💡", text: "3개월 식단·운동 개선으로 위험 30% 감소 가능" },
                  ].map(({ icon, text }) => (
                    <div key={text} className="flex items-start gap-2 text-xs text-foreground">
                      <span>{icon}</span> {text}
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
