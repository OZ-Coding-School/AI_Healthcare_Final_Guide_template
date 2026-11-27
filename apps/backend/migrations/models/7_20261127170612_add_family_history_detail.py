from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "annual_health_screenings" ADD "hypertension_family_history_mother" VARCHAR(11);
        ALTER TABLE "annual_health_screenings" ADD "diabetes_family_history_father" VARCHAR(11);
        ALTER TABLE "annual_health_screenings" ADD "hypertension_family_history_siblings" VARCHAR(11);
        ALTER TABLE "annual_health_screenings" ADD "diabetes_family_history_mother" VARCHAR(11);
        ALTER TABLE "annual_health_screenings" ADD "hypertension_family_history_father" VARCHAR(11);
        ALTER TABLE "annual_health_screenings" ADD "diabetes_family_history_siblings" VARCHAR(11);
        COMMENT ON COLUMN "annual_health_screenings"."hypertension_family_history_mother" IS '고혈압 가족력(어머니)';
COMMENT ON COLUMN "annual_health_screenings"."diabetes_family_history_father" IS '당뇨병 가족력(아버지)';
COMMENT ON COLUMN "annual_health_screenings"."hypertension_family_history_siblings" IS '고혈압 가족력(형제자매)';
COMMENT ON COLUMN "annual_health_screenings"."diabetes_family_history_mother" IS '당뇨병 가족력(어머니)';
COMMENT ON COLUMN "annual_health_screenings"."hypertension_family_history_father" IS '고혈압 가족력(아버지)';
COMMENT ON COLUMN "annual_health_screenings"."diabetes_family_history_siblings" IS '당뇨병 가족력(형제자매)';"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "annual_health_screenings" DROP COLUMN "hypertension_family_history_mother";
        ALTER TABLE "annual_health_screenings" DROP COLUMN "diabetes_family_history_father";
        ALTER TABLE "annual_health_screenings" DROP COLUMN "hypertension_family_history_siblings";
        ALTER TABLE "annual_health_screenings" DROP COLUMN "diabetes_family_history_mother";
        ALTER TABLE "annual_health_screenings" DROP COLUMN "hypertension_family_history_father";
        ALTER TABLE "annual_health_screenings" DROP COLUMN "diabetes_family_history_siblings";"""


MODELS_STATE = (
    "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"
)
