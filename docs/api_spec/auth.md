### Auth API 명세서

인증 및 계정 관련 API입니다.

---

#### 1. 회원가입
- **Endpoint:** `POST /api/v1/auth/signup`
- **Description:** 새로운 사용자로 가입합니다.
- **Request Body:**

  | 필드명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :---: | :--- |
  | email | string | Y | 이메일 (최대 40자) |
  | password | string | Y | 비밀번호 (최소 8자, 영문/숫자/특수문자 포함) |
  | name | string | Y | 이름 (최대 20자) |
  | nickname | string | Y | 닉네임 (최대 10자) |
  | phone_number | string | Y | 전화번호 (+821012345678 형식) |

- **Example Request Body:**
  ```json
  {
    "email": "user@example.com",
    "password": "Password123!",
    "name": "홍길동",
    "nickname": "길동이",
    "phone_number": "+821012345678"
  }
  ```

- **Response:** `201 Created`
- **Example Response Body:**
  ```json
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "email": "user@example.com",
    "name": "홍길동",
    "nickname": "길동이"
  }
  ```

---

#### 2. 회원가입 인증 메일 발송
- **Endpoint:** `POST /api/v1/auth/signup/send-verification-mail`
- **Description:** 회원가입을 위한 이메일 인증 코드를 발송합니다.
- **Request Body:**

  | 필드명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :---: | :--- |
  | email | string | Y | 이메일 (최대 40자) |

- **Example Request Body:**
  ```json
  {
    "email": "user@example.com"
  }
  ```

- **Response:** `201 Created`

---

#### 3. 회원가입 이메일 인증 확인
- **Endpoint:** `POST /api/v1/auth/signup/verify-email`
- **Description:** 발송된 인증 코드를 확인합니다.
- **Request Body:**

  | 필드명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :---: | :--- |
  | email | string | Y | 이메일 |
  | code | string | Y | 인증 코드 (6자리 숫자 문자열) |

- **Example Request Body:**
  ```json
  {
    "email": "user@example.com",
    "code": "123456"
  }
  ```

- **Response:** `204 No Content`

---

#### 4. 로그인
- **Endpoint:** `POST /api/v1/auth/login`
- **Description:** 이메일과 비밀번호로 로그인합니다. 성공 시 `access_token`이 반환되며, `refresh_token`은 HttpOnly 쿠키에 저장됩니다.
- **Request Body:**

  | 필드명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :---: | :--- |
  | email | string | Y | 이메일 |
  | password | string | Y | 비밀번호 |

- **Example Request Body:**
  ```json
  {
    "email": "user@example.com",
    "password": "Password123!"
  }
  ```

- **Response:** `200 OK`
- **Response Headers:**
  - `Set-Cookie: refresh_token=...; HttpOnly; Secure; SameSite=Lax; Max-Age=...`
- **Example Response Body:**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
  ```

---

#### 5. 회원 탈퇴
- **Endpoint:** `POST /api/v1/auth/withdraw`
- **Description:** 현재 로그인된 사용자의 계정을 탈퇴 처리합니다.
- **Security:** Bearer Token (JWT Access Token)
- **Request Header:**
  - `Authorization: Bearer <access_token>`
- **Request Body:**

  | 필드명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :---: | :--- |
  | reason | string | Y | 탈퇴 사유 (Enum: WithdrawalReason - NOT_USE, INCONVENIENCE, LACK_OF_FEATURES, BUG_OR_ERROR, FOUND_ALTERNATIVE, GOAL_ACHIEVED, PRIVACY_CONCERN, TOO_MANY_NOTIFICATIONS, OTHER) |
  | reason_detail | string | N | 상세 사유 |
  | feedback | string | N | 서비스 피드백 |

- **Example Request Body:**
  ```json
  {
    "reason": "INCONVENIENCE",
    "reason_detail": "UI가 불편합니다.",
    "feedback": "더 나은 서비스를 기대합니다."
  }
  ```

- **Response:** `204 No Content`

---

#### 6. 계정 복구 인증 메일 발송
- **Endpoint:** `POST /api/v1/auth/recovery/send-mail`
- **Description:** 계정 복구를 위한 이메일 인증 코드를 발송합니다.
- **Request Body:**

  | 필드명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :---: | :--- |
  | email | string | Y | 이메일 |

- **Example Request Body:**
  ```json
  {
    "email": "user@example.com"
  }
  ```

- **Response:** `200 OK`

---

#### 7. 계정 복구 이메일 인증 확인
- **Endpoint:** `POST /api/v1/auth/recovery/verify-mail`
- **Description:** 계정 복구를 위해 발송된 인증 코드를 확인하고 복구 처리합니다.
- **Request Body:**

  | 필드명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :---: | :--- |
  | email | string | Y | 이메일 |
  | code | string | Y | 인증 코드 |

- **Example Request Body:**
  ```json
  {
    "email": "user@example.com",
    "code": "123456"
  }
  ```

- **Response:** `204 No Content`

---

#### 8. 토큰 갱신
- **Endpoint:** `GET /api/v1/auth/token/refresh`
- **Description:** 쿠키에 저장된 `refresh_token`을 사용하여 새로운 `access_token`을 발급받습니다.
- **Request Header:**
  - `Cookie: refresh_token=<your_refresh_token>`
- **Response:** `200 OK`
- **Example Response Body:**
  ```json
  {
    "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
  }
  ```
