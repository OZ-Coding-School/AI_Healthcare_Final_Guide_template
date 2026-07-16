import { useState } from "react";
import { Target, Flame, Activity, Wind, Droplets, Shield, CheckCircle, Plus, Calendar } from "lucide-react";

const ACTIVE = [
  { icon: Flame, title: "저탄수화물 식단 21일", desc: "혈당 스파이크를 줄이는 식단으로 인슐린 저항성 개선", progress: 71, day: 15, total: 21, color: "#F59E0B", basis: "공복혈당 고위험 · 당뇨 위험도 68%" },
  { icon: Activity, title: "매일 30분 유산소", desc: "빠르게 걷기·조깅으로 심혈관 건강과 혈압 관리", progress: 48, day: 7, total: 21, color: "#10B981", basis: "신체활동 부족 · 복부 비만 고위험" },
  { icon: Wind, title: "스트레스 명상 10분", desc: "코르티솔 수치를 낮춰 혈당 조절과 혈압 안정", progress: 90, day: 21, total: 21, color: "#8B5CF6", basis: "월별 스트레스 지수 상승" },
];

const RECOMMENDED = [
  { icon: Droplets, title: "하루 2L 수분 섭취", desc: "신장 기능 지원 및 혈액 순환 개선", color: "#06B6D4", basis: "검진 결과 신장 기능 주의" },
  { icon: Shield, title: "나트륨 2000mg 이하", desc: "저염식으로 수축기 혈압 5~10mmHg 감소", color: "#EF4444", basis: "고혈압 위험 요인" },
];

function ActiveCard({ icon: Icon, title, desc, progress, day, total, color, basis }: typeof ACTIVE[0]) {
  const [todayDone, setTodayDone] = useState(false);

  return (
    <div className="bg-white border border-border rounded-xl p-5 flex flex-col gap-4">
      <div className="flex items-start justify-between">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${color}15` }}>
            <Icon size={20} style={{ color }} />
          </div>
          <div>
            <div className="font-semibold text-foreground text-sm">{title}</div>
            <div className="text-xs text-muted-foreground mt-0.5">{desc}</div>
          </div>
        </div>
        <span className="text-xs font-semibold px-2.5 py-1 rounded-full flex-shrink-0" style={{ fontFamily: "JetBrains Mono", backgroundColor: `${color}12`, color }}>
          D+{day}
        </span>
      </div>

      <div className="text-[11px] px-2.5 py-1.5 rounded-lg" style={{ backgroundColor: "rgba(13,59,110,0.05)", color: "#0D3B6E", fontFamily: "JetBrains Mono" }}>
        추천 근거: {basis}
      </div>

      <div>
        <div className="flex justify-between text-xs mb-1.5">
          <span className="text-muted-foreground" style={{ fontFamily: "JetBrains Mono" }}>진행률 ({day}/{total}일)</span>
          <span className="font-semibold" style={{ fontFamily: "JetBrains Mono", color }}>{progress}%</span>
        </div>
        <div className="h-2 bg-muted rounded-full overflow-hidden">
          <div className="h-full rounded-full" style={{ width: `${progress}%`, backgroundColor: color }} />
        </div>
      </div>

      <button
        onClick={() => setTodayDone(!todayDone)}
        className="flex items-center justify-center gap-2 w-full py-2.5 rounded-lg text-sm font-medium border transition-all duration-200"
        style={todayDone
          ? { backgroundColor: "rgba(16,185,129,0.1)", borderColor: "rgba(16,185,129,0.3)", color: "#10B981" }
          : { backgroundColor: "transparent", borderColor: "rgba(13,59,110,0.2)", color: "#0D3B6E" }
        }
      >
        <CheckCircle size={15} />
        {todayDone ? "오늘 완료! 🎉" : "오늘 수행 완료"}
      </button>
    </div>
  );
}

function RecommendCard({ icon: Icon, title, desc, color, basis }: typeof RECOMMENDED[0]) {
  return (
    <div className="bg-white border border-border rounded-xl p-5 flex flex-col gap-3">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-lg flex items-center justify-center" style={{ backgroundColor: `${color}15` }}>
          <Icon size={20} style={{ color }} />
        </div>
        <div>
          <div className="font-semibold text-foreground text-sm">{title}</div>
          <div className="text-xs text-muted-foreground">{desc}</div>
        </div>
      </div>
      <div className="text-[11px] px-2.5 py-1.5 rounded-lg" style={{ backgroundColor: "rgba(13,59,110,0.05)", color: "#0D3B6E", fontFamily: "JetBrains Mono" }}>
        추천 근거: {basis}
      </div>
      <button className="flex items-center justify-center gap-2 w-full py-2 rounded-lg text-sm font-medium text-white transition-opacity hover:opacity-90" style={{ backgroundColor: color }}>
        <Plus size={14} /> 챌린지 시작하기
      </button>
    </div>
  );
}

export default function Challenge() {
  return (
    <div className="p-6 lg:p-8 max-w-4xl">
      <div className="mb-8">
        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2" style={{ fontFamily: "JetBrains Mono" }}>건강 챌린지</div>
        <h1 className="text-2xl font-semibold text-foreground mb-1">건강 챌린지</h1>
        <p className="text-sm text-muted-foreground">AI가 분석한 위험 요인을 기반으로 맞춤 챌린지를 추천합니다.</p>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 mb-8">
        {[
          { label: "진행 중인 챌린지", value: "3", color: "#0D3B6E" },
          { label: "이번 주 완료일", value: "5일", color: "#10B981" },
          { label: "누적 완료 챌린지", value: "12개", color: "#8B5CF6" },
        ].map(({ label, value, color }) => (
          <div key={label} className="bg-white border border-border rounded-xl p-4 text-center">
            <div className="text-2xl font-bold" style={{ fontFamily: "JetBrains Mono", color }}>{value}</div>
            <div className="text-xs text-muted-foreground mt-1">{label}</div>
          </div>
        ))}
      </div>

      {/* Active challenges */}
      <div className="mb-8">
        <h2 className="text-base font-semibold text-foreground mb-4 flex items-center gap-2">
          <Target size={16} className="text-primary" /> 진행 중인 챌린지
        </h2>
        <div className="grid sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {ACTIVE.map((c) => <ActiveCard key={c.title} {...c} />)}
        </div>
      </div>

      {/* Recommended */}
      <div>
        <h2 className="text-base font-semibold text-foreground mb-1 flex items-center gap-2">
          <Calendar size={16} style={{ color: "#10B981" }} /> AI 추천 챌린지
        </h2>
        <p className="text-xs text-muted-foreground mb-4">최근 AI 분석 결과를 기반으로 추천한 챌린지입니다.</p>
        <div className="grid sm:grid-cols-2 gap-4">
          {RECOMMENDED.map((c) => <RecommendCard key={c.title} {...c} />)}
        </div>
      </div>
    </div>
  );
}
