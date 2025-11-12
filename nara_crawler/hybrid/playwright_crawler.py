"""
Playwright 기반 동적 콘텐츠 크롤러
케이스 3: 동적 렌더링이 필요한 Swagger API
케이스 4: 동적 렌더링이 필요한 Swagger없는 카테고리별 페이지
"""

import asyncio
from playwright.async_api import async_playwright, Page, Browser
import re
import json
from datetime import datetime
from typing import Dict, List, Optional
import time
from util.text_cleaner import clean_text, clean_all_text
from util.common import SwaggerProcessor, ApiIdExtractor
from util.table_extractor import extract_table_info_pw

class PlaywrightCrawler:
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)

    async def extract_swagger_json_pw(self, page: Page) -> Optional[Dict]:
        """Playwright로 Swagger JSON 추출 (동적 렌더링 후)"""
        
        # 1. var swaggerJson 변수에서 직접 추출 (가장 정확한 방법)
        swagger_json = await page.evaluate('''() => {
            try {
                // var swaggerJson 변수 직접 접근
                if (typeof swaggerJson !== 'undefined' && swaggerJson !== null) {
                    if (typeof swaggerJson === 'string') {
                        return JSON.parse(swaggerJson);
                    } else if (typeof swaggerJson === 'object') {
                        return swaggerJson;
                    }
                }
                return null;
            } catch (e) {
                console.error('Swagger extraction error:', e);
                return null;
            }
        }''')
        
        if swagger_json and isinstance(swagger_json, dict):
            return swagger_json
        
        # 2. 백틱(`)으로 둘러싸인 JSON 문자열만 정확히 추출
        scripts = await page.query_selector_all('script')
        for script in scripts:
            try:
                content = await script.inner_text()
                if not content:
                    continue
                
                # var swaggerJson = `{...}` 패턴만 정확히 매칭
                pattern = r'var\s+swaggerJson\s*=\s*`(\{[\s\S]*?\})`'
                match = re.search(pattern, content)
                
                if match:
                    try:
                        json_str = match.group(1)
                        # JSON 문자열 정리 (개행 문자 등 처리)
                        json_str = re.sub(r'\s+', ' ', json_str)
                        swagger_json = json.loads(json_str)
                        if swagger_json:
                            return swagger_json
                    except json.JSONDecodeError as e:
                        print(f"JSON 파싱 오류: {e}")
                        continue
            except:
                continue
        
        return None

    async def extract_general_api_info_pw(self, page: Page) -> Dict:
        """동적 렌더링된 일반 API 정보 추출"""
        general_api_info = {}

        try:
            # POST 요청을 위한 3가지 값 추출
            try:
                post_request_values = await page.evaluate('''() => {
                    const resultArray = [];

                    // publicDataDetailPk, publicDataPk 값 먼저 추출
                    let publicDataDetailPk = null;
                    let publicDataPk = null;

                    const detailPkElem = document.querySelector('#publicDataDetailPk');
                    if (detailPkElem) {
                        publicDataDetailPk = detailPkElem.value;
                    }

                    const dataPkElem = document.querySelector('#publicDataPk');
                    if (dataPkElem) {
                        publicDataPk = dataPkElem.value;
                    }

                    // oprtinSeqNo: select 박스의 모든 option에 대해 3가지 값을 묶어서 배열에 저장
                    const selectElem = document.querySelector('#open_api_detail_select');
                    if (selectElem) {
                        const options = selectElem.querySelectorAll('option');
                        options.forEach(opt => {
                            if (opt.value) {
                                resultArray.push({
                                    oprtinSeqNo: opt.value,
                                    publicDataDetailPk: publicDataDetailPk,
                                    publicDataPk: publicDataPk
                                });
                            }
                        });
                    }

                    return resultArray;
                }''')

                if post_request_values and len(post_request_values) > 0:
                    # 각 항목에 대해 POST 요청 수행
                    for item in post_request_values:
                        try:
                            # HTML을 즉시 JSON으로 파싱
                            response_data = await page.evaluate('''async (dataObj) => {
                                console.log('=== API 디테일 요청 시작 ===');
                                console.log('요청 데이터:', dataObj);

                                try {
                                    console.log('Fetch 요청 보내는 중...');
                                    const response = await fetch('https://www.data.go.kr/tcs/dss/selectApiDetailFunction.do', {
                                        method: 'POST',
                                        headers: {
                                            'Content-Type': 'application/x-www-form-urlencoded',
                                        },
                                        body: new URLSearchParams({
                                            oprtinSeqNo: dataObj.oprtinSeqNo,
                                            publicDataDetailPk: dataObj.publicDataDetailPk,
                                            publicDataPk: dataObj.publicDataPk
                                        }).toString()
                                    });

                                    console.log('응답 상태:', response.status, response.statusText);

                                    if (response.ok) {
                                        const html = await response.text();
                                        console.log('응답 HTML 길이:', html.length);

                                        // DOM 파서를 사용하여 HTML을 파싱
                                        const parser = new DOMParser();
                                        const doc = parser.parseFromString(html, 'text/html');
                                        const apiDetailDiv = doc.getElementById('open-api-detail-result');

                                        console.log('open-api-detail-result 요소 찾음:', !!apiDetailDiv);

                                        if (apiDetailDiv) {
                                            // 테이블을 JSON으로 파싱
                                            const tables = apiDetailDiv.querySelectorAll('table');
                                            console.log('포함된 테이블 개수:', tables.length);

                                            const parsedData = {
                                                tables: []
                                            };

                                            // 각 테이블 파싱
                                            tables.forEach((table, tableIndex) => {
                                                const tableData = {
                                                    headers: [],
                                                    rows: []
                                                };

                                                // 1. 헤더 추출 (첫 번째 tr의 모든 th)
                                                const headerRow = table.querySelector('tr');
                                                if (headerRow) {
                                                    const headerCells = headerRow.querySelectorAll('th');
                                                    headerCells.forEach(th => {
                                                        tableData.headers.push(th.textContent.trim());
                                                    });
                                                }

                                                // 2. 데이터 행 추출 (두 번째 tr부터)
                                                const dataRows = table.querySelectorAll('tr');
                                                for (let i = 1; i < dataRows.length; i++) {  // 첫 행(헤더) 제외
                                                    const row = dataRows[i];
                                                    const cells = row.querySelectorAll('td');
                                                    
                                                    if (cells.length > 0) {
                                                        const rowData = {};
                                                        
                                                        // 각 셀을 해당 헤더와 매핑
                                                        cells.forEach((cell, cellIndex) => {
                                                            const headerName = tableData.headers[cellIndex] || `column_${cellIndex}`;
                                                            let cellValue = cell.textContent.trim();
                                                            
                                                            // 전화번호 특별 처리
                                                            if (headerName.includes('전화번호')) {
                                                                const telElem = cell.querySelector('#telNoDiv, #telNo');
                                                                if (telElem) {
                                                                    cellValue = telElem.textContent.trim();
                                                                }
                                                            }
                                                            
                                                            // 링크 처리
                                                            if (!cellValue || cellValue === '') {
                                                                const link = cell.querySelector('a');
                                                                if (link) {
                                                                    cellValue = link.textContent.trim();
                                                                    rowData[`${headerName}_link`] = link.href;
                                                                }
                                                            }
                                                            
                                                            rowData[headerName] = cellValue;
                                                        });
                                                        
                                                        // 빈 행이 아닌 경우만 추가
                                                        if (Object.keys(rowData).length > 0) {
                                                            tableData.rows.push(rowData);
                                                        }
                                                    }
                                                }

                                                // 테이블에 데이터가 있는 경우만 추가
                                                if (tableData.rows.length > 0) {
                                                    parsedData.tables.push(tableData);
                                                }
                                            });

                                            console.log('파싱된 테이블 개수:', parsedData.tables.length);
                                            return parsedData;
                                        } else {
                                            console.log('open-api-detail-result를 찾지 못함');
                                            return null;
                                        }
                                    } else {
                                        console.error('응답 실패:', response.status);
                                        return null;
                                    }
                                } catch (e) {
                                    console.error('Fetch 에러:', e);
                                    return null;
                                }
                            }''', item)

                            # Python 측에서도 디버깅 정보 출력
                            print(f"\n=== Python 측 디버깅 ===")
                            print(f"응답 받음: {response_data is not None}")
                            if response_data:
                                print(f"파싱된 테이블 개수: {len(response_data.get('tables', []))}")
                                print(f"응답 데이터 구조: {response_data}")

                            print(f"\n=== 최종 결과 ===")
                            print(f"response_data 저장 완료: {response_data is not None}")

                            # 응답 데이터를 해당 항목에 추가
                            if response_data:
                                item['response_data'] = response_data
                            else:
                                item['response_data'] = None
                                item['error'] = 'POST 요청 실패'
                        except Exception as e:
                            print(f"POST 요청 실패 (oprtinSeqNo={item.get('oprtinSeqNo')}): {e}")
                            item['response_data'] = None
                            item['error'] = str(e)

                    general_api_info['post_request_values'] = post_request_values
            except Exception as e:
                print(f"POST 요청 값 추출 중 오류: {e}")

            # 상세기능 (동적 로드될 수 있음)
            try:
                await page.wait_for_selector('#open-api-detail-result', timeout=5000, state='attached')
                detail_div = await page.query_selector('#open-api-detail-result')
                if detail_div:
                    desc_elem = await detail_div.query_selector('h4.tit')
                    if desc_elem:
                        description = await desc_elem.inner_text()
                        general_api_info['detail_info'] = {
                            'description': clean_text(description)
                        }
            except:
                pass

            # AJAX로 로드되는 요청/응답 파라미터 대기
            try:
                await page.wait_for_selector('#request-parameter-table', timeout=5000)
            except:
                pass
            
            # 요청변수
            request_params = await page.evaluate('''() => {
                const table = document.querySelector('#request-parameter-table');
                if (!table) return [];
                
                const params = [];
                const rows = table.querySelectorAll('tr');
                for (let i = 1; i < rows.length; i++) {
                    const cols = rows[i].querySelectorAll('td');
                    if (cols.length >= 4) {
                        params.push({
                            name: cols[0].textContent.trim(),
                            type: cols[1].textContent.trim(),
                            required: cols[2].textContent.trim(),
                            description: cols[3].textContent.trim()
                        });
                    }
                }
                return params;
            }''')
            
            if request_params:
                general_api_info['request_parameters'] = request_params
            
            # 출력결과
            response_params = await page.evaluate('''() => {
                const table = document.querySelector('#response-parameter-table');
                if (!table) return [];
                
                const params = [];
                const rows = table.querySelectorAll('tr');
                for (let i = 1; i < rows.length; i++) {
                    const cols = rows[i].querySelectorAll('td');
                    if (cols.length >= 3) {
                        params.push({
                            name: cols[0].textContent.trim(),
                            type: cols[1].textContent.trim(),
                            description: cols[2].textContent.trim()
                        });
                    }
                }
                return params;
            }''')
            
            if response_params:
                general_api_info['response_parameters'] = response_params

            # API 기본 정보 (테이블 외 추가 정보)
            api_basic_info = await page.evaluate('''() => {
                const info = {};
                
                // API 제공 기관
                const orgElem = document.querySelector('.api-provider');
                if (orgElem) {
                    info.provider = orgElem.textContent.trim();
                }
                
                // API 버전
                const versionElem = document.querySelector('.api-version');
                if (versionElem) {
                    info.version = versionElem.textContent.trim();
                }
                
                // API 설명
                const descElem = document.querySelector('.api-description');
                if (descElem) {
                    info.description = descElem.textContent.trim();
                }
                
                return info;
            }''')
            
            if api_basic_info:
                general_api_info['basic_info'] = api_basic_info

        except Exception as e:
            print(f"일반 API 정보 추출 중 오류: {e}")

        return general_api_info

    async def detect_api_type(self, page: Page, table_info: Dict) -> str:
        """API 타입 감지"""
        api_type_field = table_info.get('API 유형', '').upper()
        
        # LINK 타입 체크
        if 'LINK' in api_type_field:
            return 'link'
        
        # Swagger 체크
        swagger_json = await self.extract_swagger_json_pw(page)
        if swagger_json:
            return 'swagger'
        
        # 일반 API 체크
        general_api_info = await self.extract_general_api_info_pw(page)
        if (general_api_info.get('request_parameters') or 
            general_api_info.get('response_parameters') or
            general_api_info.get('detail_info')):
            return 'general'
        
        return 'unknown'

    async def extract_api_info_pw(self, page: Page, url: str) -> Dict:
        """Playwright 메인 추출 함수"""
        result = {
            'success': False,
            'data': None,
            'errors': [],
            'api_id': None,
            'url': url,
            'method': 'playwright'
        }
        print("동적", url)
        try:
            # 페이지 로드
            await page.goto(url, wait_until='networkidle', timeout=20000)

            # 동적 콘텐츠 로드 대기
            await page.wait_for_timeout(3000)

            # API ID 추출
            api_id = ApiIdExtractor.extract_api_id(url)
            result['api_id'] = api_id
            
            # 테이블 정보 추출
            table_info = await extract_table_info_pw(page)
            
            if not table_info:
                result['errors'].append('테이블 정보 없음')
                return result

            # API 타입 감지 및 처리
            api_type = await self.detect_api_type(page, table_info)
            
            if api_type == 'link':
                result['data'] = {
                    'api_id': api_id,
                    'crawled_url': url,
                    'crawled_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'info': table_info,
                    'api_type': 'link_dynamic',
                    'skip_reason': 'LINK 타입 API는 테이블 정보만 수집'
                }
                result['success'] = True
                return result
            
            elif api_type == 'swagger':
                swagger_json = await self.extract_swagger_json_pw(page)
                if swagger_json:
                    result['data'] = SwaggerProcessor.process_swagger_data(
                        swagger_json, api_id, url, table_info, api_type='swagger_dynamic'
                    )
                    result['success'] = True
                    return result
            
            elif api_type == 'general':
                general_api_info = await self.extract_general_api_info_pw(page)
                if general_api_info:
                    result['data'] = {
                        'api_id': api_id,
                        'crawled_url': url,
                        'crawled_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                        'info': table_info,
                        'general_api_info': general_api_info,
                        'api_type': 'general_dynamic'
                    }
                    result['success'] = True
                    return result
            
            result['errors'].append(f'API 타입 감지 및 추출 실패: {api_type}')
            
        except Exception as e:
            result['errors'].append(f'Playwright 크롤링 실패: {str(e)}')
        
        return result
    
    async def crawl_single(self, browser: Browser, url: str) -> Dict:
        """단일 URL 크롤링"""
        async with self.semaphore:
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
                viewport={'width': 1920, 'height': 1080}
            )
            page = await context.new_page()
            
            try:
                result = await self.extract_api_info_pw(page, url)
            finally:
                await context.close()
            
            return result
    
    async def crawl_batch(self, urls: List[str]) -> List[Dict]:
        """배치 크롤링"""
        results = []
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-dev-shm-usage'
                ]
            )
            
            tasks = [self.crawl_single(browser, url) for url in urls]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            await browser.close()
        
        # 예외 처리 및 데이터 정제
        processed_results = []
        for result in results:
            if isinstance(result, Exception):
                processed_results.append({
                    'success': False,
                    'data': None,
                    'errors': [f'크롤링 중 예외 발생: {str(result)}'],
                    'url': 'unknown',
                    'method': 'playwright'
                })
            elif result.get('success'):
                result['data'] = clean_all_text(result['data'])
                processed_results.append(result)
            else:
                processed_results.append(result)
        
        return processed_results