### Disease Prediction API 명세서

건강 프로필·건강검진·월간 설문으로 당뇨병·고혈압 위험도를 예측하는 API입니다.

- 예측은 AI Worker가 비동기로 처리합니다. 요청(`POST`) 후 SSE(`GET .../events`)로 결과를 받습니다.
- 위험도는 현재 건강 데이터가 비슷한 집단의 유병 확률이며, 미래 발병 예측이나 진단이 아닙니다.
- 위험 등급(LOW·MODERATE·HIGH)의 경계는 질환(모델)마다 다르며 응답의 `risk_thresholds`에 포함됩니다.

```text
POST /disease-predictions  ──▶  202 {id, events_url}
GET  {events_url}  (SSE)   ──▶  event: status(PENDING) → status(PROCESSING) → result | failed  (확정 후 종료)
GET  /disease-predictions/{id}  ──▶  SSE를 받지 못했을 때 상태·결과 확인
```

- **예측 상태 (`status`)**

  | 상태 | 라벨 | 의미 |
  | :--- | :--- | :--- |
  | `PENDING` | 대기 중 | 요청을 접수했고 AI Worker가 가져가기를 기다리는 중 |
  | `PROCESSING` | 분석 중 | AI Worker가 추론 중 |
  | `COMPLETED` | 분석 완료 | 예측 성공. `results`가 채워짐 |
  | `FAILED` | 분석 실패 | 예측 실패. `error_code`로 원인 구분 |

  - 정상: `PENDING → PROCESSING → COMPLETED`, 비정상: `PENDING → PROCESSING → FAILED`
  - 요청 발행 실패(`PUBLISH_FAILED`)나 결과 보관 시간 초과(`RESULT_EXPIRED`)처럼 Worker가 처리하기 전에 끝나면 `PENDING → FAILED`

---

#### 1. 위험도 예측 요청
- **Endpoint:** `POST /api/v1/disease-predictions`
- **Security:** Bearer Token (JWT Access Token)
- **Request Body:** 비워 두면(`{}`) 가장 최근 건강검진·월간 설문을 사용합니다.

  | 필드명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :---: | :--- |
  | annual_health_screening_id | uuid | N | 사용할 건강검진 기록 ID |
  | monthly_health_survey_id | uuid | N | 사용할 월간 설문 ID |

- **입력에 쓰는 항목**
  - 건강 프로필: 성별, 생년월일, 당뇨·고혈압 진단 여부
  - 건강검진: 키, 몸무게, 허리둘레, 혈압, 공복혈당, 당화혈색소, 중성지방, 총·HDL 콜레스테롤, AST, ALT, 크레아티닌, 요단백, 요당, 가족력 상세
  - 월간 설문: 흡연·음주 상태, 하루 흡연량, 음주 빈도, 1회 음주량

- **Response:** `202 Accepted`
  ```json
  {
    "id": "01a1d3a1-2cd0-7f94-b0d4-577ce1603b53",
    "status": "PENDING",
    "events_url": "/api/v1/disease-predictions/01a1d3a1-2cd0-7f94-b0d4-577ce1603b53/events",
    "created_at": "2026-11-13T15:38:37.777072+09:00"
  }
  ```

- **Error Response**

  | 상태 | 경우 | 예시 |
  | :---: | :--- | :--- |
  | 401 | 인증 실패 | |
  | 404 | 건강 프로필·건강검진·월간 설문이 없음 (또는 다른 사용자의 기록 ID) | `Health Profile Not Found.` |
  | 409 | 진행 중(`PENDING`·`PROCESSING`)인 예측이 있음 | `Disease prediction is already in progress.` |
  | 422 | 기록 값이 예측 입력 규칙에 맞지 않음. `loc`은 고칠 기록과 필드 | `{"loc": ["annual_health_screening", "sbp"], "msg": "must be between 60 and 260"}` |
  | 503 | 예측 요청 발행 실패 (Redis 장애). 예측은 `FAILED`(`PUBLISH_FAILED`)로 기록 | |

- **예측 입력 규칙 (422)**
  - 허용 범위: 키 100~230, 몸무게 25~250, 허리둘레 40~200, 수축기 60~260, 이완기 30~160, 공복혈당 40~600, 당화혈색소 3~20, 중성지방 10~3000, 총콜레스테롤 50~600, HDL 5~200, AST·ALT 1~2000, 크레아티닌 0.1~20, 하루 흡연량 0~100, 1회 음주량 0~50
  - 이완기 < 수축기, HDL ≤ 총콜레스테롤, 검진일이 미래가 아니고 검진일 기준 만 19세 이상
  - 현재 음주하지 않으면 음주 빈도는 `NOT_APPLICABLE`, 현재 음주하면 `NOT_APPLICABLE`이 아니어야 함
  - 가족력 병력 여부가 `true`인데 상세(아버지·어머니·형제자매)가 없으면 거부

---

