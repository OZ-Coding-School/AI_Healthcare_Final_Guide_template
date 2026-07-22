from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "annual_health_screenings" DROP COLUMN "egfr";
        ALTER TABLE "annual_health_screenings" DROP COLUMN "pulse";
        ALTER TABLE "annual_health_screenings" DROP COLUMN "gamma_gtp";
        ALTER TABLE "monthly_health_surveys" ADD "drinking_frequency" VARCHAR(17) NOT NULL;
        ALTER TABLE "monthly_health_surveys" DROP COLUMN "pulse";
        ALTER TABLE "monthly_health_surveys" DROP COLUMN "drinking_fr_per_week";
        COMMENT ON COLUMN "monthly_health_surveys"."drinking_frequency" IS '음주 빈도';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "monthly_health_surveys" ADD "pulse" SMALLINT;
        ALTER TABLE "monthly_health_surveys" ADD "drinking_fr_per_week" SMALLINT;
        ALTER TABLE "monthly_health_surveys" DROP COLUMN "drinking_frequency";
        ALTER TABLE "annual_health_screenings" ADD "egfr" SMALLINT NOT NULL;
        ALTER TABLE "annual_health_screenings" ADD "pulse" SMALLINT NOT NULL;
        ALTER TABLE "annual_health_screenings" ADD "gamma_gtp" SMALLINT NOT NULL;
        COMMENT ON COLUMN "monthly_health_surveys"."pulse" IS '맥박수(분당 횟수)';
COMMENT ON COLUMN "monthly_health_surveys"."drinking_fr_per_week" IS '주당 음주 빈도';
COMMENT ON COLUMN "annual_health_screenings"."egfr" IS '추정 사구체여과율(eGFR), 신장 기능을 평가하는 지표(mL/min/1.73㎡)';
COMMENT ON COLUMN "annual_health_screenings"."pulse" IS '맥박(분당 횟수)';
COMMENT ON COLUMN "annual_health_screenings"."gamma_gtp" IS 'γ-GTP(IU/L)';"""


MODELS_STATE = (
    "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"
)
