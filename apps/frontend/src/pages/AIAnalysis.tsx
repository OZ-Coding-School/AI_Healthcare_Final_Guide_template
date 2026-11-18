import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router";
import {
  Brain,
  Zap,
  AlertTriangle,
  CheckCircle,
  ChevronRight,
  RefreshCw,
  Info,
  Target,
} from "lucide-react";
import { ApiError } from "../shared/api/client";
import { getHealthProfile, type HealthProfile } from "../shared/api/healthProfileApi";
import {
  createDiseasePrediction,
  formatFactorValue,
  getDiseasePrediction,
  getDiseasePredictions,
  inputIssuesFromPrediction,
  inputIssuesFromValidation,
  isAbortError,
  isFinalStatus,
  missingRecordOf,
  predictionErrorMessage,
  predictionStatusLabel,
  PredictionWaitTimeoutError,
  riskLevelColor,
  waitForPredictionResult,
  type DiseasePrediction,
  type DiseasePredictionResult,
  type DiseasePredictionStatus,
  type InputIssue,
  type PredictionModelType,
} from "../shared/api/diseasePredictionApi";
import {
  canRetryRecommendation,
  getChallengeRecommendation,
  recommendationErrorMessage,
  retryChallengeRecommendation,
  waitForChallengeRecommendation,
  type ChallengeRecommendation,
} from "../shared/api/challengeApi";
import ChallengeCard from "../shared/components/ChallengeCard";
import { formatDateTime } from "../shared/utils/format";

type Phase =
  | { kind: "loading" }
  | { kind: "empty" }
  | { kind: "waiting"; status: DiseasePredictionStatus }
  | { kind: "completed"; prediction: DiseasePrediction }
  | { kind: "failed"; prediction: DiseasePrediction }
  | { kind: "error"; message: string };

interface RequestError {
  message: string;
  link?: { label: string; path: string };
  issues?: InputIssue[];
}

/** 진단 받은 질환의 건강 프로필 필드 */
const DIAGNOSED_FIELD: Record<PredictionModelType, keyof HealthProfile> = {
  diabetes_risk: "has_diabetes",
  hypertension_risk: "has_hypertension",
};

function isDiagnosed(profile: HealthProfile | null, modelType: PredictionModelType): boolean {
  return Boolean(profile?.[DIAGNOSED_FIELD[modelType]]);
}

function RiskGauge({ result, diagnosed }: { result: DiseasePredictionResult; diagnosed: boolean }) {
  const r = 52;
  const circumference = Math.PI * r;
  const value = Math.min(100, Math.max(0, result.risk_score));
  const strokeDash = (value / 100) * circumference;
  const color = riskLevelColor(result.risk_level);
  const { moderate, high } = result.risk_thresholds;

  return (
    <div className="flex flex-col items-center gap-3">
      <svg width="130" height="78" viewBox="0 0 130 78">
        <path
          d={`M 13 65 A ${r} ${r} 0 0 1 117 65`}
          fill="none"
          stroke="#E2E8F0"
          strokeWidth="11"
          strokeLinecap="round"
        />
        <path
          d={`M 13 65 A ${r} ${r} 0 0 1 117 65`}
          fill="none"
          stroke={color}
          strokeWidth="11"
          strokeLinecap="round"
          strokeDasharray={`${strokeDash} ${circumference}`}
        />
        <text
          x="65"
          y="60"
          textAnchor="middle"
          fontSize="20"
          fontWeight="700"
          fill="#0B1628"
          fontFamily="JetBrains Mono"
        >
          {value.toFixed(1)}%
        </text>
      </svg>
      <div className="text-center">
        <div
          className="text-sm font-medium px-3 py-1 rounded-full inline-block"
          style={{ backgroundColor: `${color}12`, color }}
        >
          위험도 {result.risk_level_label}
        </div>
        <div className="text-sm text-muted-foreground font-medium mt-1.5">
          {result.disease_name}
          {diagnosed && (
            <span className="ml-1.5 text-[10px] px-1.5 py-0.5 rounded bg-muted">진단 받음</span>
          )}
        </div>
        <div
          className="text-[10px] text-muted-foreground mt-1"
          style={{ fontFamily: "JetBrains Mono" }}
        >
          중간 ≥ {(moderate * 100).toFixed(1)}% · 높음 ≥ {(high * 100).toFixed(1)}%
        </div>
      </div>
    </div>
  );
}

