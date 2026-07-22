import { useState, useEffect } from "react";
import {
  Plus,
  Microscope,
  ChevronRight,
  Loader2,
  AlertCircle,
  CheckCircle,
  X,
  Eye,
  User,
  Activity,
  Heart,
  Droplets,
  Clipboard,
  TestTube,
  Calendar,
  ChevronLeft,
  AlertTriangle,
} from "lucide-react";
import {
  getAnnualHealthScreenings,
  getAnnualHealthScreeningDetail,
  createAnnualHealthScreening,
  AnnualHealthScreening,
  AnnualHealthScreeningDetail,
  UrineProteinStatus,
  UrineGlucoseStatus,
  CreateAnnualHealthScreeningBody,
  urineStatusToKorean,
} from "../shared/api/annualHealthScreeningApi";
import { formatDateTime } from "../shared/utils/format";

const cn = (...cls: (string | boolean | undefined)[]) => cls.filter(Boolean).join(" ");

/* ── Status calculation ── */
type Status = "normal" | "warning" | "danger";

function getStatus(value: number, type: string): Status {
  switch (type) {
    case "sbp":
      if (value < 120) return "normal";
      if (value < 140) return "warning";
      return "danger";
    case "dbp":
      if (value < 80) return "normal";
      if (value < 90) return "warning";
      return "danger";
    case "fbs":
      if (value < 100) return "normal";
      if (value < 126) return "warning";
      return "danger";
    case "hba1c":
      if (value < 5.7) return "normal";
      if (value < 6.5) return "warning";
      return "danger";
    case "total_cholesterol":
      if (value < 200) return "normal";
      if (value < 240) return "warning";
      return "danger";
    case "ldl":
      if (value < 130) return "normal";
      if (value < 160) return "warning";
      return "danger";
    case "hdl":
      if (value >= 60) return "normal";
      if (value >= 40) return "warning";
      return "danger";
    case "triglyceride":
      if (value < 150) return "normal";
      if (value < 200) return "warning";
      return "danger";
    case "ast":
    case "alt":
      if (value < 40) return "normal";
      if (value < 100) return "warning";
      return "danger";
    case "creatinine":
      // 크레아티닌: 0.6-1.2 정상
      if (value >= 0.6 && value <= 1.2) return "normal";
      if (value > 1.2 && value <= 1.5) return "warning";
      return "danger";
    case "bmi":
      if (value >= 18.5 && value < 23) return "normal";
      if (value >= 23 && value < 25) return "warning";
      return "danger";
    case "waist":
      // 남성 90cm, 여성 85cm 기준 (여기서는 85 사용)
      if (value < 85) return "normal";
      if (value < 90) return "warning";
      return "danger";
    default:
      return "normal";
  }
}

function StatusBadge({ status }: { status: Status }) {
  const config = {
    normal: { bg: "rgba(16,185,129,0.1)", color: "#10B981", icon: CheckCircle, label: "정상" },
    warning: { bg: "rgba(245,158,11,0.1)", color: "#D97706", icon: AlertTriangle, label: "주의" },
    danger: { bg: "rgba(239,68,68,0.1)", color: "#EF4444", icon: AlertCircle, label: "위험" },
  };
  const { bg, color, icon: Icon, label } = config[status];
  return (
    <span
      className="flex items-center gap-1 text-xs font-medium px-2 py-0.5 rounded-full"
      style={{ fontFamily: "JetBrains Mono", backgroundColor: bg, color }}
    >
      <Icon size={10} /> {label}
    </span>
  );
}

/* ── Urine options ── */
const URINE_OPTIONS: { value: UrineProteinStatus | UrineGlucoseStatus; label: string }[] = [
  { value: "NEGATIVE", label: "음성 (-)" },
  { value: "TRACE", label: "미량 (±)" },
  { value: "POSITIVE_1", label: "양성 1+ (+)" },
  { value: "POSITIVE_2", label: "양성 2+ (++)" },
  { value: "POSITIVE_3", label: "양성 3+ (+++)" },
  { value: "POSITIVE_4", label: "양성 4+ (++++)" },
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
  "w-full px-3 py-2.5 rounded-lg border text-sm bg-background text-foreground outline-none transition-all duration-150",
  "focus:ring-2 focus:ring-primary/20 focus:border-primary placeholder:text-muted-foreground"
);

