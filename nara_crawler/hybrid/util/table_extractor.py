"""
테이블 정보 추출 유틸리티
BeautifulSoup 및 Playwright를 사용한 테이블 정보 추출 함수
"""

from typing import Dict
from bs4 import BeautifulSoup
from playwright.async_api import Page
from util.text_cleaner import clean_text


async def extract_table_info_pw(page: Page) -> Dict:
    """Playwright로 테이블 정보 추출"""
    table_info = {}
    # 모든 테이블 선택 (dataset-table 외의 중요 정보도 포함)
    tables = await page.query_selector_all('table')

    for table in tables:
        rows = await table.query_selector_all('tr')
        for row in rows:
            try:
                th = await row.query_selector('th')
                if th:  # th만 있어도 처리
                    key = clean_text(await th.inner_text())
                    if not key:  # key가 비어있으면 스킵
                        continue

                    value = ''
                    td = await row.query_selector('td')
                    if td:
                        value = clean_text(await td.inner_text())

                        # 전화번호 특별 처리 (div#telNoDiv 또는 span#telNo)
                        if '전화번호' in key:
                            # strong 태그 안의 div#telNoDiv 또는 span#telNo 우선 찾기
                            strong_tag = await td.query_selector('strong')
                            if strong_tag:
                                tel_elem = await strong_tag.query_selector('#telNoDiv, #telNo')
                                if tel_elem:
                                    value = clean_text(await tel_elem.inner_text())
                            # td 바로 아래의 div#telNoDiv 또는 span#telNo도 확인
                            if not value:
                                tel_elem = await td.query_selector('#telNoDiv, #telNo')
                                if tel_elem:
                                    value = clean_text(await tel_elem.inner_text())

                        # 링크 처리
                        if not value:
                            link = await td.query_selector('a')
                            if link:
                                value = clean_text(await link.inner_text())

                    # 값이 없어도 저장 (빈 문자열로)
                    table_info[key] = value
            except:
                continue

    return table_info


def extract_table_info_bs(soup: BeautifulSoup) -> Dict:
    table_info = {}
    tables = soup.select('table')

    for table in tables:
        for row in table.find_all('tr'):
            try:
                th = row.find('th')
                td = row.find('td')
                
                if th and td:
                    key = clean_text(th.get_text())
                    if not key:
                        continue

                    # 전화번호인 경우 script에서 직접 추출
                    if '전화번호' in key:
                        script = td.find('script')
                        if script and script.string:
                            import re
                            match = re.search(r'var telNo\s*=\s*"(\d+)"', script.string)
                            if match:
                                tel = match.group(1)
                                value = f"{tel[:3]}-{tel[3:7]}-{tel[7:]}"
                                table_info[key] = value
                                continue

                    # 일반적인 경우
                    value = clean_text(td.get_text())
                    table_info[key] = value
                    
            except Exception:
                continue

    return table_info