# 나라장터 API 크롤러 워크플로우

## 📋 전체 시스템 구조

```
나라장터 API 크롤러
├── main.py (메인 실행부)
├── parser.py (파싱 및 데이터 추출)
└── 출력 데이터
    ├── 일반API/ (Swagger API)
    ├── 일반API_old/ (일반 API)
    ├── LINK/ (링크 타입 API)
    ├── CSV/ (통합 테이블 정보)
    ├── 기타/ (기타 타입)
    └── uddi.txt (UDDI 값 로그)
```

## 🚀 1. 시스템 초기화 단계

### 1.1 명령행 인자 처리
```
사용자 입력 받기:
├── 시작/끝 문서번호 (-s, -e) [필수]
├── 출력 디렉토리 (-o) [기본값: output]
├── 저장 형식 (--formats) [기본값: json, xml, md, csv]
├── 동시 작업자 수 (-w) [기본값: 20, 범위: 10-40]
├── 헤드리스 모드 (--no-headless)
└── 타임아웃 설정 (--timeout) [기본값: 5초]
```

### 1.2 URL 생성 및 검증
```
URL 생성:
├── 기본 패턴: https://www.data.go.kr/data/{번호}/openapi.do
├── 범위 내 모든 번호에 대해 URL 생성
└── 입력값 검증:
    ├── 시작번호 ≤ 끝번호 체크
    ├── 작업자 수 10-40 범위 체크
    └── 범위 초과시 기본값(20)으로 설정
```

### 1.3 리소스 초기화
```
시스템 리소스 준비:
├── OptimizedDriverPool 생성 (pool_size=max_workers)
├── MemoryManager 초기화 (임계값: 2GB)
├── ThreadPoolExecutor 설정 (max_workers)
└── 결과 저장용 변수 초기화:
    ├── 성공/실패 카운터
    ├── API 유형별 카운터
    └── 시작 시간 기록
```

## 🔄 2. 병렬 크롤링 처리 단계

### 2.1 멀티스레딩 실행
```
ThreadPoolExecutor:
├── 최대 작업자 수: 10-40개 (사용자 설정)
├── 각 URL에 대해 crawl_url() 함수 실행
├── 진행상황 모니터링 (tqdm 진행바)
├── 메모리 사용량 주기적 체크 (10개마다)
└── 임계값 초과시 즉시 메모리 정리
```

### 2.2 WebDriver 풀 관리 (개선됨)
```
OptimizedDriverPool:
├── 드라이버 생성 최적화:
│   ├── 헤드리스 모드 강제 적용
│   ├── 리소스 차단 (이미지, CSS, 플러그인)
│   ├── 백그라운드 처리 비활성화
│   ├── IPC flooding 보호 비활성화
│   └── 로그 레벨 최소화 (level=3)
├── 풀 관리:
│   ├── 드라이버 할당/반환 (timeout=5초)
│   ├── 풀 부족시 새 드라이버 즉시 생성
│   ├── 반환시 세션 정리 (쿠키, 캐시)
│   └── 풀 크기 초과시 드라이버 즉시 종료
└── 안전한 종료:
    ├── 모든 드라이버 큐에서 제거
    ├── 각 드라이버 개별 종료
    └── 예외 처리로 안전 보장
```

## 🔍 3. 단일 URL 크롤링 프로세스

### 3.1 페이지 접근 및 로딩
```
페이지 로딩:
├── WebDriver 풀에서 드라이버 할당
├── URL 접근 및 페이지 로딩
├── body 태그 존재 대기 (5초 타임아웃)
├── 1초 추가 안정화 대기
└── NaraParser 인스턴스 생성
```

### 3.2 **Step 1: 테이블 정보 추출 (최우선)**
```
테이블 정보 추출:
├── CSS 선택자로 테이블 검색 (table.dataset-table)
├── 각 행의 th/td 태그에서 키-값 쌍 추출
├── 특수 처리:
│   ├── 전화번호: JavaScript 처리된 값 (#telNoDiv)
│   └── 링크: 링크 텍스트만 추출
├── UDDI 값 추출 (개선됨):
│   ├── API 유형이 LINK가 아닌 경우에만 실행
│   ├── 우선순위 1: <input id="publicDataDetailPk" value="[uddi]"/>
│   ├── 우선순위 2: 모든 hidden input에서 패턴 매칭
│   │   ├── "publicDataDetailPk" 포함
│   │   ├── "uddi" 포함
│   │   └── "detailpk" 포함
│   ├── 추출 성공시 uddi.txt 파일에 기록:
│   │   └── 형식: {UDDI값}\t{URL}\t{시간}
│   └── 실패시 조용히 넘어감
└── API 유형 필드 확인 및 로깅
```

