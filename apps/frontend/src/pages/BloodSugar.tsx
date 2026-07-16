import { useState, useEffect } from "react";
import {
  Plus,
  Droplet,
  Loader2,
  AlertCircle,
  CheckCircle,
  X,
  Trash2,
  Clock,
  Dumbbell,
  Pill,
  FileText,
  ChevronDown,
} from "lucide-react";
import {
  getBloodSugarMeasurements,
  getBloodSugarMeasurementDetail,
  createBloodSugarMeasurement,
  deleteBloodSugarMeasurement,
  BloodSugarMeasurement,
  BloodSugarMeasurementDetail,
  BloodSugarMeasureType,
  ExerciseType,
  CreateBloodSugarMeasurementBody,
} from "../shared/api/bloodSugarApi";
import { formatDateTime } from "../shared/utils/format";

const cn = (...cls: (string | boolean | undefined)[]) => cls.filter(Boolean).join(" ");

/* ── Measure Type & Exercise Type options ── */
const MEASURE_TYPE_OPTIONS: { value: BloodSugarMeasureType; label: string }[] = [
  { value: "FASTING", label: "공복" },
  { value: "BEFORE_BREAKFAST", label: "아침 식전" },
  { value: "AFTER_BREAKFAST", label: "아침 식후" },
  { value: "BEFORE_LUNCH", label: "점심 식전" },
  { value: "AFTER_LUNCH", label: "점심 식후" },
  { value: "BEFORE_DINNER", label: "저녁 식전" },
  { value: "AFTER_DINNER", label: "저녁 식후" },
  { value: "BEFORE_SLEEP", label: "취침전" },
  { value: "RANDOM", label: "임의측정" },
];

const EXERCISE_TYPE_OPTIONS: { value: ExerciseType; label: string }[] = [
  { value: "CARDIO", label: "유산소" },
  { value: "STRENGTH", label: "근력" },
  { value: "BOTH", label: "유산소, 근력" },
  { value: "NOT_APPLICABLE", label: "해당사항 없음" },
];

/* ── Blood Sugar Status ── */
type BloodSugarStatus = "low" | "normal" | "high" | "very_high";

function getBloodSugarStatus(value: number, measureType: string): BloodSugarStatus {
  const isFasting = measureType === "공복";
  if (isFasting) {
    if (value < 70) return "low";
    if (value <= 100) return "normal";
    if (value <= 125) return "high";
    return "very_high";
  }
  // 식후 등 기타
  if (value < 70) return "low";
  if (value <= 140) return "normal";
  if (value <= 199) return "high";
  return "very_high";
}

function StatusBadge({ status }: { status: BloodSugarStatus }) {
  const config = {
    low: { bg: "rgba(59,130,246,0.1)", color: "#3B82F6", label: "저혈당" },
    normal: { bg: "rgba(16,185,129,0.1)", color: "#10B981", label: "정상" },
    high: { bg: "rgba(245,158,11,0.1)", color: "#D97706", label: "높음" },
    very_high: { bg: "rgba(239,68,68,0.1)", color: "#EF4444", label: "매우 높음" },
  };
  const { bg, color, label } = config[status];
  return (
    <span
      className="flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full"
      style={{ fontFamily: "JetBrains Mono", backgroundColor: bg, color }}
    >
      {label}
    </span>
  );
}

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
  "w-full px-3 py-2.5 rounded-lg border text-sm bg-background text-foreground outline-none transition-all duration-150",
  "focus:ring-2 focus:ring-primary/20 focus:border-primary placeholder:text-muted-foreground"
);

