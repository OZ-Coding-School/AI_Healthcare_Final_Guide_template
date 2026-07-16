import { useState, useEffect, useRef } from "react";
import { useNavigate, Link } from "react-router";
import { Heart, Eye, EyeOff, ArrowRight, CheckCircle, XCircle, Mail, AlertCircle, Clock } from "lucide-react";
import { sendSignupVerificationMail, verifySignupEmail, signup } from "../shared/api/authApi";
import { ApiError } from "../shared/api/client";

const cn = (...classes: (string | boolean | undefined)[]) =>
  classes.filter(Boolean).join(" ");

const PW_RULES = [
  { id: "len",   label: "8자 이상",        test: (v: string) => v.length >= 8 },
  { id: "upper", label: "대문자 1개 이상",  test: (v: string) => /[A-Z]/.test(v) },
  { id: "lower", label: "소문자 1개 이상",  test: (v: string) => /[a-z]/.test(v) },
  { id: "spec",  label: "특수문자 1개 이상", test: (v: string) => /[^A-Za-z0-9]/.test(v) },
];

function PasswordRule({ ok, label }: { ok: boolean; label: string }) {
  return (
    <li className="flex items-center gap-2 text-xs">
      {ok ? <CheckCircle size={13} style={{ color: "#10B981" }} /> : <XCircle size={13} className="text-muted-foreground opacity-40" />}
      <span className={ok ? "text-foreground" : "text-muted-foreground"}>{label}</span>
    </li>
  );
}

function Field({ label, required, children, hint, error }: {
  label: string; required?: boolean; children: React.ReactNode; hint?: string; error?: string;
}) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-sm font-medium text-foreground">
        {label}{required && <span className="ml-1" style={{ color: "#EF4444" }}>*</span>}
      </label>
      {children}
      {error && <span className="text-xs flex items-center gap-1" style={{ color: "#EF4444" }}><AlertCircle size={11} />{error}</span>}
      {hint && !error && <span className="text-xs text-muted-foreground">{hint}</span>}
    </div>
  );
}

const INPUT_BASE = cn(
  "w-full px-4 py-3 rounded-lg border text-sm bg-background text-foreground outline-none transition-all duration-150",
  "focus:ring-2 focus:ring-primary/20 focus:border-primary placeholder:text-muted-foreground"
);

const TIMER_SEC = 180;

