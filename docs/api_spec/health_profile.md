### Health Profile API 명세서

사용자의 건강 프로필(성별, 생년월일, 키, 몸무게, 질환 여부 등) 관리 API입니다.

---

#### 1. 건강 프로필 생성
- **Endpoint:** `POST /api/v1/health-profiles`
- **Description:** 사용자의 건강 프로필을 최초로 생성합니다.
- **Security:** Bearer Token (JWT Access Token)
- **Request Header:**
  - `Authorization: Bearer <access_token>`
- **Request Body:**

  | 필드명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :---: | :--- |
  | gender | string | Y | 성별 (Enum: MALE, FEMALE) |
  | birth_date | string (date) | Y | 생년월일 (YYYY-MM-DD) |
  | height | decimal | Y | 키 (0.1 ~ 300.0) |
  | weight | decimal | Y | 몸무게 (0.1 ~ 500.0) |
  | has_diabetes | boolean | Y | 당뇨 여부 |
  | has_hypertension | boolean | Y | 고혈압 여부 |

- **Example Request Body:**
  ```json
  {
    "gender": "MALE",
    "birth_date": "1990-01-01",
    "height": 175.5,
    "weight": 70.0,
    "has_diabetes": false,
    "has_hypertension": false
  }
  ```

- **Response:** `201 Created`
- **Example Response Body:**
  ```json
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "gender": "MALE",
    "birth_date": "1990-01-01",
    "height": 175.5,
    "weight": 70.0,
    "has_diabetes": false,
    "has_hypertension": false,
    "created_at": "2024-07-15T18:00:00Z",
    "updated_at": "2024-07-15T18:00:00Z"
  }
  ```

---

#### 2. 건강 프로필 조회
- **Endpoint:** `GET /api/v1/health-profiles`
- **Description:** 현재 로그인된 사용자의 건강 프로필 정보를 조회합니다.
- **Security:** Bearer Token (JWT Access Token)
- **Request Header:**
  - `Authorization: Bearer <access_token>`
- **Response:** `200 OK`
- **Example Response Body:**
  ```json
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "gender": "MALE",
    "birth_date": "1990-01-01",
    "height": 175.5,
    "weight": 70.0,
    "has_diabetes": false,
    "has_hypertension": false,
    "created_at": "2024-07-15T18:00:00Z",
    "updated_at": "2024-07-15T18:00:00Z"
  }
  ```

---

#### 3. 건강 프로필 수정
- **Endpoint:** `PATCH /api/v1/health-profiles`
- **Description:** 사용자의 건강 프로필 정보를 업데이트합니다. (키, 몸무게, 당뇨/고혈압 여부)
- **Security:** Bearer Token (JWT Access Token)
- **Request Header:**
  - `Authorization: Bearer <access_token>`
- **Request Body:**

  | 필드명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :---: | :--- |
  | height | decimal | N | 키 (0.1 ~ 300.0) |
  | weight | decimal | N | 몸무게 (0.1 ~ 500.0) |
  | has_diabetes | boolean | N | 당뇨 여부 |
  | has_hypertension | boolean | N | 고혈압 여부 |

- **Example Request Body:**
  ```json
  {
    "height": 180.0,
    "weight": 75.0,
    "has_diabetes": true
  }
  ```

- **Response:** `200 OK`
- **Example Response Body:**
  ```json
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "gender": "MALE",
    "birth_date": "1990-01-01",
    "height": 180.0,
    "weight": 75.0,
    "has_diabetes": true,
    "has_hypertension": false,
    "created_at": "2024-07-15T18:00:00Z",
    "updated_at": "2024-07-15T18:10:00Z"
  }
  ```
