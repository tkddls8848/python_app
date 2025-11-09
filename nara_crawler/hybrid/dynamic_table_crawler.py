"""
동적 셀렉터 테이블 크롤러
셀렉트 박스로 조회 가능한 동적 테이블을 크롤링
"""
import asyncio
from playwright.async_api import async_playwright, Page
from typing import Dict, List, Optional
import re
import json
from datetime import datetime

class DynamicTableCrawler:
    """셀렉터 기반 동적 테이블 크롤러"""

    def __init__(self):
        self.results = []

    @staticmethod
    def clean_text(text):
        """텍스트 정제"""
        if not isinstance(text, str):
            return text
        text = re.sub(r'[\n\r\t]+', ' ', text)
        text = re.sub(r' +', ' ', text)
        return text.strip()

    async def extract_selector_options(self, page: Page, selector_element) -> List[Dict]:
        """셀렉터 옵션 추출"""
        options = []
        option_elements = await selector_element.query_selector_all('option')

        for option in option_elements:
            value = await option.get_attribute('value')
            text = await option.inner_text()

            # 빈 값이나 "선택" 등은 제외
            if value and value.strip() and value != '':
                options.append({
                    'value': value.strip(),
                    'text': self.clean_text(text)
                })

        return options

    async def extract_table_data(self, page: Page, table_element) -> Dict:
        """테이블 데이터 추출"""
        table_data = {
            'headers': [],
            'rows': []
        }

        # 헤더 추출
        header_row = await table_element.query_selector('thead tr, tr:first-child')
        if header_row:
            headers = await header_row.query_selector_all('th, td')
            for header in headers:
                text = await header.inner_text()
                table_data['headers'].append(self.clean_text(text))

        # 데이터 행 추출
        body_rows = await table_element.query_selector_all('tbody tr, tr')

        for row in body_rows:
            # 헤더 행은 스킵
            if await row.query_selector('th') and not await row.query_selector('td'):
                continue

            cells = await row.query_selector_all('td, th')
            row_data = []

            for cell in cells:
                text = await cell.inner_text()
                row_data.append(self.clean_text(text))

            if row_data:  # 빈 행 제외
                table_data['rows'].append(row_data)

        return table_data

    async def crawl_dynamic_selector_table(
        self,
        url: str,
        selector_css: str = None,
        selector_xpath: str = None,
        table_container_css: str = None,
        table_container_xpath: str = None,
        wait_after_select: float = 2.0
    ) -> Dict:
        """
        동적 셀렉터 테이블 크롤링

        Args:
            url: 크롤링할 URL
            selector_css: 셀렉트 박스 CSS 셀렉터
            selector_xpath: 셀렉트 박스 XPath
            table_container_css: 테이블 컨테이너 CSS 셀렉터
            table_container_xpath: 테이블 컨테이너 XPath
            wait_after_select: 셀렉터 변경 후 대기 시간(초)

        Returns:
            크롤링 결과 딕셔너리
        """
        result = {
            'success': False,
            'url': url,
            'crawled_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data': {},
            'errors': []
        }

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                # 페이지 로드
                await page.goto(url, wait_until='networkidle', timeout=30000)
                await asyncio.sleep(3)  # 추가 대기

                # 1. 셀렉트 박스 찾기
                select_element = None
                if selector_css:
                    select_element = await page.query_selector(selector_css)
                elif selector_xpath:
                    select_element = await page.query_selector(f'xpath={selector_xpath}')

                if not select_element:
                    result['errors'].append('셀렉트 박스를 찾을 수 없습니다.')
                    return result

                # 2. 셀렉터 옵션 추출
                options = await self.extract_selector_options(page, select_element)
                print(f"✓ 셀렉터 옵션 {len(options)}개 발견")

                # 3. 각 옵션별로 테이블 크롤링
                for i, option in enumerate(options):
                    print(f"\n처리 중 ({i+1}/{len(options)}): {option['text']}")

                    try:
                        # 옵션 선택
                        await select_element.select_option(value=option['value'])
                        await asyncio.sleep(wait_after_select)  # 테이블 렌더링 대기

                        # 테이블 컨테이너 찾기
                        container = None
                        if table_container_css:
                            container = await page.query_selector(table_container_css)
                        elif table_container_xpath:
                            container = await page.query_selector(f'xpath={table_container_xpath}')

                        if not container:
                            print(f"  ⚠️ 테이블 컨테이너를 찾을 수 없습니다: {option['text']}")
                            continue

                        # 테이블 추출
                        tables = await container.query_selector_all('table')
                        print(f"  ✓ 테이블 {len(tables)}개 발견")

                        option_data = {
                            'option_value': option['value'],
                            'option_text': option['text'],
                            'tables': []
                        }

                        for j, table in enumerate(tables):
                            table_data = await self.extract_table_data(page, table)
                            if table_data['rows']:  # 데이터가 있는 테이블만
                                option_data['tables'].append({
                                    'table_index': j,
                                    'data': table_data
                                })
                                print(f"    테이블 {j+1}: {len(table_data['rows'])}행")

                        if option_data['tables']:
                            result['data'][option['value']] = option_data

                    except Exception as e:
                        print(f"  ❌ 옵션 처리 실패: {str(e)}")
                        result['errors'].append(f"옵션 '{option['text']}' 처리 실패: {str(e)}")

                result['success'] = len(result['data']) > 0

            except Exception as e:
                result['errors'].append(f'크롤링 실패: {str(e)}')

            finally:
                await browser.close()

        return result

    async def crawl_specific_location(self, url: str, xpath: str) -> Dict:
        """
        특정 XPath 위치의 테이블 크롤링
        예: /html/body/div[2]/div/div[2]/div/div[2]/div[4]/div[2]/div[1]/div/div[1]
        """
        result = {
            'success': False,
            'url': url,
            'xpath': xpath,
            'crawled_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'data': None,
            'errors': []
        }

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            try:
                await page.goto(url, wait_until='networkidle', timeout=30000)
                await asyncio.sleep(3)

                # XPath로 요소 찾기
                target = await page.query_selector(f'xpath={xpath}')

                if not target:
                    result['errors'].append(f'XPath 위치에서 요소를 찾을 수 없습니다: {xpath}')
                    return result

                # 요소 정보 추출
                tag_name = await target.evaluate('el => el.tagName')
                class_name = await target.get_attribute('class')
                element_id = await target.get_attribute('id')

                result['data'] = {
                    'element_info': {
                        'tag': tag_name,
                        'class': class_name,
                        'id': element_id
                    }
                }

                # 셀렉트 박스 찾기
                selects = await target.query_selector_all('select')
                if selects:
                    result['data']['select_count'] = len(selects)
                    result['data']['selects'] = []

                    for i, select in enumerate(selects):
                        select_id = await select.get_attribute('id')
                        select_name = await select.get_attribute('name')
                        options = await self.extract_selector_options(page, select)

                        result['data']['selects'].append({
                            'index': i,
                            'id': select_id,
                            'name': select_name,
                            'options': options
                        })

                # 테이블 찾기
                tables = await target.query_selector_all('table')
                if tables:
                    result['data']['table_count'] = len(tables)
                    result['data']['tables'] = []

                    for i, table in enumerate(tables):
                        table_data = await self.extract_table_data(page, table)
                        result['data']['tables'].append({
                            'index': i,
                            'data': table_data
                        })

                result['success'] = True

            except Exception as e:
                result['errors'].append(f'크롤링 실패: {str(e)}')

            finally:
                await browser.close()

        return result


