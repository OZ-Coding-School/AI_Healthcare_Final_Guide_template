### Annual Health Screening API 명세서

사용자의 건강 검진(국가 건강 검진 등) 결과 관리 API입니다.

---

#### 1. 건강 검진 데이터 생성
- **Endpoint:** `POST /api/v1/annual-health-screenings`
- **Description:** 건강 검진 결과를 기록합니다. 키, 몸무게, 혈압, 혈당, 콜레스테롤, 간 기능 등 상세 검사 수치를 포함합니다.
- **Security:** Bearer Token (JWT Access Token)
- **Request Header:**
  - `Authorization: Bearer <access_token>`
- **Request Body:**

  | 필드명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :---: | :--- |
  | height | decimal | Y | 키 (0.1 ~ 300.0) |
  | weight | decimal | Y | 몸무게 (0.1 ~ 500.0) |
  | bmi | decimal | Y | 체질량지수 (0.1 ~ 100.0) |
  | waist_circumference | decimal | Y | 허리둘레 (0.1 ~ 200.0) |
  | sbp | integer | Y | 수축기 혈압 |
  | dbp | integer | Y | 이완기 혈압 |
  | fbs | integer | Y | 공복 혈당 |
  | hba1c | decimal | Y | 당화혈색소 |
  | triglyceride | integer | Y | 중성지방 |
  | ldl | integer | Y | LDL 콜레스테롤 |
  | hdl | integer | Y | HDL 콜레스테롤 |
  | total_cholesterol | integer | Y | 총 콜레스테롤 |
  | ast | integer | Y | AST (간기능) |
  | alt | integer | Y | ALT (간기능) |
  | creatinine | decimal | Y | 크레아티닌 |
  | urine_protein | string | Y | 요단백 (Enum: UrineProteinStatus - NEGATIVE, TRACE, POSITIVE_1, POSITIVE_2, POSITIVE_3, POSITIVE_4) |
  | urine_glucose | string | Y | 요당 (Enum: UrineGlucoseStatus - NEGATIVE, TRACE, POSITIVE_1, POSITIVE_2, POSITIVE_3, POSITIVE_4) |
  | family_history_diabetes | boolean | Y | 당뇨 가족력 여부 |
  | family_history_hypertension | boolean | Y | 고혈압 가족력 여부 |
  | screening_at | string (date) | Y | 검진 일자 (YYYY-MM-DD) |
  | is_fasting | boolean | Y | 공복 여부 |

- **Example Request Body:**
  ```json
  {
    "height": 175.5,
    "weight": 70.0,
    "bmi": 22.7,
    "waist_circumference": 85.0,
    "sbp": 120,
    "dbp": 80,
    "fbs": 95,
    "hba1c": 5.4,
    "triglyceride": 150,
    "ldl": 100,
    "hdl": 60,
    "total_cholesterol": 190,
    "ast": 25,
    "alt": 20,
    "creatinine": 1.0,
    "urine_protein": "NEGATIVE",
    "urine_glucose": "NEGATIVE",
    "family_history_diabetes": false,
    "family_history_hypertension": false,
    "screening_at": "2024-05-20",
    "is_fasting": true
  }
  ```

- **Response:** `201 Created`
- **Example Response Body:**
  ```json
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "title": "2024년 건강 검진 결과",
    "screening_at": "2024-05-20",
    "created_at": "2024-07-15T18:00:00Z"
  }
  ```

---

#### 2. 건강 검진 목록 조회
- **Endpoint:** `GET /api/v1/annual-health-screenings`
- **Description:** 사용자가 기록한 건강 검진 결과 목록을 조회합니다.
- **Security:** Bearer Token (JWT Access Token)
- **Request Header:**
  - `Authorization: Bearer <access_token>`
- **Response:** `200 OK`
- **Example Response Body:**
  ```json
  [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "title": "2024년 건강 검진 결과",
      "screening_at": "2024-05-20",
      "created_at": "2024-07-15T18:00:00Z"
    }
  ]
  ```

---

#### 3. 건강 검진 상세 조회
- **Endpoint:** `GET /api/v1/annual-health-screenings/{screening_id}`
- **Description:** 특정 건강 검진 기록의 상세 수치를 조회합니다.
- **Security:** Bearer Token (JWT Access Token)
- **Request Header:**
  - `Authorization: Bearer <access_token>`
- **Path Parameters:**

  | 필드명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :---: | :--- |
  | screening_id | uuid | Y | 건강 검진 기록 ID |

- **Response:** `200 OK`
- **Example Response Body:**
  ```json
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "title": "2024년 건강 검진 결과",
    "screening_at": "2024-05-20",
    "created_at": "2024-07-15T18:00:00Z",
    "height": 175.5,
    "weight": 70.0,
    "bmi": 22.7,
    "waist_circumference": 85.0,
    "sbp": 120,
    "dbp": 80,
    "fbs": 95,
    "hba1c": 5.4,
    "triglyceride": 150,
    "ldl": 100,
    "hdl": 60,
    "total_cholesterol": 190,
    "ast": 25,
    "alt": 20,
    "creatinine": 1.0,
    "urine_protein": "음성",
    "urine_glucose": "음성",
    "family_history_diabetes": false,
    "family_history_hypertension": false,
    "is_fasting": true
  }
  ```
