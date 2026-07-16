import { useState, useEffect } from "react";
import { User as UserIcon, Mail, Phone, Calendar, Pencil, CheckCircle, X, AlertCircle, Loader2, Shield } from "lucide-react";
import { getMyInfo, updateMyInfo, User } from "../shared/api/userApi";
import { getUser } from "../shared/api/auth";
import { formatDate, formatPhoneNumber } from "../shared/utils/format";

const cn = (...classes: (string | boolean | undefined)[]) =>
  classes.filter(Boolean).join(" ");

/* ── Input Field ── */
function Field({ label, error, children, hint }: {
  label: string; error?: string; children: React.ReactNode; hint?: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium text-foreground">{label}</label>
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

/* ── Info row (view mode) ── */
function InfoRow({ icon: Icon, label, value, mono }: {
  icon: React.ElementType; label: string; value: React.ReactNode; mono?: boolean;
}) {
  return (
    <div className="flex items-center gap-4 py-3.5 border-b border-border last:border-0">
      <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0"
        style={{ backgroundColor: "rgba(13,59,110,0.08)" }}>
        <Icon size={16} style={{ color: "#0D3B6E" }} />
      </div>
      <div className="flex-1 min-w-0 flex items-center justify-between gap-3">
        <span className="text-sm text-muted-foreground">{label}</span>
        <span className={cn("text-sm font-medium text-foreground truncate", mono && "font-mono")}
          style={mono ? { fontFamily: "JetBrains Mono" } : {}}>
          {value}
        </span>
      </div>
    </div>
  );
}

/* ── Main ── */
type Mode = "loading" | "view" | "edit";

interface FormState {
  nickname: string;
  phone_number: string;
}

export default function MyPage() {
  const localUser = getUser();
  const [mode, setMode] = useState<Mode>("loading");
  const [user, setUser] = useState<User | null>(null);
  const [form, setForm] = useState<FormState>({ nickname: "", phone_number: "" });
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [apiError, setApiError] = useState("");
  const [saving, setSaving] = useState(false);

  /* fetch on mount */
  useEffect(() => {
    getMyInfo()
      .then((u) => {
        setUser(u);
        setMode("view");
      })
      .catch((err) => {
        setApiError(err instanceof Error ? err.message : "사용자 정보를 불러올 수 없습니다.");
        setMode("view");
      });
  }, []);

  const openEdit = () => {
    if (!user) return;
    setForm({ nickname: user.nickname, phone_number: user.phone_number });
    setErrors({});
    setApiError("");
    setMode("edit");
  };

  const validate = () => {
    const e: Record<string, string> = {};
    if (!form.nickname.trim()) {
      e.nickname = "닉네임을 입력해주세요.";
    } else if (form.nickname.length > 10) {
      e.nickname = "닉네임은 최대 10자까지 입력 가능합니다.";
    }
    // phone_number는 optional
    return e;
  };

  const handleUpdate = async (ev: React.FormEvent) => {
    ev.preventDefault();
    const errs = validate();
    setErrors(errs);
    if (Object.keys(errs).length) return;

    setSaving(true);
    setApiError("");
    try {
      const updated = await updateMyInfo({
        nickname: form.nickname,
        phone_number: form.phone_number || undefined,
      });
      setUser(updated);
      setMode("view");
    } catch (err: unknown) {
      setApiError(err instanceof Error ? err.message : "수정 중 오류가 발생했습니다.");
    } finally {
      setSaving(false);
    }
  };

  const set = (k: keyof FormState) => (v: string) =>
    setForm((f) => ({ ...f, [k]: v }));

  /* ─── LOADING ─── */
  if (mode === "loading") {
    return (
      <div className="p-6 lg:p-8 flex items-center justify-center min-h-64">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 size={28} className="animate-spin" />
          <span className="text-sm">사용자 정보를 불러오는 중...</span>
        </div>
      </div>
    );
  }

  const displayName = user?.nickname || user?.name || localUser?.nickname || "사용자";
  const joinDate = user?.created_at ? user.created_at: "-";

  return (
    <div className="p-6 lg:p-8 max-w-2xl" style={{ fontFamily: "Outfit, sans-serif" }}>
      {/* Breadcrumb + title */}
      <div className="mb-8">
        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2" style={{ fontFamily: "JetBrains Mono" }}>
          마이페이지
        </div>
        <div className="flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-foreground mb-1">내 정보</h1>
            <p className="text-sm text-muted-foreground">
              {mode === "view" ? "계정 정보를 확인하고 수정할 수 있습니다." : "수정할 정보를 입력해주세요."}
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
      {mode === "view" && user && (
        <div className="flex flex-col gap-5">
          {/* Avatar card */}
          <div className="bg-white border border-border rounded-xl p-6 flex items-center gap-5">
            <div className="w-20 h-20 rounded-full flex items-center justify-center text-3xl font-bold text-white flex-shrink-0"
              style={{ backgroundColor: "#10B981" }}>
              {displayName[0].toUpperCase()}
            </div>
            <div className="flex-1 min-w-0">
              <div className="font-semibold text-foreground text-xl mb-0.5">{displayName}</div>
              <div className="text-sm text-muted-foreground mb-2">{user.email}</div>
              <div className="flex items-center gap-2 text-xs font-medium px-2.5 py-1 rounded-full inline-flex"
                style={{ backgroundColor: "rgba(13,59,110,0.08)", color: "#0D3B6E" }}>
                <Shield size={11} />
                회원가입일 : {formatDate(user.created_at)}
              </div>
            </div>
          </div>

          {/* 계정 정보 */}
          <div className="bg-white border border-border rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-border">
              <h3 className="font-semibold text-foreground text-sm">계정 정보</h3>
            </div>
            <div className="px-5">
              <InfoRow icon={UserIcon} label="이름" value={user.name} />
              <InfoRow icon={UserIcon} label="닉네임" value={user.nickname} />
              <InfoRow icon={Mail} label="이메일" value={user.email} mono />
              <InfoRow icon={Phone} label="전화번호" value={formatPhoneNumber(user.phone_number)} mono />
            </div>
          </div>
        </div>
      )}

      {/* ─── EDIT FORM ─── */}
      {mode === "edit" && (
        <form onSubmit={handleUpdate} className="flex flex-col gap-5">
          {/* API 에러 */}
          {apiError && (
            <div className="flex items-center gap-2.5 px-4 py-3 rounded-lg text-sm"
              style={{ backgroundColor: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.2)", color: "#DC2626" }}>
              <AlertCircle size={15} className="flex-shrink-0" />{apiError}
            </div>
          )}

          {/* 읽기 전용 정보 */}
          <div className="bg-white border border-border rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-border">
              <h3 className="font-semibold text-foreground text-sm">계정 정보 (변경 불가)</h3>
            </div>
            <div className="px-5">
              <InfoRow icon={UserIcon} label="이름" value={user?.name ?? "-"} />
              <InfoRow icon={Mail} label="이메일" value={user?.email ?? "-"} mono />
            </div>
          </div>

          {/* 수정 가능 정보 */}
          <div className="bg-white border border-border rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-border">
              <h3 className="font-semibold text-foreground text-sm">수정 가능 정보</h3>
            </div>
            <div className="p-5 flex flex-col gap-4">
              <Field label="닉네임" error={errors.nickname} hint="최대 10자">
                <input type="text" maxLength={10} placeholder="닉네임을 입력하세요"
                  value={form.nickname} onChange={(e) => set("nickname")(e.target.value)}
                  className={INPUT}
                  style={{ borderColor: errors.nickname ? "#EF4444" : "rgba(13,59,110,0.2)" }} />
              </Field>

              <Field label="전화번호" error={errors.phone_number} hint="예: 010-1234-5678 또는 +821012345678">
                <input type="tel" placeholder="전화번호를 입력하세요"
                  value={form.phone_number} onChange={(e) => set("phone_number")(e.target.value)}
                  className={INPUT}
                  style={{ borderColor: errors.phone_number ? "#EF4444" : "rgba(13,59,110,0.2)", fontFamily: "JetBrains Mono" }} />
              </Field>
            </div>
          </div>

          {/* Actions */}
          <div className="flex gap-3">
            <button type="button" onClick={() => { setMode("view"); setApiError(""); }}
              className="flex items-center gap-2 px-5 py-3 rounded-lg text-sm font-medium text-muted-foreground border border-border hover:bg-muted transition-colors">
              <X size={14} /> 취소
            </button>
            <button type="submit" disabled={saving}
              className="flex-1 flex items-center justify-center gap-2 py-3.5 rounded-lg text-sm font-semibold text-white hover:opacity-90 disabled:opacity-60 transition-opacity"
              style={{ backgroundColor: "#0D3B6E" }}>
              {saving ? (
                <span className="flex items-center gap-2">
                  <Loader2 size={15} className="animate-spin" />
                  저장 중...
                </span>
              ) : (
                <>
                  <CheckCircle size={15} /> 변경사항 저장
                </>
              )}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