function RiskFactorList({ result }: { result: DiseasePredictionResult }) {
  const maxImpact = Math.max(...result.risk_factors.map((f) => Math.abs(f.shap_value)), 1e-9);
  const isProbability = result.shap_output_space === "probability";

  return (
    <div className="bg-white border border-border rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-border">
        <h3 className="font-semibold text-foreground">{result.disease_name} 주요 요인</h3>
        <p className="text-xs text-muted-foreground mt-1">
          위험도에 크게 영향을 준 요인입니다. 막대 길이는 영향의 크기를 나타냅니다.
        </p>
      </div>
      <div className="p-6 flex flex-col gap-4">
        {result.risk_factors.length === 0 && (
          <p className="text-sm text-muted-foreground">표시할 요인이 없습니다.</p>
        )}
        {result.risk_factors.map((factor) => {
          const increases = factor.direction === "increase";
          const color = increases ? "#EF4444" : "#10B981";
          const impact = isProbability
            ? `${factor.shap_value > 0 ? "+" : ""}${(factor.shap_value * 100).toFixed(1)}%p`
            : factor.shap_value.toFixed(3);
          return (
            <div key={factor.feature}>
              <div className="flex items-center justify-between mb-2 gap-3">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium text-foreground">{factor.display_name}</span>
                  <span
                    className="text-[10px] text-muted-foreground"
                    style={{ fontFamily: "JetBrains Mono" }}
                  >
                    입력값 {formatFactorValue(factor.value)}
                  </span>
                  {!factor.actionable && (
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-muted text-muted-foreground">
                      {factor.reverse_causation_suspected ? "해석 주의" : "바꾸기 어려운 요인"}
                    </span>
                  )}
                </div>
                <span
                  className="text-xs font-semibold flex-shrink-0"
                  style={{ fontFamily: "JetBrains Mono", color }}
                >
                  {increases ? "위험 ↑" : "위험 ↓"} {impact}
                </span>
              </div>
              <div className="h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${(Math.abs(factor.shap_value) / maxImpact) * 100}%`,
                    backgroundColor: color,
                  }}
                />
              </div>
            </div>
          );
        })}
        {result.out_of_training_range.length > 0 && (
          <div className="flex items-start gap-2 text-xs text-amber-700 bg-amber-50 rounded-lg px-3 py-2">
            <AlertTriangle size={13} className="mt-0.5 flex-shrink-0" />
            <span>
              {result.out_of_training_range.join(", ")} 값이 학습 데이터 범위를 벗어나 결과 해석에
              주의가 필요합니다.
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

function InputIssueList({ issues }: { issues: InputIssue[] }) {
  if (issues.length === 0) return null;
  return (
    <ul className="mt-3 flex flex-col gap-1.5">
      {issues.map((issue, index) => (
        <li key={`${issue.source}-${issue.field}-${index}`} className="text-xs">
          <span className="font-semibold">
            {issue.source} · {issue.field}
          </span>{" "}
          <span className="opacity-80">({issue.reason})</span>
          {issue.sourcePath && (
            <Link to={issue.sourcePath} className="ml-2 underline font-medium">
              수정하기
            </Link>
          )}
        </li>
      ))}
    </ul>
  );
}

type RecommendationState =
  | { kind: "loading" }
  | { kind: "ready"; recommendation: ChallengeRecommendation }
  | { kind: "error"; message: string };

function ChallengeRecommendationPanel({ predictionId }: { predictionId: string }) {
  const navigate = useNavigate();
  const [state, setState] = useState<RecommendationState>({ kind: "loading" });
  const controllerRef = useRef<AbortController | null>(null);

  const follow = useCallback(
    async (task?: () => Promise<ChallengeRecommendation>) => {
      controllerRef.current?.abort();
      const controller = new AbortController();
      controllerRef.current = controller;
      const { signal } = controller;

      try {
        if (task) {
          const started = await task();
          if (signal.aborted) return;
          setState({ kind: "ready", recommendation: started });
        }
        const recommendation = await waitForChallengeRecommendation(predictionId, {
          signal,
          onUpdate: (update) => {
            if (!signal.aborted) setState({ kind: "ready", recommendation: update });
          },
        });
        if (!signal.aborted) setState({ kind: "ready", recommendation });
      } catch (err) {
        if (isAbortError(err) || signal.aborted) return;
        setState({
          kind: "error",
          message: err instanceof Error ? err.message : "챌린지 추천을 불러오지 못했습니다.",
        });
      }
    },
    [predictionId]
  );

  useEffect(() => {
    setState({ kind: "loading" });
    void follow();
    return () => controllerRef.current?.abort();
  }, [follow]);

  const recommendation = state.kind === "ready" ? state.recommendation : null;
  const processing =
    state.kind === "loading" ||
    (recommendation !== null &&
      (recommendation.status === null || recommendation.status === "PROCESSING"));

  return (
    <div className="bg-white border border-border rounded-xl overflow-hidden">
      <div className="px-6 py-4 border-b border-border flex items-center justify-between">
        <div>
          <h3 className="font-semibold text-foreground flex items-center gap-2">
            <Target size={16} className="text-primary" /> AI 맞춤 챌린지
          </h3>
          <p className="text-xs text-muted-foreground mt-1">
            생활습관으로 바꿀 수 있는 위험 요인을 바탕으로 추천합니다. 의료 진단이나 처방이
            아닙니다.
          </p>
        </div>
        <button
          onClick={() => navigate("/app/challenge")}
          className="text-xs font-medium text-primary flex items-center gap-1 flex-shrink-0"
        >
          내 챌린지 <ChevronRight size={14} />
        </button>
      </div>

      <div className="p-6">
        {processing && (
          <div className="flex flex-col items-center gap-3 py-6">
            <RefreshCw size={20} className="animate-spin text-primary" />
            <div className="text-sm text-muted-foreground">
              분석 결과에 맞는 챌린지를 만들고 있습니다...
            </div>
            {recommendation?.status === "PROCESSING" && (
              <button
                onClick={() => void follow()}
                className="text-xs underline text-muted-foreground"
              >
                다시 확인
              </button>
            )}
          </div>
        )}

        {state.kind === "error" && (
          <div className="flex flex-col items-center gap-3 py-4 text-sm text-red-600">
            {state.message}
            <button onClick={() => void follow()} className="text-xs underline">
              다시 조회
            </button>
          </div>
        )}

        {recommendation?.status === "FAILED" && (
          <div className="flex flex-col items-center gap-3 py-4 text-center">
            <div className="text-sm text-foreground">
              {recommendationErrorMessage(recommendation.error_code)}
            </div>
            {canRetryRecommendation(recommendation.error_code) ? (
              <button
                onClick={() => void follow(() => retryChallengeRecommendation(predictionId))}
                className="px-4 py-2 rounded-lg text-sm font-semibold text-white"
                style={{ backgroundColor: "#10B981" }}
              >
                다시 추천받기
              </button>
            ) : (
              recommendation.error_code !== "NO_PREDICTION_RESULT" && (
                <button
                  onClick={() => void follow(() => getChallengeRecommendation(predictionId))}
                  className="text-xs underline text-muted-foreground"
                >
                  다시 조회
                </button>
              )
            )}
          </div>
        )}

        {recommendation?.status === "COMPLETED" && (
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
            {recommendation.challenges.map((challenge) => (
              <ChallengeCard key={challenge.id} challenge={challenge} />
            ))}
            {recommendation.challenges.length === 0 && (
              <p className="text-sm text-muted-foreground">추천된 챌린지가 없습니다.</p>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

export default function AIAnalysis() {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const targetId = searchParams.get("prediction");

  const [phase, setPhase] = useState<Phase>({ kind: "loading" });
  const [profile, setProfile] = useState<HealthProfile | null>(null);
  const [requestError, setRequestError] = useState<RequestError | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const controllerRef = useRef<AbortController | null>(null);

  const newSignal = useCallback(() => {
    controllerRef.current?.abort();
    const controller = new AbortController();
    controllerRef.current = controller;
    return controller.signal;
  }, []);

  useEffect(() => () => controllerRef.current?.abort(), []);

  const showPrediction = useCallback((prediction: DiseasePrediction) => {
    setPhase(
      prediction.status === "COMPLETED"
        ? { kind: "completed", prediction }
        : { kind: "failed", prediction }
    );
  }, []);

  /** 확정 전 예측을 SSE로 기다립니다. */
  const follow = useCallback(
    async (predictionId: string, signal: AbortSignal, eventsUrl?: string) => {
      setPhase({ kind: "waiting", status: "PENDING" });
      try {
        const prediction = await waitForPredictionResult(predictionId, {
          eventsUrl,
          signal,
          onStatus: (status) => {
            if (!signal.aborted) setPhase({ kind: "waiting", status });
          },
        });
        if (!signal.aborted) showPrediction(prediction);
      } catch (err) {
        if (isAbortError(err) || signal.aborted) return;
        setPhase({
          kind: "error",
          message:
            err instanceof PredictionWaitTimeoutError
              ? "분석이 예상보다 오래 걸리고 있습니다. 잠시 후 새로고침해주세요."
              : err instanceof Error
                ? err.message
                : "분석 결과를 불러오지 못했습니다.",
        });
      }
    },
    [showPrediction]
  );

  /** 지정한 예측(?prediction=) 또는 가장 최근 예측을 불러옵니다. */
  const load = useCallback(async () => {
    const signal = newSignal();
    setPhase({ kind: "loading" });
    try {
      const [loadedProfile, predictionId] = await Promise.all([
        getHealthProfile().catch(() => null),
        targetId
          ? Promise.resolve(targetId)
          : getDiseasePredictions().then((list) => list[0]?.id ?? null),
      ]);
      if (signal.aborted) return;
      setProfile(loadedProfile);

      if (!predictionId) {
        setPhase({ kind: "empty" });
        return;
      }
      const prediction = await getDiseasePrediction(predictionId);
      if (signal.aborted) return;
      if (isFinalStatus(prediction.status)) showPrediction(prediction);
      else await follow(prediction.id, signal);
    } catch (err) {
      if (isAbortError(err) || signal.aborted) return;
      setPhase({
        kind: "error",
        message: err instanceof Error ? err.message : "분석 결과를 불러오지 못했습니다.",
      });
    }
  }, [targetId, newSignal, follow, showPrediction]);

  useEffect(() => {
    void load();
  }, [load]);

  const runAnalysis = async () => {
    setRequestError(null);
    setSubmitting(true);
    try {
      const created = await createDiseasePrediction();
      if (targetId) {
        // 이전 예측을 보고 있었다면 최신 예측 화면으로 바꾸면 load가 새 예측을 이어받습니다.
        setSearchParams({}, { replace: true });
      } else {
        await follow(created.id, newSignal(), created.events_url);
      }
    } catch (err) {
      if (!(err instanceof ApiError)) {
        setRequestError({
          message: "분석 요청 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.",
        });
      } else if (err.status === 404) {
        const missing = missingRecordOf(err);
        setRequestError(
          missing
            ? { message: `${missing.label}을(를) 먼저 입력해주세요.`, link: missing }
            : { message: "분석에 필요한 건강 기록을 찾지 못했습니다." }
        );
      } else if (err.status === 409) {
        // 이미 진행 중인 예측이 있으면 그 예측을 이어서 기다립니다.
        if (targetId) setSearchParams({}, { replace: true });
        else await load();
      } else if (err.status === 422) {
        setRequestError({
          message: "건강 기록 중 예측 기준에 맞지 않는 값이 있습니다. 아래 항목을 수정해주세요.",
          issues: inputIssuesFromValidation(err.body.errors),
        });
      } else if (err.status === 503) {
        setRequestError({
          message: "분석 서비스가 일시적으로 응답하지 않습니다. 잠시 후 다시 시도해주세요.",
        });
      } else {
        setRequestError({ message: err.message || "분석 요청에 실패했습니다." });
      }
    } finally {
      setSubmitting(false);
    }
  };

  const busy = submitting || phase.kind === "loading" || phase.kind === "waiting";
  const completed = phase.kind === "completed" ? phase.prediction : null;
  const diagnosedResults =
    completed?.results.filter((result) => isDiagnosed(profile, result.model_type)) ?? [];

  return (
    <div className="p-6 lg:p-8 max-w-4xl">
      <div className="mb-8 flex items-start justify-between">
        <div>
          <div
            className="flex items-center gap-2 text-xs text-muted-foreground mb-2"
            style={{ fontFamily: "JetBrains Mono" }}
          >
            AI / AI 위험도 분석
          </div>
          <h1 className="text-2xl font-semibold text-foreground mb-1">AI 위험도 분석</h1>
          <p className="text-sm text-muted-foreground">
            건강 프로필·건강검진·월별 기록을 바탕으로 현재 당뇨병·고혈압 위험도를 분석합니다.
          </p>
        </div>
        <button
          onClick={runAnalysis}
          disabled={busy}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold text-white transition-opacity hover:opacity-90 disabled:opacity-60 flex-shrink-0"
          style={{ backgroundColor: "#10B981" }}
        >
          <RefreshCw size={14} className={busy ? "animate-spin" : ""} />
          {phase.kind === "waiting"
            ? "분석 중..."
            : phase.kind === "empty"
              ? "분석 시작"
              : "재분석"}
        </button>
      </div>

      {requestError && (
        <div className="mb-6 rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
          <div className="flex items-start gap-2">
            <AlertTriangle size={15} className="mt-0.5 flex-shrink-0" />
            <div>
              <span>{requestError.message}</span>
              {requestError.link && (
                <Link to={requestError.link.path} className="ml-2 underline font-medium">
                  {requestError.link.label} 입력하기
                </Link>
              )}
              <InputIssueList issues={requestError.issues ?? []} />
            </div>
          </div>
        </div>
      )}

      {phase.kind === "loading" && (
        <div className="bg-white border border-border rounded-xl p-10 flex justify-center text-sm text-muted-foreground">
          분석 결과를 불러오는 중...
        </div>
      )}

      {phase.kind === "waiting" && (
        <div className="bg-white border border-border rounded-xl p-10 flex flex-col items-center gap-4 mb-6">
          <div
            className="w-14 h-14 rounded-full flex items-center justify-center animate-pulse"
            style={{ backgroundColor: "rgba(16,185,129,0.1)" }}
          >
            <Brain size={26} style={{ color: "#10B981" }} />
          </div>
          <div className="text-sm font-medium text-foreground">
            AI가 건강 데이터를 분석하고 있습니다...
          </div>
          <div className="text-xs text-muted-foreground" style={{ fontFamily: "JetBrains Mono" }}>
            {predictionStatusLabel(phase.status)} · 건강 프로필 · 최근 건강검진 · 최근 월별 기록
          </div>
          <div className="w-48 h-1.5 bg-muted rounded-full overflow-hidden">
            <div
              className="h-full rounded-full animate-pulse"
              style={{
                width: phase.status === "PROCESSING" ? "70%" : "30%",
                backgroundColor: "#10B981",
              }}
            />
          </div>
        </div>
      )}

      {phase.kind === "empty" && (
        <div className="bg-white border border-border rounded-xl p-10 flex flex-col items-center gap-3 text-center">
          <Brain size={28} className="text-muted-foreground" />
          <div className="text-sm font-medium text-foreground">아직 분석 결과가 없습니다.</div>
          <p className="text-xs text-muted-foreground leading-relaxed">
            <Link to="/app/health/profile" className="underline">
              건강 프로필
            </Link>
            ,{" "}
            <Link to="/app/health/checkup" className="underline">
              건강검진
            </Link>
            ,{" "}
            <Link to="/app/health/monthly" className="underline">
              월별 기록
            </Link>
            을 입력한 뒤 분석을 시작하세요.
          </p>
        </div>
      )}

      {phase.kind === "error" && (
        <div className="bg-white border border-border rounded-xl p-10 flex flex-col items-center gap-3 text-center">
          <AlertTriangle size={24} className="text-red-500" />
          <div className="text-sm text-foreground">{phase.message}</div>
          <button onClick={() => void load()} className="text-xs underline text-muted-foreground">
            다시 불러오기
          </button>
        </div>
      )}

      {phase.kind === "failed" && (
        <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-sm text-red-700">
          <div className="flex items-start gap-2">
            <AlertTriangle size={15} className="mt-0.5 flex-shrink-0" />
            <div>
              <div className="font-semibold">
                {predictionErrorMessage(phase.prediction.error_code)}
              </div>
              <div className="text-xs mt-1 opacity-80">
                {formatDateTime(phase.prediction.created_at)} 요청 · 재분석 버튼으로 다시 시도할 수
                있습니다.
              </div>
              <InputIssueList issues={inputIssuesFromPrediction(phase.prediction)} />
            </div>
          </div>
        </div>
      )}

      {completed && (
        <div className="flex flex-col gap-5">
          {/* Data source notice */}
          <div
            className="flex items-center gap-3 px-4 py-3 rounded-lg border text-sm"
            style={{
              backgroundColor: "rgba(13,59,110,0.04)",
              borderColor: "rgba(13,59,110,0.12)",
              color: "#0D3B6E",
            }}
          >
            <CheckCircle size={15} />
            <span>분석 기준: 건강 프로필 + 건강검진 + 월별 기록</span>
            <span
              className="ml-auto text-xs text-muted-foreground"
              style={{ fontFamily: "JetBrains Mono" }}
            >
              {formatDateTime(completed.completed_at)} 분석
            </span>
          </div>

          {/* Gauges */}
          <div className="bg-white border border-border rounded-xl p-8 flex justify-around">
            {completed.results.map((result, index) => (
              <div key={result.model_type} className="flex">
                {index > 0 && <div className="w-px bg-border self-stretch mr-8" />}
                <RiskGauge result={result} diagnosed={isDiagnosed(profile, result.model_type)} />
              </div>
            ))}
          </div>

          {/* Interpretation notice */}
          <div className="flex items-start gap-2 px-4 py-3 rounded-lg bg-muted/60 text-xs text-muted-foreground leading-relaxed">
            <Info size={14} className="mt-0.5 flex-shrink-0" />
            <div>
              <p>
                위험도는 현재 건강 데이터가 비슷한 사람들 중 해당 질환이 있는 비율이며, 미래 발병
                예측이나 의학적 진단이 아닙니다.
              </p>
              {diagnosedResults.length > 0 && (
                <p className="mt-1">
                  이미 {diagnosedResults.map((r) => r.disease_name).join("·")} 진단을 받으셨다면
                  위험도가 높게 나오는 것이 자연스럽습니다. 이 결과는 새로운 진단이 아니며, 치료와
                  관리는 담당 의료진과 상의해주세요.
                </p>
              )}
            </div>
          </div>

          {/* Risk factors */}
          {completed.results.map((result) => (
            <RiskFactorList key={result.model_type} result={result} />
          ))}

          {/* Challenge recommendation */}
          <ChallengeRecommendationPanel predictionId={completed.id} />

          {/* CTA to report */}
          <button
            onClick={() => navigate("/app/ai/report")}
            className="flex items-center justify-between p-5 bg-white border border-border rounded-xl hover:shadow-sm transition-shadow text-left"
          >
            <div className="flex items-center gap-3">
              <div
                className="w-10 h-10 rounded-lg flex items-center justify-center"
                style={{ backgroundColor: "rgba(13,59,110,0.07)" }}
              >
                <Zap size={18} className="text-primary" />
              </div>
              <div>
                <div className="text-sm font-semibold text-foreground">AI 건강리포트 확인하기</div>
                <div className="text-xs text-muted-foreground">
                  지난 분석 결과와 위험도 변화를 확인합니다.
                </div>
              </div>
            </div>
            <ChevronRight size={16} className="text-muted-foreground" />
          </button>
        </div>
      )}
    </div>
  );
}
