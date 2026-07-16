
  # AI 헬스케어 가이드 (Frontend)

  AI 헬스케어 가이드는 사용자의 건강 데이터를 관리하고 AI 기반의 분석 리포트를 제공하는 서비스의 프론트엔드 애플리케이션입니다.

  ## 주요 기능

  - **대시보드**: 건강 프로필, 혈당 기록, 월별 설문 상태를 한눈에 파악
  - **혈당 기록 관리**: 공복, 식전/식후 등 다양한 타입별 혈당 측정값 기록 및 리스트 조회
  - **연간 건강검진**: 건강검진 결과를 기록하고 상세 정보(혈압, 콜레스테롤, 간 수치 등) 확인
  - **월별 건강 설문**: 매달 건강 습관을 체크하고 데이터 누적 관리
  - **건강 프로필**: 신체 정보(키, 몸무게) 및 질환 정보 관리
  - **AI 분석 리포트**: 누적된 데이터를 기반으로 AI가 생성한 건강 분석 리포트 제공 (구현 예정 포함)
  - **마이페이지**: 개인 정보 확인 및 계정 관리련

  ## 기술 스택

  - **Framework**: React 19 (React Router 7)
  - **Build Tool**: Vite
  - **Styling**: Tailwind CSS v4
  - **Icons**: Lucide React
  - **API Client**: Fetch API 기반 커스텀 클라이언트
  - **Code Quality**: ESLint, Prettier

  ## 시작하기

  ### 환경 변수 설정

  프로젝트 루트의 `.env` 파일에 백엔드 API URL을 설정합니다.

  ```env
  VITE_BACKEND_URL=http://your-backend-api-url
  ```

  ### 설치 및 실행

  ```bash
  # 의존성 설치
  npm install

  # 개발 서버 실행
  npm run dev

  # 프로덕션 빌드
  npm run build
  ```

  ## 프로젝트 구조

  ```text
  src/
  ├── pages/          # 페이지 컴포넌트
  ├── shared/         # 공통 리소스
  │   ├── api/        # API 요청 함수 및 클라이언트
  │   ├── components/ # 공통 UI 및 레이아웃 컴포넌트
  │   └── utils/      # 날짜, 포맷팅 등 공통 유틸리티
  ├── styles/         # 전역 CSS 및 테마 설정
  ├── App.tsx         # 앱 진입점 및 컨테이너
  └── routes.tsx      # 라우팅 설정
  ```

  ## 개발 가이드

  ### 코드 스타일 및 린트

  프로젝트의 코드 품질 유지를 위해 ESLint와 Prettier를 사용합니다.

  - **린트 검사**: `npm run lint`
  - **코드 포맷팅**: `npm run format`

  커밋 시 `pre-commit` 훅을 통해 자동으로 린트 검사가 수행됩니다.

  ### API 요청

  `src/shared/api/client.ts`의 공통 `request` 함수를 사용합니다. 401 에러 발생 시 자동으로 토큰 갱신 시도 및 재시도 로직이 포함되어 있습니다.

  ### 날짜 및 시간 처리

  `src/shared/utils/format.ts`의 `formatDate`, `formatDateTime` 함수를 사용하여 일관된 날짜 형식을 제공합니다.