#### 2. 예측 결과 SSE
- **Endpoint:** `GET /api/v1/disease-predictions/{prediction_id}/events`
- **Security:** Bearer Token. 브라우저 `EventSource`는 헤더를 보낼 수 없으므로 `fetch` 스트리밍으로 읽습니다.
- **Response:** `200 OK`, `Content-Type: text/event-stream`
- 연결하면 현재 상태를 `status` 이벤트로 보내고, `PROCESSING`으로 바뀌면 다시 보냅니다. 결과가 확정되면 `result`·`failed` 이벤트 1건을 보내고 연결을 닫습니다.
- 기다리는 동안 10초마다 `: heartbeat` 주석을 보냅니다. 최대 30초 기다립니다.
- 이미 확정된 예측이면 `status` 없이 바로 결과를 보냅니다. 같은 상태는 두 번 보내지 않습니다.

  | 이벤트 | 의미 | data |
  | :--- | :--- | :--- |
  | `status` | 진행 상태 (`PENDING`·`PROCESSING`) | `{"id": "...", "status": "PROCESSING", "status_label": "분석 중"}` |
  | `result` | 예측 성공 (`COMPLETED`) | 상세 조회(3번)와 같은 JSON |
  | `failed` | 예측 실패 (`FAILED`) | 상세 조회와 같은 JSON (`error_code`, `errors`) |
  | `timeout` | 대기 시간 초과. 예측은 계속 진행 중일 수 있음 | `{"id": "...", "status": "PROCESSING", "status_label": "분석 중"}` |
  | `error` | 서버 오류로 결과를 확인하지 못함 | `{"id": "...", "code": "SERVICE_UNAVAILABLE"}` |

- `timeout`·`error`를 받으면 잠시 후 SSE에 다시 연결하거나 상세 조회로 확인합니다.
- **Example**
  ```text
  event: status
  data: {"id":"01a1d3a1-...","status":"PENDING","status_label":"대기 중"}

  event: status
  data: {"id":"01a1d3a1-...","status":"PROCESSING","status_label":"분석 중"}

  : heartbeat

  event: result
  data: {"id":"01a1d3a1-...","status":"COMPLETED", ...}
  ```

- **Error Response:** `401`, `404` (없는 예측 또는 다른 사용자의 예측)

---

#### 3. 예측 상세 조회
- **Endpoint:** `GET /api/v1/disease-predictions/{prediction_id}`
- **Description:** 확정 전(`PENDING`·`PROCESSING`)이면 AI Worker가 남긴 상태·결과를 확인해 반영한 뒤 반환합니다. 1시간이 지나도 확정되지 않으면 `FAILED`(`RESULT_EXPIRED`)로 바뀝니다.
- **Response:** `200 OK` (수치는 예시)
  ```json
  {
    "id": "01a1d3a1-2cd0-7f94-b0d4-577ce1603b53",
    "status": "COMPLETED",
    "status_label": "분석 완료",
    "annual_health_screening_id": "01a1d3a1-...",
    "monthly_health_survey_id": "01a1d3a1-...",
    "error_code": null,
    "errors": [],
    "created_at": "2026-11-13T15:38:37.777072+09:00",
    "started_at": "2026-11-13T15:38:37.801234+09:00",
    "completed_at": "2026-11-13T15:38:38.912345+09:00",
    "results": [
      {
        "model_type": "diabetes_risk",
        "disease_name": "당뇨병",
        "model_version": "diabetes_risk:train_b:LightGBM:27e6dd8beeea",
        "risk_probability": 0.3052,
        "risk_score": 30.52,
        "risk_level": "HIGH",
        "risk_level_label": "높음",
        "risk_thresholds": {"moderate": 0.10512, "high": 0.28733},
        "shap_output_space": "probability",
        "base_value": 0.152346,
        "risk_factors": [
          {
            "feature": "나이",
            "display_name": "나이",
            "value": 56,
            "shap_value": 0.0812,
            "direction": "increase",
            "actionable": false,
            "reverse_causation_suspected": false
          }
        ],
        "out_of_training_range": []
      }
    ]
  }
  ```

  | 필드 | 설명 |
  | :--- | :--- |
  | status | `PENDING`·`PROCESSING`·`COMPLETED`·`FAILED` (맨 위 상태표 참고) |
  | started_at | AI Worker가 추론을 시작한 시간. `PENDING`이면 `null` |
  | results | 질환별 결과. 당뇨병 → 고혈압 순. `COMPLETED`일 때만 채워짐 |
  | risk_score | 위험 확률 × 100 (%) |
  | risk_factors | 위험도에 크게 기여한 상위 5개 요인. `direction`이 `increase`면 위험을 높임 |
  | actionable | `false`면 생활습관으로 바꿀 수 없거나(나이·가족력 등) 역인과가 의심되는 요인 |
  | out_of_training_range | 학습 데이터 범위를 벗어난 입력 변수. 있으면 결과 해석에 주의 |
  | error_code | `INVALID_INPUT`, `MODEL_ERROR`, `INTERNAL_ERROR`, `INVALID_MESSAGE`, `INVALID_RESULT`, `PUBLISH_FAILED`, `RESULT_EXPIRED` |
  | errors | `INVALID_INPUT`일 때만 `{field, reason}` 목록. 그 밖의 실패는 빈 목록 |

- **Error Response:** `401`, `404` (`Disease Prediction Not Found.`)

---

#### 4. 예측 목록 조회
- **Endpoint:** `GET /api/v1/disease-predictions`
- **Description:** 최신순으로 반환합니다.
- **Response:** `200 OK`
  ```json
  [
    {
      "id": "01a1d3a1-2cd0-7f94-b0d4-577ce1603b53",
      "status": "COMPLETED",
      "created_at": "2026-11-13T15:38:37.777072+09:00",
      "completed_at": "2026-11-13T15:38:38.912345+09:00",
      "results": [
        {"model_type": "diabetes_risk", "disease_name": "당뇨병", "risk_score": 30.52, "risk_level": "HIGH", "risk_level_label": "높음"},
        {"model_type": "hypertension_risk", "disease_name": "고혈압", "risk_score": 35.96, "risk_level": "MODERATE", "risk_level_label": "중간"}
      ]
    }
  ]
  ```
