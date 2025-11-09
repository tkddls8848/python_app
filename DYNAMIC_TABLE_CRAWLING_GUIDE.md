# 동적 셀렉터 테이블 크롤링 가이드

## 개요

공공데이터 포털의 일부 API 페이지는 **셀렉트 박스**로 조회 옵션을 선택하면 동적으로 테이블이 변경되는 구조입니다.

예: https://www.data.go.kr/data/15001700/openapi.do
위치: `/html/body/div[2]/div/div[2]/div/div[2]/div[4]/div[2]/div[1]/div/div[1]`

이러한 동적 테이블은 기존 BeautifulSoup 크롤러로는 수집이 불가능하며, Playwright를 사용한 동적 크롤링이 필요합니다.

---

## 크롤링 전략

### 1단계: 페이지 구조 분석
```python
from nara_crawler.hybrid.dynamic_table_crawler import DynamicTableCrawler

crawler = DynamicTableCrawler()

# 특정 위치 분석
result = await crawler.crawl_specific_location(
    url="https://www.data.go.kr/data/15001700/openapi.do",
    xpath='/html/body/div[2]/div/div[2]/div/div[2]/div[4]/div[2]/div[1]/div/div[1]'
)

# 결과 확인
print(f"셀렉트 박스: {result['data']['select_count']}개")
print(f"테이블: {result['data']['table_count']}개")

for select_info in result['data']['selects']:
    print(f"셀렉트 ID: {select_info['id']}")
    print(f"옵션 개수: {len(select_info['options'])}")
```

### 2단계: 셀렉터별 크롤링
```python
# 셀렉트 박스의 모든 옵션을 순회하며 테이블 수집
result = await crawler.crawl_dynamic_selector_table(
    url="https://www.data.go.kr/data/15001700/openapi.do",

    # 셀렉트 박스 지정 (CSS 또는 XPath)
    selector_css="select#selectId",  # 또는
    selector_xpath='//select[@id="selectId"]',

    # 테이블 컨테이너 지정
    table_container_xpath='/html/body/div[2]/div/div[2]/div/div[2]/div[4]/div[2]/div[1]/div/div[1]',

    # 셀렉터 변경 후 대기 시간 (테이블 렌더링 대기)
    wait_after_select=2.0
)

# 결과 구조
{
    'success': True,
    'data': {
        'option_value_1': {
            'option_text': '옵션 1',
            'tables': [
                {
                    'table_index': 0,
                    'data': {
                        'headers': ['컬럼1', '컬럼2', '컬럼3'],
                        'rows': [
                            ['값1', '값2', '값3'],
                            ['값4', '값5', '값6']
                        ]
                    }
                }
            ]
        },
        'option_value_2': { ... }
    }
}
```

---

## 사용 방법

### 방법 1: 독립 실행

```bash
cd /home/user/python_app
python -m nara_crawler.hybrid.dynamic_table_crawler
```

### 방법 2: 기존 크롤러 통합

`playwright_crawler.py`에 동적 테이블 크롤링 기능 추가:

```python
from .dynamic_table_crawler import DynamicTableCrawler

# PlaywrightCrawler 클래스 내부에 메서드 추가
async def extract_dynamic_selector_table(self, page: Page) -> Dict:
    """동적 셀렉터 테이블 추출"""

    # 셀렉트 박스 찾기
    selector = await page.query_selector('select#operationSelector, select.api-selector')

    if not selector:
        return {}

    dynamic_crawler = DynamicTableCrawler()
    options = await dynamic_crawler.extract_selector_options(page, selector)

    result = {}
    for option in options:
        await selector.select_option(value=option['value'])
        await asyncio.sleep(1.5)

        # 테이블 추출
        tables = await page.query_selector_all('.dynamic-table, table.result-table')
        for table in tables:
            table_data = await dynamic_crawler.extract_table_data(page, table)
            result[option['value']] = table_data

    return result
```

---

## 실전 예제: 15001700 페이지

### 1. 구조 분석
```bash
# 분석 스크립트 실행
python analyze_dynamic_table.py
```

예상 구조:
- 셀렉트 박스: "operation" 선택 (각 API 엔드포인트)
- 테이블: 선택한 operation의 파라미터 정보

### 2. 크롤링 구현

```python
async def crawl_15001700():
    crawler = DynamicTableCrawler()

    # 1단계: 구조 분석
    analysis = await crawler.crawl_specific_location(
        url="https://www.data.go.kr/data/15001700/openapi.do",
        xpath='/html/body/div[2]/div/div[2]/div/div[2]/div[4]/div[2]/div[1]/div/div[1]'
    )

    # 셀렉트 ID 확인
    if analysis['success'] and analysis['data']['selects']:
        select_id = analysis['data']['selects'][0]['id']

        # 2단계: 전체 크롤링
        result = await crawler.crawl_dynamic_selector_table(
            url="https://www.data.go.kr/data/15001700/openapi.do",
            selector_css=f"select#{select_id}",
            table_container_xpath='/html/body/div[2]/div/div[2]/div/div[2]/div[4]/div[2]/div[1]/div/div[1]',
            wait_after_select=2.0
        )

        # 3단계: 결과 저장
        with open('api_15001700_dynamic.json', 'w', encoding='utf-8') as f:
            json.dump(result, f, ensure_ascii=False, indent=2)

# 실행
asyncio.run(crawl_15001700())
```

