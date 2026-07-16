import { useState, useEffect } from "react";
import { useNavigate } from "react-router";
import { motion } from "motion/react";
import {
  Activity, Brain, ChevronRight, Heart, Shield, Target, TrendingUp,
  Users, Zap, CheckCircle, ArrowRight, BarChart3, Droplets, Wind,
  Flame, Star, Menu, X, ClipboardList, CalendarDays, FileText,
  UserCircle, Lock, Microscope, LineChart, ChevronDown,
} from "lucide-react";

const cn = (...classes: (string | boolean | undefined)[]) =>
  classes.filter(Boolean).join(" ");

const NAV_ITEMS = [
  { id: "how", label: "작동 방식" },
  { id: "features", label: "주요 기능" },
  { id: "predict", label: "AI 예측" },
  { id: "challenges", label: "챌린지" },
  { id: "reviews", label: "후기" },
];

function SideNav({ activeSection }: { activeSection: string }) {
  const scrollTo = (id: string) =>
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
  return (
    <div className="fixed right-5 top-1/2 -translate-y-1/2 z-40 hidden lg:flex flex-col gap-2">
      {NAV_ITEMS.map(({ id, label }) => {
        const isActive = activeSection === id;
        return (
          <button key={id} onClick={() => scrollTo(id)} className="group flex items-center justify-end gap-2.5 cursor-pointer">
            <span
              className={cn("text-xs font-medium px-2.5 py-1 rounded-md transition-all duration-200 whitespace-nowrap",
                isActive ? "opacity-100 translate-x-0" : "opacity-0 translate-x-2 group-hover:opacity-100 group-hover:translate-x-0")}
              style={{ fontFamily: "JetBrains Mono", backgroundColor: isActive ? "rgba(13,59,110,0.12)" : "rgba(11,22,40,0.08)", color: isActive ? "#0D3B6E" : "#64748B", backdropFilter: "blur(8px)" }}
            >
              {label}
            </span>
            <div
              className={cn("rounded-full transition-all duration-300 flex-shrink-0", isActive ? "w-3 h-3" : "w-2 h-2 group-hover:w-2.5 group-hover:h-2.5")}
              style={{ backgroundColor: isActive ? "#0D3B6E" : "rgba(100,116,139,0.45)", boxShadow: isActive ? "0 0 0 3px rgba(13,59,110,0.15)" : "none" }}
            />
          </button>
        );
      })}
    </div>
  );
}

function RiskGauge({ label, value, color, risk }: { label: string; value: number; color: string; risk: string }) {
  const r = 48;
  const circumference = Math.PI * r;
  const strokeDash = (value / 100) * circumference;
  return (
    <div className="flex flex-col items-center gap-2">
      <svg width="120" height="72" viewBox="0 0 120 72">
        <path d={`M 12 60 A ${r} ${r} 0 0 1 108 60`} fill="none" stroke="#E2E8F0" strokeWidth="10" strokeLinecap="round" />
        <path d={`M 12 60 A ${r} ${r} 0 0 1 108 60`} fill="none" stroke={color} strokeWidth="10" strokeLinecap="round" strokeDasharray={`${strokeDash} ${circumference}`} />
        <text x="60" y="54" textAnchor="middle" fontSize="18" fontWeight="700" fill="#0B1628" fontFamily="JetBrains Mono">{value}%</text>
      </svg>
      <span className="text-xs font-medium" style={{ color, fontFamily: "JetBrains Mono" }}>{risk}</span>
      <span className="text-sm text-muted-foreground font-medium">{label}</span>
    </div>
  );
}

