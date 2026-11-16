from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "disease_prediction_results" DROP CONSTRAINT IF EXISTS "disease_prediction_results_prediction_id_key";
        DROP INDEX IF EXISTS "uid_disease_pre_predict_ce56a2";
        ALTER TABLE "disease_prediction_results" DROP CONSTRAINT IF EXISTS "fk_disease__disease__bf2a848e";
        ALTER TABLE "annual_health_screenings" ADD "hypertension_family_history_mother" VARCHAR(11);
        ALTER TABLE "annual_health_screenings" ADD "hypertension_family_history_siblings" VARCHAR(11);
        ALTER TABLE "annual_health_screenings" ADD "diabetes_family_history_siblings" VARCHAR(11);
        ALTER TABLE "annual_health_screenings" ADD "diabetes_family_history_mother" VARCHAR(11);
        ALTER TABLE "annual_health_screenings" ADD "hypertension_family_history_father" VARCHAR(11);
        ALTER TABLE "annual_health_screenings" ADD "diabetes_family_history_father" VARCHAR(11);
        ALTER TABLE "disease_predictions" ADD "error_code" VARCHAR(30);
        ALTER TABLE "disease_predictions" ADD "completed_at" TIMESTAMPTZ;
        ALTER TABLE "disease_predictions" ADD "status" VARCHAR(10) NOT NULL DEFAULT 'PENDING';
        ALTER TABLE "disease_predictions" ADD "started_at" TIMESTAMPTZ;
        ALTER TABLE "disease_predictions" ADD "errors" JSONB;
        ALTER TABLE "disease_predictions" ADD "monthly_health_survey_id" UUID;
        ALTER TABLE "disease_predictions" ADD "annual_health_screening_id" UUID;
        ALTER TABLE "disease_predictions" DROP COLUMN "using_model_name";
        ALTER TABLE "disease_predictions" DROP COLUMN "threshold";
        COMMENT ON COLUMN "disease_predictions"."feature" IS 'AI Worker에 보낸 예측 입력';
        ALTER TABLE "disease_prediction_results" ADD "threshold_high" DECIMAL(6,5) NOT NULL;
        ALTER TABLE "disease_prediction_results" ADD "threshold_moderate" DECIMAL(6,5) NOT NULL;
        ALTER TABLE "disease_prediction_results" ADD "model_type" VARCHAR(17) NOT NULL;
        ALTER TABLE "disease_prediction_results" ADD "model_version" VARCHAR(100) NOT NULL;
        ALTER TABLE "disease_prediction_results" ADD "out_of_training_range" JSONB NOT NULL;
        ALTER TABLE "disease_prediction_results" ADD "shap_output_space" VARCHAR(20) NOT NULL;
        ALTER TABLE "disease_prediction_results" ADD "risk_probability" DECIMAL(6,5) NOT NULL;
        COMMENT ON COLUMN "disease_prediction_results"."shap_results" IS '위험도에 기여한 상위 요인의 SHAP 분석 결과';
        ALTER TABLE "disease_prediction_results" ALTER COLUMN "confidence_score" DROP NOT NULL;
        COMMENT ON COLUMN "disease_prediction_results"."confidence_score" IS '질병 위험도 예측 신뢰도 점수(현재 모델은 산출하지 않음)';
        COMMENT ON COLUMN "disease_prediction_results"."base_value" IS 'SHAP 기준값';
        ALTER TABLE "disease_prediction_results" ALTER COLUMN "base_value" TYPE DECIMAL(12,6) USING "base_value"::DECIMAL(12,6);
        COMMENT ON COLUMN "disease_prediction_results"."risk_score" IS '질병 위험도 점수(%, 0~100)';
        COMMENT ON COLUMN "annual_health_screenings"."hypertension_family_history_mother" IS '고혈압 가족력(어머니)';
