# 나라장터 API 크롤러

나라장터 API 문서를 자동으로 크롤링하여 JSON, XML, Markdown 형식으로 저장하는 도구입니다.

## 기능

- Swagger JSON 객체 자동 추출
- API 기본 정보 및 엔드포인트 정보 추출
- 다양한 형식(JSON, XML, Markdown)으로 저장
- 제공기관별 자동 분류
- 범위 내 모든 API 문서 자동 크롤링
- 병렬 처리로 빠른 크롤링

## 설치

1. Python 3.8 이상 설치
2. 의존성 패키지 설치:
   ```bash
   pip install -r requirements.txt
   ```
3. Chrome 브라우저 설치

## 사용 방법

### 범위 크롤링 (권장)

```bash
python main.py -s <시작번호> -e <끝번호>
```

예시:
```bash
# 15129300부터 15129400까지 크롤링
python main.py -s 15129300 -e 15129400

# 동시 작업자 수 지정
python main.py -s 15129300 -e 15129400 --workers 15

# 특정 형식만 저장
python main.py -s 15129300 -e 15129400 --formats json md
```

### 옵션

- `-s, --start`: 시작 문서 번호 (필수)
- `-e, --end`: 끝 문서 번호 (필수)
- `--output-dir`: 출력 디렉토리 (기본값: output)
- `--formats`: 저장할 파일 형식 (기본값: json xml md)
- `--workers`: 동시 작업자 수 (기본값: 10, 최대: 30)
- `--no-headless`: 헤드리스 모드 비활성화
- `--timeout`: 페이지 로드 타임아웃 (초) (기본값: 30)

## 출력 구조

```
output/
├── crawling_summary.json    # 크롤링 결과 요약
├── failed_urls.txt         # 실패한 URL 목록
└── [제공기관명]/
    ├── json/
    │   └── [API_ID]_api_docs.json
    ├── xml/
    │   └── [API_ID]_api_docs.xml
    └── markdown/
        └── [API_ID]_api_docs.md
```

## 주의사항

1. Chrome 브라우저가 설치되어 있어야 합니다.
2. 인터넷 연결이 필요합니다.
3. 일부 웹사이트는 크롤링을 제한할 수 있습니다.
4. API 문서의 구조에 따라 일부 정보가 누락될 수 있습니다.
5. 동시 작업자 수는 시스템 성능을 고려하여 설정하세요.

## 라이선스

MIT License 