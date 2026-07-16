import { useState, useEffect } from "react";
import { useNavigate } from "react-router";
import {
  Heart,
  Activity,
  Droplet,
  TrendingUp,
  Calendar,
  Brain,
  Target,
  ChevronRight,
  AlertCircle,
  Clock,
  Loader2,
  BarChart3,
  Scale,
  Gauge,
  User,
  Wind,
} from "lucide-react";
import { getUser } from "../shared/api/auth";
import { getHealthProfile, HealthProfile } from "../shared/api/healthProfileApi";
import {
  getHealthSurveyDetail,
  getHealthSurveys,
  HealthSurveyDetail,
} from "../shared/api/healthSurveyApi";
import { formatDateTime, formatDate } from "../shared/utils/format";

const cn = (...cls: (string | boolean | undefined)[]) => cls.filter(Boolean).join(" ");

/* ── Health Indicator Card ── */
function HealthIndicatorCard({
  icon: Icon,
  label,
  value,
  unit,
  status,
  statusLabel,
  color,
  bgColor,
  onClick,
}: {
  icon: React.ElementType;
  label: string;
  value: string | number;
  unit?: string;
  status?: "good" | "warning" | "danger" | "normal";
  statusLabel?: string;
  color: string;
  bgColor: string;
  onClick?: () => void;
}) {
  const statusColors = {
    good: { bg: "rgba(16,185,129,0.1)", text: "#10B981", border: "rgba(16,185,129,0.2)" },
    normal: { bg: "rgba(59,130,246,0.1)", text: "#3B82F6", border: "rgba(59,130,246,0.2)" },
    warning: { bg: "rgba(245,158,11,0.1)", text: "#F59E0B", border: "rgba(245,158,11,0.2)" },
    danger: { bg: "rgba(239,68,68,0.1)", text: "#EF4444", border: "rgba(239,68,68,0.2)" },
  };

  const statusStyle = status ? statusColors[status] : null;

  return (
    <button
      onClick={onClick}
      disabled={!onClick}
      className={cn(
        "border border-border rounded-xl p-5 text-left transition-all hover:shadow-sm w-full",
        onClick && "cursor-pointer hover:border-primary/30"
      )}
      style={{ backgroundColor: bgColor }}
    >
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-3">
          <div
            className="w-10 h-10 rounded-lg flex items-center justify-center"
            style={{ backgroundColor: "rgba(255, 255, 255, 0.5)" }}
          >
            <Icon size={18} style={{ color }} />
          </div>
          <div className="text-xs font-medium text-muted-foreground">{label}</div>
        </div>
        {status && statusLabel && statusStyle && (
          <div
            className="px-2.5 py-1 rounded-md text-xs font-medium"
            style={{
              backgroundColor: statusStyle.bg,
              color: statusStyle.text,
              border: `1px solid ${statusStyle.border}`,
            }}
          >
            {statusLabel}
          </div>
        )}
      </div>
      <div className="flex items-baseline gap-1.5">
        <span className="text-2xl font-bold" style={{ fontFamily: "JetBrains Mono", color }}>
          {value}
        </span>
        {unit && <span className="text-sm text-muted-foreground">{unit}</span>}
      </div>
    </button>
  );
}

/* ── Action Card ── */
function ActionCard({
  icon: Icon,
  title,
  description,
  color,
  bgColor,
  onClick,
}: {
  icon: React.ElementType;
  title: string;
  description: string;
  color: string;
  bgColor: string;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className="w-full bg-white border border-border rounded-xl p-5 text-left transition-all hover:shadow-sm hover:border-primary/30"
    >
      <div className="flex items-start gap-4">
        <div
          className="w-12 h-12 rounded-xl flex items-center justify-center flex-shrink-0"
          style={{ backgroundColor: bgColor }}
        >
          <Icon size={20} style={{ color }} />
        </div>
        <div className="flex-1 min-w-0">
          <h3 className="font-semibold text-foreground mb-1">{title}</h3>
          <p className="text-sm text-muted-foreground">{description}</p>
        </div>
        <ChevronRight size={18} className="text-muted-foreground flex-shrink-0 mt-1" />
      </div>
    </button>
  );
}

