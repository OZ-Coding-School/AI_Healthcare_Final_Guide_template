from tortoise import BaseDBAsyncClient

RUN_IN_TRANSACTION = True


async def upgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "disease_predictions" ADD "challenge_status" VARCHAR(10);
        ALTER TABLE "disease_predictions" ADD "challenge_model_name" VARCHAR(100);
        ALTER TABLE "disease_predictions" ADD "challenge_started_at" TIMESTAMPTZ;
        ALTER TABLE "disease_predictions" ADD "challenge_completed_at" TIMESTAMPTZ;
        ALTER TABLE "disease_predictions" ADD "challenge_error_code" VARCHAR(30);
        ALTER TABLE "personal_challenges" ADD "basis" JSONB NOT NULL DEFAULT '[]'::jsonb;
        ALTER TABLE "personal_challenges" ADD "total_rounds" SMALLINT;
        ALTER TABLE "personal_challenges" ADD "prediction_id" UUID;
        ALTER TABLE "personal_challenges" ADD "target_diseases" JSONB NOT NULL DEFAULT '[]'::jsonb;
        COMMENT ON COLUMN "disease_predictions"."challenge_status" IS 'LLM 챌린지 추천 상태 (예측 완료 전에는 null)';
COMMENT ON COLUMN "disease_predictions"."challenge_model_name" IS '챌린지 추천에 사용한 LLM 모델 이름';
COMMENT ON COLUMN "disease_predictions"."challenge_started_at" IS '챌린지 추천 생성 시작 시간';
COMMENT ON COLUMN "disease_predictions"."challenge_completed_at" IS '챌린지 추천 완료(성공·실패) 시간';
COMMENT ON COLUMN "disease_predictions"."challenge_error_code" IS '챌린지 추천 실패 코드';
COMMENT ON COLUMN "personal_challenges"."basis" IS '추천 근거 요인 목록({model_type, feature, display_name})';
COMMENT ON COLUMN "personal_challenges"."total_rounds" IS '목표 회차 수(일간: 일, 주간: 주, 월간: 개월, 횟수형: 횟수)';
COMMENT ON COLUMN "personal_challenges"."prediction_id" IS '추천 근거가 된 질병 위험도 예측';
COMMENT ON COLUMN "personal_challenges"."target_diseases" IS '챌린지가 겨냥하는 질환(model_type 목록)';
        ALTER TABLE "personal_challenges" ADD CONSTRAINT "fk_personal_disease__0c79a512" FOREIGN KEY ("prediction_id") REFERENCES "disease_predictions" ("id") ON DELETE SET NULL;"""


async def downgrade(db: BaseDBAsyncClient) -> str:
    return """
        ALTER TABLE "personal_challenges" DROP CONSTRAINT IF EXISTS "fk_personal_disease__0c79a512";
        ALTER TABLE "disease_predictions" DROP COLUMN "challenge_status";
        ALTER TABLE "disease_predictions" DROP COLUMN "challenge_model_name";
        ALTER TABLE "disease_predictions" DROP COLUMN "challenge_started_at";
        ALTER TABLE "disease_predictions" DROP COLUMN "challenge_completed_at";
        ALTER TABLE "disease_predictions" DROP COLUMN "challenge_error_code";
        ALTER TABLE "personal_challenges" DROP COLUMN "basis";
        ALTER TABLE "personal_challenges" DROP COLUMN "total_rounds";
        ALTER TABLE "personal_challenges" DROP COLUMN "prediction_id";
        ALTER TABLE "personal_challenges" DROP COLUMN "target_diseases";"""


MODELS_STATE = (
    "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"
)
