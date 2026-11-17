### Challenge API 명세서

질병 위험도 예측 결과와 주요 위험 요인(SHAP)을 바탕으로 LLM(Claude)이 생활습관 챌린지를 추천하는 API입니다.

- 예측이 `COMPLETED`로 확정되면 추천이 **자동으로** 시작됩니다. 별도 생성 요청은 없습니다.
- LLM 호출은 백그라운드에서 진행되므로, 예측 결과 SSE는 추천을 기다리지 않고 바로 끝납니다.
- 추천 챌린지는 `PENDING`(수락 대기) 상태로 저장되며, 수락 기한(`expired_at`)은 추천 후 7일입니다(`CHALLENGE_ACCEPT_EXPIRE_DAYS`).
- 추천 근거는 생활습관으로 바꿀 수 있는 요인만 사용합니다. 나이·성별·키·가족력·진단 여부, 역인과가 의심되는 총콜레스테롤, 학습 범위를 벗어난 값은 근거에서 제외합니다.
- 챌린지는 의료 진단이나 처방이 아닙니다. 약물·처방·치료 관련 표현이 있는 추천은 저장하지 않습니다.

```text
(예측 COMPLETED) ──▶ 추천 자동 시작 (status: PROCESSING)
GET  /disease-predictions/{id}/challenges        ──▶ PROCESSING이면 2~3초 간격으로 다시 조회
                                                  ──▶ COMPLETED: challenges 표시 / FAILED: error_code 확인
POST /disease-predictions/{id}/challenges/retry  ──▶ FAILED일 때만 다시 생성
GET  /challenges?status=PENDING                  ──▶ 내 챌린지 목록
```

- **추천 상태 (`status`)**

  | 상태 | 라벨 | 의미 |
  | :--- | :--- | :--- |
  | `null` | | 예측 완료 직후 아직 시작 전 (조회하면 바로 시작) |
  | `PROCESSING` | 추천 생성 중 | LLM이 챌린지를 생성하는 중 |
  | `COMPLETED` | 추천 완료 | `challenges`가 채워짐 |
  | `FAILED` | 추천 실패 | `error_code`로 원인 구분. retry API로 다시 생성 |

  - 생성 중 서버가 재시작되어 5분(`CHALLENGE_RECOMMENDATION_STALE_SECONDS`) 넘게 `PROCESSING`에 머문 추천은 조회할 때 다시 시작합니다.
  - API 키 없이 `LLM_NOT_CONFIGURED`로 실패한 추천은, 키를 등록하고 서버를 다시 시작한 뒤 조회하면 retry 없이 다시 생성됩니다. 다른 원인으로 실패한 추천은 retry API로 다시 생성합니다.

- **추천 실패 코드 (`error_code`)**

  | 코드 | 의미 | 재시도 |
  | :--- | :--- | :---: |
  | `LLM_NOT_CONFIGURED` | `ANTHROPIC_API_KEY`가 설정되지 않음 | 키 설정 후 |
  | `LLM_UNAVAILABLE` | 네트워크 오류, 요청 한도(429), 서버 오류·과부하(5xx·529) | O |
  | `LLM_REQUEST_FAILED` | 잘못된 키·모델 등 설정 오류(4xx) | 설정 확인 후 |
  | `LLM_INVALID_RESPONSE` | 응답이 형식·규칙 검증을 통과하지 못함 (재요청 포함 모두 실패) | O |
  | `NO_PREDICTION_RESULT` | 질환별 예측 결과가 없음 | X |
  | `INTERNAL_ERROR` | 서버 내부 오류 | O |

---

#### 1. 예측 결과 기반 챌린지 추천 조회
- **Endpoint:** `GET /api/v1/disease-predictions/{prediction_id}/challenges`
- **Security:** Bearer Token (JWT Access Token)
- **Response:** `200 OK`
  ```json
  {
    "prediction_id": "01a1d3a1-2cd0-7f94-b0d4-577ce1603b53",
    "status": "COMPLETED",
    "status_label": "추천 완료",
    "error_code": null,
    "model_name": "claude-haiku-5-5",
    "started_at": "2026-11-17T15:38:40.112233+09:00",
    "completed_at": "2026-11-17T15:38:45.445566+09:00",
    "challenges": [
      {
        "id": 12,
        "prediction_id": "01a1d3a1-2cd0-7f94-b0d4-577ce1603b53",
        "title": "매일 30분 빠르게 걷기",
        "description": "저녁 식사 후 30분 동안 빠르게 걷습니다. 숨이 약간 찰 정도의 속도를 유지합니다.",
        "challenge_type": "DAILY",
        "challenge_type_label": "일일 챌린지",
        "total_rounds": 21,
        "expected_effect": "꾸준한 유산소 활동은 허리둘레 관리와 혈당 조절에 도움이 됩니다.",
        "target_diseases": [{ "model_type": "diabetes_risk", "disease_name": "당뇨병" }],
        "basis": [{ "model_type": "diabetes_risk", "feature": "허리둘레", "display_name": "허리둘레" }],
        "status": "PENDING",
        "status_label": "대기중",
        "expired_at": "2026-11-24T15:38:45.445566+09:00",
        "joined_at": null,
        "completed_at": null,
        "created_at": "2026-11-17T15:38:45.445566+09:00"
      }
    ]
  }
  ```

