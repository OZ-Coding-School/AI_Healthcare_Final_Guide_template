import { useState } from "react";
import { useNavigate, Link } from "react-router";
import { Heart, Eye, EyeOff, ArrowRight, AlertCircle } from "lucide-react";
import { login } from "../shared/api/authApi";
import { ApiError } from "../shared/api/client";
import { saveUser } from "../shared/api/auth";
import {getMyInfo} from "../shared/api/userApi";

const cn = (...classes: (string | boolean | undefined)[]) =>
  classes.filter(Boolean).join(" ");

export default function Login() {
  const navigate = useNavigate();
  const [form, setForm] = useState({ email: "", password: "" });
  const [showPw, setShowPw] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError("");
    if (!form.email || !form.password) {
      setError("이메일과 비밀번호를 입력해주세요.");
      return;
    }
    setLoading(true);
    try {
      await login(form.email, form.password);
      // access_token은 login() 내부에서 저장됨
      // 사용자 정보는 별도 /me API 연동 전까지 이메일 기반으로 임시 저장
      const loginUser = await getMyInfo()
      saveUser({ email: loginUser.email, nickname: loginUser.nickname, name: loginUser.name });
      navigate("/app");
    } catch (err) {
      if (err instanceof ApiError) {
        setError(
          err.status === 401
            ? "이메일 또는 비밀번호가 올바르지 않습니다."
            : err.message,
        );
      } else {
        setError("로그인 중 오류가 발생했습니다. 잠시 후 다시 시도해주세요.");
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex" style={{ fontFamily: "Outfit, sans-serif" }}>
      {/* Left — Branding */}
      <div
        className="hidden lg:flex flex-col justify-between w-[480px] flex-shrink-0 p-12"
        style={{ backgroundColor: "#0B1628" }}
      >
        <Link to="/" className="flex items-center gap-2 w-fit">
          <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
            <Heart size={16} className="text-white" />
          </div>
          <span className="font-bold text-lg text-white" style={{ fontFamily: "Oxanium, sans-serif", letterSpacing: "0.04em" }}>
            VitalAI
          </span>
        </Link>

        <div className="flex flex-col gap-6">
          <div className="inline-flex items-center gap-2 text-xs font-medium px-3 py-1.5 rounded-full border w-fit"
            style={{ fontFamily: "JetBrains Mono", color: "#10B981", borderColor: "rgba(16,185,129,0.3)", backgroundColor: "rgba(16,185,129,0.08)" }}>
            <span className="w-1.5 h-1.5 rounded-full animate-pulse" style={{ backgroundColor: "#10B981" }} />
            AI 기반 만성질환 예방
          </div>
          <h2 className="text-4xl font-normal text-white leading-snug" style={{ fontFamily: "Instrument Serif, serif" }}>
            다시 돌아오신 것을<br />
            <span style={{ color: "#10B981" }}>환영합니다</span>
          </h2>
          <p className="text-sm leading-relaxed" style={{ color: "rgba(255,255,255,0.5)" }}>
            로그인하고 AI가 분석한 건강 리포트와 맞춤 챌린지를 바로 확인하세요.
          </p>
          <div className="grid grid-cols-2 gap-4 mt-4">
            {[
              { value: "94.2%", label: "AI 예측 정확도" },
              { value: "12,400+", label: "누적 사용자" },
              { value: "평균 28%", label: "위험도 감소" },
              { value: "3개월", label: "평균 개선 기간" },
            ].map(({ value, label }) => (
              <div key={label} className="p-4 rounded-xl" style={{ backgroundColor: "rgba(255,255,255,0.04)", border: "1px solid rgba(255,255,255,0.07)" }}>
                <div className="text-lg font-bold text-white" style={{ fontFamily: "JetBrains Mono" }}>{value}</div>
                <div className="text-xs mt-0.5" style={{ color: "rgba(255,255,255,0.4)" }}>{label}</div>
              </div>
            ))}
          </div>
        </div>

        <p className="text-xs" style={{ color: "rgba(255,255,255,0.25)", fontFamily: "JetBrains Mono" }}>
          © 2025 VitalAI · 의료 진단을 대체하지 않습니다
        </p>
      </div>

      {/* Right — Form */}
      <div className="flex-1 flex items-center justify-center px-6 py-16 bg-background">
        <div className="w-full max-w-md">
          <Link to="/" className="lg:hidden flex items-center gap-2 mb-10">
            <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center">
              <Heart size={16} className="text-white" />
            </div>
            <span className="font-bold text-lg text-foreground" style={{ fontFamily: "Oxanium, sans-serif", letterSpacing: "0.04em" }}>VitalAI</span>
          </Link>

          <div className="mb-8">
            <h1 className="text-2xl font-semibold text-foreground mb-2">로그인</h1>
            <p className="text-sm text-muted-foreground">
              계정이 없으신가요?{" "}
              <Link to="/signup" className="font-medium hover:underline" style={{ color: "#0D3B6E" }}>회원가입</Link>
            </p>
          </div>

          <form onSubmit={handleSubmit} className="flex flex-col gap-4">
            {error && (
              <div className="flex items-center gap-2.5 px-4 py-3 rounded-lg text-sm"
                style={{ backgroundColor: "rgba(239,68,68,0.06)", border: "1px solid rgba(239,68,68,0.2)", color: "#DC2626" }}>
                <AlertCircle size={15} className="flex-shrink-0" />
                {error}
              </div>
            )}

            {/* Email */}
            <div className="flex flex-col gap-1.5">
              <label className="text-sm font-medium text-foreground">이메일</label>
              <input
                type="email"
                placeholder="example@email.com"
                value={form.email}
                onChange={(e) => setForm({ ...form, email: e.target.value })}
                className={cn(
                  "w-full px-4 py-3 rounded-lg border text-sm bg-background text-foreground outline-none transition-all duration-150",
                  "focus:ring-2 focus:ring-primary/20 focus:border-primary placeholder:text-muted-foreground"
                )}
                style={{ borderColor: "rgba(13,59,110,0.2)" }}
              />
            </div>

            {/* Password */}
            <div className="flex flex-col gap-1.5">
              <div className="flex items-center justify-between">
                <label className="text-sm font-medium text-foreground">비밀번호</label>
                <Link to="/recovery" className="text-xs font-medium hover:underline" style={{ color: "#0D3B6E" }}>
                  비밀번호 찾기
                </Link>
              </div>
              <div className="relative">
                <input
                  type={showPw ? "text" : "password"}
                  placeholder="비밀번호를 입력하세요"
                  value={form.password}
                  onChange={(e) => setForm({ ...form, password: e.target.value })}
                  className={cn(
                    "w-full px-4 py-3 pr-11 rounded-lg border text-sm bg-background text-foreground outline-none transition-all duration-150",
                    "focus:ring-2 focus:ring-primary/20 focus:border-primary placeholder:text-muted-foreground"
                  )}
                  style={{ borderColor: "rgba(13,59,110,0.2)" }}
                />
                <button type="button" onClick={() => setShowPw(!showPw)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors">
                  {showPw ? <EyeOff size={17} /> : <Eye size={17} />}
                </button>
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="mt-2 w-full flex items-center justify-center gap-2 py-3.5 rounded-lg text-sm font-semibold text-white transition-all duration-200 hover:opacity-90 disabled:opacity-60"
              style={{ backgroundColor: "#0D3B6E" }}
            >
              {loading ? (
                <span className="flex items-center gap-2">
                  <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8z" />
                  </svg>
                  로그인 중...
                </span>
              ) : (
                <>로그인 <ArrowRight size={16} /></>
              )}
            </button>
          </form>

          <div className="flex items-center gap-3 my-6">
            <div className="flex-1 h-px bg-border" />
            <span className="text-xs text-muted-foreground" style={{ fontFamily: "JetBrains Mono" }}>또는</span>
            <div className="flex-1 h-px bg-border" />
          </div>

          <button type="button" className="w-full flex items-center justify-center gap-3 py-3 rounded-lg border border-border text-sm font-medium text-foreground hover:bg-muted transition-colors">
            <svg width="18" height="18" viewBox="0 0 18 18">
              <path fill="#4285F4" d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844c-.209 1.125-.843 2.078-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z"/>
              <path fill="#34A853" d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 009 18z"/>
              <path fill="#FBBC05" d="M3.964 10.707A5.41 5.41 0 013.682 9c0-.593.102-1.17.282-1.707V4.961H.957A8.996 8.996 0 000 9c0 1.452.348 2.827.957 4.039l3.007-2.332z"/>
              <path fill="#EA4335" d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 00.957 4.961L3.964 7.293C4.672 5.163 6.656 3.58 9 3.58z"/>
            </svg>
            Google로 로그인
          </button>

          <p className="mt-8 text-xs text-center text-muted-foreground">
            로그인 시{" "}
            <a href="#" className="underline hover:text-foreground">이용약관</a>{" "}및{" "}
            <a href="#" className="underline hover:text-foreground">개인정보처리방침</a>에 동의하는 것으로 간주합니다.
          </p>
        </div>
      </div>
    </div>
  );
}
