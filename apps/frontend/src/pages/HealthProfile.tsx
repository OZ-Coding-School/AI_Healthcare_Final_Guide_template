import { useState, useEffect } from "react";
import { UserCircle, Pencil, CheckCircle, X, AlertCircle, Plus, Loader2 } from "lucide-react";
import {
  getHealthProfile, createHealthProfile, updateHealthProfile,
  HealthProfile as HealthProfileData, Gender,
} from "../shared/api/healthProfileApi";
import { getUser } from "../shared/api/auth";
import { formatDateTime } from "../shared/utils/format";

const cn = (...classes: (string | boolean | undefined)[]) =>
  classes.filter(Boolean).join(" ");

/* ── BMI 계산 ── */
function calcBmi(height: number, weight: number) {
  if (!height || !weight) return null;
  const h = height / 100;
  return +(weight / (h * h)).toFixed(1);
}
function bmiLabel(bmi: number) {
  if (bmi < 18.5) return { label: "저체중", color: "#06B6D4" };
  if (bmi < 23)   return { label: "정상",   color: "#10B981" };
  if (bmi < 25)   return { label: "과체중", color: "#F59E0B" };
  return              { label: "비만",   color: "#EF4444" };
}

/* ── 나이 계산 ── */
function calcAge(birthDate: string) {
  const birth = new Date(birthDate);
  const today = new Date();
  let age = today.getFullYear() - birth.getFullYear();
  const m = today.getMonth() - birth.getMonth();
  if (m < 0 || (m === 0 && today.getDate() < birth.getDate())) age--;
  return age;
}

/* ── Input ── */
function Field({ label, required, error, children, hint }: {
  label: string; required?: boolean; error?: string; children: React.ReactNode; hint?: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium text-foreground">
        {label}{required && <span className="ml-1 text-red-500">*</span>}
      </label>
      {children}
      {error && <span className="text-xs flex items-center gap-1 text-red-500"><AlertCircle size={11}/>{error}</span>}
      {hint && !error && <span className="text-xs text-muted-foreground">{hint}</span>}
    </div>
  );
}

const INPUT = cn(
  "w-full px-4 py-3 rounded-lg border text-sm bg-background text-foreground outline-none transition-all duration-150",
  "focus:ring-2 focus:ring-primary/20 focus:border-primary placeholder:text-muted-foreground"
);

/* ── Toggle switch ── */
function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" onClick={() => onChange(!checked)}
      className="flex items-center justify-between w-full px-4 py-3.5 rounded-lg border transition-all duration-150 hover:border-primary/30"
      style={{ borderColor: checked ? "rgba(13,59,110,0.3)" : "rgba(0,0,0,0.1)", backgroundColor: checked ? "rgba(13,59,110,0.04)" : "transparent" }}>
      <span className="text-sm font-medium text-foreground">{label}</span>
      <div className={cn("relative w-11 h-6 rounded-full transition-colors duration-200 flex-shrink-0", checked ? "bg-primary" : "bg-muted")}>
        <div className={cn("absolute top-1 w-4 h-4 rounded-full bg-white shadow-sm transition-all duration-200", checked ? "left-6" : "left-1")} />
      </div>
    </button>
  );
}

/* ── Info row (view mode) ── */
function InfoRow({ label, value, mono }: { label: string; value: React.ReactNode; mono?: boolean }) {
  return (
    <div className="flex items-center justify-between py-3 border-b border-border last:border-0">
      <span className="text-sm text-muted-foreground">{label}</span>
      <span className={cn("text-sm font-medium text-foreground", mono && "font-mono")}
        style={mono ? { fontFamily: "JetBrains Mono" } : {}}>
        {value}
      </span>
    </div>
  );
}

/* ── Main ── */
type Mode = "loading" | "create" | "view" | "edit";

interface FormState {
  gender: Gender | "";
  birth_date: string;
  height: string;
  weight: string;
  has_diabetes: boolean;
  has_hypertension: boolean;
}

const EMPTY_FORM: FormState = {
  gender: "", birth_date: "", height: "", weight: "",
  has_diabetes: false, has_hypertension: false,
};

