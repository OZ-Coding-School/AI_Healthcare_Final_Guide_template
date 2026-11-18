import { useEffect, useState } from "react";
import { useNavigate } from "react-router";
import { FileText, ChevronRight, AlertTriangle } from "lucide-react";
import {
  getDiseasePredictions,
  predictionStatusLabel,
  riskLevelColor,
  type DiseasePredictionSummary,
} from "../shared/api/diseasePredictionApi";
import { formatDateTime } from "../shared/utils/format";

function RiskPill({ result }: { result: DiseasePredictionSummary["results"][number] }) {
  const color = riskLevelColor(result.risk_level);
  return (
    <div className="flex items-center gap-1.5 text-xs" style={{ fontFamily: "JetBrains Mono" }}>
      <div className="w-2 h-2 rounded-full" style={{ backgroundColor: color }} />
      <span className="text-muted-foreground">{result.disease_name}</span>
      <span className="font-semibold" style={{ color }}>
        {result.risk_score.toFixed(1)}% · {result.risk_level_label}
      </span>
    </div>
  );
}

export default function AIReport() {
  const navigate = useNavigate();
  const [reports, setReports] = useState<DiseasePredictionSummary[] | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    let active = true;
    getDiseasePredictions()
      .then((list) => {
        if (active) setReports(list);
      })
      .catch((err) => {
        if (active) setError(err instanceof Error ? err.message : "리포트를 불러오지 못했습니다.");
      });
    return () => {
      active = false;
    };
  }, []);

  const latestCompletedId = reports?.find((report) => report.status === "COMPLETED")?.id;

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
          지금까지의 AI 위험도 분석 결과를 최신순으로 조회합니다.
        </p>
      </div>

      {error && (
        <div className="flex items-center gap-2 rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
          <AlertTriangle size={15} /> {error}
        </div>
      )}

      {!error && reports === null && (
        <div className="text-sm text-muted-foreground">리포트를 불러오는 중...</div>
      )}

      {reports?.length === 0 && (
        <div className="bg-white border border-border rounded-xl p-10 flex flex-col items-center gap-3 text-center">
          <FileText size={26} className="text-muted-foreground" />
          <div className="text-sm text-foreground">아직 분석 결과가 없습니다.</div>
          <button
            onClick={() => navigate("/app/ai/analysis")}
            className="px-4 py-2 rounded-lg text-sm font-semibold text-white"
            style={{ backgroundColor: "#10B981" }}
          >
            AI 위험도 분석하기
          </button>
        </div>
      )}

      <div className="flex flex-col gap-4">
        {reports?.map((report) => (
          <button
            key={report.id}
            onClick={() => navigate(`/app/ai/analysis?prediction=${report.id}`)}
            className="bg-white border border-border rounded-xl overflow-hidden hover:shadow-sm transition-shadow text-left"
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
                    {report.id === latestCompletedId && (
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
                    {report.status !== "COMPLETED" && (
                      <span
                        className="text-[10px] font-semibold px-2 py-0.5 rounded-full bg-muted"
                        style={{
                          fontFamily: "JetBrains Mono",
                          color: report.status === "FAILED" ? "#EF4444" : undefined,
                        }}
                      >
                        {predictionStatusLabel(report.status)}
                      </span>
                    )}
                  </div>
                  <div
                    className="text-xs text-muted-foreground mb-2"
                    style={{ fontFamily: "JetBrains Mono" }}
                  >
                    {formatDateTime(report.completed_at ?? report.created_at)}
                  </div>
                  <div className="flex flex-wrap items-center gap-4">
                    {report.results.map((result) => (
                      <RiskPill key={result.model_type} result={result} />
                    ))}
                  </div>
                </div>
              </div>
              <ChevronRight size={16} className="text-muted-foreground flex-shrink-0" />
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
