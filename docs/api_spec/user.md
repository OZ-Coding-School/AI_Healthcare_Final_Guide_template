### User API 명세서

사용자 정보 관리 관련 API입니다.

---

#### 1. 내 정보 조회
- **Endpoint:** `GET /api/v1/users/me`
- **Description:** 현재 로그인된 사용자의 상세 정보를 조회합니다.
- **Security:** Bearer Token (JWT Access Token)
- **Request Header:**
  - `Authorization: Bearer <access_token>`
- **Response:** `200 OK`
- **Example Response Body:**
  ```json
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "홍길동",
    "nickname": "길동이",
    "email": "user@example.com",
    "phone_number": "+821012345678",
    "created_at": "2024-07-15T18:00:00Z"
  }
  ```

---

#### 2. 내 정보 수정
- **Endpoint:** `PATCH /api/v1/users/me`
- **Description:** 현재 로그인된 사용자의 정보를 수정합니다.
- **Security:** Bearer Token (JWT Access Token)
- **Request Header:**
  - `Authorization: Bearer <access_token>`
- **Request Body:**

  | 필드명 | 타입 | 필수여부 | 설명 |
  | :--- | :--- | :---: | :--- |
  | nickname | string | N | 닉네임 (최대 10자) |
  | phone_number | string | N | 전화번호 (+821012345678, 01012345678 등) |

- **Example Request Body:**
  ```json
  {
    "nickname": "새닉네임",
    "phone_number": "010-9876-5432"
  }
  ```

- **Response:** `200 OK`
- **Example Response Body:**
  ```json
  {
    "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
    "name": "홍길동",
    "nickname": "새닉네임",
    "email": "user@example.com",
    "phone_number": "+821098765432",
    "created_at": "2024-07-15T18:00:00Z"
  }
  ```
