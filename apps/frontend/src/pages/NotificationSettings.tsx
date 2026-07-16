import { useState } from "react";
import { Bell, Heart, Calendar, Brain, Target, Check } from "lucide-react";

const cn = (...cls: (string | boolean | undefined)[]) => cls.filter(Boolean).join(" ");

interface NotificationSetting {
  id: string;
  label: string;
  description: string;
  icon: React.ElementType;
  enabled: boolean;
  color: string;
}

export default function NotificationSettings() {
  const [settings, setSettings] = useState<NotificationSetting[]>([
    {
      id: "health-survey",
      label: "월별 건강설문 알림",
      description: "매월 건강설문 작성 시기가 되면 알려드립니다",
      icon: Calendar,
      enabled: true,
      color: "#0D3B6E",
    },
    {
      id: "ai-analysis",
      label: "AI 분석 완료 알림",
      description: "AI 위험도 분석이 완료되면 알려드립니다",
      icon: Brain,
      enabled: true,
      color: "#8B5CF6",
    },
    {
      id: "challenge",
      label: "챌린지 리마인더",
      description: "진행 중인 챌린지의 목표 달성을 위한 리마인더를 보냅니다",
      icon: Target,
      enabled: true,
      color: "#F59E0B",
    },
    {
      id: "blood-sugar",
      label: "혈당 측정 알림",
      description: "정기적인 혈당 측정 시간을 알려드립니다",
      icon: Heart,
      enabled: false,
      color: "#EF4444",
    },
    {
      id: "health-tips",
      label: "건강 팁 알림",
      description: "맞춤형 건강 관리 팁을 주기적으로 제공합니다",
      icon: Heart,
      enabled: true,
      color: "#10B981",
    },
  ]);

  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const toggleSetting = (id: string) => {
    setSettings((prev) =>
      prev.map((s) => (s.id === id ? { ...s, enabled: !s.enabled } : s))
    );
  };

  const handleSave = async () => {
    setIsSaving(true);
    setSaveSuccess(false);

    // Simulate API call
    await new Promise((resolve) => setTimeout(resolve, 800));

    setIsSaving(false);
    setSaveSuccess(true);

    // Hide success message after 3 seconds
    setTimeout(() => setSaveSuccess(false), 3000);
  };

  return (
    <div className="p-6 lg:p-8 max-w-4xl mx-auto" style={{ fontFamily: "Outfit, sans-serif" }}>
      {/* Header */}
      <div className="mb-8">
        <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2" style={{ fontFamily: "JetBrains Mono" }}>
          <Bell size={12} />
          설정
        </div>
        <h1 className="text-2xl font-semibold text-foreground mb-2">알림 설정</h1>
        <p className="text-sm text-muted-foreground">
          받고 싶은 알림을 선택하여 건강 관리를 더욱 효과적으로 하세요.
        </p>
      </div>

      {/* Success Message */}
      {saveSuccess && (
        <div className="mb-6 p-4 rounded-lg border flex items-center gap-3" style={{ backgroundColor: "rgba(16,185,129,0.1)", borderColor: "rgba(16,185,129,0.3)" }}>
          <div className="w-5 h-5 rounded-full flex items-center justify-center flex-shrink-0" style={{ backgroundColor: "#10B981" }}>
            <Check size={12} className="text-white" />
          </div>
          <span className="text-sm font-medium" style={{ color: "#10B981" }}>
            알림 설정이 저장되었습니다.
          </span>
        </div>
      )}

      {/* Notification Settings */}
      <div className="bg-white border border-border rounded-xl overflow-hidden mb-6">
        {settings.map((setting, index) => {
          const Icon = setting.icon;
          return (
            <div
              key={setting.id}
              className={cn(
                "p-5 flex items-start gap-4 transition-colors hover:bg-muted/30",
                index !== settings.length - 1 && "border-b border-border"
              )}
            >
              <div className="w-10 h-10 rounded-lg flex items-center justify-center flex-shrink-0" style={{ backgroundColor: `${setting.color}15` }}>
                <Icon size={18} style={{ color: setting.color }} />
              </div>
              <div className="flex-1 min-w-0">
                <h3 className="font-semibold text-foreground mb-1">{setting.label}</h3>
                <p className="text-sm text-muted-foreground">{setting.description}</p>
              </div>
              <button
                onClick={() => toggleSetting(setting.id)}
                className={cn(
                  "relative flex-shrink-0 w-12 h-6 rounded-full transition-colors",
                  setting.enabled ? "bg-primary" : "bg-muted"
                )}
                style={setting.enabled ? { backgroundColor: setting.color } : undefined}
              >
                <span
                  className={cn(
                    "absolute top-0.5 left-0.5 w-5 h-5 bg-white rounded-full transition-transform shadow-sm",
                    setting.enabled && "translate-x-6"
                  )}
                />
              </button>
            </div>
          );
        })}
      </div>

      {/* Save Button */}
      <div className="flex justify-end gap-3">
        <button
          onClick={handleSave}
          disabled={isSaving}
          className="px-6 py-2.5 rounded-lg text-sm font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-50 flex items-center gap-2"
          style={{ backgroundColor: "#0D3B6E" }}
        >
          {isSaving ? (
            <>
              <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              저장 중...
            </>
          ) : (
            "설정 저장"
          )}
        </button>
      </div>

      {/* Additional Info */}
      <div className="mt-8 p-4 rounded-lg border border-border bg-muted/30">
        <h3 className="font-semibold text-foreground mb-2 text-sm flex items-center gap-2">
          <Bell size={14} style={{ color: "#0D3B6E" }} />
          알림에 대하여
        </h3>
        <ul className="text-xs text-muted-foreground space-y-1.5">
          <li>• 알림은 앱 내 알림센터와 브라우저 푸시 알림으로 전송됩니다.</li>
          <li>• 브라우저 알림 권한을 허용해야 푸시 알림을 받을 수 있습니다.</li>
          <li>• 알림 설정은 언제든지 변경할 수 있습니다.</li>
        </ul>
      </div>
    </div>
  );
}