### 3.3 **Step 2: API 유형 판별 및 분기 처리**
```
API 유형 체크:
├── 'API 유형' 필드에서 'LINK' 키워드 확인
├── LINK 타입인 경우:
│   ├── api_type = 'link' 설정
│   ├── skip_reason = 'LINK 타입 API는 테이블 정보만 수집'
│   ├── 데이터 저장 (모든 형식)
│   ├── 즉시 성공 반환 (조기 종료)
│   └── 추가 크롤링 완전 건너뛰기
└── LINK가 아닌 경우: Step 3으로 진행
```

### 3.4 **Step 3: Swagger JSON 추출 시도 (개선됨)**
```
Swagger JSON 추출 (우선순위 순):
├── 1. JavaScript 변수에서 직접 추출:
│   ├── swaggerJson 전역 변수 확인
│   ├── 타입 체크 (string vs object)
│   ├── 문자열인 경우 JSON.parse() 실행
│   ├── 빈 문자열 체크 및 제외
│   └── 유효한 객체만 반환
├── 2. Script 태그에서 패턴 매칭:
│   ├── 모든 script 태그 스캔
│   ├── 빈 값 패턴 우선 체크:
│   │   ├── var swaggerJson = "";
│   │   ├── swaggerJson = "";
│   │   ├── var swaggerJson = ``;
│   │   └── swaggerJson = ``;
│   ├── JSON 추출 패턴들:
│   │   ├── var swaggerJson = {...};
│   │   ├── swaggerJson = {...};
│   │   ├── swaggerJson: {...}
│   │   ├── var swaggerJson = `{...}`;
│   │   └── swaggerJson = `{...}`;
│   ├── 정규식 매칭 및 JSON 파싱
│   └── 유효성 검증 후 반환
├── 3. window.swaggerUi 객체에서 추출:
│   └── window.swaggerUi.spec 확인
└── 4. 외부 URL에서 추출:
    ├── SwaggerUIBundle 설정에서 URL 추출
    ├── 상대 경로를 절대 경로로 변환
    ├── HTTP 요청으로 JSON 다운로드 (timeout=10초)
    └── 인라인 spec 객체 추출
```

### 3.5 **Step 4: API 정보 추출 및 구성**

#### 3.5.1 Swagger API인 경우
```
Swagger API 처리:
├── API 기본 정보 추출:
│   ├── info 섹션에서 title, description, version
│   └── x-* 확장 필드들 처리
├── Base URL 구성:
│   ├── schemes[0] + host + basePath
│   └── 기본값: https 스킴 사용
├── 엔드포인트 정보 추출:
│   ├── paths 객체의 각 경로 처리
│   ├── HTTP 메서드별 (GET, POST, PUT, DELETE, PATCH) 정보:
│   │   ├── summary/description → description
│   │   ├── parameters → 파라미터 목록
│   │   ├── responses → 응답 목록
│   │   ├── tags → 섹션 분류
│   │   └── section = tags[0] 또는 'Default'
│   ├── 파라미터 정보: name, description, required, type
│   └── 응답 정보: status_code, description
├── api_type = 'swagger' 설정
└── 완전한 API 문서 구성
```

