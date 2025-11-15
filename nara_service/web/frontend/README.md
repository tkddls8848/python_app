# NARA Service Frontend

Next.js + TypeScript + TailwindCSS 기반 프론트엔드

## 시작하기

### 1. 패키지 설치

```bash
npm install
```

### 2. 개발 서버 실행

```bash
npm run dev
```

브라우저에서 [http://localhost:3000](http://localhost:3000) 열기

### 3. FastAPI 백엔드 연결

백엔드 서버가 `http://localhost:8000`에서 실행 중이어야 합니다.

```bash
# 백엔드 폴더에서
cd ../backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

## 기술 스택

- **Next.js 15** - React 프레임워크
- **TypeScript** - 타입 안전성
- **TailwindCSS** - 스타일링
- **Axios** - HTTP 클라이언트

## 프로젝트 구조

```
frontend/
├── src/
│   ├── app/              # Next.js App Router
│   │   ├── layout.tsx    # 루트 레이아웃
│   │   ├── page.tsx      # 홈페이지
│   │   └── globals.css   # 전역 스타일
│   └── lib/
│       └── api.ts        # Axios 인스턴스 (FastAPI 연결)
├── public/               # 정적 파일
├── .env.local           # 환경 변수
└── package.json
```

## 빌드 및 배포

```bash
# 프로덕션 빌드
npm run build

# 프로덕션 서버 실행
npm start
```