export default function Signup() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    email: "", code: "", password: "", passwordConfirm: "",
    nickname: "", name: "", phone: "",
  });
  const [showPw, setShowPw]   = useState(false);
  const [showPwC, setShowPwC] = useState(false);
  const [errors, setErrors]   = useState<Record<string, string>>({});
  const [globalError, setGlobalError] = useState("");

  const [codeSent,       setCodeSent]       = useState(false);
  const [codeVerified,   setCodeVerified]   = useState(false);
  const [sendingCode,    setSendingCode]    = useState(false);
  const [verifyingCode,  setVerifyingCode]  = useState(false);
  const [timer,          setTimer]          = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const pwOk    = PW_RULES.map((r) => r.test(form.password));
  const allPwOk = pwOk.every(Boolean);

  const startTimer = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    setTimer(TIMER_SEC);
    timerRef.current = setInterval(() => {
      setTimer((t) => { if (t <= 1) { clearInterval(timerRef.current!); return 0; } return t - 1; });
    }, 1000);
  };

  useEffect(() => () => { if (timerRef.current) clearInterval(timerRef.current); }, []);

  const formatTime = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  const sendCode = async () => {
    const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRe.test(form.email)) {
      setErrors((e) => ({ ...e, email: "올바른 이메일 형식을 입력해주세요." }));
      return;
    }
    setErrors((e) => ({ ...e, email: "" }));
    setSendingCode(true);
    try {
      await sendSignupVerificationMail(form.email);
      setCodeSent(true);
      setCodeVerified(false);
      setForm((f) => ({ ...f, code: "" }));
      startTimer();
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "인증 코드 발송에 실패했습니다.";
      setErrors((e) => ({ ...e, email: msg }));
    } finally {
      setSendingCode(false);
    }
  };

  const verifyCode = async () => {
    if (form.code.length !== 6) {
      setErrors((e) => ({ ...e, code: "6자리 코드를 입력해주세요." }));
      return;
    }
    setVerifyingCode(true);
    try {
      await verifySignupEmail(form.email, form.code);
      setCodeVerified(true);
      setErrors((e) => ({ ...e, code: "" }));
      if (timerRef.current) clearInterval(timerRef.current);
    } catch (err) {
      const msg = err instanceof ApiError && err.status === 400
        ? "인증 코드가 일치하지 않습니다."
        : "인증에 실패했습니다. 다시 시도해주세요.";
      setErrors((e) => ({ ...e, code: msg }));
    } finally {
      setVerifyingCode(false);
    }
  };

  const validate = () => {
    const e: Record<string, string> = {};
    if (!codeVerified) e.code = "이메일 인증을 완료해주세요.";
    if (!allPwOk) e.password = "비밀번호 조건을 모두 충족해주세요.";
    if (form.password !== form.passwordConfirm) e.passwordConfirm = "비밀번호가 일치하지 않습니다.";
    const nickLen = form.nickname.trim().length;
    if (nickLen < 1 || nickLen > 10) e.nickname = "닉네임은 1~10자로 입력해주세요.";
    if (!form.name.trim()) e.name = "이름을 입력해주세요.";
    const phoneRe = /^01[0-9]{8,9}$/;
    if (!phoneRe.test(form.phone.replace(/-/g, ""))) e.phone = "올바른 휴대폰 번호를 입력해주세요. (예: 01012345678)";
    return e;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setGlobalError("");
    const errs = validate();
    setErrors(errs);
    if (Object.keys(errs).length > 0) return;
    setSubmitting(true);
    try {
      await signup({
        email: form.email,
        password: form.password,
        name: form.name.trim(),
        nickname: form.nickname.trim(),
        phone_number: form.phone.replace(/-/g, ""),
      });
      navigate("/login", { state: { signupSuccess: true } });
    } catch (err) {
      const msg = err instanceof ApiError ? err.message : "회원가입 중 오류가 발생했습니다.";
      setGlobalError(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const set = (k: string) => (e: React.ChangeEvent<HTMLInputElement>) =>
    setForm((f) => ({ ...f, [k]: e.target.value }));

  return (
    <div className="min-h-screen flex" style={{ fontFamily: "Outfit, sans-serif" }}>
      {/* Left */}
      <div className="hidden lg:flex flex-col justify-between w-[440px] flex-shrink-0 p-12" style={{ backgroundColor: "#0B1628" }}>
        <Link to="/" className="flex items-center gap-2 w-fit">
          <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center"><Heart size={16} className="text-white" /></div>
          <span className="font-bold text-lg text-white" style={{ fontFamily: "Oxanium, sans-serif", letterSpacing: "0.04em" }}>VitalAI</span>
        </Link>
        <div className="flex flex-col gap-6">
          <div className="inline-flex items-center gap-2 text-xs font-medium px-3 py-1.5 rounded-full border w-fit"
            style={{ fontFamily: "JetBrains Mono", color: "#10B981", borderColor: "rgba(16,185,129,0.3)", backgroundColor: "rgba(16,185,129,0.08)" }}>
            <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: "#10B981" }} />무료로 시작하기
          </div>
          <h2 className="text-4xl font-normal text-white leading-snug" style={{ fontFamily: "Instrument Serif, serif" }}>
            건강한 내일을<br /><span style={{ color: "#10B981" }}>지금 시작하세요</span>
          </h2>
          <p className="text-sm leading-relaxed" style={{ color: "rgba(255,255,255,0.5)" }}>
            가입 후 건강 프로필을 등록하면 AI가 당뇨병·고혈압 위험도를 즉시 분석합니다.
          </p>
          <ul className="flex flex-col gap-3 mt-2">
            {["이메일 인증으로 안전한 계정 생성", "건강 데이터 즉시 입력 가능", "AI 위험도 예측 및 리포트 무료 제공", "맞춤형 건강 챌린지 추천"].map((item) => (
              <li key={item} className="flex items-center gap-3 text-sm" style={{ color: "rgba(255,255,255,0.7)" }}>
                <div className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0" style={{ backgroundColor: "rgba(16,185,129,0.15)" }}>
                  <CheckCircle size={12} style={{ color: "#10B981" }} />
                </div>
                {item}
              </li>
            ))}
          </ul>
        </div>
        <p className="text-xs" style={{ color: "rgba(255,255,255,0.25)", fontFamily: "JetBrains Mono" }}>
          © 2025 VitalAI · 의료 진단을 대체하지 않습니다
        </p>
      </div>

      {/* Right */}
      <div className="flex-1 flex items-start justify-center px-6 py-16 bg-background overflow-y-auto">
        <div className="w-full max-w-md">
          <Link to="/" className="lg:hidden flex items-center gap-2 mb-10">
            <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center"><Heart size={16} className="text-white" /></div>
            <span className="font-bold text-lg text-foreground" style={{ fontFamily: "Oxanium, sans-serif", letterSpacing: "0.04em" }}>VitalAI</span>
          </Link>

          <div className="mb-8">
            <h1 className="text-2xl font-semibold text-foreground mb-2">회원가입</h1>
            <p className="text-sm text-muted-foreground">
              이미 계정이 있으신가요?{" "}
              <Link to="/login" className="font-medium hover:underline" style={{ color: "#0D3B6E" }}>로그인</Link>
            </p>
          </div>

          {globalError && (
            <div className="flex items-center gap-2.5 px-4 py-3 rounded-lg text-sm mb-5"
              style={{ backgroundColor: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.2)", color: "#DC2626" }}>
              <AlertCircle size={15} className="flex-shrink-0" />{globalError}
            </div>
          )}

          <form onSubmit={handleSubmit} className="flex flex-col gap-5">
            {/* ── 이메일 인증 ── */}
            <div className="flex flex-col gap-3 p-4 rounded-xl border transition-colors"
              style={{ borderColor: codeVerified ? "rgba(16,185,129,0.3)" : "rgba(13,59,110,0.12)", backgroundColor: codeVerified ? "rgba(16,185,129,0.04)" : "transparent" }}>
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold text-foreground">이메일 인증</span>
                {codeVerified && (
                  <span className="flex items-center gap-1.5 text-xs font-medium" style={{ color: "#10B981", fontFamily: "JetBrains Mono" }}>
                    <CheckCircle size={13} /> 인증 완료
                  </span>
                )}
              </div>

              <Field label="이메일" required error={errors.email}>
                <div className="flex gap-2">
                  <input type="email" placeholder="example@email.com" value={form.email} onChange={set("email")}
                    disabled={codeVerified}
                    className={cn(INPUT_BASE, "flex-1", codeVerified && "opacity-60 cursor-not-allowed")}
                    style={{ borderColor: errors.email ? "#EF4444" : "rgba(13,59,110,0.2)" }} />
                  <button type="button" onClick={sendCode} disabled={sendingCode || codeVerified}
                    className="flex-shrink-0 px-4 py-3 rounded-lg text-sm font-semibold text-white transition-all hover:opacity-90 disabled:opacity-50 whitespace-nowrap"
                    style={{ backgroundColor: "#0D3B6E" }}>
                    {sendingCode ? "전송 중..." : codeSent ? "재전송" : "코드 전송"}
                  </button>
                </div>
              </Field>

              {codeSent && !codeVerified && (
                <Field label="인증 코드" required error={errors.code} hint="이메일로 발송된 6자리 코드를 입력하세요.">
                  <div className="flex gap-2">
                    <div className="relative flex-1">
                      <input type="text" inputMode="numeric" maxLength={6} placeholder="123456"
                        value={form.code} onChange={set("code")}
                        className={cn(INPUT_BASE, "pr-20")}
                        style={{ borderColor: errors.code ? "#EF4444" : "rgba(13,59,110,0.2)", letterSpacing: "0.15em", fontFamily: "JetBrains Mono" }} />
                      {timer > 0 && (
                        <span className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1 text-xs"
                          style={{ color: timer < 30 ? "#EF4444" : "#64748B", fontFamily: "JetBrains Mono" }}>
                          <Clock size={11} /> {formatTime(timer)}
                        </span>
                      )}
                    </div>
                    <button type="button" onClick={verifyCode} disabled={verifyingCode || form.code.length !== 6}
                      className="flex-shrink-0 px-4 py-3 rounded-lg text-sm font-semibold transition-all hover:opacity-90 disabled:opacity-50"
                      style={{ backgroundColor: "rgba(16,185,129,0.1)", color: "#10B981" }}>
                      {verifyingCode ? "확인 중..." : "확인"}
                    </button>
                  </div>
                  {timer === 0 && (
                    <div className="flex items-center gap-2 text-xs mt-1" style={{ color: "#EF4444" }}>
                      <AlertCircle size={12} /> 인증 시간이 만료되었습니다. 코드를 재전송해주세요.
                    </div>
                  )}
                </Field>
              )}

              {!codeSent && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Mail size={13} /> 이메일로 6자리 인증 코드를 발송합니다.
                </div>
              )}
            </div>

            {/* 비밀번호 */}
            <Field label="비밀번호" required error={errors.password}>
              <div className="relative">
                <input type={showPw ? "text" : "password"} placeholder="비밀번호를 입력하세요"
                  value={form.password} onChange={set("password")}
                  className={cn(INPUT_BASE, "pr-11")}
                  style={{ borderColor: errors.password ? "#EF4444" : "rgba(13,59,110,0.2)" }} />
                <button type="button" onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors">
                  {showPw ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
              {form.password && (
                <ul className="grid grid-cols-2 gap-x-4 gap-y-1.5 mt-2">
                  {PW_RULES.map((r, i) => <PasswordRule key={r.id} ok={pwOk[i]} label={r.label} />)}
                </ul>
              )}
            </Field>

            {/* 비밀번호 확인 */}
            <Field label="비밀번호 확인" required error={errors.passwordConfirm}>
              <div className="relative">
                <input type={showPwC ? "text" : "password"} placeholder="비밀번호를 다시 입력하세요"
                  value={form.passwordConfirm} onChange={set("passwordConfirm")}
                  className={cn(INPUT_BASE, "pr-11")}
                  style={{ borderColor: errors.passwordConfirm ? "#EF4444" : form.passwordConfirm && form.password === form.passwordConfirm ? "#10B981" : "rgba(13,59,110,0.2)" }} />
                <button type="button" onClick={() => setShowPwC(!showPwC)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors">
                  {showPwC ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
              {form.passwordConfirm && form.password === form.passwordConfirm && (
                <span className="text-xs flex items-center gap-1" style={{ color: "#10B981" }}>
                  <CheckCircle size={11} /> 비밀번호가 일치합니다.
                </span>
              )}
            </Field>

            {/* 닉네임 */}
            <Field label="닉네임" required error={errors.nickname} hint="1~10자로 입력해주세요.">
              <div className="relative">
                <input type="text" placeholder="사용할 닉네임" maxLength={10}
                  value={form.nickname} onChange={set("nickname")}
                  className={cn(INPUT_BASE, "pr-14")}
                  style={{ borderColor: errors.nickname ? "#EF4444" : "rgba(13,59,110,0.2)" }} />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground" style={{ fontFamily: "JetBrains Mono" }}>
                  {form.nickname.length}/10
                </span>
              </div>
            </Field>

            {/* 이름 */}
            <Field label="이름" required error={errors.name}>
              <input type="text" placeholder="실명을 입력하세요" maxLength={20}
                value={form.name} onChange={set("name")}
                className={INPUT_BASE}
                style={{ borderColor: errors.name ? "#EF4444" : "rgba(13,59,110,0.2)" }} />
            </Field>

            {/* 휴대폰 번호 */}
            <Field label="휴대폰 번호" required error={errors.phone} hint="인증 없이 저장됩니다. (예: 01012345678)">
              <input type="tel" placeholder="01012345678" maxLength={11}
                value={form.phone} onChange={set("phone")}
                className={INPUT_BASE}
                style={{ borderColor: errors.phone ? "#EF4444" : "rgba(13,59,110,0.2)", fontFamily: "JetBrains Mono" }} />
            </Field>

            <button type="submit" disabled={submitting}
              className="mt-2 w-full flex items-center justify-center gap-2 py-3.5 rounded-lg text-sm font-semibold text-white transition-all duration-200 hover:opacity-90 disabled:opacity-60"
              style={{ backgroundColor: "#0D3B6E" }}>
              {submitting ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                  </svg>
                  가입 처리 중...
                </span>
              ) : <>가입 완료 <ArrowRight size={16} /></>}
            </button>

            <p className="text-xs text-center text-muted-foreground pb-4">
              가입 시{" "}<a href="#" className="underline hover:text-foreground">이용약관</a>{" "}및{" "}
              <a href="#" className="underline hover:text-foreground">개인정보처리방침</a>에 동의하는 것으로 간주합니다.
            </p>
          </form>
        </div>
      </div>
    </div>
  );
}
