# NARA Service API

FastAPI 기반 백엔드 API 서버

## 설치

```bash
# 가상환경 생성 (권장)
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt
```

## 환경 설정

```bash
# .env 파일 생성
cp .env.example .env
```

## 실행

```bash
# 개발 서버 실행
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

서버가 실행되면 다음 주소에서 확인할 수 있습니다:
- API: http://localhost:8000
- API 문서 (Swagger): http://localhost:8000/docs
- API 문서 (ReDoc): http://localhost:8000/redoc

## 프로젝트 구조

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI 애플리케이션 진입점
│   ├── api/                 # API 라우트
│   │   ├── __init__.py
│   │   └── routes/          # API 엔드포인트
│   │       └── __init__.py
│   ├── core/                # 핵심 설정
│   │   ├── __init__.py
│   │   └── config.py        # 앱 설정
│   ├── models/              # 데이터베이스 모델
│   │   └── __init__.py
│   └── schemas/             # Pydantic 스키마
│       └── __init__.py
├── .env.example             # 환경 변수 예제
└── requirements.txt         # Python 의존성
```
