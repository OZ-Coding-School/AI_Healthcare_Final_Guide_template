import { useState, useRef, useEffect } from "react";
import { Link, useNavigate } from "react-router";
import { Heart, Mail, Clock, CheckCircle, AlertCircle, ArrowRight, ArrowLeft } from "lucide-react";
import { sendRecoveryMail, verifyRecoveryMail } from "../shared/api/authApi";
import { ApiError } from "../shared/api/client";

const cn = (...classes: (string | boolean | undefined)[]) => classes.filter(Boolean).join(" ");

const INPUT_BASE = cn(
  "w-full px-4 py-3 rounded-lg border text-sm bg-background text-foreground outline-none transition-all duration-150",
  "focus:ring-2 focus:ring-primary/20 focus:border-primary placeholder:text-muted-foreground"
);

const TIMER_SEC = 180;

type Step = "email" | "code" | "done";

export default function Recovery() {
  const navigate = useNavigate();
  const [step, setStep] = useState<Step>("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [emailError, setEmailError] = useState("");
  const [codeError, setCodeError] = useState("");
  const [sending, setSending] = useState(false);
  const [verifying, setVerifying] = useState(false);
  const [timer, setTimer] = useState(0);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const startTimer = () => {
    if (timerRef.current) clearInterval(timerRef.current);
    setTimer(TIMER_SEC);
    timerRef.current = setInterval(() => {
      setTimer((t) => {
        if (t <= 1) {
          clearInterval(timerRef.current!);
          return 0;
        }
        return t - 1;
      });
    }, 1000);
  };
  useEffect(
    () => () => {
      if (timerRef.current) clearInterval(timerRef.current);
    },
    []
  );

  const formatTime = (s: number) =>
    `${String(Math.floor(s / 60)).padStart(2, "0")}:${String(s % 60).padStart(2, "0")}`;

  const handleSendMail = async (e: React.FormEvent) => {
    e.preventDefault();
    const emailRe = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!emailRe.test(email)) {
      setEmailError("올바른 이메일 형식을 입력해주세요.");
      return;
    }
    setEmailError("");
    setSending(true);
    try {
      await sendRecoveryMail(email);
      setStep("code");
      startTimer();
    } catch (err) {
      const msg =
        err instanceof ApiError
          ? err.status === 404
            ? "등록되지 않은 이메일입니다."
            : err.message
          : "메일 발송에 실패했습니다. 잠시 후 다시 시도해주세요.";
      setEmailError(msg);
    } finally {
      setSending(false);
    }
  };

  const handleVerify = async (e: React.FormEvent) => {
    e.preventDefault();
    if (code.length !== 6) {
      setCodeError("6자리 코드를 입력해주세요.");
      return;
    }
    setCodeError("");
    setVerifying(true);
    try {
      await verifyRecoveryMail(email, code);
      if (timerRef.current) clearInterval(timerRef.current);
      setStep("done");
    } catch (err) {
      const msg =
        err instanceof ApiError && err.status === 400
          ? "인증 코드가 일치하지 않습니다."
          : "인증에 실패했습니다. 다시 시도해주세요.";
      setCodeError(msg);
    } finally {
      setVerifying(false);
    }
  };

  const handleResend = async () => {
    setSending(true);
    try {
      await sendRecoveryMail(email);
      setCode("");
      setCodeError("");
      startTimer();
    } catch {
      setCodeError("재발송에 실패했습니다.");
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="min-h-screen flex" style={{ fontFamily: "Outfit, sans-serif" }}>
      {/* Left */}
      <div
        className="hidden lg:flex flex-col justify-between w-[440px] flex-shrink-0 p-12"
        style={{ backgroundColor: "#0B1628" }}
      >
        <Link to="/" className="flex items-center gap-2 w-fit">
          <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
            <Heart size={16} className="text-white" />
          </div>
          <span
            className="font-bold text-lg text-white"
            style={{ fontFamily: "Oxanium, sans-serif", letterSpacing: "0.04em" }}
          >
            VitalAI
          </span>
        </Link>
        <div className="flex flex-col gap-5">
          <h2
            className="text-4xl font-normal text-white leading-snug"
            style={{ fontFamily: "Instrument Serif, serif" }}
          >
            계정을
            <br />
            <span style={{ color: "#10B981" }}>복구합니다</span>
          </h2>
          <p className="text-sm leading-relaxed" style={{ color: "rgba(255,255,255,0.5)" }}>
            가입 시 사용한 이메일 주소로 인증 코드를 발송합니다. 코드 확인 후 계정 복구가
            완료됩니다.
          </p>
          {/* Steps */}
          <div className="flex flex-col gap-3 mt-4">
            {[
              { num: "01", label: "이메일 입력", done: step !== "email" },
              { num: "02", label: "인증 코드 확인", done: step === "done" },
              { num: "03", label: "복구 완료", done: false },
            ].map(({ num, label, done }) => (
              <div key={num} className="flex items-center gap-3">
                <div
                  className="w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0"
                  style={{
                    backgroundColor: done ? "rgba(16,185,129,0.2)" : "rgba(255,255,255,0.07)",
                    color: done ? "#10B981" : "rgba(255,255,255,0.4)",
                    fontFamily: "JetBrains Mono",
                  }}
                >
                  {done ? <CheckCircle size={14} /> : num}
                </div>
                <span
                  className="text-sm"
                  style={{ color: done ? "rgba(255,255,255,0.8)" : "rgba(255,255,255,0.4)" }}
                >
                  {label}
                </span>
              </div>
            ))}
          </div>
        </div>
        <p
          className="text-xs"
          style={{ color: "rgba(255,255,255,0.25)", fontFamily: "JetBrains Mono" }}
        >
          © 2025 VitalAI · 의료 진단을 대체하지 않습니다
        </p>
      </div>

      {/* Right */}
      <div className="flex-1 flex items-center justify-center px-6 py-16 bg-background">
        <div className="w-full max-w-md">
          <Link to="/" className="lg:hidden flex items-center gap-2 mb-10">
            <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
              <Heart size={16} className="text-white" />
            </div>
            <span
              className="font-bold text-lg text-foreground"
              style={{ fontFamily: "Oxanium, sans-serif", letterSpacing: "0.04em" }}
            >
              VitalAI
            </span>
          </Link>

          {/* STEP: email */}
          {step === "email" && (
            <>
              <div className="mb-8">
                <h1 className="text-2xl font-semibold text-foreground mb-2">계정 복구</h1>
                <p className="text-sm text-muted-foreground">
                  가입 시 사용한 이메일로 인증 코드를 받으세요.
                </p>
              </div>
              <form onSubmit={handleSendMail} className="flex flex-col gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm font-medium text-foreground">이메일 주소</label>
                  <input
                    type="email"
                    placeholder="example@email.com"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    className={INPUT_BASE}
                    style={{ borderColor: emailError ? "#EF4444" : "rgba(13,59,110,0.2)" }}
                  />
                  {emailError && (
                    <span className="text-xs flex items-center gap-1" style={{ color: "#EF4444" }}>
                      <AlertCircle size={11} />
                      {emailError}
                    </span>
                  )}
                </div>
                <button
                  type="submit"
                  disabled={sending}
                  className="mt-2 w-full flex items-center justify-center gap-2 py-3.5 rounded-lg text-sm font-semibold text-white hover:opacity-90 disabled:opacity-60 transition-opacity"
                  style={{ backgroundColor: "#0D3B6E" }}
                >
                  {sending ? (
                    <span className="flex items-center gap-2">
                      <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                        />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                      </svg>
                      발송 중...
                    </span>
                  ) : (
                    <>
                      <Mail size={15} /> 인증 코드 발송
                    </>
                  )}
                </button>
              </form>
              <p className="mt-6 text-sm text-center text-muted-foreground">
                <Link
                  to="/login"
                  className="flex items-center justify-center gap-1.5 hover:text-foreground transition-colors"
                >
                  <ArrowLeft size={14} /> 로그인으로 돌아가기
                </Link>
              </p>
            </>
          )}

          {/* STEP: code */}
          {step === "code" && (
            <>
              <div className="mb-8">
                <h1 className="text-2xl font-semibold text-foreground mb-2">인증 코드 입력</h1>
                <p className="text-sm text-muted-foreground">
                  <span className="font-medium text-foreground">{email}</span>로 발송된
                  <br />
                  6자리 인증 코드를 입력해주세요.
                </p>
              </div>
              <form onSubmit={handleVerify} className="flex flex-col gap-4">
                <div className="flex flex-col gap-1.5">
                  <label className="text-sm font-medium text-foreground">인증 코드</label>
                  <div className="relative">
                    <input
                      type="text"
                      inputMode="numeric"
                      maxLength={6}
                      placeholder="123456"
                      value={code}
                      onChange={(e) => setCode(e.target.value)}
                      className={cn(
                        INPUT_BASE,
                        "pr-24 text-center tracking-widest text-lg font-semibold"
                      )}
                      style={{
                        borderColor: codeError ? "#EF4444" : "rgba(13,59,110,0.2)",
                        fontFamily: "JetBrains Mono",
                      }}
                    />
                    {timer > 0 && (
                      <span
                        className="absolute right-3 top-1/2 -translate-y-1/2 flex items-center gap-1 text-xs"
                        style={{
                          color: timer < 30 ? "#EF4444" : "#64748B",
                          fontFamily: "JetBrains Mono",
                        }}
                      >
                        <Clock size={11} /> {formatTime(timer)}
                      </span>
                    )}
                  </div>
                  {codeError && (
                    <span className="text-xs flex items-center gap-1" style={{ color: "#EF4444" }}>
                      <AlertCircle size={11} />
                      {codeError}
                    </span>
                  )}
                  {timer === 0 && (
                    <div className="flex items-center justify-between text-xs mt-1">
                      <span style={{ color: "#EF4444" }}>인증 시간이 만료되었습니다.</span>
                      <button
                        type="button"
                        onClick={handleResend}
                        disabled={sending}
                        className="font-medium hover:underline disabled:opacity-50"
                        style={{ color: "#0D3B6E" }}
                      >
                        {sending ? "재발송 중..." : "코드 재발송"}
                      </button>
                    </div>
                  )}
                </div>

                <button
                  type="submit"
                  disabled={verifying || code.length !== 6}
                  className="mt-2 w-full flex items-center justify-center gap-2 py-3.5 rounded-lg text-sm font-semibold text-white hover:opacity-90 disabled:opacity-60 transition-opacity"
                  style={{ backgroundColor: "#0D3B6E" }}
                >
                  {verifying ? (
                    <span className="flex items-center gap-2">
                      <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                        <circle
                          className="opacity-25"
                          cx="12"
                          cy="12"
                          r="10"
                          stroke="currentColor"
                          strokeWidth="4"
                        />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                      </svg>
                      확인 중...
                    </span>
                  ) : (
                    <>
                      인증 확인 <ArrowRight size={16} />
                    </>
                  )}
                </button>

                {timer > 0 && (
                  <button
                    type="button"
                    onClick={handleResend}
                    disabled={sending}
                    className="w-full py-3 rounded-lg text-sm font-medium text-muted-foreground border border-border hover:bg-muted transition-colors disabled:opacity-50"
                  >
                    {sending ? "재발송 중..." : "인증 코드 재발송"}
                  </button>
                )}
              </form>

              <button
                onClick={() => setStep("email")}
                className="mt-6 w-full flex items-center justify-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                <ArrowLeft size={14} /> 이메일 다시 입력
              </button>
            </>
          )}

          {/* STEP: done */}
          {step === "done" && (
            <div className="flex flex-col items-center text-center gap-6">
              <div
                className="w-20 h-20 rounded-full flex items-center justify-center"
                style={{ backgroundColor: "rgba(16,185,129,0.1)" }}
              >
                <CheckCircle size={40} style={{ color: "#10B981" }} />
              </div>
              <div>
                <h1 className="text-2xl font-semibold text-foreground mb-2">계정 복구 완료</h1>
                <p className="text-sm text-muted-foreground leading-relaxed">
                  계정이 성공적으로 복구되었습니다.
                  <br />
                  새로운 비밀번호로 로그인해주세요.
                </p>
              </div>
              <button
                onClick={() => navigate("/login")}
                className="flex items-center gap-2 px-8 py-3.5 rounded-lg text-sm font-semibold text-white hover:opacity-90 transition-opacity"
                style={{ backgroundColor: "#0D3B6E" }}
              >
                로그인하기 <ArrowRight size={16} />
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
