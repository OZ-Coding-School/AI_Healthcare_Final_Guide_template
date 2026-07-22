### Blood Sugar Measurement API 명세서

사용자의 혈당 측정 데이터 관리 API입니다.

---

#### 1. 혈당 측정 데이터 생성
- **Endpoint:** `POST /api/v1/blood-sugar-measurements`
- **Description:** 새로운 혈당 측정 데이터를 기록합니다. 측정 유형(공복, 식후 등)과 운동/복약 여부에 따라 추가 정보를 입력할 수 있습니다.
- **Security:** Bearer Token (JWT Access Token)
- **Request Header:**
  - `Authorization: Bearer <access_token>`
- **Request Body:**

  | 필드명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :---: | :--- |
  | measure_type | string | Y | 측정 유형 (Enum: BloodSugarMeasurementType - FASTING, BEFORE_BREAKFAST, AFTER_BREAKFAST, BEFORE_LUNCH, AFTER_LUNCH, BEFORE_DINNER, AFTER_DINNER, BEFORE_SLEEP, RANDOM) |
  | blood_glucose | integer | Y | 혈당 수치 (1 ~ 1000) |
  | minutes_since_meal | integer | N | 식후 경과 시간 (분) |
  | has_exercised | boolean | Y | 운동 여부 |
  | exercise_type | string | N | 운동 유형 (Enum: ExerciseType - CARDIO, STRENGTH, BOTH, NOT_APPLICABLE) |
  | exercise_minutes | integer | N | 운동 시간 (분) |
  | minutes_since_exercise | integer | N | 운동 후 경과 시간 (분) |
  | has_medicated | boolean | Y | 복약 여부 |
  | medicine_name | string | N | 약 이름 |
  | minutes_since_medication | integer | N | 복약 후 경과 시간 (분) |
  | memo | string | N | 참고 메모 (최대 1000자) |
  | measured_at | string (datetime)| Y | 측정 일시 (ISO8601) |

- **Example Request Body:**
  ```json
  {
    "measure_type": "AFTER_LUNCH",
    "blood_glucose": 140,
    "minutes_since_meal": 60,
    "has_exercised": true,
    "exercise_type": "CARDIO",
    "exercise_minutes": 30,
    "minutes_since_exercise": 20,
    "has_medicated": false,
    "measured_at": "2024-07-15T12:00:00Z",
    "memo": "점심 식후 가벼운 산책"
  }
  ```

- **Response:** `201 Created`
- **Example Response Body:**
  ```json
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "measure_type": "점심 식후",
    "measured_at": "2024-07-15T12:00:00Z",
    "created_at": "2024-07-15T12:05:00Z",
    "blood_glucose": 140,
    "has_exercised": true,
    "has_medicated": false,
    "memo": "점심 식후 가벼운 산책"
  }
  ```

---

#### 2. 혈당 측정 목록 조회
- **Endpoint:** `GET /api/v1/blood-sugar-measurements`
- **Description:** 사용자의 혈당 측정 기록 목록을 조회합니다. 날짜 범위 필터링이 가능합니다.
- **Security:** Bearer Token (JWT Access Token)
- **Request Header:**
  - `Authorization: Bearer <access_token>`
- **Query Parameters:**

  | 필드명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :---: | :--- |
  | start_date | string (date) | N | 시작 날짜 (YYYY-MM-DD, 2000년 이후) |
  | end_date | string (date) | N | 종료 날짜 (start_date 입력 시 필수) |

- **Example Request:** `GET /api/v1/blood-sugar-measurements?start_date=2024-07-01&end_date=2024-07-31`

- **Response:** `200 OK`
- **Example Response Body:**
  ```json
  [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "measure_type": "점심 식후",
      "measured_at": "2024-07-15T12:00:00Z",
      "created_at": "2024-07-15T12:05:00Z"
    }
  ]
  ```

---

#### 3. 혈당 측정 상세 조회
- **Endpoint:** `GET /api/v1/blood-sugar-measurements/{measurement_id}`
- **Description:** 특정 혈당 측정 기록의 상세 내용을 조회합니다.
- **Security:** Bearer Token (JWT Access Token)
- **Request Header:**
  - `Authorization: Bearer <access_token>`
- **Path Parameters:**

  | 필드명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :---: | :--- |
  | measurement_id | uuid | Y | 혈당 측정 기록 ID |

- **Response:** `200 OK`
- **Example Response Body:**
  ```json
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "measure_type": "식후",
    "measured_at": "2024-07-15T12:00:00Z",
    "created_at": "2024-07-15T12:05:00Z",
    "blood_glucose": 140,
    "minutes_since_meal": 60,
    "has_exercised": true,
    "exercise_type": "유산소",
    "exercise_minutes": 30,
    "minutes_since_exercise": 20,
    "has_medicated": false,
    "medicine_name": null,
    "minutes_since_medication": null,
    "memo": "점심 식후 가벼운 산책"
  }
  ```

---

#### 4. 혈당 측정 데이터 삭제
- **Endpoint:** `DELETE /api/v1/blood-sugar-measurements/{measurement_id}`
- **Description:** 특정 혈당 측정 기록을 삭제합니다.
- **Security:** Bearer Token (JWT Access Token)
- **Request Header:**
  - `Authorization: Bearer <access_token>`
- **Path Parameters:**

  | 필드명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :---: | :--- |
  | measurement_id | uuid | Y | 혈당 측정 기록 ID |

- **Response:** `204 No Content`
