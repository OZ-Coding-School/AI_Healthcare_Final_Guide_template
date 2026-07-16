import { useState, useEffect } from "react";
import {
  Plus,
  CalendarDays,
  ChevronRight,
  Loader2,
  AlertCircle,
  CheckCircle,
  X,
  Cigarette,
  Wine,
  Heart,
  Activity,
  Eye,
} from "lucide-react";
import { toast } from "sonner";
import {
  getHealthSurveys,
  getHealthSurveyDetail,
  createHealthSurvey,
  HealthSurvey,
  HealthSurveyDetail,
  HabitStatus,
  CreateHealthSurveyBody,
} from "../shared/api/healthSurveyApi";
import { ApiError } from "../shared/api/client";
import { formatDateTime } from "../shared/utils/format";

const cn = (...cls: (string | boolean | undefined)[]) => cls.filter(Boolean).join(" ");

/* ── Habit status options ── */
const HABIT_OPTIONS: { value: HabitStatus; label: string }[] = [
  { value: "NEVER", label: "안함" },
  { value: "FORMER", label: "과거" },
  { value: "CURRENT", label: "현재" },
];

/* ── Input Field ── */
function Field({
  label,
  required,
  error,
  hint,
  children,
}: {
  label: string;
  required?: boolean;
  error?: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium text-foreground">
        {label}
        {required && <span className="text-red-500 ml-0.5">*</span>}
      </label>
      {children}
      {error && (
        <span className="text-xs flex items-center gap-1 text-red-500">
          <AlertCircle size={11} />
          {error}
        </span>
      )}
      {hint && !error && <span className="text-xs text-muted-foreground">{hint}</span>}
    </div>
  );
}

const INPUT = cn(
  "w-full px-4 py-3 rounded-lg border text-sm bg-background text-foreground outline-none transition-all duration-150",
  "focus:ring-2 focus:ring-primary/20 focus:border-primary placeholder:text-muted-foreground"
);