/* ── Dashboard ── */
export default function Dashboard() {
  const navigate = useNavigate();
  const user = getUser();
  const [healthProfile, setHealthProfile] = useState<HealthProfile | null>(null);
  const [latestHealthSurvey, setLatestHealthSurvey] = useState<HealthSurveyDetail | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const loadProfile = async () => {
      try {
        const profile = await getHealthProfile();
        setHealthProfile(profile);
      } catch (err) {
        console.error("Failed to load health profile:", err);
      } finally {
        setLoading(false);
      }
    };
    loadProfile();
  }, []);

  useEffect(() => {
    const loadLatestSurvey = async () => {
      try {
        const surveys = await getHealthSurveys();
        let latestSurvey = surveys && surveys.length > 0 ? surveys[0] : null;
        if (latestSurvey) {
          latestSurvey = await getHealthSurveyDetail(latestSurvey.id);
        }
        setLatestHealthSurvey(latestSurvey as HealthSurveyDetail);
      } catch (err) {
        console.error("Failed to load latest health survey:", err);
      }
    };
    loadLatestSurvey();
  }, []);

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <Loader2 size={32} className="animate-spin" />
          <span className="text-sm">대시보드를 불러오는 중...</span>
        </div>
      </div>
    );
  }

  const displayName = user?.nickname || user?.name || "사용자";
  const hasDiabetes = healthProfile?.has_diabetes ?? false;
  const hasHypertension = healthProfile?.has_hypertension ?? false;

  // Calculate BMI
  const calculateBMI = (height?: number, weight?: number) => {
    if (!height || !weight) return null;
    const heightInMeters = height / 100;
    return (weight / (heightInMeters * heightInMeters)).toFixed(1);
  };

  const getBMIStatus = (
    bmi: number
  ): { status: "good" | "normal" | "warning" | "danger"; label: string } => {
    if (bmi < 18.5) return { status: "warning", label: "저체중" };
    if (bmi < 23) return { status: "good", label: "정상" };
    if (bmi < 25) return { status: "normal", label: "과체중" };
    if (bmi < 30) return { status: "warning", label: "비만" };
    return { status: "danger", label: "고도비만" };
  };

  const getBloodPressureStatus = (
    systolic?: number,
    diastolic?: number
  ): { status: "good" | "normal" | "warning" | "danger"; label: string } | null => {
    if (!systolic || !diastolic) return null;
    if (systolic < 120 && diastolic < 80) return { status: "good", label: "정상" };
    if (systolic < 130 && diastolic < 85) return { status: "normal", label: "주의" };
    if (systolic < 140 || diastolic < 90) return { status: "warning", label: "고혈압 전단계" };
    return { status: "danger", label: "고혈압" };
  };

  const getFastingBloodSugarStatus = (
    fbs?: number
  ): { status: "good" | "normal" | "warning" | "danger"; label: string } | null => {
    if (!fbs) return null;
    if (fbs < 100) return { status: "good", label: "정상" };
    if (fbs < 126) return { status: "warning", label: "공복혈당장애" };
    return { status: "danger", label: "당뇨" };
  };

  const calculateAge = (birthDate?: string) => {
    if (!birthDate) return null;
    const today = new Date();
    const birth = new Date(birthDate);
    let age = today.getFullYear() - birth.getFullYear();
    const monthDiff = today.getMonth() - birth.getMonth();
    if (monthDiff < 0 || (monthDiff === 0 && today.getDate() < birth.getDate())) {
      age--;
    }
    return age;
  };

  const bmi = healthProfile ? calculateBMI(healthProfile.height, healthProfile.weight) : null;
  const bmiStatus = bmi ? getBMIStatus(parseFloat(bmi)) : null;
  const bpStatus = getBloodPressureStatus(
    healthProfile?.systolic_blood_pressure,
    healthProfile?.diastolic_blood_pressure
  );
  const fbsStatus = getFastingBloodSugarStatus(healthProfile?.fasting_blood_sugar);
  const age = calculateAge(healthProfile?.birth_date);

  // Get latest health survey
  const latestSurvey = latestHealthSurvey;
  const surveyBpStatus = latestSurvey
    ? getBloodPressureStatus(latestSurvey.systolic_bp, latestSurvey.diastolic_bp)
    : null;

  const today = new Date();
  const lastSurveyDate = latestSurvey ? formatDate(latestSurvey.created_at) : null;
  const thisSurveyStatus = lastSurveyDate === formatDate(today.toISOString());
  // const thisSurveyStatus = false
  // 작성 필요/미작성 시 사용할 레드 컬러
  const warningColor = "#EF4444"; // Red 500
  const warningBg = "rgba(239, 68, 68, 0.1)";

  return (
    <div className="p-6 lg:p-8 max-w-7xl mx-auto" style={{ fontFamily: "Outfit, sans-serif" }}>
      {/* Header */}
      <div className="mb-8">
        <div
          className="flex items-center gap-2 text-xs text-muted-foreground mb-2"
          style={{ fontFamily: "JetBrains Mono" }}
        >
          <Heart size={12} />
          대시보드
        </div>
        <h1 className="text-2xl font-semibold text-foreground mb-2">
          안녕하세요, <span style={{ color: "#10B981" }}>{displayName}</span>님 👋
        </h1>
        <p className="text-sm text-muted-foreground">
          오늘도 건강한 하루 되세요. 건강 관리 현황을 확인해보세요.
        </p>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <HealthIndicatorCard
          icon={Heart}
          label="건강 프로필"
          value={healthProfile ? "작성 완료" : "작성 필요"}
          color={healthProfile ? "#10B981" : warningColor}
          bgColor={healthProfile ? "rgba(16,185,129,0.1)" : warningBg}
          onClick={() => navigate("/app/health/profile")}
        />
        <HealthIndicatorCard
          icon={Activity}
          label="월별 건강설문"
          value={thisSurveyStatus ? "완료" : "미작성"}
          color={thisSurveyStatus ? "#0D3B6E" : warningColor}
          bgColor={thisSurveyStatus ? "rgba(13,59,110,0.1)" : warningBg}
          onClick={() => navigate("/app/health/monthly")}
        />
        <HealthIndicatorCard
          icon={Brain}
          label="AI 위험도 분석"
          value="분석 가능"
          color="#8B5CF6"
          bgColor="rgba(139,92,246,0.1)"
          onClick={() => navigate("/app/ai/analysis")}
        />
        <HealthIndicatorCard
          icon={Target}
          label="진행 중인 챌린지"
          value="0"
          unit="개"
          color="#F59E0B"
          bgColor="rgba(245,158,11,0.1)"
          onClick={() => navigate("/app/challenge")}
        />
      </div>

      {/* Health Indicators */}
      {healthProfile && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
            <Gauge size={18} style={{ color: "#0D3B6E" }} />
            나의 건강지표
          </h2>

          {bmi || bpStatus || fbsStatus || latestSurvey ? (
            <div className="bg-white border border-border rounded-xl p-6">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
                {/* Left: Health Profile Data */}
                <div>
                  <div className="flex items-center gap-2 mb-4 pb-3 border-b border-border">
                    <User size={16} style={{ color: "#0D3B6E" }} />
                    <h3 className="font-semibold text-foreground">건강 프로필</h3>
                  </div>
                  <div className="space-y-4">
                    {/* Basic Info */}
                    <div className="grid grid-cols-2 gap-4">
                      {age && (
                        <div>
                          <div className="text-xs text-muted-foreground mb-1">나이</div>
                          <div
                            className="font-semibold text-foreground"
                            style={{ fontFamily: "JetBrains Mono" }}
                          >
                            {age}
                            <span className="text-sm text-muted-foreground ml-1">세</span>
                          </div>
                        </div>
                      )}
                      {healthProfile.gender && (
                        <div>
                          <div className="text-xs text-muted-foreground mb-1">성별</div>
                          <div className="font-semibold text-foreground">
                            {healthProfile.gender === "M"
                              ? "남성"
                              : healthProfile.gender === "F"
                                ? "여성"
                                : "기타"}
                          </div>
                        </div>
                      )}
                      {healthProfile.height && (
                        <div>
                          <div className="text-xs text-muted-foreground mb-1">키</div>
                          <div
                            className="font-semibold text-foreground"
                            style={{ fontFamily: "JetBrains Mono" }}
                          >
                            {healthProfile.height}
                            <span className="text-sm text-muted-foreground ml-1">cm</span>
                          </div>
                        </div>
                      )}
                      {healthProfile.weight && (
                        <div>
                          <div className="text-xs text-muted-foreground mb-1">몸무게</div>
                          <div
                            className="font-semibold text-foreground"
                            style={{ fontFamily: "JetBrains Mono" }}
                          >
                            {healthProfile.weight}
                            <span className="text-sm text-muted-foreground ml-1">kg</span>
                          </div>
                        </div>
                      )}
                    </div>

                    {/* Key Indicators */}
                    <div className="pt-2 space-y-3">
                      {bmi && bmiStatus && (
                        <div
                          className="flex items-center justify-between p-3 rounded-lg"
                          style={{ backgroundColor: "rgba(59,130,246,0.05)" }}
                        >
                          <div className="flex items-center gap-2">
                            <Scale size={16} style={{ color: "#3B82F6" }} />
                            <span className="text-sm text-foreground">체질량지수 (BMI)</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span
                              className="font-bold"
                              style={{ fontFamily: "JetBrains Mono", color: "#3B82F6" }}
                            >
                              {bmi}
                            </span>
                            <div
                              className="px-2 py-0.5 rounded text-xs font-medium"
                              style={{
                                backgroundColor:
                                  bmiStatus.status === "good"
                                    ? "rgba(16,185,129,0.1)"
                                    : bmiStatus.status === "normal"
                                      ? "rgba(59,130,246,0.1)"
                                      : bmiStatus.status === "warning"
                                        ? "rgba(245,158,11,0.1)"
                                        : "rgba(239,68,68,0.1)",
                                color:
                                  bmiStatus.status === "good"
                                    ? "#10B981"
                                    : bmiStatus.status === "normal"
                                      ? "#3B82F6"
                                      : bmiStatus.status === "warning"
                                        ? "#F59E0B"
                                        : "#EF4444",
                              }}
                            >
                              {bmiStatus.label}
                            </div>
                          </div>
                        </div>
                      )}

                      {healthProfile.systolic_blood_pressure &&
                        healthProfile.diastolic_blood_pressure &&
                        bpStatus && (
                          <div
                            className="flex items-center justify-between p-3 rounded-lg"
                            style={{ backgroundColor: "rgba(249,115,22,0.05)" }}
                          >
                            <div className="flex items-center gap-2">
                              <Activity size={16} style={{ color: "#F97316" }} />
                              <span className="text-sm text-foreground">혈압</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span
                                className="font-bold"
                                style={{ fontFamily: "JetBrains Mono", color: "#F97316" }}
                              >
                                {healthProfile.systolic_blood_pressure}/
                                {healthProfile.diastolic_blood_pressure}
                                <span className="text-xs text-muted-foreground ml-1">mmHg</span>
                              </span>
                              <div
                                className="px-2 py-0.5 rounded text-xs font-medium"
                                style={{
                                  backgroundColor:
                                    bpStatus.status === "good"
                                      ? "rgba(16,185,129,0.1)"
                                      : bpStatus.status === "normal"
                                        ? "rgba(59,130,246,0.1)"
                                        : bpStatus.status === "warning"
                                          ? "rgba(245,158,11,0.1)"
                                          : "rgba(239,68,68,0.1)",
                                  color:
                                    bpStatus.status === "good"
                                      ? "#10B981"
                                      : bpStatus.status === "normal"
                                        ? "#3B82F6"
                                        : bpStatus.status === "warning"
                                          ? "#F59E0B"
                                          : "#EF4444",
                                }}
                              >
                                {bpStatus.label}
                              </div>
                            </div>
                          </div>
                        )}

                      {healthProfile.fasting_blood_sugar && fbsStatus && (
                        <div
                          className="flex items-center justify-between p-3 rounded-lg"
                          style={{ backgroundColor: "rgba(239,68,68,0.05)" }}
                        >
                          <div className="flex items-center gap-2">
                            <Droplet size={16} style={{ color: "#EF4444" }} />
                            <span className="text-sm text-foreground">공복혈당</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span
                              className="font-bold"
                              style={{ fontFamily: "JetBrains Mono", color: "#EF4444" }}
                            >
                              {healthProfile.fasting_blood_sugar}
                              <span className="text-xs text-muted-foreground ml-1">mg/dL</span>
                            </span>
                            <div
                              className="px-2 py-0.5 rounded text-xs font-medium"
                              style={{
                                backgroundColor:
                                  fbsStatus.status === "good"
                                    ? "rgba(16,185,129,0.1)"
                                    : fbsStatus.status === "normal"
                                      ? "rgba(59,130,246,0.1)"
                                      : fbsStatus.status === "warning"
                                        ? "rgba(245,158,11,0.1)"
                                        : "rgba(239,68,68,0.1)",
                                color:
                                  fbsStatus.status === "good"
                                    ? "#10B981"
                                    : fbsStatus.status === "normal"
                                      ? "#3B82F6"
                                      : fbsStatus.status === "warning"
                                        ? "#F59E0B"
                                        : "#EF4444",
                              }}
                            >
                              {fbsStatus.label}
                            </div>
                          </div>
                        </div>
                      )}
                    </div>

                    <button
                      onClick={() => navigate("/app/health/profile")}
                      className="flex items-center gap-1.5 text-xs font-medium transition-opacity hover:opacity-70 mt-3"
                      style={{ color: "#0D3B6E" }}
                    >
                      프로필 상세보기 <ChevronRight size={12} />
                    </button>
                  </div>
                </div>

                {/* Right: Latest Health Survey */}
                <div>
                  <div className="flex items-center gap-2 mb-4 pb-3 border-b border-border">
                    <Calendar size={16} style={{ color: "#10B981" }} />
                    <h3 className="font-semibold text-foreground">최근 월별 건강설문</h3>
                  </div>

                  {latestSurvey ? (
                    <div className="space-y-4">
                      {/* Survey Date */}
                      <div
                        className="flex items-center gap-2 text-xs text-muted-foreground"
                        style={{ fontFamily: "JetBrains Mono" }}
                      >
                        <Clock size={12} />
                        건강설문 제출일시: {formatDateTime(latestSurvey.created_at)}
                      </div>

                      {/* Habits */}
                      <div className="space-y-3">
                        <div
                          className="flex items-center justify-between p-3 rounded-lg"
                          style={{ backgroundColor: "rgba(139,92,246,0.05)" }}
                        >
                          <div className="flex items-center gap-2">
                            <Wind size={16} style={{ color: "#8B5CF6" }} />
                            <span className="text-sm text-foreground">흡연</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-sm" style={{ color: "#8B5CF6" }}>
                              {latestSurvey.smoking_status}
                            </span>
                            {latestSurvey.smoking_fr_per_day && (
                              <span
                                className="text-xs text-muted-foreground"
                                style={{ fontFamily: "JetBrains Mono" }}
                              >
                                ({latestSurvey.smoking_fr_per_day}개비/일)
                              </span>
                            )}
                          </div>
                        </div>

                        <div
                          className="flex items-center justify-between p-3 rounded-lg"
                          style={{ backgroundColor: "rgba(245,158,11,0.05)" }}
                        >
                          <div className="flex items-center gap-2">
                            <Droplet size={16} style={{ color: "#F59E0B" }} />
                            <span className="text-sm text-foreground">음주</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-sm" style={{ color: "#F59E0B" }}>
                              {latestSurvey.drinking_status}
                            </span>
                            {latestSurvey.drinking_fr_per_week && (
                              <span
                                className="text-xs text-muted-foreground"
                                style={{ fontFamily: "JetBrains Mono" }}
                              >
                                ({latestSurvey.drinking_fr_per_week}회/주)
                              </span>
                            )}
                          </div>
                        </div>

                        {surveyBpStatus && (
                          <div
                            className="flex items-center justify-between p-3 rounded-lg"
                            style={{ backgroundColor: "rgba(249,115,22,0.05)" }}
                          >
                            <div className="flex items-center gap-2">
                              <Activity size={16} style={{ color: "#F97316" }} />
                              <span className="text-sm text-foreground">측정 혈압</span>
                            </div>
                            <div className="flex items-center gap-2">
                              <span
                                className="font-bold"
                                style={{ fontFamily: "JetBrains Mono", color: "#F97316" }}
                              >
                                {latestSurvey.systolic_bp}/{latestSurvey.diastolic_bp}
                                <span className="text-xs text-muted-foreground ml-1">mmHg</span>
                              </span>
                              <div
                                className="px-2 py-0.5 rounded text-xs font-medium"
                                style={{
                                  backgroundColor:
                                    surveyBpStatus.status === "good"
                                      ? "rgba(16,185,129,0.1)"
                                      : surveyBpStatus.status === "normal"
                                        ? "rgba(59,130,246,0.1)"
                                        : surveyBpStatus.status === "warning"
                                          ? "rgba(245,158,11,0.1)"
                                          : "rgba(239,68,68,0.1)",
                                  color:
                                    surveyBpStatus.status === "good"
                                      ? "#10B981"
                                      : surveyBpStatus.status === "normal"
                                        ? "#3B82F6"
                                        : surveyBpStatus.status === "warning"
                                          ? "#F59E0B"
                                          : "#EF4444",
                                }}
                              >
                                {surveyBpStatus.label}
                              </div>
                            </div>
                          </div>
                        )}

                        {latestSurvey.pulse && (
                          <div
                            className="flex items-center justify-between p-3 rounded-lg"
                            style={{ backgroundColor: "rgba(16,185,129,0.05)" }}
                          >
                            <div className="flex items-center gap-2">
                              <Heart size={16} style={{ color: "#10B981" }} />
                              <span className="text-sm text-foreground">맥박</span>
                            </div>
                            <span
                              className="font-bold"
                              style={{ fontFamily: "JetBrains Mono", color: "#10B981" }}
                            >
                              {latestSurvey.pulse}
                              <span className="text-xs text-muted-foreground ml-1">bpm</span>
                            </span>
                          </div>
                        )}
                      </div>

                      <button
                        onClick={() => navigate("/app/health/monthly")}
                        className="flex items-center gap-1.5 text-xs font-medium transition-opacity hover:opacity-70 mt-3"
                        style={{ color: "#10B981" }}
                      >
                        설문 상세보기 <ChevronRight size={12} />
                      </button>
                    </div>
                  ) : (
                    <div className="flex flex-col items-center justify-center py-8 text-center">
                      <div
                        className="w-12 h-12 rounded-full flex items-center justify-center mb-3"
                        style={{ backgroundColor: "rgba(16,185,129,0.1)" }}
                      >
                        <Calendar size={20} style={{ color: "#10B981" }} />
                      </div>
                      <p className="text-sm text-muted-foreground mb-3">
                        아직 작성된 월별 건강설문이 없습니다.
                      </p>
                      <button
                        onClick={() => navigate("/app/health/monthly")}
                        className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white transition-opacity hover:opacity-90"
                        style={{ backgroundColor: "#10B981" }}
                      >
                        설문 작성하기 <ChevronRight size={14} />
                      </button>
                    </div>
                  )}
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white border border-border rounded-xl p-6 text-center">
              <div
                className="w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-3"
                style={{ backgroundColor: "rgba(13,59,110,0.05)" }}
              >
                <Gauge size={20} style={{ color: "#0D3B6E" }} />
              </div>
              <p className="text-sm text-muted-foreground mb-3">
                건강지표를 확인하려면 건강 프로필을 완성해주세요.
              </p>
              <button
                onClick={() => navigate("/app/health/profile")}
                className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium text-white transition-opacity hover:opacity-90"
                style={{ backgroundColor: "#0D3B6E" }}
              >
                건강 프로필 완성하기 <ChevronRight size={14} />
              </button>
            </div>
          )}
        </div>
      )}

      {/* Conditional Cards for Diabetes/Hypertension */}
      {(hasDiabetes || hasHypertension) && (
        <div className="mb-8">
          <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
            <AlertCircle size={18} style={{ color: "#0D3B6E" }} />
            맞춤 관리
          </h2>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {hasDiabetes && (
              <ActionCard
                icon={Target}
                title="당뇨병 관리"
                description="혈당 측정 기록을 통해 당뇨병을 체계적으로 관리하세요."
                color="#EF4444"
                bgColor="rgba(245,158,11,0.1)"
                onClick={() => navigate("/app/health/blood-sugar")}
              />
            )}
            <ActionCard
              icon={Target}
              title="건강 챌린지 시작"
              description="맞춤형 건강 챌린지로 목표를 달성하세요"
              color="#F59E0B"
              bgColor="rgba(245,158,11,0.1)"
              onClick={() => navigate("/app/challenge")}
            />
          </div>
        </div>
      )}

      {/* Quick Actions */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
          <TrendingUp size={18} style={{ color: "#0D3B6E" }} />
          빠른 실행
        </h2>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <ActionCard
            icon={Brain}
            title="AI 위험도 분석"
            description="당뇨병과 고혈압 위험도를 AI로 예측해보세요"
            color="#8B5CF6"
            bgColor="rgba(139,92,246,0.1)"
            onClick={() => navigate("/app/ai/analysis")}
          />
          <ActionCard
            icon={BarChart3}
            title="AI 건강리포트 확인"
            description="종합적인 건강 분석 리포트를 확인하세요"
            color="#10B981"
            bgColor="rgba(16,185,129,0.1)"
            onClick={() => navigate("/app/ai/report")}
          />
        </div>
      </div>

      {/* Recent Activity Placeholder */}
      <div className="mb-8">
        <h2 className="text-lg font-semibold text-foreground mb-4 flex items-center gap-2">
          <Clock size={18} style={{ color: "#0D3B6E" }} />
          최근 활동
        </h2>
        <div className="bg-white border border-border rounded-xl p-8 text-center">
          <div
            className="w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-3"
            style={{ backgroundColor: "rgba(13,59,110,0.05)" }}
          >
            <Activity size={20} style={{ color: "#0D3B6E" }} />
          </div>
          <p className="text-sm text-muted-foreground">
            아직 기록된 활동이 없습니다. <br />
            건강 정보를 입력하고 AI 분석을 시작해보세요.
          </p>
        </div>
      </div>
    </div>
  );
}