async def main():
    """테스트 실행"""
    crawler = DynamicTableCrawler()

    # 예제 1: 특정 XPath 위치 분석
    print("=" * 60)
    print("특정 위치 테이블 분석")
    print("=" * 60)

    result = await crawler.crawl_specific_location(
        url="https://www.data.go.kr/data/15001700/openapi.do",
        xpath='/html/body/div[2]/div/div[2]/div/div[2]/div[4]/div[2]/div[1]/div/div[1]'
    )

    print(f"\n성공: {result['success']}")
    if result['success']:
        print(f"셀렉트 박스: {result['data'].get('select_count', 0)}개")
        print(f"테이블: {result['data'].get('table_count', 0)}개")

        if result['data'].get('selects'):
            for select_info in result['data']['selects']:
                print(f"\n셀렉트 {select_info['index'] + 1}:")
                print(f"  ID: {select_info['id']}")
                print(f"  옵션: {len(select_info['options'])}개")

    # 결과 저장
    with open('/home/user/python_app/dynamic_table_result.json', 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n💾 결과가 dynamic_table_result.json에 저장되었습니다.")

    # 예제 2: 셀렉터 기반 크롤링 (실제 셀렉터 정보가 필요)
    # result2 = await crawler.crawl_dynamic_selector_table(
    #     url="https://www.data.go.kr/data/15001700/openapi.do",
    #     selector_css="select#yourSelectId",  # 실제 셀렉터로 변경 필요
    #     table_container_xpath='/html/body/div[2]/div/div[2]/div/div[2]/div[4]/div[2]/div[1]/div/div[1]'
    # )


if __name__ == "__main__":
    asyncio.run(main())