#### 3.5.2 일반 API인 경우 (Swagger 없음)
```
일반 API 정보 추출:
├── 상세기능 정보 추출:
│   ├── #open-api-detail-result div 검색
│   ├── h4.tit에서 API 설명 추출
│   ├── .box-gray .dot-list에서 상세 정보:
│   │   ├── 활용승인 절차:
│   │   │   ├── 정규식: 개발단계\s*:\s*([^/]+)
│   │   │   └── 정규식: 운영단계\s*:\s*(.+)
│   │   ├── 신청가능 트래픽:
│   │   │   ├── 정규식: 개발계정\s*:\s*([^/]+)
│   │   │   └── 정규식: 운영계정\s*:\s*(.+)
│   │   ├── 요청주소 추출
│   │   └── 서비스URL 추출
├── 요청변수 테이블 추출:
│   ├── "요청변수" + "Request Parameter" 헤더 검색
│   ├── following-sibling div.col-table 테이블 찾기
│   ├── tbody의 각 행에서 6개 열 추출:
│   │   ├── 항목명(국문), 항목명(영문)
│   │   ├── 항목크기, 항목구분(필/옵)
│   │   ├── 샘플데이터, 항목설명
│   │   └── 빈 값이 아닌 경우만 추가
├── 출력결과 테이블 추출:
│   ├── "출력결과" + "Response Element" 헤더 검색
│   ├── 동일한 구조로 응답 요소 정보 추출
│   └── 빈 값이 아닌 경우만 추가
└── api_type = 'general' 설정
```

### 3.6 **Step 5: 데이터 검증 및 실패 처리**
```
데이터 검증:
├── 일반 API의 경우 정보 충분성 체크:
│   ├── detail_info 존재 여부
│   ├── request_parameters 존재 여부
│   └── response_elements 존재 여부
├── 정보 부족시:
│   ├── failed_urls.txt에 URL 기록 (append 모드)
│   ├── 에러 메시지 추가
│   └── False 반환으로 실패 처리
└── 충분한 정보가 있으면 데이터 저장 진행
```

## 💾 4. 데이터 저장 단계 (개선됨)

### 4.1 저장 경로 결정 로직
```
디렉토리 구조 결정:
├── API 유형별 분류 (개선됨):
│   ├── api_type == 'link' 또는 'LINK' in API유형
│   │   └── → output/LINK/{제공기관}/
│   ├── api_type == 'general'
│   │   └── → output/일반API_old/{제공기관}/
│   ├── api_type == 'swagger'
│   │   └── → output/일반API/{제공기관}/
│   └── 기타 → output/기타/{제공기관}/
├── 제공기관명 정리:
│   ├── 특수문자 제거: [^\w\s-] → ''
│   ├── 공백을 언더스코어로: [\s]+ → _
│   └── 앞뒤 공백 제거
├── 파일명 생성:
│   ├── URL에서 문서번호 추출: /data/(\d+)/openapi\.do
│   ├── 테이블에서 수정일 추출
│   └── 형식: {문서번호}_{수정일}.{확장자}
└── 디렉토리 생성: os.makedirs(exist_ok=True)
```

### 4.2 다중 형식 저장
```
파일 형식별 저장:
├── JSON 형식:
│   ├── 원본 데이터 구조 완전 유지
│   ├── UTF-8 인코딩
│   ├── 들여쓰기 2칸 적용
│   └── ensure_ascii=False
├── XML 형식:
│   ├── 딕셔너리를 XML 요소로 재귀 변환
│   ├── 특수문자 및 유효하지 않은 태그명 정리:
│   │   ├── [^a-zA-Z0-9_-] → _
│   │   ├── 숫자로 시작하는 태그 → item_{태그명}
│   │   └── 빈 태그명 → unnamed_item
│   ├── 리스트 처리: item_0, item_1, ...
│   ├── minidom으로 예쁜 포맷팅
│   └── UTF-8 인코딩으로 저장
├── Markdown 형식:
│   ├── API 유형별 템플릿 적용
│   ├── 테이블 형태로 파라미터 정보 표시
│   ├── 가독성 좋은 문서 구조
│   └── UTF-8 인코딩
└── CSV 형식 (통합):
    ├── 모든 문서의 테이블 정보를 하나의 파일에 누적
    ├── 저장 위치: output/CSV/all_table_info.csv
    ├── CP949 인코딩 (MS Office 호환성)
    ├── 헤더: 문서번호, 크롤링시간, URL + 표준 필드들
    ├── 파일 존재시 헤더 건너뛰고 데이터만 추가
    └── 표준 필드: 분류체계, 제공기관, 관리부서명, 전화번호, API유형, 등록일, 수정일 등
```

### 4.3 Markdown 변환 상세 프로세스

