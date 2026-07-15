from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "aerich" (
    "id" SERIAL NOT NULL PRIMARY KEY,
    "version" VARCHAR(255) NOT NULL,
    "app" VARCHAR(100) NOT NULL,
    "content" JSONB NOT NULL
);
CREATE TABLE IF NOT EXISTS "users" (
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "id" UUID NOT NULL PRIMARY KEY,
    "email" VARCHAR(40) NOT NULL UNIQUE,
    "hashed_password" VARCHAR(255) NOT NULL,
    "nickname" VARCHAR(10) NOT NULL,
    "name" VARCHAR(20) NOT NULL,
    "phone_number" VARCHAR(11) NOT NULL UNIQUE,
    "is_active" BOOL NOT NULL DEFAULT True,
    "is_admin" BOOL NOT NULL DEFAULT False,
    "last_login" TIMESTAMPTZ
);
COMMENT ON COLUMN "users"."phone_number" IS 'Available Format: 01011112222';
CREATE TABLE IF NOT EXISTS "user_withdrawals" (
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "id" UUID NOT NULL PRIMARY KEY,
    "reason" VARCHAR(22) NOT NULL,
    "reason_detail" TEXT,
    "feedback" TEXT,
    "user_id" UUID UNIQUE REFERENCES "users" ("id") ON DELETE SET NULL
);
COMMENT ON COLUMN "user_withdrawals"."reason" IS 'NOT_USE: NOT_USE\nINCONVENIENT: INCONVENIENT\nLACK_OF_FEATURES: LACK_OF_FEATURES\nBUG_OR_ERROR: BUG_OR_ERROR\nFOUND_ALTERNATIVE: FOUND_ALTERNATIVE\nGOAL_ACHIEVED: GOAL_ACHIEVED\nPRIVACY_CONCERN: PRIVACY_CONCERN\nTOO_MANY_NOTIFICATIONS: TOO_MANY_NOTIFICATIONS\nOTHER: OTHER';
CREATE TABLE IF NOT EXISTS "blood_sugar_measurements" (
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "id" UUID NOT NULL PRIMARY KEY,
    "measure_type" VARCHAR(16) NOT NULL,
    "blood_glucose" SMALLINT NOT NULL,
    "minutes_since_meal" SMALLINT,
    "has_exercised" BOOL NOT NULL,
    "exercise_type" VARCHAR(14) NOT NULL DEFAULT 'NOT_APPLICABLE',
    "exercise_minutes" SMALLINT,
    "minutes_since_exercise" SMALLINT,
    "has_medicated" BOOL NOT NULL,
    "medicine_name" VARCHAR(100),
    "minutes_since_medication" SMALLINT,
    "memo" TEXT,
    "measured_at" TIMESTAMPTZ NOT NULL,
    "user_id" UUID NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "blood_sugar_measurements"."measure_type" IS '혈당 수치 테스트 유형';
COMMENT ON COLUMN "blood_sugar_measurements"."blood_glucose" IS '혈당 수치(mg/dL)';
COMMENT ON COLUMN "blood_sugar_measurements"."minutes_since_meal" IS '식후 경과 시간(분)';
COMMENT ON COLUMN "blood_sugar_measurements"."has_exercised" IS '운동 여부';
COMMENT ON COLUMN "blood_sugar_measurements"."exercise_type" IS '운동 유형';
COMMENT ON COLUMN "blood_sugar_measurements"."exercise_minutes" IS '운동 시간(분)';
COMMENT ON COLUMN "blood_sugar_measurements"."minutes_since_exercise" IS '운동 후 경과 시간(분)';
COMMENT ON COLUMN "blood_sugar_measurements"."has_medicated" IS '복약 여부';
COMMENT ON COLUMN "blood_sugar_measurements"."medicine_name" IS '복용한 약물명';
COMMENT ON COLUMN "blood_sugar_measurements"."minutes_since_medication" IS '복약 후 경과 시간(분)';
COMMENT ON COLUMN "blood_sugar_measurements"."memo" IS '참고사항(ex. 어떤걸 먹었고, 어떤 운동을 했는지 등)';
COMMENT ON COLUMN "blood_sugar_measurements"."measured_at" IS '측정시간';
CREATE TABLE IF NOT EXISTS "health_profiles" (
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "id" UUID NOT NULL PRIMARY KEY,
    "gender" VARCHAR(1) NOT NULL,
    "birth_date" DATE NOT NULL,
    "height" DECIMAL(4,1) NOT NULL,
    "weight" DECIMAL(4,1) NOT NULL,
    "has_diabetes" BOOL NOT NULL,
    "has_hypertension" BOOL NOT NULL,
    "user_id" UUID NOT NULL UNIQUE REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "health_profiles"."gender" IS 'M: MALE\nF: FEMALE';
CREATE TABLE IF NOT EXISTS "monthly_health_surveys" (
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "id" UUID NOT NULL PRIMARY KEY,
    "smoking_status" VARCHAR(7) NOT NULL,
    "smoking_fr_per_day" SMALLINT,
    "drinking_status" VARCHAR(7) NOT NULL,
    "drinking_fr_per_week" SMALLINT,
    "drinking_amount_per_session" SMALLINT,
    "systolic_bp" SMALLINT NOT NULL,
    "diastolic_bp" SMALLINT NOT NULL,
    "pulse" SMALLINT,
    "user_id" UUID NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "monthly_health_surveys"."smoking_status" IS 'NEVER: NEVER\nFORMER: FORMER\nCURRENT: CURRENT';
COMMENT ON COLUMN "monthly_health_surveys"."smoking_fr_per_day" IS '일당 흡연 빈도';
COMMENT ON COLUMN "monthly_health_surveys"."drinking_status" IS '음주상태';
COMMENT ON COLUMN "monthly_health_surveys"."drinking_fr_per_week" IS '주당 음주 빈도';
COMMENT ON COLUMN "monthly_health_surveys"."drinking_amount_per_session" IS '회당 음주량(잔)';
COMMENT ON COLUMN "monthly_health_surveys"."systolic_bp" IS '수축기 혈압(최고 혈압, mmHg)';
COMMENT ON COLUMN "monthly_health_surveys"."diastolic_bp" IS '이완기 혈압(최저 혈압, mmHg)';
COMMENT ON COLUMN "monthly_health_surveys"."pulse" IS '맥박수(분당 횟수)';
CREATE TABLE IF NOT EXISTS "disease_predictions" (
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "id" UUID NOT NULL PRIMARY KEY,
    "using_model_name" VARCHAR(30) NOT NULL,
    "threshold" DECIMAL(3,2) NOT NULL,
    "feature" JSONB NOT NULL,
    "user_id" UUID NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "disease_predictions"."using_model_name" IS '질병 위험도 예측에 사용한 모델 이름';
COMMENT ON COLUMN "disease_predictions"."threshold" IS '질병 위험도 예측에 사용한 모델의 임계값(0~1)';
COMMENT ON COLUMN "disease_predictions"."feature" IS '질병 위험도 예측에 사용한 변수 파라미터';
CREATE TABLE IF NOT EXISTS "disease_prediction_reports" (
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "id" UUID NOT NULL PRIMARY KEY,
    "using_model_name" VARCHAR(30) NOT NULL,
    "content" TEXT NOT NULL,
    "prediction_id" UUID NOT NULL UNIQUE REFERENCES "disease_predictions" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "disease_prediction_reports"."using_model_name" IS '질병 위험도 예측에 사용한 모델 이름';
COMMENT ON COLUMN "disease_prediction_reports"."content" IS '질병 위험도 예측 결과 요약';
CREATE TABLE IF NOT EXISTS "disease_prediction_results" (
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "id" UUID NOT NULL PRIMARY KEY,
    "confidence_score" DECIMAL(5,2) NOT NULL,
    "risk_score" DECIMAL(5,2) NOT NULL,
    "risk_level" VARCHAR(8) NOT NULL,
    "summary" TEXT,
    "base_value" DECIMAL(5,2) NOT NULL,
    "shap_results" JSONB NOT NULL,
    "prediction_id" UUID NOT NULL UNIQUE REFERENCES "disease_predictions" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "disease_prediction_results"."confidence_score" IS '질병 위험도 예측 신뢰도 점수';
COMMENT ON COLUMN "disease_prediction_results"."risk_score" IS '질병 위험도 점수';
COMMENT ON COLUMN "disease_prediction_results"."risk_level" IS '질병 위험도 레벨';
COMMENT ON COLUMN "disease_prediction_results"."summary" IS '질병 위험도 예측 결과 요약';
COMMENT ON COLUMN "disease_prediction_results"."base_value" IS '질병 위험도 예측에 사용한 모델의 기반값';
COMMENT ON COLUMN "disease_prediction_results"."shap_results" IS '예측에 활용된 변수들의 가중치, 기여도 SHAP 분석 결과';
CREATE TABLE IF NOT EXISTS "challenge_reports" (
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "id" UUID NOT NULL PRIMARY KEY,
    "using_model_name" VARCHAR(100) NOT NULL,
    "content" TEXT NOT NULL,
    "user_id" UUID NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "challenge_reports"."using_model_name" IS '리포트 생성시 사용한 LLM 모델 이름';
COMMENT ON COLUMN "challenge_reports"."content" IS '챌린지 리포트 내용';
CREATE TABLE IF NOT EXISTS "personal_challenges" (
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "title" VARCHAR(30) NOT NULL,
    "description" TEXT NOT NULL,
    "challenge_type" VARCHAR(11) NOT NULL,
    "expected_effect" TEXT NOT NULL,
    "status" VARCHAR(11) NOT NULL DEFAULT 'PENDING',
    "expired_at" TIMESTAMPTZ NOT NULL,
    "joined_at" TIMESTAMPTZ,
    "completed_at" TIMESTAMPTZ,
    "user_id" UUID NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "personal_challenges"."title" IS '개인 챌린지 제목';
COMMENT ON COLUMN "personal_challenges"."description" IS '개인 챌린지 설명';
COMMENT ON COLUMN "personal_challenges"."challenge_type" IS '챌린지 유형(일간, 주간, 월간, 횟수 기반)';
COMMENT ON COLUMN "personal_challenges"."expected_effect" IS '챌린지 수행 후 기대 효과';
COMMENT ON COLUMN "personal_challenges"."status" IS '챌린지 상태(진행중, 완료)';
COMMENT ON COLUMN "personal_challenges"."expired_at" IS '챌린지 수락 만료 시간';
COMMENT ON COLUMN "personal_challenges"."joined_at" IS '챌린지 참여(수락) 시간';
COMMENT ON COLUMN "personal_challenges"."completed_at" IS '챌린지 완료 시간';
CREATE TABLE IF NOT EXISTS "personal_challenge_histories" (
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "id" BIGSERIAL NOT NULL PRIMARY KEY,
    "current_round" SMALLINT NOT NULL,
    "is_success" BOOL NOT NULL,
    "memo" TEXT,
    "challenge_id" BIGINT NOT NULL REFERENCES "personal_challenges" ("id") ON DELETE CASCADE,
    CONSTRAINT "uid_personal_ch_challen_32df1c" UNIQUE ("challenge_id", "current_round")
);
COMMENT ON COLUMN "personal_challenge_histories"."current_round" IS '현재 진행 회차';
COMMENT ON COLUMN "personal_challenge_histories"."is_success" IS '회차 챌린지 성공 여부';
COMMENT ON COLUMN "personal_challenge_histories"."memo" IS '챌린지 수행 관련 메모(어떤 것을 했는지, 계획, 다짐, 느낀점 등)';
CREATE TABLE IF NOT EXISTS "challenge_proof_files" (
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "id" UUID NOT NULL PRIMARY KEY,
    "file_name" VARCHAR(100) NOT NULL,
    "file_ext" VARCHAR(10) NOT NULL,
    "file_url" VARCHAR(512) NOT NULL,
    "challenge_history_id" BIGINT NOT NULL REFERENCES "personal_challenge_histories" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "challenge_proof_files"."file_name" IS '파일 이름';
COMMENT ON COLUMN "challenge_proof_files"."file_ext" IS '파일 확장자';
COMMENT ON COLUMN "challenge_proof_files"."file_url" IS '파일 URL';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        """


MODELS_STATE = (
    "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"
    "vrszza6KPx2Ij+BG//g/pWIz7A=="
)