/* ── Measurement Form ── */
function MeasurementForm({ onCancel, onSuccess }: { onCancel: () => void; onSuccess: () => void }) {
  const now = new Date();
  const [form, setForm] = useState<CreateBloodSugarMeasurementBody>({
    measure_type: "FASTING",
    blood_glucose: 0,
    has_exercised: false,
    has_medicated: false,
    measured_at: now.toISOString().slice(0, 16),
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [apiError, setApiError] = useState("");

  const set =
    (k: keyof CreateBloodSugarMeasurementBody) => (v: string | number | boolean | undefined) => {
      setForm((f) => ({ ...f, [k]: v }));
    };

  const validate = () => {
    const e: Record<string, string> = {};

    if (!form.blood_glucose || form.blood_glucose < 1 || form.blood_glucose > 1000) {
      e.blood_glucose = "혈당 수치를 올바르게 입력해주세요 (1~1000).";
    }

    if (form.has_exercised) {
      if (!form.exercise_type) e.exercise_type = "운동 유형을 선택해주세요.";
      if (!form.exercise_minutes || form.exercise_minutes <= 0) {
        e.exercise_minutes = "운동 시간을 입력해주세요.";
      }
    }

    if (form.has_medicated) {
      if (!form.medicine_name || form.medicine_name.trim() === "") {
        e.medicine_name = "약 이름을 입력해주세요.";
      }
    }

    if (!form.measured_at) e.measured_at = "측정 일시를 선택해주세요.";

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
      const payload: CreateBloodSugarMeasurementBody = {
        measure_type: form.measure_type,
        blood_glucose: form.blood_glucose,
        has_exercised: form.has_exercised,
        has_medicated: form.has_medicated,
        measured_at: new Date(form.measured_at).toISOString(),
      };

      if (form.measure_type === "POST_MEAL" && form.minutes_since_meal) {
        payload.minutes_since_meal = form.minutes_since_meal;
      }

      if (form.has_exercised) {
        if (form.exercise_type) payload.exercise_type = form.exercise_type;
        if (form.exercise_minutes) payload.exercise_minutes = form.exercise_minutes;
        if (form.minutes_since_exercise)
          payload.minutes_since_exercise = form.minutes_since_exercise;
      }

      if (form.has_medicated) {
        if (form.medicine_name) payload.medicine_name = form.medicine_name;
        if (form.minutes_since_medication)
          payload.minutes_since_medication = form.minutes_since_medication;
      }

      if (form.memo && form.memo.trim() !== "") {
        payload.memo = form.memo;
      }

      await createBloodSugarMeasurement(payload);
      onSuccess();
    } catch (err: unknown) {
      setApiError(
        err instanceof Error ? err.message : "혈당 측정 기록 저장 중 오류가 발생했습니다."
      );
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-white border border-border rounded-xl p-6 mb-6">
      <h3 className="font-semibold text-foreground mb-5 flex items-center gap-2">
        <Droplet size={16} style={{ color: "#0D3B6E" }} /> 혈당 측정 기록 추가
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

      {/* 측정 정보 */}
      <div className="mb-5 pb-5 border-b border-border">
        <div className="flex items-center gap-2 mb-3">
          <Droplet size={16} style={{ color: "#0D3B6E" }} />
          <h4 className="font-semibold text-foreground text-sm">측정 정보</h4>
        </div>
        <div className="grid sm:grid-cols-2 gap-4 mb-4">
          <Field label="측정 유형" required>
            <div className="grid grid-cols-2 gap-2">
              {MEASURE_TYPE_OPTIONS.map((opt) => (
                <button
                  key={opt.value}
                  type="button"
                  onClick={() => set("measure_type")(opt.value)}
                  className={cn(
                    "px-3 py-2 rounded-lg text-sm font-medium border transition-all",
                    form.measure_type === opt.value
                      ? "border-primary text-white"
                      : "border-border text-foreground hover:border-primary/50"
                  )}
                  style={form.measure_type === opt.value ? { backgroundColor: "#0D3B6E" } : {}}
                >
                  {opt.label}
                </button>
              ))}
            </div>
          </Field>
          <Field label="측정 일시" required error={errors.measured_at}>
            <input
              type="datetime-local"
              value={form.measured_at}
              onChange={(e) => set("measured_at")(e.target.value)}
              className={INPUT}
              style={{
                borderColor: errors.measured_at ? "#EF4444" : "rgba(13,59,110,0.2)",
                fontFamily: "JetBrains Mono",
              }}
            />
          </Field>
        </div>
        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="혈당 수치 (mg/dL)" required error={errors.blood_glucose} hint="1~1000">
            <input
              type="number"
              min="1"
              max="1000"
              placeholder="100"
              value={form.blood_glucose || ""}
              onChange={(e) => set("blood_glucose")(e.target.value ? Number(e.target.value) : 0)}
              className={INPUT}
              style={{
                borderColor: errors.blood_glucose ? "#EF4444" : "rgba(13,59,110,0.2)",
                fontFamily: "JetBrains Mono",
              }}
            />
          </Field>
          {form.measure_type === "POST_MEAL" && (
            <Field label="식후 경과 시간 (분)" hint="선택 사항">
              <input
                type="number"
                min="1"
                placeholder="60"
                value={form.minutes_since_meal ?? ""}
                onChange={(e) =>
                  set("minutes_since_meal")(e.target.value ? Number(e.target.value) : undefined)
                }
                className={INPUT}
                style={{ borderColor: "rgba(13,59,110,0.2)", fontFamily: "JetBrains Mono" }}
              />
            </Field>
          )}
        </div>
      </div>

      {/* 운동 여부 */}
      <div className="mb-5 pb-5 border-b border-border">
        <div className="flex items-center gap-2 mb-3">
          <Dumbbell size={16} style={{ color: "#0D3B6E" }} />
          <h4 className="font-semibold text-foreground text-sm">운동 여부</h4>
        </div>
        <div className="flex gap-2 mb-3">
          {[
            { v: true, l: "운동함" },
            { v: false, l: "안함" },
          ].map(({ v, l }) => (
            <button
              key={String(v)}
              type="button"
              onClick={() => {
                set("has_exercised")(v);
                if (!v) {
                  set("exercise_type")(undefined);
                  set("exercise_minutes")(undefined);
                  set("minutes_since_exercise")(undefined);
                }
              }}
              className={cn(
                "px-4 py-2 rounded-lg text-sm font-medium border transition-all",
                form.has_exercised === v
                  ? "border-primary text-white"
                  : "border-border text-foreground hover:border-primary/50"
              )}
              style={form.has_exercised === v ? { backgroundColor: "#0D3B6E" } : {}}
            >
              {l}
            </button>
          ))}
        </div>
        {form.has_exercised && (
          <div className="grid sm:grid-cols-3 gap-4">
            <Field label="운동 유형" required error={errors.exercise_type}>
              <select
                value={form.exercise_type ?? ""}
                onChange={(e) => set("exercise_type")(e.target.value as ExerciseType)}
                className={INPUT}
                style={{
                  borderColor: errors.exercise_type ? "#EF4444" : "rgba(13,59,110,0.2)",
                  fontFamily: "JetBrains Mono",
                }}
              >
                <option value="">선택</option>
                {EXERCISE_TYPE_OPTIONS.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </Field>
            <Field label="운동 시간 (분)" required error={errors.exercise_minutes}>
              <input
                type="number"
                min="1"
                placeholder="30"
                value={form.exercise_minutes ?? ""}
                onChange={(e) =>
                  set("exercise_minutes")(e.target.value ? Number(e.target.value) : undefined)
                }
                className={INPUT}
                style={{
                  borderColor: errors.exercise_minutes ? "#EF4444" : "rgba(13,59,110,0.2)",
                  fontFamily: "JetBrains Mono",
                }}
              />
            </Field>
            <Field label="운동 후 경과 시간 (분)" hint="선택">
              <input
                type="number"
                min="1"
                placeholder="20"
                value={form.minutes_since_exercise ?? ""}
                onChange={(e) =>
                  set("minutes_since_exercise")(e.target.value ? Number(e.target.value) : undefined)
                }
                className={INPUT}
                style={{ borderColor: "rgba(13,59,110,0.2)", fontFamily: "JetBrains Mono" }}
              />
            </Field>
          </div>
        )}
      </div>

      {/* 복약 여부 */}
      <div className="mb-5 pb-5 border-b border-border">
        <div className="flex items-center gap-2 mb-3">
          <Pill size={16} style={{ color: "#0D3B6E" }} />
          <h4 className="font-semibold text-foreground text-sm">복약 여부</h4>
        </div>
        <div className="flex gap-2 mb-3">
          {[
            { v: true, l: "복약함" },
            { v: false, l: "안함" },
          ].map(({ v, l }) => (
            <button
              key={String(v)}
              type="button"
              onClick={() => {
                set("has_medicated")(v);
                if (!v) {
                  set("medicine_name")(undefined);
                  set("minutes_since_medication")(undefined);
                }
              }}
              className={cn(
                "px-4 py-2 rounded-lg text-sm font-medium border transition-all",
                form.has_medicated === v
                  ? "border-primary text-white"
                  : "border-border text-foreground hover:border-primary/50"
              )}
              style={form.has_medicated === v ? { backgroundColor: "#0D3B6E" } : {}}
            >
              {l}
            </button>
          ))}
        </div>
        {form.has_medicated && (
          <div className="grid sm:grid-cols-2 gap-4">
            <Field label="약 이름" required error={errors.medicine_name}>
              <input
                type="text"
                placeholder="예: 메트포르민"
                value={form.medicine_name ?? ""}
                onChange={(e) => set("medicine_name")(e.target.value)}
                className={INPUT}
                style={{ borderColor: errors.medicine_name ? "#EF4444" : "rgba(13,59,110,0.2)" }}
              />
            </Field>
            <Field label="복약 후 경과 시간 (분)" hint="선택">
              <input
                type="number"
                min="1"
                placeholder="120"
                value={form.minutes_since_medication ?? ""}
                onChange={(e) =>
                  set("minutes_since_medication")(
                    e.target.value ? Number(e.target.value) : undefined
                  )
                }
                className={INPUT}
                style={{ borderColor: "rgba(13,59,110,0.2)", fontFamily: "JetBrains Mono" }}
              />
            </Field>
          </div>
        )}
      </div>

      {/* 메모 */}
      <div className="mb-5">
        <div className="flex items-center gap-2 mb-3">
          <FileText size={16} style={{ color: "#0D3B6E" }} />
          <h4 className="font-semibold text-foreground text-sm">메모</h4>
        </div>
        <Field label="참고 메모" hint="최대 1000자">
          <textarea
            placeholder="예: 점심 식후 가벼운 산책"
            value={form.memo ?? ""}
            onChange={(e) => set("memo")(e.target.value)}
            rows={3}
            maxLength={1000}
            className={INPUT}
            style={{ borderColor: "rgba(13,59,110,0.2)", resize: "vertical" }}
          />
        </Field>
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

/* ── Main ── */
export default function BloodSugar() {
  const [showForm, setShowForm] = useState(false);
  const [measurements, setMeasurements] = useState<BloodSugarMeasurement[]>([]);
  const [detailsMap, setDetailsMap] = useState<Record<string, BloodSugarMeasurementDetail>>({});
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [loadingDetails, setLoadingDetails] = useState<Record<string, boolean>>({});

  const loadMeasurements = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getBloodSugarMeasurements();
      setMeasurements(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "혈당 측정 목록을 불러올 수 없습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadMeasurements();
  }, []);

  const handleSuccess = () => {
    setShowForm(false);
    loadMeasurements();
  };

  const handleToggleCard = async (measurementId: string) => {
    // 이미 펼쳐진 카드를 클릭하면 닫기
    if (expandedId === measurementId) {
      setExpandedId(null);
      return;
    }

    // 상세 정보가 이미 로드되어 있으면 바로 펼치기
    if (detailsMap[measurementId]) {
      setExpandedId(measurementId);
      return;
    }

    // 상세 정보 로드
    setLoadingDetails((prev) => ({ ...prev, [measurementId]: true }));
    try {
      const detail = await getBloodSugarMeasurementDetail(measurementId);
      setDetailsMap((prev) => ({ ...prev, [measurementId]: detail }));
      setExpandedId(measurementId);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "상세 정보를 불러올 수 없습니다.");
    } finally {
      setLoadingDetails((prev) => ({ ...prev, [measurementId]: false }));
    }
  };

  const handleDelete = async (measurementId: string) => {
    if (!confirm("이 기록을 삭제하시겠습니까?")) return;

    try {
      await deleteBloodSugarMeasurement(measurementId);
      setExpandedId(null);
      loadMeasurements();
    } catch (err: unknown) {
      alert(err instanceof Error ? err.message : "삭제 중 오류가 발생했습니다.");
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
            건강정보 기록 / 혈당 측정 기록
          </div>
          <h1 className="text-2xl font-semibold text-foreground mb-1">혈당 측정 기록</h1>
          <p className="text-sm text-muted-foreground">
            당뇨병 관리를 위한 일별 혈당 측정 기록을 관리합니다.
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold text-white transition-opacity hover:opacity-90 flex-shrink-0"
          style={{ backgroundColor: "#0D3B6E" }}
        >
          <Plus size={15} /> 측정 기록 추가
        </button>
      </div>

      {/* Form */}
      {showForm && (
        <MeasurementForm onCancel={() => setShowForm(false)} onSuccess={handleSuccess} />
      )}

      {/* Error */}
      {!showForm && error && (
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
      {!showForm && loading && (
        <div className="flex items-center justify-center py-12">
          <div className="flex flex-col items-center gap-3 text-muted-foreground">
            <Loader2 size={28} className="animate-spin" />
            <span className="text-sm">측정 목록을 불러오는 중...</span>
          </div>
        </div>
      )}

      {/* Measurement List */}
      {!showForm && !loading && measurements.length === 0 && (
        <div className="text-center py-12">
          <Droplet size={40} className="mx-auto mb-3 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">아직 등록된 혈당 측정 기록이 없습니다.</p>
        </div>
      )}

      {!showForm && !loading && measurements.length > 0 && (
        <div className="flex flex-col gap-3">
          {measurements.map((measurement) => {
            const isExpanded = expandedId === measurement.id;
            const detail = detailsMap[measurement.id];
            const isLoadingDetail = loadingDetails[measurement.id];
            const status = detail
              ? getBloodSugarStatus(detail.blood_glucose, detail.measure_type)
              : undefined;

            return (
              <div
                key={measurement.id}
                className="bg-white border border-border rounded-xl overflow-hidden transition-shadow hover:shadow-sm"
              >
                {/* Card Header */}
                <button
                  onClick={() => handleToggleCard(measurement.id)}
                  className="w-full px-5 py-4 flex items-center justify-between text-left"
                  disabled={isLoadingDetail}
                >
                  <div className="flex items-center gap-3 flex-1 min-w-0">
                    <div
                      className="w-10 h-10 rounded-lg flex items-center justify-center text-xs font-medium flex-shrink-0"
                      style={{ backgroundColor: "rgba(13,59,110,0.07)", color: "#0D3B6E" }}
                    >
                      <Droplet size={16} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="font-semibold text-foreground text-m">
                          {measurement.measure_type} 혈당 기록
                        </span>
                      </div>
                      <div className="text-xs text-muted-foreground mt-0.5">
                        - 측정일시: {formatDateTime(measurement.measured_at)}
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    {isLoadingDetail ? (
                      <Loader2 size={16} className="animate-spin text-muted-foreground" />
                    ) : (
                      <ChevronDown
                        size={18}
                        className="text-muted-foreground transition-transform duration-200"
                        style={{ transform: isExpanded ? "rotate(180deg)" : "rotate(0deg)" }}
                      />
                    )}
                  </div>
                </button>

                {/* Card Detail (expanded) */}
                {isExpanded && detail && (
                  <div className="px-5 pb-5 border-t border-border">
                    <div className="pt-4 flex flex-col gap-4">
                      {/* 혈당 수치 */}
                      <div className="px-4 py-3 bg-muted/50 rounded-lg">
                        <div className="flex items-center gap-2 mb-2">
                          <Droplet size={14} style={{ color: "#0D3B6E" }} />
                          <div className="text-xs font-semibold text-foreground">혈당 수치</div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span
                            className="text-2xl font-bold text-foreground"
                            style={{ fontFamily: "JetBrains Mono" }}
                          >
                            {detail.blood_glucose}
                          </span>
                          <span className="text-sm text-muted-foreground">mg/dL</span>
                          {status && <StatusBadge status={status} />}
                        </div>
                      </div>

                      {/* 식후 경과 시간 */}
                      {detail.minutes_since_meal && (
                        <div className="px-4 py-2.5 bg-muted/50 rounded-lg">
                          <div className="flex items-center gap-1.5 mb-0.5">
                            <Clock size={12} style={{ color: "#0D3B6E" }} />
                            <div className="text-xs text-muted-foreground">식후 경과 시간</div>
                          </div>
                          <div
                            className="text-sm text-foreground font-medium"
                            style={{ fontFamily: "JetBrains Mono" }}
                          >
                            {detail.minutes_since_meal}분
                          </div>
                        </div>
                      )}

                      {/* 운동 정보 */}
                      {detail.has_exercised && (
                        <div className="px-4 py-3 bg-muted/50 rounded-lg">
                          <div className="flex items-center gap-2 mb-2">
                            <Dumbbell size={14} style={{ color: "#0D3B6E" }} />
                            <div className="text-xs font-semibold text-foreground">운동 정보</div>
                          </div>
                          <div className="text-sm text-foreground">
                            {detail.exercise_type} · {detail.exercise_minutes}분
                          </div>
                          {detail.minutes_since_exercise && (
                            <div className="flex items-center gap-1.5 text-xs text-muted-foreground mt-1">
                              <Clock size={11} style={{ color: "#0D3B6E" }} />
                              운동 후 {detail.minutes_since_exercise}분 경과
                            </div>
                          )}
                        </div>
                      )}

                      {/* 복약 정보 */}
                      {detail.has_medicated && (
                        <div className="px-4 py-3 bg-muted/50 rounded-lg">
                          <div className="flex items-center gap-2 mb-2">
                            <Pill size={14} style={{ color: "#0D3B6E" }} />
                            <div className="text-xs font-semibold text-foreground">복약 정보</div>
                          </div>
                          <div className="text-sm text-foreground font-medium">
                            {detail.medicine_name}
                          </div>
                          {detail.minutes_since_medication && (
                            <div className="flex items-center gap-1.5 text-xs text-muted-foreground mt-1">
                              <Clock size={11} style={{ color: "#0D3B6E" }} />
                              복약 후 {detail.minutes_since_medication}분 경과
                            </div>
                          )}
                        </div>
                      )}

                      {/* 메모 */}
                      {detail.memo && (
                        <div className="px-4 py-3 bg-muted/50 rounded-lg">
                          <div className="flex items-center gap-2 mb-2">
                            <FileText size={14} style={{ color: "#0D3B6E" }} />
                            <div className="text-xs font-semibold text-foreground">메모</div>
                          </div>
                          <div className="text-sm text-foreground whitespace-pre-wrap">
                            {detail.memo}
                          </div>
                        </div>
                      )}

                      {/* Actions */}
                      <div className="flex justify-end pt-2">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            handleDelete(measurement.id);
                          }}
                          className="flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-medium text-red-600 hover:bg-red-50 transition-colors"
                        >
                          <Trash2 size={13} />
                          삭제
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