/* ── Survey Form ── */
function SurveyForm({ onCancel, onSuccess }: { onCancel: () => void; onSuccess: () => void }) {
  const [form, setForm] = useState<CreateHealthSurveyBody>({
    smoking_status: "NEVER",
    drinking_status: "NEVER",
    systolic_bp: 0,
    diastolic_bp: 0,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [apiError, setApiError] = useState("");

  const set = (k: keyof CreateHealthSurveyBody) => (v: string | number | undefined) =>
    setForm((f) => ({ ...f, [k]: v }));

  const validate = () => {
    const e: Record<string, string> = {};

    if (form.smoking_status === "CURRENT") {
      if (!form.smoking_fr_per_day || form.smoking_fr_per_day <= 0) {
        e.smoking_fr_per_day = "하루 흡연량을 입력해주세요.";
      }
    }

    if (form.drinking_status === "CURRENT") {
      if (!form.drinking_fr_per_week || form.drinking_fr_per_week <= 0) {
        e.drinking_fr_per_week = "주당 음주 횟수를 입력해주세요.";
      }
      if (!form.drinking_amount_per_session || form.drinking_amount_per_session <= 0) {
        e.drinking_amount_per_session = "1회 음주량을 입력해주세요.";
      }
    }

    if (!form.systolic_bp || form.systolic_bp <= 0) {
      e.systolic_bp = "수축기 혈압을 입력해주세요.";
    }
    if (!form.diastolic_bp || form.diastolic_bp <= 0) {
      e.diastolic_bp = "이완기 혈압을 입력해주세요.";
    }

    return e;
  };

  const handleSubmit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    const errs = validate();
    setErrors(errs);
    if (Object.keys(errs).length) return;

    setSaving(true);
    setApiError("");
    try {
      // Clean up optional fields
      const payload: CreateHealthSurveyBody = {
        smoking_status: form.smoking_status,
        drinking_status: form.drinking_status,
        systolic_bp: form.systolic_bp,
        diastolic_bp: form.diastolic_bp,
      };

      if (form.smoking_status === "CURRENT" && form.smoking_fr_per_day) {
        payload.smoking_fr_per_day = form.smoking_fr_per_day;
      }
      if (form.drinking_status === "CURRENT") {
        if (form.drinking_fr_per_week) payload.drinking_fr_per_week = form.drinking_fr_per_week;
        if (form.drinking_amount_per_session)
          payload.drinking_amount_per_session = form.drinking_amount_per_session;
      }
      if (form.pulse && form.pulse > 0) {
        payload.pulse = form.pulse;
      }

      await createHealthSurvey(payload);
      onSuccess();
    } catch (err: unknown) {
      if (err instanceof ApiError && err.status === 409) {
        toast.error("이번 달은 이미 건강 설문을 기록했습니다.");
        onCancel();
        return;
      }
      setApiError(err instanceof Error ? err.message : "설문 저장 중 오류가 발생했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const now = new Date();
  const monthLabel = `${now.getFullYear()}년 ${String(now.getMonth() + 1).padStart(2, "0")}월`;

  return (
    <form onSubmit={handleSubmit} className="bg-white border border-border rounded-xl p-6 mb-6">
      <h3 className="font-semibold text-foreground mb-5 flex items-center gap-2">
        <CalendarDays size={16} style={{ color: "#0D3B6E" }} /> {monthLabel} 건강 설문
      </h3>

      {apiError && (
        <div
          className="flex items-center gap-2.5 px-4 py-3 rounded-lg text-sm mb-5"
          style={{
            backgroundColor: "rgba(239,68,68,0.06)",
            border: "1px solid rgba(239,68,68,0.2)",
            color: "#DC2626",
          }}
        >
          <AlertCircle size={15} className="flex-shrink-0" />
          {apiError}
        </div>
      )}

      {/* 흡연 */}
      <div className="mb-5 pb-5 border-b border-border">
        <div className="flex items-center gap-2 mb-3">
          <Cigarette size={16} style={{ color: "#0D3B6E" }} />
          <h4 className="font-semibold text-foreground text-sm">흡연 상태</h4>
        </div>
        <div className="flex gap-2 mb-3">
          {HABIT_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => {
                set("smoking_status")(opt.value);
                if (opt.value !== "CURRENT") set("smoking_fr_per_day")(undefined);
              }}
              className={cn(
                "px-4 py-2 rounded-lg text-sm font-medium border transition-all",
                form.smoking_status === opt.value
                  ? "border-primary text-white"
                  : "border-border text-foreground hover:border-primary/50"
              )}
              style={form.smoking_status === opt.value ? { backgroundColor: "#0D3B6E" } : {}}
            >
              {opt.label}
            </button>
          ))}
        </div>
        {form.smoking_status === "CURRENT" && (
          <Field
            label="하루 흡연량 (개비)"
            required
            error={errors.smoking_fr_per_day}
            hint="예: 10"
          >
            <input
              type="number"
              min="1"
              placeholder="10"
              value={form.smoking_fr_per_day ?? ""}
              onChange={(e) =>
                set("smoking_fr_per_day")(e.target.value ? Number(e.target.value) : undefined)
              }
              className={INPUT}
              style={{
                borderColor: errors.smoking_fr_per_day ? "#EF4444" : "rgba(13,59,110,0.2)",
                fontFamily: "JetBrains Mono",
              }}
            />
          </Field>
        )}
      </div>

      {/* 음주 */}
      <div className="mb-5 pb-5 border-b border-border">
        <div className="flex items-center gap-2 mb-3">
          <Wine size={16} style={{ color: "#0D3B6E" }} />
          <h4 className="font-semibold text-foreground text-sm">음주 상태</h4>
        </div>
        <div className="flex gap-2 mb-3">
          {HABIT_OPTIONS.map((opt) => (
            <button
              key={opt.value}
              type="button"
              onClick={() => {
                set("drinking_status")(opt.value);
                if (opt.value !== "CURRENT") {
                  set("drinking_fr_per_week")(undefined);
                  set("drinking_amount_per_session")(undefined);
                }
              }}
              className={cn(
                "px-4 py-2 rounded-lg text-sm font-medium border transition-all",
                form.drinking_status === opt.value
                  ? "border-primary text-white"
                  : "border-border text-foreground hover:border-primary/50"
              )}
              style={form.drinking_status === opt.value ? { backgroundColor: "#0D3B6E" } : {}}
            >
              {opt.label}
            </button>
          ))}
        </div>
        {form.drinking_status === "CURRENT" && (
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="주당 음주 횟수" required error={errors.drinking_fr_per_week} hint="예: 2">
              <input
                type="number"
                min="1"
                placeholder="2"
                value={form.drinking_fr_per_week ?? ""}
                onChange={(e) =>
                  set("drinking_fr_per_week")(e.target.value ? Number(e.target.value) : undefined)
                }
                className={INPUT}
                style={{
                  borderColor: errors.drinking_fr_per_week ? "#EF4444" : "rgba(13,59,110,0.2)",
                  fontFamily: "JetBrains Mono",
                }}
              />
            </Field>
            <Field
              label="1회 음주량 (잔)"
              required
              error={errors.drinking_amount_per_session}
              hint="예: 5"
            >
              <input
                type="number"
                min="1"
                placeholder="5"
                value={form.drinking_amount_per_session ?? ""}
                onChange={(e) =>
                  set("drinking_amount_per_session")(
                    e.target.value ? Number(e.target.value) : undefined
                  )
                }
                className={INPUT}
                style={{
                  borderColor: errors.drinking_amount_per_session
                    ? "#EF4444"
                    : "rgba(13,59,110,0.2)",
                  fontFamily: "JetBrains Mono",
                }}
              />
            </Field>
          </div>
        )}
      </div>

      {/* 혈압 & 맥박 */}
      <div className="mb-5">
        <div className="flex items-center gap-2 mb-3">
          <Heart size={16} style={{ color: "#0D3B6E" }} />
          <h4 className="font-semibold text-foreground text-sm">혈압 & 맥박</h4>
        </div>
        <div className="grid sm:grid-cols-3 gap-4">
          <Field label="수축기 혈압 (mmHg)" required error={errors.systolic_bp} hint="예: 120">
            <input
              type="number"
              min="1"
              placeholder="120"
              value={form.systolic_bp || ""}
              onChange={(e) => set("systolic_bp")(e.target.value ? Number(e.target.value) : 0)}
              className={INPUT}
              style={{
                borderColor: errors.systolic_bp ? "#EF4444" : "rgba(13,59,110,0.2)",
                fontFamily: "JetBrains Mono",
              }}
            />
          </Field>
          <Field label="이완기 혈압 (mmHg)" required error={errors.diastolic_bp} hint="예: 80">
            <input
              type="number"
              min="1"
              placeholder="80"
              value={form.diastolic_bp || ""}
              onChange={(e) => set("diastolic_bp")(e.target.value ? Number(e.target.value) : 0)}
              className={INPUT}
              style={{
                borderColor: errors.diastolic_bp ? "#EF4444" : "rgba(13,59,110,0.2)",
                fontFamily: "JetBrains Mono",
              }}
            />
          </Field>
          <Field label="맥박 (bpm)" error={errors.pulse} hint="선택 사항">
            <input
              type="number"
              min="1"
              placeholder="72"
              value={form.pulse ?? ""}
              onChange={(e) => set("pulse")(e.target.value ? Number(e.target.value) : undefined)}
              className={INPUT}
              style={{
                borderColor: errors.pulse ? "#EF4444" : "rgba(13,59,110,0.2)",
                fontFamily: "JetBrains Mono",
              }}
            />
          </Field>
        </div>
      </div>

      {/* Actions */}
      <div className="flex gap-3 justify-end">
        <button
          type="button"
          onClick={onCancel}
          className="flex items-center gap-2 px-5 py-3 rounded-lg text-sm font-medium text-muted-foreground border border-border hover:bg-muted transition-colors"
        >
          <X size={14} /> 취소
        </button>
        <button
          type="submit"
          disabled={saving}
          className="flex items-center justify-center gap-2 px-5 py-3 rounded-lg text-sm font-semibold text-white hover:opacity-90 disabled:opacity-60 transition-opacity"
          style={{ backgroundColor: "#10B981" }}
        >
          {saving ? (
            <span className="flex items-center gap-2">
              <Loader2 size={15} className="animate-spin" />
              저장 중...
            </span>
          ) : (
            <>
              <CheckCircle size={15} /> 저장
            </>
          )}
        </button>
      </div>
    </form>
  );
}

/* ── Detail Modal ── */
function DetailModal({ survey, onClose }: { survey: HealthSurveyDetail; onClose: () => void }) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl max-w-xl w-full max-h-[90vh] overflow-y-auto shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-border px-6 py-4 flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-foreground">{survey.title}</h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              {formatDateTime(survey.created_at)}
            </p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-lg flex items-center justify-center hover:bg-muted transition-colors"
          >
            <X size={16} />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 flex flex-col gap-5">
          {/* 흡연 */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Cigarette size={15} style={{ color: "#0D3B6E" }} />
              <h4 className="font-semibold text-foreground text-sm">흡연</h4>
            </div>
            <div className="px-4 py-3 bg-muted rounded-lg">
              <div className="text-sm text-foreground mb-1">{survey.smoking_status}</div>
              {survey.smoking_fr_per_day && (
                <div className="text-xs text-muted-foreground">
                  하루 {survey.smoking_fr_per_day}개비
                </div>
              )}
            </div>
          </div>

          {/* 음주 */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Wine size={15} style={{ color: "#0D3B6E" }} />
              <h4 className="font-semibold text-foreground text-sm">음주</h4>
            </div>
            <div className="px-4 py-3 bg-muted rounded-lg">
              <div className="text-sm text-foreground mb-1">{survey.drinking_status}</div>
              {survey.drinking_fr_per_week && survey.drinking_amount_per_session && (
                <div className="text-xs text-muted-foreground">
                  주 {survey.drinking_fr_per_week}회 · 1회 {survey.drinking_amount_per_session}잔
                </div>
              )}
            </div>
          </div>

          {/* 혈압 & 맥박 */}
          <div>
            <div className="flex items-center gap-2 mb-3">
              <Heart size={15} style={{ color: "#0D3B6E" }} />
              <h4 className="font-semibold text-foreground text-sm">혈압 & 맥박</h4>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="px-4 py-3 bg-muted rounded-lg">
                <div className="text-xs text-muted-foreground mb-1">수축기 혈압</div>
                <div
                  className="text-lg font-semibold text-foreground"
                  style={{ fontFamily: "JetBrains Mono" }}
                >
                  {survey.systolic_bp} <span className="text-sm font-normal">mmHg</span>
                </div>
              </div>
              <div className="px-4 py-3 bg-muted rounded-lg">
                <div className="text-xs text-muted-foreground mb-1">이완기 혈압</div>
                <div
                  className="text-lg font-semibold text-foreground"
                  style={{ fontFamily: "JetBrains Mono" }}
                >
                  {survey.diastolic_bp} <span className="text-sm font-normal">mmHg</span>
                </div>
              </div>
              {survey.pulse && (
                <div className="px-4 py-3 bg-muted rounded-lg col-span-2">
                  <div className="text-xs text-muted-foreground mb-1">맥박</div>
                  <div
                    className="text-lg font-semibold text-foreground"
                    style={{ fontFamily: "JetBrains Mono" }}
                  >
                    {survey.pulse} <span className="text-sm font-normal">bpm</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Main ── */
export default function MonthlyHealth() {
  const [showForm, setShowForm] = useState(false);
  const [surveys, setSurveys] = useState<HealthSurvey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedSurvey, setSelectedSurvey] = useState<HealthSurveyDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState(false);

  const loadSurveys = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getHealthSurveys();
      setSurveys(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "설문 목록을 불러올 수 없습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSurveys();
  }, []);

  const handleSuccess = () => {
    setShowForm(false);
    loadSurveys();
  };

  const handleViewDetail = async (surveyId: string) => {
    setLoadingDetail(true);
    try {
      const detail = await getHealthSurveyDetail(surveyId);
      setSelectedSurvey(detail);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "설문 상세 정보를 불러올 수 없습니다.");
    } finally {
      setLoadingDetail(false);
    }
  };

  return (
    <div className="p-6 lg:p-8 max-w-4xl" style={{ fontFamily: "Outfit, sans-serif" }}>
      {/* Header */}
      <div className="mb-8 flex items-start justify-between">
        <div>
          <div
            className="flex items-center gap-2 text-xs text-muted-foreground mb-2"
            style={{ fontFamily: "JetBrains Mono" }}
          >
            건강정보 기록 / 월별 건강설문
          </div>
          <h1 className="text-2xl font-semibold text-foreground mb-1">월별 건강설문</h1>
          <p className="text-sm text-muted-foreground">
            매월 건강 상태를 기록하고 변화 추이를 확인합니다.
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold text-white transition-opacity hover:opacity-90 flex-shrink-0"
          style={{ backgroundColor: "#0D3B6E" }}
        >
          <Plus size={15} /> 이번 달 기록
        </button>
      </div>

      {/* Form */}
      {showForm && <SurveyForm onCancel={() => setShowForm(false)} onSuccess={handleSuccess} />}

      {/* Error */}
      {error && (
        <div
          className="flex items-center gap-2.5 px-4 py-3 rounded-lg text-sm mb-6"
          style={{
            backgroundColor: "rgba(239,68,68,0.06)",
            border: "1px solid rgba(239,68,68,0.2)",
            color: "#DC2626",
          }}
        >
          <AlertCircle size={15} className="flex-shrink-0" />
          {error}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-12">
          <div className="flex flex-col items-center gap-3 text-muted-foreground">
            <Loader2 size={28} className="animate-spin" />
            <span className="text-sm">설문 목록을 불러오는 중...</span>
          </div>
        </div>
      )}

      {/* Survey List */}
      {!loading && surveys.length === 0 && (
        <div className="text-center py-12">
          <Activity size={40} className="mx-auto mb-3 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">아직 작성된 건강설문이 없습니다.</p>
        </div>
      )}

      {!loading && surveys.length > 0 && (
        <div className="flex flex-col gap-3">
          {surveys.map((survey) => (
            <button
              key={survey.id}
              onClick={() => handleViewDetail(survey.id)}
              className="bg-white border border-border rounded-xl overflow-hidden hover:shadow-sm transition-shadow text-left"
              disabled={loadingDetail}
            >
              <div className="px-5 py-4 flex items-center justify-between">
                <div className="flex items-center gap-3 flex-1 min-w-0">
                  <div
                    className="w-10 h-10 rounded-lg flex items-center justify-center text-xs font-medium flex-shrink-0"
                    style={{
                      backgroundColor: "rgba(13,59,110,0.07)",
                      color: "#0D3B6E",
                      fontFamily: "JetBrains Mono",
                    }}
                  >
                    <CalendarDays size={16} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-foreground text-sm">{survey.title}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      - 등록일시: {formatDateTime(survey.created_at)}
                    </div>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Eye size={14} />
                  상세보기
                  <ChevronRight size={16} className="text-muted-foreground" />
                </div>
              </div>
            </button>
          ))}
        </div>
      )}

      {/* Detail Modal */}
      {selectedSurvey && (
        <DetailModal survey={selectedSurvey} onClose={() => setSelectedSurvey(null)} />
      )}
    </div>
  );
}