#### 4.3.1 LINK 타입 Markdown
```
LINK 타입 문서 구성:
├── 제목: "# LINK 타입 API"
├── 크롤링 정보 (시간, URL)
├── 📋 API 정보 섹션
├── 📊 상세 정보 테이블 (테이블 정보 key-value)
├── ℹ️ 처리 정보 (skip_reason)
└── 📝 생성 정보 푸터 (API ID, 타입)
```

#### 4.3.2 Swagger API Markdown
```
Swagger 문서 구성:
├── 제목: API title
├── 크롤링 정보 (시간, URL)
├── 📋 API 기본 정보:
│   ├── 설명 (줄바꿈 제거)
│   ├── Base URL (코드 블록)
│   └── 지원 프로토콜
├── 🔗 API 엔드포인트 섹션:
│   ├── Base URL 표시
│   ├── 섹션별 그룹화 (tags 기준)
│   ├── 각 엔드포인트별:
│   │   ├── HTTP 메서드와 경로
│   │   ├── 완전한 URL 표시
│   │   ├── 설명 (줄바꿈 제거)
│   │   ├── 파라미터 테이블:
│   │   │   └── | 이름 | 타입 | 필수 | 설명 |
│   │   ├── 응답 테이블:
│   │   │   └── | 상태 코드 | 설명 |
│   │   └── 구분선 (---)
└── 📝 생성 정보 푸터
```

#### 4.3.3 일반 API Markdown
```
일반 API 문서 구성:
├── 제목: 기능 설명 (50자 제한 + ...)
├── 크롤링 정보 (시간, URL)
├── 📋 API 상세정보:
│   ├── 기능 설명
│   ├── 요청 주소 (코드 블록)
│   ├── 서비스 URL (코드 블록)
│   ├── 활용승인 절차 (개발/운영단계)
│   └── 신청가능 트래픽 (개발/운영계정)
├── 📤 요청변수 테이블:
│   └── | 항목명(국문) | 항목명(영문) | 크기 | 필수여부 | 샘플데이터 | 설명 |
├── 📥 출력결과 테이블:
│   └── | 항목명(국문) | 항목명(영문) | 크기 | 필수여부 | 샘플데이터 | 설명 |
└── 📝 생성 정보 푸터 (API 타입: 일반 API)
```

## 📊 5. 결과 집계 및 보고 단계

### 5.1 실시간 모니터링
```
진행상황 추적:
├── tqdm 진행바로 실시간 표시
├── 10개 처리마다 메모리 정리 (gc.collect())
├── 메모리 사용량이 2GB 초과시 즉시 정리
├── 성공/실패 카운트 실시간 업데이트
└── 예외 발생한 URL 별도 기록
```

### 5.2 결과 요약 생성 (개선됨)
```
crawling_summary.json 생성:
├── 처리 통계:
│   ├── total: 총 처리 URL 수
│   ├── success: 성공 개수
│   ├── failed: 실패 개수
│   ├── link_type, swagger_type, general_type: 유형별 카운터
│   ├── insufficient_info: 정보부족 개수 (failed_urls.txt 기준)
│   └── success_rate: 성공률 (백분율)
├── 시간 정보:
│   ├── start_time: 시작 시간
│   └── end_time: 종료 시간
├── failed_urls: 예외 발생 URL 목록
└── 향후 확장 가능한 구조
```

### 5.3 실패 URL 관리 (개선됨)
```
실패 URL 분류 저장:
├── failed_urls.txt: 정보 부족으로 실패한 URL
│   ├── crawl_url() 함수 내에서 직접 기록
│   ├── API 정보를 찾을 수 없는 경우
│   └── 재처리 가능한 케이스
├── exception_urls.txt: 예외 발생으로 실패한 URL
│   ├── main() 함수에서 예외 캐치하여 기록
│   ├── 네트워크, 파싱, 시스템 오류
│   └── 별도 디버깅 필요한 케이스
└── 각각 다른 이유로 분류하여 재처리 전략 수립 가능
```

## 🧹 6. 리소스 정리 단계

### 6.1 메모리 관리 (개선됨)
```
MemoryManager 클래스:
├── get_memory_usage(): RSS 메모리 사용량 MB 단위 반환
├── check_memory_threshold(): 2GB 임계값 체크
├── cleanup(): gc.collect() 실행
├── 주기적 모니터링:
│   ├── 10개 처리마다 체크
│   ├── 임계값 초과시 즉시 정리
│   └── 정리 메시지 출력
└── 최종 정리: crawl_url() 완료시마다 실행
```