/* ── Screening Form ── */
function ScreeningForm({ onCancel, onSuccess }: { onCancel: () => void; onSuccess: () => void }) {
  const [form, setForm] = useState<CreateAnnualHealthScreeningBody>({
    height: 0,
    weight: 0,
    bmi: 0,
    waist_circumference: 0,
    sbp: 0,
    dbp: 0,
    fbs: 0,
    hba1c: 0,
    triglyceride: 0,
    ldl: 0,
    hdl: 0,
    total_cholesterol: 0,
    ast: 0,
    alt: 0,
    creatinine: 0,
    urine_protein: "NEGATIVE",
    urine_glucose: "NEGATIVE",
    family_history_diabetes: false,
    family_history_hypertension: false,
    screening_at: "",
    is_fasting: true,
  });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [saving, setSaving] = useState(false);
  const [apiError, setApiError] = useState("");

  const set = (k: keyof CreateAnnualHealthScreeningBody) => (v: string | number | boolean) => {
    setForm((f) => ({ ...f, [k]: v }));
    // Auto-calculate BMI when height or weight changes
    if (k === "height" || k === "weight") {
      const h = k === "height" ? Number(v) : form.height;
      const w = k === "weight" ? Number(v) : form.weight;
      if (h > 0 && w > 0) {
        const bmi = w / (h / 100) ** 2;
        setForm((f) => ({ ...f, bmi: Math.round(bmi * 10) / 10 }));
      }
    }
  };

  const validate = () => {
    const e: Record<string, string> = {};

    // Required fields
    if (!form.height || form.height <= 0 || form.height > 300)
      e.height = "키를 올바르게 입력해주세요 (0.1~300.0).";
    if (!form.weight || form.weight <= 0 || form.weight > 500)
      e.weight = "체중을 올바르게 입력해주세요 (0.1~500.0).";
    if (!form.bmi || form.bmi <= 0 || form.bmi > 100)
      e.bmi = "BMI를 올바르게 입력해주세요 (0.1~100.0).";
    if (
      !form.waist_circumference ||
      form.waist_circumference <= 0 ||
      form.waist_circumference > 200
    )
      e.waist_circumference = "허리둘레를 올바르게 입력해주세요.";
    if (!form.sbp || form.sbp <= 0) e.sbp = "수축기 혈압을 입력해주세요.";
    if (!form.dbp || form.dbp <= 0) e.dbp = "이완기 혈압을 입력해주세요.";
    if (!form.fbs || form.fbs <= 0) e.fbs = "공복 혈당을 입력해주세요.";
    if (!form.hba1c || form.hba1c <= 0) e.hba1c = "당화혈색소를 입력해주세요.";
    if (!form.triglyceride || form.triglyceride <= 0) e.triglyceride = "중성지방을 입력해주세요.";
    if (!form.ldl || form.ldl <= 0) e.ldl = "LDL 콜레스테롤을 입력해주세요.";
    if (!form.hdl || form.hdl <= 0) e.hdl = "HDL 콜레스테롤을 입력해주세요.";
    if (!form.total_cholesterol || form.total_cholesterol <= 0)
      e.total_cholesterol = "총 콜레스테롤을 입력해주세요.";
    if (!form.ast || form.ast <= 0) e.ast = "AST를 입력해주세요.";
    if (!form.alt || form.alt <= 0) e.alt = "ALT를 입력해주세요.";
    if (!form.creatinine || form.creatinine <= 0) e.creatinine = "크레아티닌을 입력해주세요.";
    if (!form.screening_at) e.screening_at = "검진 일자를 선택해주세요.";

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
      await createAnnualHealthScreening(form);
      onSuccess();
    } catch (err: unknown) {
      setApiError(err instanceof Error ? err.message : "검진 기록 저장 중 오류가 발생했습니다.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <form onSubmit={handleSubmit} className="bg-white border border-border rounded-xl p-6 mb-6">
      <h3 className="font-semibold text-foreground mb-5 flex items-center gap-2">
        <Microscope size={16} style={{ color: "#0D3B6E" }} /> 건강 검진 결과 입력
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

      {/* 검진 정보 */}
      <div className="mb-5 pb-5 border-b border-border">
        <div className="flex items-center gap-2 mb-3">
          <Calendar size={16} style={{ color: "#0D3B6E" }} />
          <h4 className="font-semibold text-foreground text-sm">검진 정보</h4>
        </div>
        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="검진 일자" required error={errors.screening_at}>
            <input
              type="date"
              value={form.screening_at}
              onChange={(e) => set("screening_at")(e.target.value)}
              className={INPUT}
              style={{
                borderColor: errors.screening_at ? "#EF4444" : "rgba(13,59,110,0.2)",
                fontFamily: "JetBrains Mono",
              }}
            />
          </Field>
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium text-foreground">공복 여부</label>
            <div className="flex gap-2">
              {[
                { v: true, l: "공복" },
                { v: false, l: "비공복" },
              ].map(({ v, l }) => (
                <button
                  key={String(v)}
                  type="button"
                  onClick={() => set("is_fasting")(v)}
                  className={cn(
                    "flex-1 px-4 py-2.5 rounded-lg text-sm font-medium border transition-all",
                    form.is_fasting === v
                      ? "border-primary text-white"
                      : "border-border text-foreground hover:border-primary/50"
                  )}
                  style={form.is_fasting === v ? { backgroundColor: "#0D3B6E" } : {}}
                >
                  {l}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* 신체 측정 */}
      <div className="mb-5 pb-5 border-b border-border">
        <div className="flex items-center gap-2 mb-3">
          <User size={16} style={{ color: "#0D3B6E" }} />
          <h4 className="font-semibold text-foreground text-sm">신체 측정</h4>
        </div>
        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="키 (cm)" required error={errors.height} hint="예: 175.5">
            <input
              type="number"
              step="0.1"
              min="0.1"
              max="300"
              placeholder="175.5"
              value={form.height || ""}
              onChange={(e) => set("height")(e.target.value ? Number(e.target.value) : 0)}
              className={INPUT}
              style={{
                borderColor: errors.height ? "#EF4444" : "rgba(13,59,110,0.2)",
                fontFamily: "JetBrains Mono",
              }}
            />
          </Field>
          <Field label="체중 (kg)" required error={errors.weight} hint="예: 70.0">
            <input
              type="number"
              step="0.1"
              min="0.1"
              max="500"
              placeholder="70.0"
              value={form.weight || ""}
              onChange={(e) => set("weight")(e.target.value ? Number(e.target.value) : 0)}
              className={INPUT}
              style={{
                borderColor: errors.weight ? "#EF4444" : "rgba(13,59,110,0.2)",
                fontFamily: "JetBrains Mono",
              }}
            />
          </Field>
          <Field label="BMI" required error={errors.bmi} hint="자동 계산됨">
            <input
              type="number"
              step="0.1"
              min="0.1"
              max="100"
              placeholder="22.7"
              value={form.bmi || ""}
              onChange={(e) => set("bmi")(e.target.value ? Number(e.target.value) : 0)}
              className={INPUT}
              style={{
                borderColor: errors.bmi ? "#EF4444" : "rgba(13,59,110,0.2)",
                fontFamily: "JetBrains Mono",
              }}
              readOnly
            />
          </Field>
          <Field label="허리둘레 (cm)" required error={errors.waist_circumference} hint="예: 85.0">
            <input
              type="number"
              step="0.1"
              min="0.1"
              max="200"
              placeholder="85.0"
              value={form.waist_circumference || ""}
              onChange={(e) =>
                set("waist_circumference")(e.target.value ? Number(e.target.value) : 0)
              }
              className={INPUT}
              style={{
                borderColor: errors.waist_circumference ? "#EF4444" : "rgba(13,59,110,0.2)",
                fontFamily: "JetBrains Mono",
              }}
            />
          </Field>
        </div>
      </div>

      {/* 혈압 */}
      <div className="mb-5 pb-5 border-b border-border">
        <div className="flex items-center gap-2 mb-3">
          <Heart size={16} style={{ color: "#0D3B6E" }} />
          <h4 className="font-semibold text-foreground text-sm">혈압</h4>
        </div>
        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="수축기 혈압 (mmHg)" required error={errors.sbp}>
            <input
              type="number"
              min="1"
              placeholder="120"
              value={form.sbp || ""}
              onChange={(e) => set("sbp")(e.target.value ? Number(e.target.value) : 0)}
              className={INPUT}
              style={{
                borderColor: errors.sbp ? "#EF4444" : "rgba(13,59,110,0.2)",
                fontFamily: "JetBrains Mono",
              }}
            />
          </Field>
          <Field label="이완기 혈압 (mmHg)" required error={errors.dbp}>
            <input
              type="number"
              min="1"
              placeholder="80"
              value={form.dbp || ""}
              onChange={(e) => set("dbp")(e.target.value ? Number(e.target.value) : 0)}
              className={INPUT}
              style={{
                borderColor: errors.dbp ? "#EF4444" : "rgba(13,59,110,0.2)",
                fontFamily: "JetBrains Mono",
              }}
            />
          </Field>
        </div>
      </div>

      {/* 혈당 */}
      <div className="mb-5 pb-5 border-b border-border">
        <div className="flex items-center gap-2 mb-3">
          <Droplets size={16} style={{ color: "#0D3B6E" }} />
          <h4 className="font-semibold text-foreground text-sm">혈당</h4>
        </div>
        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="공복 혈당 (mg/dL)" required error={errors.fbs}>
            <input
              type="number"
              min="1"
              placeholder="95"
              value={form.fbs || ""}
              onChange={(e) => set("fbs")(e.target.value ? Number(e.target.value) : 0)}
              className={INPUT}
              style={{
                borderColor: errors.fbs ? "#EF4444" : "rgba(13,59,110,0.2)",
                fontFamily: "JetBrains Mono",
              }}
            />
          </Field>
          <Field label="당화혈색소 (%)" required error={errors.hba1c}>
            <input
              type="number"
              step="0.1"
              min="0.1"
              placeholder="5.4"
              value={form.hba1c || ""}
              onChange={(e) => set("hba1c")(e.target.value ? Number(e.target.value) : 0)}
              className={INPUT}
              style={{
                borderColor: errors.hba1c ? "#EF4444" : "rgba(13,59,110,0.2)",
                fontFamily: "JetBrains Mono",
              }}
            />
          </Field>
        </div>
      </div>

      {/* 콜레스테롤 */}
      <div className="mb-5 pb-5 border-b border-border">
        <div className="flex items-center gap-2 mb-3">
          <Activity size={16} style={{ color: "#0D3B6E" }} />
          <h4 className="font-semibold text-foreground text-sm">콜레스테롤</h4>
        </div>
        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="중성지방 (mg/dL)" required error={errors.triglyceride}>
            <input
              type="number"
              min="1"
              placeholder="150"
              value={form.triglyceride || ""}
              onChange={(e) => set("triglyceride")(e.target.value ? Number(e.target.value) : 0)}
              className={INPUT}
              style={{
                borderColor: errors.triglyceride ? "#EF4444" : "rgba(13,59,110,0.2)",
                fontFamily: "JetBrains Mono",
              }}
            />
          </Field>
          <Field label="총 콜레스테롤 (mg/dL)" required error={errors.total_cholesterol}>
            <input
              type="number"
              min="1"
              placeholder="190"
              value={form.total_cholesterol || ""}
              onChange={(e) =>
                set("total_cholesterol")(e.target.value ? Number(e.target.value) : 0)
              }
              className={INPUT}
              style={{
                borderColor: errors.total_cholesterol ? "#EF4444" : "rgba(13,59,110,0.2)",
                fontFamily: "JetBrains Mono",
              }}
            />
          </Field>
          <Field label="LDL 콜레스테롤 (mg/dL)" required error={errors.ldl}>
            <input
              type="number"
              min="1"
              placeholder="100"
              value={form.ldl || ""}
              onChange={(e) => set("ldl")(e.target.value ? Number(e.target.value) : 0)}
              className={INPUT}
              style={{
                borderColor: errors.ldl ? "#EF4444" : "rgba(13,59,110,0.2)",
                fontFamily: "JetBrains Mono",
              }}
            />
          </Field>
          <Field label="HDL 콜레스테롤 (mg/dL)" required error={errors.hdl}>
            <input
              type="number"
              min="1"
              placeholder="60"
              value={form.hdl || ""}
              onChange={(e) => set("hdl")(e.target.value ? Number(e.target.value) : 0)}
              className={INPUT}
              style={{
                borderColor: errors.hdl ? "#EF4444" : "rgba(13,59,110,0.2)",
                fontFamily: "JetBrains Mono",
              }}
            />
          </Field>
        </div>
      </div>

      {/* 간기능 & 신기능 */}
      <div className="mb-5 pb-5 border-b border-border">
        <div className="flex items-center gap-2 mb-3">
          <TestTube size={16} style={{ color: "#0D3B6E" }} />
          <h4 className="font-semibold text-foreground text-sm">간기능 & 신기능</h4>
        </div>
        <div className="grid sm:grid-cols-3 gap-4">
          <Field label="AST (U/L)" required error={errors.ast}>
            <input
              type="number"
              min="1"
              placeholder="25"
              value={form.ast || ""}
              onChange={(e) => set("ast")(e.target.value ? Number(e.target.value) : 0)}
              className={INPUT}
              style={{
                borderColor: errors.ast ? "#EF4444" : "rgba(13,59,110,0.2)",
                fontFamily: "JetBrains Mono",
              }}
            />
          </Field>
          <Field label="ALT (U/L)" required error={errors.alt}>
            <input
              type="number"
              min="1"
              placeholder="20"
              value={form.alt || ""}
              onChange={(e) => set("alt")(e.target.value ? Number(e.target.value) : 0)}
              className={INPUT}
              style={{
                borderColor: errors.alt ? "#EF4444" : "rgba(13,59,110,0.2)",
                fontFamily: "JetBrains Mono",
              }}
            />
          </Field>
          <Field label="크레아티닌 (mg/dL)" required error={errors.creatinine}>
            <input
              type="number"
              step="0.1"
              min="0.1"
              placeholder="1.0"
              value={form.creatinine || ""}
              onChange={(e) => set("creatinine")(e.target.value ? Number(e.target.value) : 0)}
              className={INPUT}
              style={{
                borderColor: errors.creatinine ? "#EF4444" : "rgba(13,59,110,0.2)",
                fontFamily: "JetBrains Mono",
              }}
            />
          </Field>
        </div>
      </div>

      {/* 요검사 */}
      <div className="mb-5 pb-5 border-b border-border">
        <div className="flex items-center gap-2 mb-3">
          <Clipboard size={16} style={{ color: "#0D3B6E" }} />
          <h4 className="font-semibold text-foreground text-sm">요검사</h4>
        </div>
        <div className="grid sm:grid-cols-2 gap-4">
          <Field label="단백" required>
            <select
              value={form.urine_protein}
              onChange={(e) => set("urine_protein")(e.target.value as UrineProteinStatus)}
              className={INPUT}
              style={{ borderColor: "rgba(13,59,110,0.2)", fontFamily: "JetBrains Mono" }}
            >
              {URINE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </Field>
          <Field label="요당" required>
            <select
              value={form.urine_glucose}
              onChange={(e) => set("urine_glucose")(e.target.value as UrineGlucoseStatus)}
              className={INPUT}
              style={{ borderColor: "rgba(13,59,110,0.2)", fontFamily: "JetBrains Mono" }}
            >
              {URINE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </Field>
        </div>
      </div>

      {/* 가족력 */}
      <div className="mb-5">
        <div className="flex items-center gap-2 mb-3">
          <Clipboard size={16} style={{ color: "#0D3B6E" }} />
          <h4 className="font-semibold text-foreground text-sm">가족력</h4>
        </div>
        <div className="flex flex-col gap-3">
          <label className="flex items-center gap-3 p-3 rounded-lg border border-border cursor-pointer hover:bg-muted/30 transition-colors">
            <input
              type="checkbox"
              checked={form.family_history_diabetes}
              onChange={(e) => set("family_history_diabetes")(e.target.checked)}
              className="w-4 h-4 rounded border-border"
            />
            <span className="text-sm text-foreground">당뇨 가족력 있음</span>
          </label>
          <label className="flex items-center gap-3 p-3 rounded-lg border border-border cursor-pointer hover:bg-muted/30 transition-colors">
            <input
              type="checkbox"
              checked={form.family_history_hypertension}
              onChange={(e) => set("family_history_hypertension")(e.target.checked)}
              className="w-4 h-4 rounded border-border"
            />
            <span className="text-sm text-foreground">고혈압 가족력 있음</span>
          </label>
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
const Section = ({
  icon: Icon,
  title,
  children,
}: {
  icon: typeof User;
  title: string;
  children: React.ReactNode;
}) => (
  <div>
    <div className="flex items-center gap-2 mb-3">
      <Icon size={15} style={{ color: "#0D3B6E" }} />
      <h4 className="font-semibold text-foreground text-sm">{title}</h4>
    </div>
    <div className="grid grid-cols-2 gap-3">{children}</div>
  </div>
);

const Item = ({ label, value, unit }: { label: string; value: string | number; unit?: string }) => (
  <div className="px-4 py-3 bg-muted rounded-lg">
    <div className="text-xs text-muted-foreground mb-1">{label}</div>
    <div
      className="text-base font-semibold text-foreground"
      style={{ fontFamily: "JetBrains Mono" }}
    >
      {value} {unit && <span className="text-sm font-normal">{unit}</span>}
    </div>
  </div>
);

const ItemWithStatus = ({
  label,
  value,
  unit,
  type,
}: {
  label: string;
  value: number;
  unit?: string;
  type: string;
}) => {
  const status = getStatus(value, type);
  return (
    <div className="px-4 py-3 bg-muted rounded-lg">
      <div className="flex items-center justify-between mb-1">
        <div className="text-xs text-muted-foreground">{label}</div>
        <StatusBadge status={status} />
      </div>
      <div
        className="text-base font-semibold text-foreground"
        style={{ fontFamily: "JetBrains Mono" }}
      >
        {value} {unit && <span className="text-sm font-normal">{unit}</span>}
      </div>
    </div>
  );
};

function DetailModal({
  screening,
  onClose,
}: {
  screening: AnnualHealthScreeningDetail;
  onClose: () => void;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4"
      onClick={onClose}
    >
      <div
        className="bg-white rounded-xl max-w-3xl w-full max-h-[90vh] overflow-y-auto shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="sticky top-0 bg-white border-b border-border px-6 py-4 flex items-center justify-between">
          <div>
            <h3 className="font-semibold text-foreground">{screening.title}</h3>
            <p className="text-xs text-muted-foreground mt-0.5">
              - 검진일자: {screening.screening_at}
            </p>
            <p className="text-xs text-muted-foreground mt-0.5">
              - 공복 검사 여부: {screening.is_fasting ? "공복" : "비공복"}
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
          <Section icon={User} title="신체 측정">
            <Item label="키" value={screening.height} unit="cm" />
            <Item label="체중" value={screening.weight} unit="kg" />
            <Item label="BMI" value={screening.bmi} />
            <Item label="허리둘레" value={screening.waist_circumference} unit="cm" />
          </Section>

          <Section icon={Heart} title="혈압">
            <ItemWithStatus label="수축기 혈압" value={screening.sbp} unit="mmHg" type="sbp" />
            <ItemWithStatus label="이완기 혈압" value={screening.dbp} unit="mmHg" type="dbp" />
          </Section>

          <Section icon={Droplets} title="혈당">
            <ItemWithStatus label="공복 혈당" value={screening.fbs} unit="mg/dL" type="fbs" />
            <ItemWithStatus label="당화혈색소" value={screening.hba1c} unit="%" type="hba1c" />
          </Section>

          <Section icon={Activity} title="콜레스테롤">
            <ItemWithStatus
              label="중성지방"
              value={screening.triglyceride}
              unit="mg/dL"
              type="triglyceride"
            />
            <ItemWithStatus
              label="총 콜레스테롤"
              value={screening.total_cholesterol}
              unit="mg/dL"
              type="total_cholesterol"
            />
            <ItemWithStatus label="LDL 콜레스테롤" value={screening.ldl} unit="mg/dL" type="ldl" />
            <ItemWithStatus label="HDL 콜레스테롤" value={screening.hdl} unit="mg/dL" type="hdl" />
          </Section>

          <Section icon={TestTube} title="간기능 & 신기능">
            <ItemWithStatus label="AST" value={screening.ast} unit="U/L" type="ast" />
            <ItemWithStatus label="ALT" value={screening.alt} unit="U/L" type="alt" />
            <ItemWithStatus
              label="크레아티닌"
              value={screening.creatinine}
              unit="mg/dL"
              type="creatinine"
            />
          </Section>

          <Section icon={Clipboard} title="요검사">
            <Item
              label="요단백"
              value={urineStatusToKorean(screening.urine_protein as UrineProteinStatus)}
            />
            <Item
              label="요당"
              value={urineStatusToKorean(screening.urine_glucose as UrineGlucoseStatus)}
            />
          </Section>

          <div>
            <div className="flex items-center gap-2 mb-3">
              <Clipboard size={15} style={{ color: "#0D3B6E" }} />
              <h4 className="font-semibold text-foreground text-sm">가족력</h4>
            </div>
            <div className="flex gap-3">
              <div
                className={cn(
                  "flex-1 px-4 py-3 rounded-lg border",
                  screening.family_history_diabetes
                    ? "border-red-200 bg-red-50"
                    : "border-border bg-muted"
                )}
              >
                <div className="text-sm text-foreground">
                  {screening.family_history_diabetes ? "✓ 당뇨 가족력 있음" : "당뇨 가족력 없음"}
                </div>
              </div>
              <div
                className={cn(
                  "flex-1 px-4 py-3 rounded-lg border",
                  screening.family_history_hypertension
                    ? "border-red-200 bg-red-50"
                    : "border-border bg-muted"
                )}
              >
                <div className="text-sm text-foreground">
                  {screening.family_history_hypertension
                    ? "✓ 고혈압 가족력 있음"
                    : "고혈압 가족력 없음"}
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

/* ── Main ── */
export default function HealthCheckup() {
  const [showForm, setShowForm] = useState(false);
  const [screenings, setScreenings] = useState<AnnualHealthScreening[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedScreening, setSelectedScreening] = useState<AnnualHealthScreeningDetail | null>(
    null
  );
  const [loadingDetail, setLoadingDetail] = useState(false);

  const loadScreenings = async () => {
    setLoading(true);
    setError("");
    try {
      const data = await getAnnualHealthScreenings();
      setScreenings(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "검진 목록을 불러올 수 없습니다.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadScreenings();
  }, []);

  const handleSuccess = () => {
    setShowForm(false);
    loadScreenings();
  };

  const handleViewDetail = async (screeningId: string) => {
    setLoadingDetail(true);
    try {
      const detail = await getAnnualHealthScreeningDetail(screeningId);
      setSelectedScreening(detail);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "검진 상세 정보를 불러올 수 없습니다.");
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
            건강정보 기록 / 건강검진 기록
          </div>
          <h1 className="text-2xl font-semibold text-foreground mb-1">건강검진 기록</h1>
          <p className="text-sm text-muted-foreground">
            연도별 건강검진 결과를 기록하고 AI 분석에 활용합니다.
          </p>
        </div>
        <button
          onClick={() => setShowForm(!showForm)}
          className="flex items-center gap-2 px-4 py-2.5 rounded-lg text-sm font-semibold text-white transition-opacity hover:opacity-90 flex-shrink-0"
          style={{ backgroundColor: "#0D3B6E" }}
        >
          {showForm ? (
            <>
              <ChevronLeft size={15} /> 목록
            </>
          ) : (
            <>
              <Plus size={15} /> 검진 결과 추가
            </>
          )}
        </button>
      </div>

      {/* Form */}
      {showForm && <ScreeningForm onCancel={() => setShowForm(false)} onSuccess={handleSuccess} />}

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
            <span className="text-sm">검진 목록을 불러오는 중...</span>
          </div>
        </div>
      )}

      {/* Screening List */}
      {!showForm && !loading && screenings.length === 0 && (
        <div className="text-center py-12">
          <Microscope size={40} className="mx-auto mb-3 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">아직 등록된 건강검진 기록이 없습니다.</p>
        </div>
      )}

      {!showForm && !loading && screenings.length > 0 && (
        <div className="flex flex-col gap-3">
          {screenings.map((screening) => (
            <button
              key={screening.id}
              onClick={() => handleViewDetail(screening.id)}
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
                    <Microscope size={16} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="font-semibold text-foreground text-sm">{screening.title}</div>
                    <div className="text-xs text-muted-foreground mt-0.5">
                      등록일시: {formatDateTime(screening.created_at)}
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
      {selectedScreening && (
        <DetailModal screening={selectedScreening} onClose={() => setSelectedScreening(null)} />
      )}
    </div>
  );
}