---

## 결과 데이터 구조

```json
{
  "success": true,
  "url": "https://www.data.go.kr/data/15001700/openapi.do",
  "crawled_time": "2025-11-09 03:30:00",
  "data": {
    "getOperation1": {
      "option_value": "getOperation1",
      "option_text": "작업1 조회",
      "tables": [
        {
          "table_index": 0,
          "data": {
            "headers": ["항목명", "항목크기", "항목구분", "샘플데이터", "항목설명"],
            "rows": [
              ["param1", "10", "필수", "example1", "설명1"],
              ["param2", "20", "선택", "example2", "설명2"]
            ]
          }
        }
      ]
    },
    "getOperation2": {
      "option_value": "getOperation2",
      "option_text": "작업2 조회",
      "tables": [ ... ]
    }
  }
}
```

---

## 기존 크롤러와 통합

### main_crawler.py 수정

```python
# main_crawler.py에 동적 테이블 크롤링 옵션 추가

class HybridCrawler:
    async def crawl_with_dynamic_tables(self, url: str) -> Dict:
        """동적 테이블 포함 크롤링"""

        # 1. 기본 크롤링
        result = await self.bs_crawler.extract_api_info(session, url)

        # 2. 동적 테이블 체크 (Swagger UI가 있는 경우)
        if not result['success'] or '동적' in result.get('errors', []):
            from .dynamic_table_crawler import DynamicTableCrawler

            dynamic_crawler = DynamicTableCrawler()

            # XPath 목록 (동적 테이블이 있을 것으로 예상되는 위치)
            xpath_candidates = [
                '/html/body/div[2]/div/div[2]/div/div[2]/div[4]/div[2]/div[1]/div/div[1]',
                '//div[@class="swagger-ui"]',
                '//div[@id="swagger-ui"]'
            ]

            for xpath in xpath_candidates:
                dynamic_result = await dynamic_crawler.crawl_specific_location(url, xpath)

                if dynamic_result['success'] and dynamic_result['data'].get('selects'):
                    # 동적 테이블 크롤링
                    select_id = dynamic_result['data']['selects'][0]['id']

                    full_result = await dynamic_crawler.crawl_dynamic_selector_table(
                        url=url,
                        selector_css=f"select#{select_id}",
                        table_container_xpath=xpath
                    )

                    # 결과 병합
                    result['data']['dynamic_tables'] = full_result['data']
                    result['success'] = True
                    break

        return result
```

---

## 주의사항

1. **대기 시간 조정**
   - `wait_after_select` 파라미터로 테이블 렌더링 대기 시간 조정
   - 네트워크 속도에 따라 1.0 ~ 3.0초 사이 권장

2. **셀렉터 식별**
   - CSS 셀렉터가 XPath보다 빠르고 안정적
   - 가능하면 `id` 속성을 사용한 셀렉터 권장

3. **에러 처리**
   - 일부 옵션에서 테이블이 로드되지 않을 수 있음
   - 각 옵션별로 try-catch 처리 필수

4. **성능**
   - 옵션이 많을 경우 크롤링 시간이 길어짐
   - 병렬 처리는 권장하지 않음 (동일 페이지에서 순차 처리 필요)

---

## 트러블슈팅

### 문제 1: 테이블이 로드되지 않음
```python
# 대기 시간 증가
wait_after_select=3.0

# 또는 명시적 대기 추가
await page.wait_for_selector('table.result-table', timeout=5000)
```

### 문제 2: 셀렉터를 찾을 수 없음
```python
# 여러 후보 셀렉터 시도
selectors = [
    'select#operationSelector',
    'select.api-selector',
    '//select[@name="operation"]'
]

for selector in selectors:
    element = await page.query_selector(selector)
    if element:
        break
```

### 문제 3: 중복 데이터 수집
```python
# 테이블 데이터 해시로 중복 제거
import hashlib

def get_table_hash(table_data):
    data_str = json.dumps(table_data, sort_keys=True)
    return hashlib.md5(data_str.encode()).hexdigest()

# 중복 체크
seen_hashes = set()
for table in tables:
    table_hash = get_table_hash(table)
    if table_hash not in seen_hashes:
        seen_hashes.add(table_hash)
        # 저장
```

---

## 다음 단계

1. **분석 실행**: `analyze_dynamic_table.py` 실행하여 페이지 구조 파악
2. **셀렉터 식별**: 셀렉트 박스의 ID/클래스 확인
3. **크롤링 테스트**: `dynamic_table_crawler.py`로 테스트 크롤링
4. **통합**: 기존 크롤러에 통합 또는 별도 실행

필요시 `main_crawler.py`에 `--dynamic-tables` 옵션 추가하여 자동 감지 가능.