### 6.2 WebDriver 정리 (개선됨)
```
OptimizedDriverPool.close_all():
├── 큐가 빌 때까지 반복:
│   ├── get_nowait()로 드라이버 추출
│   ├── driver.quit() 개별 실행
│   └── 예외 처리로 안전 보장
├── 모든 브라우저 프로세스 정리
├── 임시 파일 자동 정리
└── 리소스 완전 해제 보장
```

## 📈 7. 최종 결과 출력 (개선됨)

### 7.1 콘솔 결과 요약
```
최종 결과 출력:
├── 🏁 배치 크롤링 완료! (헤더)
├── 📊 전체 결과:
│   ├── 📋 총 처리: {total}개 URL
│   ├── ✅ 성공: {success}개 ({success_rate})
│   ├── ❌ 실패: {failed}개
│   └── 📝 정보부족: {insufficient_info}개 (조건부 표시)
├── 📁 결과 위치: {output_dir}
├── 📋 요약 파일: crawling_summary.json
├── 📄 예외 목록: exception_urls.txt (실패가 있는 경우)
└── 📄 정보부족 목록: failed_urls.txt (정보부족이 있는 경우)
```

### 7.2 생성된 파일들
```
출력 파일 구조:
├── {API유형별 디렉토리}/
│   └── {제공기관명}/
│       ├── {문서번호}_{수정일}.json
│       ├── {문서번호}_{수정일}.xml
│       └── {문서번호}_{수정일}.md
├── CSV/
│   └── all_table_info.csv (모든 테이블 정보 통합)
├── crawling_summary.json (전체 요약)
├── failed_urls.txt (정보부족 URL)
├── exception_urls.txt (예외 발생 URL)
└── uddi.txt (UDDI 값 로그)
```

## 🔧 8. 에러 처리 및 복구

### 8.1 예외 처리 계층
```
에러 처리 단계:
├── 개별 URL 레벨:
│   ├── crawl_url() 함수 전체 try-catch
│   ├── 각 추출 단계별 개별 try-catch
│   └── 실패시 False 반환으로 격리
├── 스레드 레벨:
│   ├── Future.result() 예외 캐치
│   ├── 예외 URL을 failed_urls에 기록
│   └── 다른 스레드에 영향 없이 계속 진행
├── 전체 시스템 레벨:
│   ├── finally 블록에서 리소스 정리 보장
│   └── driver_pool.close_all() 항상 실행
└── 파일 저장 레벨:
    ├── 각 형식별 개별 try-catch
    └── 부분적 저장 실패시에도 다른 형식은 계속
```

### 8.2 재시도 및 복구 메커니즘
```
복구 메커니즘:
├── 드라이버 풀 관리:
│   ├── 풀 부족시 새 드라이버 즉시 생성
│   ├── 드라이버 오류시 자동 교체
│   └── 반환시 세션 정리 후 재사용
├── 네트워크 오류 처리:
│   ├── 페이지 로딩 타임아웃 (5초)
│   ├── Swagger JSON 다운로드 타임아웃 (10초)
│   └── 실패시 다음 URL 계속 처리
├── 파싱 실패 복구:
│   ├── 여러 패턴으로 Swagger JSON 추출 시도
│   ├── 실패시 일반 API 추출로 폴백
│   └── 최종 실패시 failed_urls.txt 기록
└── 메모리 관리:
    ├── 임계값 초과시 즉시 정리
    ├── 주기적 가비지 컬렉션
    └── OOM 방지 메커니즘
```

## 🎯 9. 성능 최적화 포인트

### 9.1 병렬 처리 최적화
- **WebDriver 풀링**: 드라이버 생성/종료 오버헤드 최소화 (재사용률 90%+)
- **멀티스레딩**: CPU 바운드 작업과 I/O 바운드 작업 효율적 분리
- **메모리 관리**: 주기적 가비지 컬렉션으로 메모리 누수 방지 (2GB 임계값)
- **동적 스케일링**: 풀 부족시 즉시 확장, 초과시 즉시 축소

### 9.2 크롤링 성능 향상
- **헤드리스 모드**: 브라우저 UI 비활성화로 30-50% 속도 향상
- **리소스 차단**: 이미지