export default function HealthProfile() {
  const user = getUser();
  const [mode,    setMode]    = useState<Mode>("loading");
  const [profile, setProfile] = useState<HealthProfileData | null>(null);
  const [form,    setForm]    = useState<FormState>(EMPTY_FORM);
  const [errors,  setErrors]  = useState<Record<string, string>>({});
  const [apiError, setApiError] = useState("");
  const [saving,  setSaving]  = useState(false);

  /* fetch on mount */
  useEffect(() => {
    getHealthProfile()
      .then((p) => {
        if (p) {
          setProfile(p);
          setMode("view");
        } else {
          setMode("create");
        }
      })
      .catch(() => setMode("create"));
  }, []);

  const openEdit = () => {
    if (!profile) return;
    setForm({
      gender:           profile.gender,
      birth_date:       profile.birth_date,
      height:           String(profile.height),
      weight:           String(profile.weight),
      has_diabetes:     profile.has_diabetes,
      has_hypertension: profile.has_hypertension,
    });
    setErrors({});
    setApiError("");
    setMode("edit");
  };

  const validate = (isCreate: boolean) => {
    const e: Record<string, string> = {};
    if (isCreate) {
      if (!form.gender)     e.gender     = "성별을 선택해주세요.";
      if (!form.birth_date) e.birth_date = "생년월일을 입력해주세요.";
    }
    const h = parseFloat(form.height);
    const w = parseFloat(form.weight);
    if (!form.height || isNaN(h) || h <= 0 || h > 300) e.height = "키를 올바르게 입력해주세요. (0 초과 300 이하)";
    if (!form.weight || isNaN(w) || w <= 0 || w > 500) e.weight = "몸무게를 올바르게 입력해주세요. (0 초과 500 이하)";
    return e;
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs = validate(true);
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setSaving(true); setApiError("");
    try {
      await createHealthProfile({
        gender:           form.gender as Gender,
        birth_date:       form.birth_date,
        height:           Math.round(parseFloat(form.height) * 10) / 10,
        weight:           Math.round(parseFloat(form.weight) * 10) / 10,
        has_diabetes:     form.has_diabetes,
        has_hypertension: form.has_hypertension,
      });
      // re-fetch to get server-assigned id / timestamps
      const p = await getHealthProfile();
      setProfile(p);
      setMode("view");
    } catch (err: unknown) {
      setApiError(err instanceof Error ? err.message : "저장 중 오류가 발생했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const handleUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    const errs = validate(false);
    setErrors(errs);
    if (Object.keys(errs).length) return;
    setSaving(true); setApiError("");
    try {
      const updated = await updateHealthProfile({
        height:           Math.round(parseFloat(form.height) * 10) / 10,
        weight:           Math.round(parseFloat(form.weight) * 10) / 10,
        has_diabetes:     form.has_diabetes,
        has_hypertension: form.has_hypertension,
      });
      setProfile(updated);
      setMode("view");
    } catch (err: unknown) {
      setApiError(err instanceof Error ? err.message : "수정 중 오류가 발생했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const set = (k: keyof FormState) => (v: string | boolean) =>
    setForm((f) => ({ ...f, [k]: v }));

  /* ─── LOADING ─── */
  if (mode === "loading") {
    return (
      <div className="p-6 lg:p-8 flex items-center justify-center min-h-64">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 size={28} className="animate-spin" />
          <span className="text-sm">건강 프로필을 불러오는 중...</span>
        </div>
      </div>
    );
  }

  const bmi    = profile ? calcBmi(profile.height, profile.weight) : null;
  const bmiInfo = bmi ? bmiLabel(bmi) : null;
  const age    = profile ? calcAge(profile.birth_date) : null;
  const displayName = user?.nickname || "?";

  return (
    <div className="p-6 lg:p-8 max-w-2xl" style={{ fontFamily: "Outfit, sans-serif" }}>
      {/* Breadcrumb + title */}
      <div className="mb-8">
        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2" style={{ fontFamily: "JetBrains Mono" }}>
          건강정보 기록 / 건강 프로필
        </div>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-foreground mb-1">건강 프로필</h1>
            <p className="text-sm text-muted-foreground">
              {mode === "create" ? "AI 분석의 기준이 될 기본 건강 정보를 등록해주세요." : "AI 분석의 기준이 되는 기본 건강 정보입니다."}
            </p>
          </div>
          {mode === "view" && (
            <button onClick={openEdit}
              className="flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-semibold text-white hover:opacity-90 transition-opacity flex-shrink-0"
              style={{ backgroundColor: "#0D3B6E" }}>
              <Pencil size={14} /> 수정
            </button>
          )}
        </div>
      </div>

      {/* ─── VIEW MODE ─── */}
      {mode === "view" && profile && (
        <div className="flex flex-col gap-5">
          {/* Avatar card */}
          <div className="bg-white border border-border rounded-xl p-5 flex items-center gap-5">
            <div className="w-16 h-16 rounded-full flex items-center justify-center text-2xl font-bold text-white flex-shrink-0"
              style={{ backgroundColor: "#10B981" }}>
              {displayName[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-foreground text-lg">{displayName}</div>
              <div className="text-sm text-muted-foreground">{user?.email}</div>
              <div className="flex items-center gap-4 mt-2">
                <span className="text-xs text-muted-foreground">
                  {profile.gender === "M" ? "남성" : "여성"} · {age}세
                </span>
                {bmi && bmiInfo && (
                  <span className="text-xs font-semibold px-2 py-0.5 rounded-full"
                    style={{ fontFamily: "JetBrains Mono", backgroundColor: `${bmiInfo.color}12`, color: bmiInfo.color }}>
                    BMI {bmi} ({bmiInfo.label})
                  </span>
                )}
              </div>
            </div>
          </div>

          {/* 신체 정보 */}
          <div className="bg-white border border-border rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-border">
              <h3 className="font-semibold text-foreground text-sm">신체 정보</h3>
            </div>
            <div className="px-5">
              <InfoRow label="성별" value={profile.gender === "M" ? "남성" : "여성"} />
              <InfoRow label="생년월일" value={profile.birth_date} mono />
              <InfoRow label="나이" value={`${age}세`} />
              <InfoRow label="키" value={`${profile.height} cm`} mono />
              <InfoRow label="몸무게" value={`${profile.weight} kg`} mono />
              {bmi && bmiInfo && (
                <InfoRow
                  label="BMI"
                  value={
                    <span className="flex items-center gap-2">
                      <span style={{ fontFamily: "JetBrains Mono" }}>{bmi}</span>
                      <span className="text-xs px-2 py-0.5 rounded-full font-medium"
                        style={{ backgroundColor: `${bmiInfo.color}12`, color: bmiInfo.color }}>
                        {bmiInfo.label}
                      </span>
                    </span>
                  }
                />
              )}
            </div>
          </div>

          {/* 질환 여부 */}
          <div className="bg-white border border-border rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-border">
              <h3 className="font-semibold text-foreground text-sm">질환 여부</h3>
              <p className="text-xs text-muted-foreground mt-0.5">AI 예측 모델의 핵심 입력 데이터입니다.</p>
            </div>
            <div className="px-5">
              <InfoRow
                label="당뇨"
                value={
                  <span className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full"
                    style={{
                      fontFamily: "JetBrains Mono",
                      backgroundColor: profile.has_diabetes ? "rgba(245,158,11,0.1)" : "rgba(16,185,129,0.1)",
                      color: profile.has_diabetes ? "#D97706" : "#10B981",
                    }}>
                    {profile.has_diabetes ? "있음" : "없음"}
                  </span>
                }
              />
              <InfoRow
                label="고혈압"
                value={
                  <span className="flex items-center gap-1.5 text-xs font-semibold px-2.5 py-1 rounded-full"
                    style={{
                      fontFamily: "JetBrains Mono",
                      backgroundColor: profile.has_hypertension ? "rgba(239,68,68,0.1)" : "rgba(16,185,129,0.1)",
                      color: profile.has_hypertension ? "#EF4444" : "#10B981",
                    }}>
                    {profile.has_hypertension ? "있음" : "없음"}
                  </span>
                }
              />
            </div>
          </div>

          {/* 메타 */}
          <div className="text-xs text-muted-foreground flex flex-col gap-1 px-1"
            style={{ fontFamily: "JetBrains Mono" }}>
            <span>- 최초 등록: {formatDateTime(profile.created_at)}</span>
            <span>- 최근 수정: {formatDateTime(profile.updated_at)}</span>
          </div>
        </div>
      )}

      {/* ─── CREATE / EDIT FORM ─── */}
      {(mode === "create" || mode === "edit") && (
        <form onSubmit={mode === "create" ? handleCreate : handleUpdate} className="flex flex-col gap-5">

          {/* API 에러 */}
          {apiError && (
            <div className="flex items-center gap-2.5 px-4 py-3 rounded-lg text-sm"
              style={{ backgroundColor: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.2)", color: "#DC2626" }}>
              <AlertCircle size={15} className="flex-shrink-0" />{apiError}
            </div>
          )}

          {/* 성별 + 생년월일 — 최초 등록 시만 입력, 수정 시 읽기 전용 */}
          <div className="bg-white border border-border rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-border flex items-center justify-between">
              <div>
                <h3 className="font-semibold text-foreground text-sm">기본 정보</h3>
                {mode === "edit" && (
                  <p className="text-xs text-muted-foreground mt-0.5">성별과 생년월일은 최초 등록 후 변경할 수 없습니다.</p>
                )}
              </div>
            </div>
            <div className="p-5 flex flex-col gap-4">
              {/* 성별 */}
              {mode === "create" ? (
                <Field label="성별" required error={errors.gender}>
                  <div className="grid grid-cols-2 gap-3">
                    {(["M", "F"] as Gender[]).map((g) => (
                      <button key={g} type="button"
                        onClick={() => set("gender")(g)}
                        className={cn(
                          "py-3 rounded-lg border text-sm font-medium transition-all duration-150",
                          form.gender === g ? "text-primary border-primary bg-secondary" : "border-border text-muted-foreground hover:border-primary/40"
                        )}>
                        {g === "M" ? "남성" : "여성"}
                      </button>
                    ))}
                  </div>
                </Field>
              ) : (
                <InfoRow label="성별" value={profile?.gender === "M" ? "남성" : "여성"} />
              )}

              {/* 생년월일 */}
              {mode === "create" ? (
                <Field label="생년월일" required error={errors.birth_date} hint="형식: YYYY-MM-DD">
                  <input type="date" value={form.birth_date}
                    onChange={(e) => set("birth_date")(e.target.value)}
                    max={new Date().toISOString().split("T")[0]}
                    className={INPUT}
                    style={{ borderColor: errors.birth_date ? "#EF4444" : "rgba(13,59,110,0.2)", fontFamily: "JetBrains Mono" }} />
                </Field>
              ) : (
                <InfoRow label="생년월일" value={profile?.birth_date ?? "-"} mono />
              )}
            </div>
          </div>

          {/* 신체 정보 */}
          <div className="bg-white border border-border rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-border">
              <h3 className="font-semibold text-foreground text-sm">신체 정보</h3>
            </div>
            <div className="p-5 flex flex-col gap-4">
              <div className="grid grid-cols-2 gap-4">
                <Field label="키 (cm)" required error={errors.height} hint="소수점 1자리까지">
                  <input type="number" step="0.1" min="0.1" max="300" placeholder="예: 175.0"
                    value={form.height} onChange={(e) => set("height")(e.target.value)}
                    className={INPUT}
                    style={{ borderColor: errors.height ? "#EF4444" : "rgba(13,59,110,0.2)", fontFamily: "JetBrains Mono" }} />
                </Field>
                <Field label="몸무게 (kg)" required error={errors.weight} hint="소수점 1자리까지">
                  <input type="number" step="0.1" min="0.1" max="500" placeholder="예: 70.0"
                    value={form.weight} onChange={(e) => set("weight")(e.target.value)}
                    className={INPUT}
                    style={{ borderColor: errors.weight ? "#EF4444" : "rgba(13,59,110,0.2)", fontFamily: "JetBrains Mono" }} />
                </Field>
              </div>

              {/* 실시간 BMI 미리보기 */}
              {form.height && form.weight && !errors.height && !errors.weight && (() => {
                const previewBmi = calcBmi(parseFloat(form.height), parseFloat(form.weight));
                const info = previewBmi ? bmiLabel(previewBmi) : null;
                return previewBmi && info ? (
                  <div className="flex items-center gap-3 px-4 py-3 rounded-lg text-sm"
                    style={{ backgroundColor: `${info.color}08`, border: `1px solid ${info.color}25` }}>
                    <span className="text-muted-foreground">BMI 미리보기</span>
                    <span className="font-bold" style={{ fontFamily: "JetBrains Mono", color: info.color }}>{previewBmi}</span>
                    <span className="text-xs font-semibold px-2 py-0.5 rounded-full"
                      style={{ backgroundColor: `${info.color}15`, color: info.color }}>{info.label}</span>
                  </div>
                ) : null;
              })()}
            </div>
          </div>

          {/* 질환 여부 */}
          <div className="bg-white border border-border rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-border">
              <h3 className="font-semibold text-foreground text-sm">질환 여부</h3>
              <p className="text-xs text-muted-foreground mt-0.5">AI 위험도 예측 모델에 직접 반영됩니다.</p>
            </div>
            <div className="p-5 flex flex-col gap-3">
              <Toggle checked={form.has_diabetes} onChange={(v) => set("has_diabetes")(v)} label="당뇨 (진단받은 경우)" />
              <Toggle checked={form.has_hypertension} onChange={(v) => set("has_hypertension")(v)} label="고혈압 (진단받은 경우)" />
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            {mode === "edit" && (
              <button type="button" onClick={() => { setMode("view"); setApiError(""); }}
                className="flex items-center gap-2 px-5 py-3 rounded-lg text-sm font-medium text-muted-foreground border border-border hover:bg-muted transition-colors">
                <X size={14} /> 취소
              </button>
            )}
            <button type="submit" disabled={saving}
              className="flex-1 flex items-center justify-center gap-2 py-3.5 rounded-lg text-sm font-semibold text-white hover:opacity-90 disabled:opacity-60 transition-opacity"
              style={{ backgroundColor: "#0D3B6E" }}>
              {saving ? (
                <span className="flex items-center gap-2">
                  <Loader2 size={15} className="animate-spin" />
                  {mode === "create" ? "등록 중..." : "저장 중..."}
                </span>
              ) : (
                <>
                  {mode === "create" ? <><Plus size={15} /> 건강 프로필 등록</> : <><CheckCircle size={15} /> 변경사항 저장</>}
                </>
              )}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