- **챌린지 필드**

  | 필드명 | 설명 |
  | :--- | :--- |
  | challenge_type | `DAILY`(일일), `WEEKLY`(주간), `MONTHLY`(월간), `COUNT_BASED`(횟수형) |
  | total_rounds | 목표 회차. 일일=일 수(7~30), 주간=주 수(2~12), 월간=개월 수(1~3), 횟수형=횟수(3~30) |
  | target_diseases | 챌린지가 겨냥하는 질환 |
  | basis | 추천 근거가 된 위험 요인. 화면의 "추천 근거"에 `display_name`을 표시 |

- **Error Response**

  | 상태 | 경우 | 예시 |
  | :---: | :--- | :--- |
  | 401 | 인증 실패 | |
  | 404 | 예측이 없거나 다른 사용자의 예측 | `Disease Prediction Not Found.` |
  | 409 | 예측이 아직 완료되지 않았거나 실패함 | `Disease prediction is not completed.` |

---

#### 2. 실패한 챌린지 추천 다시 생성
- **Endpoint:** `POST /api/v1/disease-predictions/{prediction_id}/challenges/retry`
- **Security:** Bearer Token (JWT Access Token)
- **Response:** `202 Accepted` — 1번과 같은 형식, `status`는 `PROCESSING`, `challenges`는 빈 배열입니다. 이후 1번으로 조회합니다.
- **Error Response**

  | 상태 | 경우 | 예시 |
  | :---: | :--- | :--- |
  | 401 | 인증 실패 | |
  | 404 | 예측이 없거나 다른 사용자의 예측 | `Disease Prediction Not Found.` |
  | 409 | 예측이 완료되지 않음 | `Disease prediction is not completed.` |
  | 409 | 추천이 실패 상태가 아님(진행 중·완료) | `Only failed challenge recommendations can be retried.` |

---

#### 3. 내 챌린지 목록 조회
- **Endpoint:** `GET /api/v1/challenges`
- **Security:** Bearer Token (JWT Access Token)
- **Query Parameters**

  | 이름 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :---: | :--- |
  | status | string | N | `PENDING`, `IN_PROGRESS`, `COMPLETED`, `FAILED`, `ABANDONED` |

- **Response:** `200 OK` — 1번 `challenges` 항목과 같은 형식의 배열, 최근 추천 순
- **Error Response**

  | 상태 | 경우 |
  | :---: | :--- |
  | 401 | 인증 실패 |
  | 422 | 알 수 없는 `status` 값 |

---

#### 캐시 (Redis)

자주 조회되는 1번(추천 조회)과 3번(목록 조회)에 Redis Key-Value 캐시를 적용합니다.

| API | 캐시 대상 | 키 | TTL | 무효화 |
| :--- | :--- | :--- | :--- | :--- |
| 1. 추천 조회 | `status`가 `COMPLETED`인 응답만 | `challenge:recommendation:{user_id}:{prediction_id}` | 600초 + 무작위 0~20% | 추천이 저장될 때 삭제 |
| 3. 목록 조회 | 사용자·`status` 필터별 응답 | `challenge:list:{user_id}:v{version}:{status\|all}` | 60초 + 무작위 0~20% | 추천이 저장되면 `challenge:list:version:{user_id}`를 1 올림 |

- 생성 중(`PROCESSING`)·실패(`FAILED`) 상태는 몇 초 안에 바뀌므로 캐시하지 않습니다. 생성 중 반복 조회는 매번 DB 상태를 반환합니다.
- Cache Stampede는 Randomized TTL로 막습니다. 캐시를 다시 채우는 비용이 인덱스 조회 한 번이라 Stale-While-Revalidate·PER은 쓰지 않습니다.
- 목록은 상태 필터마다 키가 달라, 키를 찾아 지우는 대신 버전을 올려 이전 키를 읽지 않게 합니다. 이전 키는 TTL로 사라집니다.
- Redis 장애 시 캐시 없이 DB 결과를 반환합니다. 캐시 때문에 API가 실패하지 않습니다.
- 챌린지 수락·기록 API를 추가할 때는 두 캐시를 함께 무효화해야 합니다.

---

#### 환경 변수

| 이름 | 기본값 | 설명 |
| :--- | :--- | :--- |
| `ANTHROPIC_API_KEY` | (빈 값) | Claude Console에서 발급한 API 키. 비어 있으면 추천은 `LLM_NOT_CONFIGURED`로 실패 |
| `LLM_MODEL` | `claude-haiku-5-5` | 추천에 사용할 Claude 모델 |
| `ANTHROPIC_API_VERSION` | `2026-10-21` | Claude API 버전 헤더 |
| `LLM_TIMEOUT_SECONDS` | `30` | LLM 호출 시간 제한(초) |
| `LLM_MAX_ATTEMPTS` | `2` | 일시적 장애·형식 오류를 포함한 최대 호출 횟수 |
| `CHALLENGE_RECOMMENDATION_COUNT` | `3` | 예측 1건당 추천 챌린지 수 |
| `CHALLENGE_ACCEPT_EXPIRE_DAYS` | `7` | 추천 챌린지 수락 기한(일) |
| `CHALLENGE_RECOMMENDATION_CACHE_TTL_SECONDS` | `600` | 완료된 추천 캐시 기본 TTL(초) |
| `CHALLENGE_LIST_CACHE_TTL_SECONDS` | `60` | 챌린지 목록 캐시 기본 TTL(초) |
| `CACHE_TTL_JITTER_RATIO` | `0.2` | TTL에 무작위로 더하는 최대 비율 |