function FeatureCard({ icon: Icon, title, desc, color, tag, delay }: { icon: React.ElementType; title: string; desc: string; color: string; tag?: string; delay: number }) {
  return (
    <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.45, delay }}
      className="bg-card border border-border rounded-xl p-5 flex flex-col gap-3 hover:shadow-md transition-shadow duration-300">
      <div className="flex items-start justify-between">
        <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${color}14` }}>
          <Icon size={20} style={{ color }} />
        </div>
        {tag && <span className="text-[10px] font-semibold px-2 py-0.5 rounded-full" style={{ fontFamily: "JetBrains Mono", backgroundColor: `${color}12`, color }}>{tag}</span>}
      </div>
      <div>
        <h4 className="font-semibold text-foreground mb-1 text-sm">{title}</h4>
        <p className="text-xs text-muted-foreground leading-relaxed">{desc}</p>
      </div>
    </motion.div>
  );
}

function StepCard({ num, icon: Icon, title, desc, sub, delay }: { num: string; icon: React.ElementType; title: string; desc: string; sub: string[]; delay: number }) {
  return (
    <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.5, delay }} className="flex flex-col gap-4">
      <div className="flex items-center gap-3">
        <span className="text-xs font-medium text-muted-foreground" style={{ fontFamily: "JetBrains Mono" }}>{num}</span>
        <div className="h-px flex-1 bg-border" />
      </div>
      <div className="w-12 h-12 bg-secondary rounded-xl flex items-center justify-center"><Icon size={22} className="text-primary" /></div>
      <div>
        <h3 className="font-semibold text-foreground text-lg mb-1.5">{title}</h3>
        <p className="text-muted-foreground leading-relaxed text-sm mb-3">{desc}</p>
        <ul className="flex flex-col gap-1.5">
          {sub.map((s) => (
            <li key={s} className="flex items-center gap-2 text-xs text-muted-foreground">
              <CheckCircle size={12} className="text-accent flex-shrink-0" />{s}
            </li>
          ))}
        </ul>
      </div>
    </motion.div>
  );
}

function ChallengeCard({ icon: Icon, title, desc, progress, days, color, basis, delay }: { icon: React.ElementType; title: string; desc: string; progress: number; days: string; color: string; basis: string; delay: number }) {
  return (
    <motion.div initial={{ opacity: 0, y: 24 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.5, delay }}
      className="bg-card border border-border rounded-xl p-6 flex flex-col gap-4 hover:shadow-lg transition-shadow duration-300">
      <div className="flex items-start justify-between">
        <div className="w-11 h-11 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${color}15` }}><Icon size={22} style={{ color }} /></div>
        <span className="text-xs font-medium px-2.5 py-1 rounded-full" style={{ fontFamily: "JetBrains Mono", backgroundColor: `${color}12`, color }}>{days}</span>
      </div>
      <div>
        <h4 className="font-semibold text-foreground mb-1">{title}</h4>
        <p className="text-sm text-muted-foreground leading-relaxed">{desc}</p>
      </div>
      <div className="text-[11px] px-2.5 py-1.5 rounded-lg" style={{ backgroundColor: "rgba(13,59,110,0.05)", color: "#0D3B6E", fontFamily: "JetBrains Mono" }}>
        추천 근거: {basis}
      </div>
      <div>
        <div className="flex justify-between items-center mb-1.5">
          <span className="text-xs text-muted-foreground" style={{ fontFamily: "JetBrains Mono" }}>진행률</span>
          <span className="text-xs font-medium" style={{ fontFamily: "JetBrains Mono", color }}>{progress}%</span>
        </div>
        <div className="h-1.5 bg-muted rounded-full overflow-hidden">
          <div className="h-full rounded-full" style={{ width: `${progress}%`, backgroundColor: color }} />
        </div>
      </div>
    </motion.div>
  );
}

function Testimonial({ name, role, text, avatar, delay }: { name: string; role: string; text: string; avatar: string; delay: number }) {
  return (
    <motion.div initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.5, delay }}
      className="bg-card border border-border rounded-xl p-6 flex flex-col gap-4">
      <div className="flex gap-0.5">{[...Array(5)].map((_, i) => <Star key={i} size={14} fill="#F59E0B" stroke="none" />)}</div>
      <p className="text-sm text-foreground leading-relaxed">"{text}"</p>
      <div className="flex items-center gap-3 mt-auto">
        <img src={avatar} alt={name} className="w-9 h-9 rounded-full object-cover bg-muted" />
        <div>
          <div className="text-sm font-semibold text-foreground">{name}</div>
          <div className="text-xs text-muted-foreground">{role}</div>
        </div>
      </div>
    </motion.div>
  );
}