COMMENT ON COLUMN "annual_health_screenings"."hypertension_family_history_siblings" IS '고혈압 가족력(형제자매)';
COMMENT ON COLUMN "annual_health_screenings"."diabetes_family_history_siblings" IS '당뇨병 가족력(형제자매)';
COMMENT ON COLUMN "annual_health_screenings"."diabetes_family_history_mother" IS '당뇨병 가족력(어머니)';
COMMENT ON COLUMN "annual_health_screenings"."hypertension_family_history_father" IS '고혈압 가족력(아버지)';
COMMENT ON COLUMN "annual_health_screenings"."diabetes_family_history_father" IS '당뇨병 가족력(아버지)';
COMMENT ON COLUMN "disease_predictions"."error_code" IS '예측 실패 코드';
COMMENT ON COLUMN "disease_predictions"."completed_at" IS '예측 완료(성공·실패) 시간';
COMMENT ON COLUMN "disease_predictions"."status" IS '예측 진행 상태';
COMMENT ON COLUMN "disease_predictions"."started_at" IS 'AI Worker가 추론을 시작한 시간';
COMMENT ON COLUMN "disease_predictions"."errors" IS '입력 오류 필드와 사유';
COMMENT ON COLUMN "disease_predictions"."monthly_health_survey_id" IS '예측에 사용한 월간 건강 설문';
COMMENT ON COLUMN "disease_predictions"."annual_health_screening_id" IS '예측에 사용한 건강검진 기록';
COMMENT ON COLUMN "disease_prediction_results"."threshold_high" IS 'HIGH 등급 경계 확률';
COMMENT ON COLUMN "disease_prediction_results"."threshold_moderate" IS 'MODERATE 등급 경계 확률';
COMMENT ON COLUMN "disease_prediction_results"."model_type" IS '예측 질환(모델 종류)';
COMMENT ON COLUMN "disease_prediction_results"."model_version" IS '예측에 사용한 서빙 모델 버전';
COMMENT ON COLUMN "disease_prediction_results"."out_of_training_range" IS '학습 데이터 범위를 벗어난 입력 변수';
COMMENT ON COLUMN "disease_prediction_results"."shap_output_space" IS 'SHAP 값의 공간(probability, log_odds, raw)';
COMMENT ON COLUMN "disease_prediction_results"."risk_probability" IS '보정된 위험 확률(0~1)';
        ALTER TABLE "disease_predictions" ADD CONSTRAINT "fk_disease__monthly__22e3ce59" FOREIGN KEY ("monthly_health_survey_id") REFERENCES "monthly_health_surveys" ("id") ON DELETE SET NULL;
        ALTER TABLE "disease_predictions" ADD CONSTRAINT "fk_disease__annual_h_65bb971d" FOREIGN KEY ("annual_health_screening_id") REFERENCES "annual_health_screenings" ("id") ON DELETE SET NULL;
        ALTER TABLE "disease_prediction_results" ADD CONSTRAINT "fk_disease__disease__bf2a848e" FOREIGN KEY ("prediction_id") REFERENCES "disease_predictions" ("id") ON DELETE CASCADE;
        CREATE UNIQUE INDEX IF NOT EXISTS "uid_disease_pre_predict_551d86" ON "disease_prediction_results" ("prediction_id", "model_type");"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP INDEX IF EXISTS "uid_disease_pre_predict_551d86";
        ALTER TABLE "disease_prediction_results" DROP CONSTRAINT IF EXISTS "fk_disease__disease__bf2a848e";
        ALTER TABLE "disease_predictions" DROP CONSTRAINT IF EXISTS "fk_disease__annual_h_65bb971d";
        ALTER TABLE "disease_predictions" DROP CONSTRAINT IF EXISTS "fk_disease__monthly__22e3ce59";
        ALTER TABLE "disease_predictions" ADD "using_model_name" VARCHAR(30) NOT NULL;
        ALTER TABLE "disease_predictions" ADD "threshold" DECIMAL(3,2) NOT NULL;
        ALTER TABLE "disease_predictions" DROP COLUMN "error_code";
        ALTER TABLE "disease_predictions" DROP COLUMN "completed_at";
        ALTER TABLE "disease_predictions" DROP COLUMN "status";
        ALTER TABLE "disease_predictions" DROP COLUMN "started_at";
        ALTER TABLE "disease_predictions" DROP COLUMN "errors";
        ALTER TABLE "disease_predictions" DROP COLUMN "monthly_health_survey_id";
        ALTER TABLE "disease_predictions" DROP COLUMN "annual_health_screening_id";
        COMMENT ON COLUMN "disease_predictions"."feature" IS '질병 위험도 예측에 사용한 변수 파라미터';
        ALTER TABLE "annual_health_screenings" DROP COLUMN "hypertension_family_history_mother";
        ALTER TABLE "annual_health_screenings" DROP COLUMN "hypertension_family_history_siblings";
        ALTER TABLE "annual_health_screenings" DROP COLUMN "diabetes_family_history_siblings";
        ALTER TABLE "annual_health_screenings" DROP COLUMN "diabetes_family_history_mother";
        ALTER TABLE "annual_health_screenings" DROP COLUMN "hypertension_family_history_father";
        ALTER TABLE "annual_health_screenings" DROP COLUMN "diabetes_family_history_father";
        ALTER TABLE "disease_prediction_results" DROP COLUMN "threshold_high";
        ALTER TABLE "disease_prediction_results" DROP COLUMN "threshold_moderate";
        ALTER TABLE "disease_prediction_results" DROP COLUMN "model_type";
        ALTER TABLE "disease_prediction_results" DROP COLUMN "model_version";
        ALTER TABLE "disease_prediction_results" DROP COLUMN "out_of_training_range";
        ALTER TABLE "disease_prediction_results" DROP COLUMN "shap_output_space";
        ALTER TABLE "disease_prediction_results" DROP COLUMN "risk_probability";
        COMMENT ON COLUMN "disease_prediction_results"."shap_results" IS '예측에 활용된 변수들의 가중치, 기여도 SHAP 분석 결과';
        ALTER TABLE "disease_prediction_results" ALTER COLUMN "confidence_score" SET NOT NULL;
        COMMENT ON COLUMN "disease_prediction_results"."confidence_score" IS '질병 위험도 예측 신뢰도 점수';
        COMMENT ON COLUMN "disease_prediction_results"."base_value" IS '질병 위험도 예측에 사용한 모델의 기반값';
        ALTER TABLE "disease_prediction_results" ALTER COLUMN "base_value" TYPE DECIMAL(5,2) USING "base_value"::DECIMAL(5,2);
        COMMENT ON COLUMN "disease_prediction_results"."risk_score" IS '질병 위험도 점수';
        COMMENT ON COLUMN "disease_predictions"."using_model_name" IS '질병 위험도 예측에 사용한 모델 이름';
COMMENT ON COLUMN "disease_predictions"."threshold" IS '질병 위험도 예측에 사용한 모델의 임계값(0~1)';
        ALTER TABLE "disease_prediction_results" ADD CONSTRAINT "fk_disease__disease__bf2a848e" FOREIGN KEY ("prediction_id") REFERENCES "disease_predictions" ("id") ON DELETE CASCADE;
        CREATE UNIQUE INDEX IF NOT EXISTS "uid_disease_pre_predict_ce56a2" ON "disease_prediction_results" ("prediction_id");"""


MODELS_STATE = (
    "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"
    "AczoP/8fNBIFew=="
)
