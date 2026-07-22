### Health Survey API 명세서

사용자의 월간 건강 설문(흡연, 음주, 혈압 등) 관리 API입니다.

---

#### 1. 월간 건강 설문 생성
- **Endpoint:** `POST /api/v1/health-surveys`
- **Description:** 월간 건강 설문을 작성합니다. 흡연 및 음주 여부에 따라 추가 상세 정보를 입력해야 합니다.
- **Security:** Bearer Token (JWT Access Token)
- **Request Header:**
  - `Authorization: Bearer <access_token>`
- **Request Body:**

  | 필드명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :---: | :--- |
  | smoking_status | string | Y | 흡연 상태 (Enum: HabitStatus - NEVER, FORMER, CURRENT) |
  | smoking_fr_per_day | integer | N | 하루 흡연량 (smoking_status가 CURRENT인 경우 필수) |
  | drinking_status | string | Y | 음주 상태 (Enum: HabitStatus) |
  | drinking_frequency | string | Y | 음주 빈도 (Enum: DrinkingFrequency - LESS_THAN_MONTHLY, MONTHLY, MONTHLY_2_TO_4, WEEKLY_2_TO_3, WEEKLY_4_OR_MORE, NOT_APPLICABLE) |
  | drinking_amount_per_session | integer | N | 1회 음주량 (drinking_status가 CURRENT인 경우 필수) |
  | systolic_bp | integer | Y | 수축기 혈압 |
  | diastolic_bp | integer | Y | 이완기 혈압 |

- **Example Request Body:**
  ```json
  {
    "smoking_status": "CURRENT",
    "smoking_fr_per_day": 10,
    "drinking_status": "CURRENT",
    "drinking_frequency": "WEEKLY_2_TO_3",
    "drinking_amount_per_session": 5,
    "systolic_bp": 120,
    "diastolic_bp": 80
  }
  ```

- **Response:** `201 Created`
- **Example Response Body:**
  ```json
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "title": "2024년 07월 건강 설문",
    "created_at": "2024-07-15T18:00:00Z"
  }
  ```

---

#### 2. 월간 건강 설문 목록 조회
- **Endpoint:** `GET /api/v1/health-surveys`
- **Description:** 사용자가 작성한 월간 건강 설문 목록을 조회합니다. 연도별 필터링이 가능합니다.
- **Security:** Bearer Token (JWT Access Token)
- **Request Header:**
  - `Authorization: Bearer <access_token>`
- **Query Parameters:**

  | 필드명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :---: | :--- |
  | start_year | integer | N | 시작 연도 (2000 이상) |
  | end_year | integer | N | 종료 연도 (2000 이상) |

- **Example Request:** `GET /api/v1/health-surveys?start_year=2024`

- **Response:** `200 OK`
- **Example Response Body:**
  ```json
  [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "title": "2024년 07월 건강 설문",
      "created_at": "2024-07-15T18:00:00Z"
    }
  ]
  ```

---

#### 3. 월간 건강 설문 상세 조회
- **Endpoint:** `GET /api/v1/health-surveys/{survey_id}`
- **Description:** 특정 월간 건강 설문의 상세 내용을 조회합니다.
- **Security:** Bearer Token (JWT Access Token)
- **Request Header:**
  - `Authorization: Bearer <access_token>`
- **Path Parameters:**

  | 필드명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :---: | :--- |
  | survey_id | uuid | Y | 건강 설문 ID |

- **Response:** `200 OK`
- **Example Response Body:**
  ```json
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "title": "2024년 07월 건강 설문",
    "created_at": "2024-07-15T18:00:00Z",
    "smoking_status": "하고 있음",
    "smoking_fr_per_day": 10,
    "drinking_status": "하고 있음",
    "drinking_frequency": "주 2~3회",
    "drinking_amount_per_session": 5,
    "systolic_bp": 120,
    "diastolic_bp": 80
  }
  ```
