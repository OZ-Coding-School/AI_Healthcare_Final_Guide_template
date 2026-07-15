from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        CREATE TABLE IF NOT EXISTS "annual_health_screenings" (
    "created_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updated_at" TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "id" UUID NOT NULL PRIMARY KEY,
    "height" DECIMAL(4,1) NOT NULL,
    "weight" DECIMAL(4,1) NOT NULL,
    "bmi" DECIMAL(4,1) NOT NULL,
    "waist_circumference" DECIMAL(4,1) NOT NULL,
    "sbp" SMALLINT NOT NULL,
    "dbp" SMALLINT NOT NULL,
    "pulse" SMALLINT NOT NULL,
    "fbs" SMALLINT NOT NULL,
    "hba1c" DECIMAL(3,1) NOT NULL,
    "triglyceride" SMALLINT NOT NULL,
    "ldl" SMALLINT NOT NULL,
    "hdl" SMALLINT NOT NULL,
    "total_cholesterol" SMALLINT NOT NULL,
    "ast" SMALLINT NOT NULL,
    "alt" SMALLINT NOT NULL,
    "gamma_gtp" SMALLINT NOT NULL,
    "egfr" SMALLINT NOT NULL,
    "creatinine" DECIMAL(3,2) NOT NULL,
    "urine_protein" VARCHAR(10) NOT NULL,
    "urine_glucose" VARCHAR(10) NOT NULL,
    "family_history_diabetes" BOOL NOT NULL,
    "family_history_hypertension" BOOL NOT NULL,
    "screening_at" DATE NOT NULL,
    "is_fasting" BOOL NOT NULL,
    "user_id" UUID NOT NULL REFERENCES "users" ("id") ON DELETE CASCADE
);
COMMENT ON COLUMN "annual_health_screenings"."height" IS '키(cm)';
COMMENT ON COLUMN "annual_health_screenings"."weight" IS '체중(kg)';
COMMENT ON COLUMN "annual_health_screenings"."bmi" IS 'BMI';
COMMENT ON COLUMN "annual_health_screenings"."waist_circumference" IS '허리둘레(cm)';
COMMENT ON COLUMN "annual_health_screenings"."sbp" IS '수축기 혈압(mmHg)';
COMMENT ON COLUMN "annual_health_screenings"."dbp" IS '이완기 혈압(mmHg)';
COMMENT ON COLUMN "annual_health_screenings"."pulse" IS '맥박(분당 횟수)';
COMMENT ON COLUMN "annual_health_screenings"."fbs" IS '공복혈당(mg/dL)';
COMMENT ON COLUMN "annual_health_screenings"."hba1c" IS '당화혈색소(HbA1c, %)';
COMMENT ON COLUMN "annual_health_screenings"."triglyceride" IS '혈액 속 중성지방(mg/dL)';
COMMENT ON COLUMN "annual_health_screenings"."ldl" IS 'LDL(저밀도 지단백) 콜레스테롤(mg/dL)';
COMMENT ON COLUMN "annual_health_screenings"."hdl" IS 'HDL(고밀도 지단백) 콜레스테롤(mg/dL)';
COMMENT ON COLUMN "annual_health_screenings"."total_cholesterol" IS '총콜레스테롤(mg/dL)';
COMMENT ON COLUMN "annual_health_screenings"."ast" IS '아스파르테이트 아미노전이효소(AST)(IU/L)';
COMMENT ON COLUMN "annual_health_screenings"."alt" IS '알라닌 아미노전이효소(ALT)(IU/L)';
COMMENT ON COLUMN "annual_health_screenings"."gamma_gtp" IS 'γ-GTP(IU/L)';
COMMENT ON COLUMN "annual_health_screenings"."egfr" IS '추정 사구체여과율(eGFR), 신장 기능을 평가하는 지표(mL/min/1.73㎡)';
COMMENT ON COLUMN "annual_health_screenings"."creatinine" IS '혈중 크레아티닌(mg/dL)';
COMMENT ON COLUMN "annual_health_screenings"."urine_protein" IS '요단백 수치 검사 결과';
COMMENT ON COLUMN "annual_health_screenings"."urine_glucose" IS '요당 수치 검사 결과';
COMMENT ON COLUMN "annual_health_screenings"."family_history_diabetes" IS '직계 가족의 당뇨병 병력 여부';
COMMENT ON COLUMN "annual_health_screenings"."family_history_hypertension" IS '직계 가족의 고혈압 병력 여부';
COMMENT ON COLUMN "annual_health_screenings"."screening_at" IS '검진 날짜';
COMMENT ON COLUMN "annual_health_screenings"."is_fasting" IS '공복 검사 여부';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        DROP TABLE IF EXISTS "annual_health_screenings";"""


MODELS_STATE = (
    "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"
)