export default function Landing() {
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  const [activeSection, setActiveSection] = useState("");

  useEffect(() => {
    const onScroll = () => {
      setScrolled(window.scrollY > 24);
      const offsets = NAV_ITEMS.map(({ id }) => {
        const el = document.getElementById(id);
        if (!el) return { id, top: Infinity };
        return { id, top: Math.abs(el.getBoundingClientRect().top - 120) };
      });
      const closest = offsets.reduce((a, b) => (a.top < b.top ? a : b));
      if (closest.top < 400) setActiveSection(closest.id);
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <div className="min-h-screen bg-background text-foreground" style={{ fontFamily: "Outfit, sans-serif" }}>
      <SideNav activeSection={activeSection} />

      {/* NAV */}
      <nav className={cn("fixed top-0 left-0 right-0 z-50 transition-all duration-300", scrolled ? "bg-white/95 backdrop-blur-md border-b border-border shadow-sm" : "bg-transparent")}>
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center"><Heart size={16} className="text-white" /></div>
            <span className={cn("font-bold text-lg transition-colors duration-300", scrolled ? "text-foreground" : "text-white")} style={{ fontFamily: "Oxanium, sans-serif", letterSpacing: "0.04em" }}>VitalAI</span>
          </div>
          <div className="hidden md:flex items-center gap-3">
            <button onClick={() => navigate("/login")} className={cn("text-sm font-medium transition-colors duration-300 px-4 py-2", scrolled ? "text-muted-foreground hover:text-foreground" : "text-white/70 hover:text-white")}>로그인</button>
            <button onClick={() => navigate("/signup")} className="text-sm font-semibold bg-primary text-white px-4 py-2 rounded-lg hover:opacity-90 transition-opacity">무료로 시작하기</button>
          </div>
          <button className={cn("md:hidden p-2 transition-colors duration-300", scrolled ? "text-foreground" : "text-white")} onClick={() => setMenuOpen(!menuOpen)}>
            {menuOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
        {menuOpen && (
          <div className="md:hidden bg-white border-b border-border px-6 py-4 flex flex-col gap-4">
            {NAV_ITEMS.map(({ id, label }) => (
              <a key={id} href={`#${id}`} className="text-sm font-medium text-muted-foreground hover:text-foreground transition-colors" onClick={() => setMenuOpen(false)}>{label}</a>
            ))}
            <button onClick={() => navigate("/signup")} className="text-sm font-semibold bg-primary text-white px-4 py-2.5 rounded-lg w-full">무료로 시작하기</button>
          </div>
        )}
      </nav>

      {/* HERO */}
      <section className="relative min-h-screen flex items-center overflow-hidden" style={{ backgroundColor: "#0B1628" }}>
        <div className="absolute inset-0 opacity-[0.04]" style={{ backgroundImage: `linear-gradient(rgba(255,255,255,0.6) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.6) 1px, transparent 1px)`, backgroundSize: "48px 48px" }} />
        <div className="absolute top-1/3 right-1/4 w-96 h-96 rounded-full opacity-10 blur-3xl" style={{ backgroundColor: "#10B981" }} />
        <div className="relative max-w-6xl mx-auto px-6 pt-24 pb-20 grid md:grid-cols-2 gap-16 items-center w-full">
          <div className="flex flex-col gap-8">
            <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
              <span className="inline-flex items-center gap-2 text-xs font-medium px-3 py-1.5 rounded-full border mb-6" style={{ fontFamily: "JetBrains Mono", color: "#10B981", borderColor: "rgba(16,185,129,0.3)", backgroundColor: "rgba(16,185,129,0.08)" }}>
                <span className="w-1.5 h-1.5 rounded-full bg-accent animate-pulse" />
                AI 기반 만성질환 예방 플랫폼
              </span>
              <h1 className="text-5xl md:text-6xl font-normal text-white leading-[1.1] tracking-tight" style={{ fontFamily: "Instrument Serif, serif" }}>
                당신의 건강 데이터,<br /><span style={{ color: "#10B981" }}>AI가 먼저</span><br />알려드립니다
              </h1>
            </motion.div>
            <motion.p initial={{ opacity: 0, y: 12 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.15 }} className="text-lg leading-relaxed" style={{ color: "rgba(255,255,255,0.6)" }}>
              건강 프로필·월별 건강 기록·연간 검진 결과를 쌓으면, AI가 당뇨병·고혈압 위험도를 분석하고 맞춤 리포트와 챌린지로 예방까지 이어드립니다.
            </motion.p>
            <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.25 }} className="flex flex-col sm:flex-row gap-3">
              <button onClick={() => navigate("/signup")} className="flex items-center justify-center gap-2 text-sm font-semibold px-6 py-3.5 rounded-lg transition-all duration-200 hover:opacity-90 hover:gap-3" style={{ backgroundColor: "#10B981", color: "#fff" }}>
                무료로 시작하기 <ArrowRight size={16} />
              </button>
              <button className="flex items-center justify-center gap-2 text-sm font-medium px-6 py-3.5 rounded-lg border transition-all duration-200 hover:bg-white/5" style={{ color: "rgba(255,255,255,0.8)", borderColor: "rgba(255,255,255,0.2)" }}>
                기능 살펴보기 <ChevronDown size={16} />
              </button>
            </motion.div>
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.6, delay: 0.4 }} className="flex items-center gap-6 pt-2">
              {[{ label: "AI 예측 정확도", value: "94.2%" }, { label: "누적 사용자", value: "12,400+" }, { label: "예방 성공 사례", value: "8,200건" }].map(({ label, value }) => (
                <div key={label}>
                  <div className="text-xl font-bold text-white" style={{ fontFamily: "JetBrains Mono" }}>{value}</div>
                  <div className="text-xs mt-0.5" style={{ color: "rgba(255,255,255,0.4)" }}>{label}</div>
                </div>
              ))}
            </motion.div>
          </div>

          <motion.div initial={{ opacity: 0, x: 24 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.7, delay: 0.2 }} className="hidden md:block">
            <div className="rounded-2xl p-6 border" style={{ backgroundColor: "rgba(255,255,255,0.04)", borderColor: "rgba(255,255,255,0.1)", backdropFilter: "blur(12px)" }}>
              <div className="flex items-center justify-between mb-5">
                <div>
                  <div className="text-xs text-white/40 mb-1" style={{ fontFamily: "JetBrains Mono" }}>김민준 · 42세 · 건강 리포트</div>
                  <div className="text-white font-semibold">AI 위험도 분석 결과</div>
                </div>
                <div className="text-xs px-2.5 py-1 rounded-full" style={{ fontFamily: "JetBrains Mono", backgroundColor: "rgba(16,185,129,0.15)", color: "#10B981" }}>2025.01 리포트</div>
              </div>
              <div className="flex justify-around mb-5 py-4 rounded-xl" style={{ backgroundColor: "#ffffff" }}>
                <RiskGauge label="당뇨병" value={68} color="#F59E0B" risk="주의 필요" />
                <div className="w-px bg-border self-stretch" />
                <RiskGauge label="고혈압" value={31} color="#10B981" risk="정상 범위" />
              </div>
              <div className="rounded-xl p-4 mb-4 border" style={{ backgroundColor: "rgba(245,158,11,0.06)", borderColor: "rgba(245,158,11,0.2)" }}>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-xs text-white/60 font-medium" style={{ fontFamily: "JetBrains Mono" }}>혈당 측정 기록 (최근 7일)</span>
                  <span className="text-[10px] px-2 py-0.5 rounded-full" style={{ fontFamily: "JetBrains Mono", backgroundColor: "rgba(245,158,11,0.2)", color: "#F59E0B" }}>당뇨 환자 전용</span>
                </div>
                <div className="flex items-end gap-1.5 h-10">
                  {[88, 112, 134, 98, 145, 118, 107].map((v, i) => (
                    <div key={i} className="flex-1">
                      <div className="w-full rounded-sm" style={{ height: `${(v / 160) * 32}px`, backgroundColor: v > 126 ? "#EF4444" : v > 100 ? "#F59E0B" : "#10B981", opacity: 0.8 }} />
                    </div>
                  ))}
                </div>
                <div className="flex justify-between mt-1">
                  {["월", "화", "수", "목", "금", "토", "일"].map((d) => (
                    <span key={d} className="flex-1 text-center text-[9px] text-white/30" style={{ fontFamily: "JetBrains Mono" }}>{d}</span>
                  ))}
                </div>
              </div>
              <div className="rounded-xl p-4 flex items-center gap-3" style={{ background: "linear-gradient(135deg, rgba(16,185,129,0.15), rgba(13,59,110,0.15))", border: "1px solid rgba(16,185,129,0.2)" }}>
                <div className="w-9 h-9 rounded-lg flex items-center justify-center flex-shrink-0" style={{ backgroundColor: "rgba(16,185,129,0.2)" }}><Zap size={18} style={{ color: "#10B981" }} /></div>
                <div className="flex-1 min-w-0">
                  <div className="text-white text-sm font-semibold">추천 챌린지</div>
                  <div className="text-white/50 text-xs mt-0.5 truncate">저탄수화물 식단 21일 · 혈당 위험 요인 기반</div>
                </div>
                <ChevronRight size={16} className="text-white/40 flex-shrink-0" />
              </div>
            </div>
          </motion.div>
        </div>
      </section>

      {/* HOW IT WORKS */}
      <section id="how" className="py-24 bg-background">
        <div className="max-w-6xl mx-auto px-6">
          <motion.div initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.5 }} className="mb-16">
            <span className="text-xs font-medium text-muted-foreground mb-3 block" style={{ fontFamily: "JetBrains Mono" }}>HOW IT WORKS</span>
            <h2 className="text-4xl font-normal text-foreground leading-tight" style={{ fontFamily: "Instrument Serif, serif" }}>데이터를 쌓을수록<br />예측이 정확해집니다</h2>
          </motion.div>
          <div className="grid md:grid-cols-4 gap-8">
            <StepCard num="01" icon={UserCircle} title="건강 프로필 등록" desc="나이, 성별, 기저질환, 가족력 등 기본 정보를 입력해 AI 분석의 기준을 세웁니다." sub={["프로필 등록 및 수정", "이메일 기반 안전한 계정"]} delay={0} />
            <StepCard num="02" icon={ClipboardList} title="건강 데이터 기록" desc="월별 건강 상태, 연간 검진 결과, 당뇨 환자라면 매일 혈당까지 꾸준히 기록합니다." sub={["월별 건강 상태 기록", "연간 건강검진 결과 관리", "일별 혈당 측정 기록"]} delay={0.08} />
            <StepCard num="03" icon={Brain} title="AI 예측 및 리포트" desc="축적된 데이터를 기반으로 AI가 당뇨병·고혈압 위험도와 위험 요인을 분석하고 리포트를 생성합니다." sub={["당뇨병·고혈압 위험도 예측", "위험 요인 상세 분석", "월별 AI 리포트 생성"]} delay={0.16} />
            <StepCard num="04" icon={Target} title="맞춤 챌린지 수행" desc="예측 결과와 위험 요인을 기반으로 AI가 가장 효과적인 건강 챌린지를 추천하고 이행을 도웁니다." sub={["위험 요인 기반 챌린지 추천", "일별 수행 기록", "목표 달성 트래킹"]} delay={0.24} />
          </div>
        </div>
      </section>

      {/* FEATURES */}
      <section id="features" className="py-24" style={{ backgroundColor: "#F8FAFC" }}>
        <div className="max-w-6xl mx-auto px-6">
          <motion.div initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.5 }} className="mb-12">
            <span className="text-xs font-medium text-muted-foreground mb-3 block" style={{ fontFamily: "JetBrains Mono" }}>FEATURES</span>
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
              <h2 className="text-4xl font-normal text-foreground leading-tight" style={{ fontFamily: "Instrument Serif, serif" }}>건강 관리에 필요한<br />모든 기능이 한 곳에</h2>
              <p className="text-muted-foreground max-w-xs leading-relaxed text-sm">회원가입부터 챌린지 완료까지, 만성질환 예방을 위한 전체 흐름을 하나의 서비스로 제공합니다.</p>
            </div>
          </motion.div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <FeatureCard icon={Lock} title="이메일 회원가입 · 로그인" desc="이메일 기반으로 안전하게 가입하고, 내 건강 데이터를 보호된 환경에서 관리합니다." color="#0D3B6E" delay={0} />
            <FeatureCard icon={UserCircle} title="건강 프로필 관리" desc="나이, 성별, 키·체중, 기저질환, 가족력 등 기본 건강 프로필을 언제든 등록·수정합니다." color="#8B5CF6" delay={0.05} />
            <FeatureCard icon={CalendarDays} title="월별 건강 상태 기록" desc="혈압, 혈당, 체중 등 주요 수치를 매월 기록하고 변화 추이를 한눈에 확인합니다." color="#10B981" delay={0.1} />
            <FeatureCard icon={Microscope} title="연간 건강검진 결과 관리" desc="건강검진 결과를 연도별로 기록·조회·삭제하고, AI 분석의 중요한 기초 데이터로 활용합니다." color="#06B6D4" delay={0.15} />
            <FeatureCard icon={Droplets} title="일별 혈당 측정 기록" desc="당뇨 환자를 위한 전용 기능. 매일 공복·식후 혈당을 기록하고 패턴을 추적합니다." color="#F59E0B" tag="당뇨 전용" delay={0.2} />
            <FeatureCard icon={Brain} title="AI 위험도 예측" desc="축적된 건강 데이터를 머신러닝 모델로 분석해 당뇨병·고혈압 발생 위험도를 예측합니다." color="#EF4444" delay={0.25} />
            <FeatureCard icon={FileText} title="AI 리포트 생성·조회" desc="예측 결과와 위험 요인 분석을 담은 리포트를 자동 생성하고 언제든 다시 확인합니다." color="#0D3B6E" delay={0.3} />
            <FeatureCard icon={Target} title="맞춤 챌린지 추천" desc="위험 요인을 기반으로 AI가 가장 효과적인 건강 챌린지를 추천하고 수행을 지원합니다." color="#10B981" delay={0.35} />
          </div>
        </div>
      </section>

      {/* AI PREDICT */}
      <section id="predict" className="py-24 bg-background">
        <div className="max-w-6xl mx-auto px-6">
          <div className="grid md:grid-cols-2 gap-16 items-center">
            <motion.div initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.5 }}>
              <span className="text-xs font-medium text-muted-foreground mb-3 block" style={{ fontFamily: "JetBrains Mono" }}>AI PREDICTION · REPORT</span>
              <h2 className="text-4xl font-normal text-foreground leading-tight mb-6" style={{ fontFamily: "Instrument Serif, serif" }}>쌓인 데이터가 많을수록<br />더 정밀하게 예측합니다</h2>
              <p className="text-muted-foreground leading-relaxed mb-8">건강 프로필, 월별 기록, 검진 결과, 혈당 데이터를 복합적으로 분석해 단순 수치 비교를 넘어선 맥락 기반 위험도를 산출합니다. 분석 결과는 리포트로 생성되어 언제든 다시 조회할 수 있습니다.</p>
              <div className="flex flex-col gap-4">
                {[
                  { icon: LineChart, title: "복합 데이터 기반 예측", desc: "4가지 데이터 소스(프로필·월별·검진·혈당)를 통합 분석", color: "#0D3B6E" },
                  { icon: Microscope, title: "위험 요인 상세 분석", desc: "어떤 요인이 위험도를 높이는지 기여도와 함께 설명", color: "#F59E0B" },
                  { icon: FileText, title: "리포트 생성 및 이력 조회", desc: "예측 결과를 리포트로 저장하고 시간별 변화를 추적", color: "#10B981" },
                ].map(({ icon: Icon, title, desc, color }) => (
                  <div key={title} className="flex items-start gap-4">
                    <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0 mt-0.5" style={{ backgroundColor: `${color}15` }}><Icon size={18} style={{ color }} /></div>
                    <div>
                      <div className="font-semibold text-foreground mb-0.5">{title}</div>
                      <div className="text-sm text-muted-foreground">{desc}</div>
                    </div>
                  </div>
                ))}
              </div>
            </motion.div>
            <motion.div initial={{ opacity: 0, x: 20 }} whileInView={{ opacity: 1, x: 0 }} viewport={{ once: true }} transition={{ duration: 0.6 }} className="bg-white rounded-2xl border border-border shadow-sm overflow-hidden">
              <div className="border-b border-border px-6 py-4 flex items-center justify-between">
                <span className="font-semibold text-foreground">위험 요인 분석 리포트</span>
                <span className="text-xs text-muted-foreground" style={{ fontFamily: "JetBrains Mono" }}>2025.01.14</span>
              </div>
              <div className="p-6 flex flex-col gap-4">
                <div className="text-xs text-muted-foreground mb-1" style={{ fontFamily: "JetBrains Mono" }}>분석 근거: 건강프로필 + 월별기록 6개월 + 2024 검진결과 + 혈당 30일</div>
                {[
                  { label: "복부 비만", level: 78, color: "#EF4444", impact: "매우 높음", src: "프로필·월별" },
                  { label: "공복혈당 수치", level: 62, color: "#F59E0B", impact: "높음", src: "혈당·검진" },
                  { label: "신체활동 부족", level: 55, color: "#F59E0B", impact: "보통", src: "월별기록" },
                  { label: "가족력 (당뇨)", level: 45, color: "#8B5CF6", impact: "보통", src: "프로필" },
                  { label: "수면 품질", level: 28, color: "#10B981", impact: "낮음", src: "월별기록" },
                ].map(({ label, level, color, impact, src }) => (
                  <div key={label}>
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium text-foreground">{label}</span>
                        <span className="text-[10px] text-muted-foreground" style={{ fontFamily: "JetBrains Mono" }}>{src}</span>
                      </div>
                      <span className="text-xs font-medium" style={{ fontFamily: "JetBrains Mono", color }}>{impact}</span>
                    </div>
                    <div className="h-2 bg-muted rounded-full overflow-hidden">
                      <div className="h-full rounded-full" style={{ width: `${level}%`, backgroundColor: color }} />
                    </div>
                  </div>
                ))}
                <div className="mt-1 p-4 rounded-xl text-sm leading-relaxed" style={{ backgroundColor: "#FFF7ED", color: "#92400E" }}>
                  <strong>AI 종합 의견:</strong> 복부 비만과 공복혈당이 주요 위험 요인입니다. 저탄수화물 식단과 유산소 챌린지를 3개월 수행하면 위험도를 약 30% 낮출 수 있습니다.
                </div>
              </div>
            </motion.div>
          </div>
        </div>
      </section>

      {/* CHALLENGES */}
      <section id="challenges" className="py-24" style={{ backgroundColor: "#F8FAFC" }}>
        <div className="max-w-6xl mx-auto px-6">
          <motion.div initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.5 }} className="mb-12">
            <span className="text-xs font-medium text-muted-foreground mb-3 block" style={{ fontFamily: "JetBrains Mono" }}>PERSONALIZED CHALLENGES</span>
            <div className="flex flex-col md:flex-row md:items-end justify-between gap-4">
              <h2 className="text-4xl font-normal text-foreground leading-tight" style={{ fontFamily: "Instrument Serif, serif" }}>예측 결과가<br />챌린지가 됩니다</h2>
              <p className="text-muted-foreground max-w-xs leading-relaxed text-sm">AI가 분석한 위험 요인을 직접 공략하는 챌린지를 추천합니다. 추천 근거를 함께 확인하세요.</p>
            </div>
          </motion.div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            <ChallengeCard icon={Flame} title="저탄수화물 식단 21일" desc="혈당 스파이크를 줄이는 식단으로 인슐린 저항성을 개선합니다." progress={71} days="D+15" color="#F59E0B" basis="공복혈당 고위험 · 당뇨 위험도 68%" delay={0} />
            <ChallengeCard icon={Activity} title="매일 30분 유산소" desc="빠르게 걷기·조깅으로 심혈관 건강과 혈압을 함께 관리합니다." progress={48} days="D+7" color="#10B981" basis="신체활동 부족 · 복부 비만 고위험" delay={0.08} />
            <ChallengeCard icon={Wind} title="스트레스 명상 10분" desc="코르티솔 수치를 낮춰 혈당 조절과 혈압 안정에 도움을 줍니다." progress={90} days="D+21" color="#8B5CF6" basis="월별 스트레스 지수 상승 추이" delay={0.16} />
            <ChallengeCard icon={Droplets} title="하루 2L 수분 섭취" desc="충분한 수분은 신장 기능을 지원하고 혈액 순환을 원활하게 합니다." progress={33} days="D+3" color="#06B6D4" basis="검진 결과 신장 기능 주의" delay={0.24} />
            <ChallengeCard icon={Shield} title="나트륨 2000mg 이하" desc="저염식으로 수축기 혈압을 평균 5~10mmHg 낮출 수 있습니다." progress={60} days="D+10" color="#EF4444" basis="고혈압 위험 요인 · 월별 혈압 상승" delay={0.32} />
            <ChallengeCard icon={Target} title="수면 7시간 확보" desc="규칙적인 수면은 혈당 조절 호르몬의 균형을 유지시킵니다." progress={82} days="D+18" color="#0D3B6E" basis="월별 수면 시간 부족 기록" delay={0.4} />
          </div>
        </div>
      </section>

      {/* STATS */}
      <section className="py-16" style={{ backgroundColor: "#0B1628" }}>
        <div className="max-w-6xl mx-auto px-6">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            {[
              { value: "94.2%", label: "AI 예측 정확도", icon: Brain },
              { value: "12,400+", label: "누적 사용자", icon: Users },
              { value: "4가지", label: "데이터 소스 통합 분석", icon: BarChart3 },
              { value: "평균 28%", label: "3개월 위험도 감소", icon: TrendingUp },
            ].map(({ value, label, icon: Icon }) => (
              <div key={label} className="flex flex-col gap-2">
                <Icon size={20} style={{ color: "#10B981" }} />
                <div className="text-3xl font-bold text-white" style={{ fontFamily: "JetBrains Mono" }}>{value}</div>
                <div className="text-sm" style={{ color: "rgba(255,255,255,0.5)" }}>{label}</div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* TESTIMONIALS */}
      <section id="reviews" className="py-24 bg-background">
        <div className="max-w-6xl mx-auto px-6">
          <motion.div initial={{ opacity: 0, y: 16 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.5 }} className="mb-12">
            <span className="text-xs font-medium text-muted-foreground mb-3 block" style={{ fontFamily: "JetBrains Mono" }}>USER STORIES</span>
            <h2 className="text-4xl font-normal text-foreground leading-tight" style={{ fontFamily: "Instrument Serif, serif" }}>실제로 변화한<br />사람들의 이야기</h2>
          </motion.div>
          <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-5">
            <Testimonial name="이수연" role="직장인 · 38세" text="월별 기록을 6개월 쌓았더니 AI 리포트가 처음과 완전히 달라졌어요. '경계성 고위험'을 짚어줘서 챌린지를 시작했고, 3개월 만에 공복혈당이 정상으로 돌아왔습니다." avatar="https://images.unsplash.com/photo-1494790108377-be9c29b29330?w=64&h=64&fit=crop&auto=format" delay={0} />
            <Testimonial name="박준호" role="자영업자 · 51세" text="혈당 기록을 매일 하다 보니 어떤 음식이 혈당을 올리는지 패턴이 보이더라고요. AI가 그걸 분석해서 딱 맞는 챌린지를 추천해줬어요. 주치의 선생님도 놀라셨습니다." avatar="https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?w=64&h=64&fit=crop&auto=format" delay={0.1} />
            <Testimonial name="김미영" role="교사 · 44세" text="검진 결과를 연도별로 쌓았더니 AI가 3년 추이를 보고 '고혈압 전단계 진입 가능성'을 알려줬어요. 리포트가 명확해서 가족들한테도 공유했습니다." avatar="https://images.unsplash.com/photo-1534528741775-53994a69daeb?w=64&h=64&fit=crop&auto=format" delay={0.2} />
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="py-24" style={{ backgroundColor: "#F8FAFC" }}>
        <div className="max-w-3xl mx-auto px-6 text-center">
          <motion.div initial={{ opacity: 0, y: 20 }} whileInView={{ opacity: 1, y: 0 }} viewport={{ once: true }} transition={{ duration: 0.6 }} className="flex flex-col items-center gap-6">
            <div className="w-16 h-16 rounded-2xl flex items-center justify-center mb-2" style={{ backgroundColor: "#0B1628" }}><Heart size={28} className="text-white" /></div>
            <h2 className="text-4xl md:text-5xl font-normal text-foreground leading-tight" style={{ fontFamily: "Instrument Serif, serif" }}>오늘 기록한 데이터가<br />내일의 예방이 됩니다</h2>
            <p className="text-muted-foreground leading-relaxed max-w-md">건강 프로필을 등록하고 첫 기록을 남겨보세요. AI가 분석하고, 리포트를 만들고, 챌린지를 추천합니다. 무료로 시작할 수 있습니다.</p>
            <div className="flex flex-col sm:flex-row gap-3 mt-2">
              <button onClick={() => navigate("/signup")} className="flex items-center justify-center gap-2 text-sm font-semibold px-7 py-3.5 rounded-lg transition-all duration-200 hover:opacity-90" style={{ backgroundColor: "#0D3B6E", color: "#fff" }}>
                무료로 시작하기 <ArrowRight size={16} />
              </button>
              <button className="flex items-center justify-center gap-2 text-sm font-medium px-7 py-3.5 rounded-lg border border-border bg-white text-foreground hover:bg-muted transition-colors">
                <BarChart3 size={16} /> 샘플 리포트 보기
              </button>
            </div>
            <div className="flex items-center gap-2 text-xs text-muted-foreground mt-1">
              <CheckCircle size={13} className="text-accent" /> 신용카드 불필요 · 개인정보 보호 · 언제든 탈퇴 가능
            </div>
          </motion.div>
        </div>
      </section>

      {/* FOOTER */}
      <footer style={{ backgroundColor: "#0B1628" }} className="py-12">
        <div className="max-w-6xl mx-auto px-6">
          <div className="flex flex-col md:flex-row justify-between gap-8 mb-10">
            <div className="flex flex-col gap-4 max-w-xs">
              <div className="flex items-center gap-2">
                <div className="w-8 h-8 bg-primary rounded-lg flex items-center justify-center"><Heart size={16} className="text-white" /></div>
                <span className="font-bold text-lg text-white" style={{ fontFamily: "Oxanium, sans-serif", letterSpacing: "0.04em" }}>VitalAI</span>
              </div>
              <p className="text-sm leading-relaxed" style={{ color: "rgba(255,255,255,0.4)" }}>건강 데이터 기반 AI 당뇨병·고혈압 예측 및 맞춤형 건강 챌린지 플랫폼</p>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-3 gap-8 text-sm">
              {[
                { title: "서비스", links: ["건강 프로필", "건강 기록", "AI 예측·리포트", "챌린지"] },
                { title: "회사", links: ["소개", "블로그", "채용", "문의"] },
                { title: "법적 고지", links: ["개인정보처리방침", "이용약관", "의료 면책조항"] },
              ].map(({ title, links }) => (
                <div key={title}>
                  <div className="font-semibold text-white mb-3 text-xs uppercase tracking-wider" style={{ fontFamily: "JetBrains Mono" }}>{title}</div>
                  <div className="flex flex-col gap-2">
                    {links.map((link) => <a key={link} href="#" className="transition-colors hover:text-white" style={{ color: "rgba(255,255,255,0.4)" }}>{link}</a>)}
                  </div>
                </div>
              ))}
            </div>
          </div>
          <div className="pt-6 border-t flex flex-col md:flex-row justify-between items-center gap-3 text-xs" style={{ borderColor: "rgba(255,255,255,0.08)", color: "rgba(255,255,255,0.3)" }}>
            <span>© 2025 VitalAI. All rights reserved.</span>
            <span style={{ fontFamily: "JetBrains Mono" }}>이 서비스는 의료 진단을 대체하지 않습니다.</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
