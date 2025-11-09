"""
Playwright 기반 동적 콘텐츠 크롤러
케이스 4: 동적 렌더링이 필요한 Swagger API

메타데이터 스캔은 metadata/base_scanner.py 기반으로 처리:
- metadata/metadata_fileData.py: FileData 스캔
- metadata/metadata_openapi.py: OpenAPI 스캔
- metadata/metadata_standard.py: Standard 스캔
"""

import asyncio
from playwright.async_api import async_playwright, Page, Browser
import re
import json
from datetime import datetime
from typing import Dict, List, Optional
import time

class PlaywrightCrawler:
    def __init__(self, max_workers: int = 10):
        self.max_workers = max_workers
        self.semaphore = asyncio.Semaphore(max_workers)
        
    @staticmethod
    def clean_text(text):
        """텍스트 정제"""
        if not isinstance(text, str):
            return text
        text = re.sub(r'[\n\r\t]+', ' ', text)
        text = re.sub(r'<[^>]+>', '', text)
        text = re.sub(r' +', ' ', text)
        return text.strip()
    
    def clean_all_text(self, obj):
        """재귀적으로 모든 텍스트 정제"""
        if isinstance(obj, dict):
            return {k: self.clean_all_text(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self.clean_all_text(v) for v in obj]
        elif isinstance(obj, str):
            return self.clean_text(obj)
        else:
            return obj
    
    async def extract_table_info_pw(self, page: Page) -> Dict:
        """Playwright로 테이블 정보 추출"""
        table_info = {}
        # 모든 테이블 선택 (dataset-table 외의 중요 정보도 포함)
        tables = await page.query_selector_all('table')

        for table in tables:
            rows = await table.query_selector_all('tr')
            for row in rows:
                try:
                    th = await row.query_selector('th')
                    td = await row.query_selector('td')
                    if th and td:
                        key = self.clean_text(await th.inner_text())
                        value = self.clean_text(await td.inner_text())
                        
                        if '전화번호' in key:
                            tel_div = await td.query_selector('#telNoDiv')
                            if tel_div:
                                value = self.clean_text(await tel_div.inner_text())
                        
                        if not value:
                            link = await td.query_selector('a')
                            if link:
                                value = self.clean_text(await link.inner_text())
                        
                        if key and value:
                            table_info[key] = value
                except:
                    continue
        
        return table_info
    
    async def extract_swagger_json_pw(self, page: Page) -> Optional[Dict]:
        """Playwright로 Swagger JSON 추출 (동적 렌더링 후)"""
        swagger_json = None
        
        # 1. window 객체에서 직접 추출 (동적 생성된 경우)
        swagger_json = await page.evaluate('''() => {
            try {
                // 다양한 경로 체크
                if (typeof swaggerJson !== 'undefined' && swaggerJson !== null) {
                    if (typeof swaggerJson === 'string' && swaggerJson.trim() !== '') {
                        return JSON.parse(swaggerJson);
                    } else if (typeof swaggerJson === 'object') {
                        return swaggerJson;
                    }
                }
                
                // window 객체 체크
                if (window.swaggerJson) {
                    if (typeof window.swaggerJson === 'string') {
                        return JSON.parse(window.swaggerJson);
                    }
                    return window.swaggerJson;
                }
                
                // 다른 가능한 변수명들
                const possibleVars = ['swagger', 'apiSpec', 'openApiSpec', 'specification'];
                for (const varName of possibleVars) {
                    if (window[varName] && typeof window[varName] === 'object') {
                        return window[varName];
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
        
        # 2. DOM에서 동적으로 렌더링된 Swagger UI 체크
        swagger_ui = await page.query_selector('.swagger-ui')
        if swagger_ui:
            # Swagger UI가 렌더링된 경우, API 정의 추출 시도
            api_definition = await page.evaluate('''() => {
                try {
                    const ui = window.ui;
                    if (ui && ui.specSelectors && ui.specSelectors.specJson) {
                        return ui.specSelectors.specJson();
                    }
                    return null;
                } catch (e) {
                    return null;
                }
            }''')
            
            if api_definition:
                return api_definition
        
        # 3. script 태그에서 추출 (정적 포함 + 동적 생성)
        scripts = await page.query_selector_all('script')
        for script in scripts:
            try:
                content = await script.inner_text()
                if not content:
                    continue
                
                patterns = [
                    r'var\s+swaggerJson\s*=\s*(\{.*?\})\s*;',
                    r'var\s+swaggerJson\s*=\s*`(\{.*?\})`',
                    r'const\s+swaggerJson\s*=\s*(\{.*?\})',
                    r'let\s+swaggerJson\s*=\s*(\{.*?\})'
                ]
                
                for pattern in patterns:
                    match = re.search(pattern, content, re.DOTALL)
                    if match:
                        try:
                            json_str = match.group(1)
                            swagger_json = json.loads(json_str)
                            if swagger_json:
                                return swagger_json
                        except:
                            continue
            except:
                continue
        
        return None
    
    def process_swagger_data(self, swagger_json: Dict, api_id: str,
                           url: str, table_info: Dict) -> Dict:
        """Swagger 데이터 처리"""
        from util.parser import NaraParser
        parser = NaraParser(None)
        
        api_info = parser.extract_api_info(swagger_json)
        base_url = parser.extract_base_url(swagger_json)
        api_info['base_url'] = base_url
        api_info['schemes'] = swagger_json.get('schemes', ['https'])
        endpoints = parser.extract_endpoints(swagger_json)
        
        return {
            'api_id': api_id,
            'crawled_url': url,
            'crawled_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'info': table_info,
            'api_info': api_info,
            'endpoints': endpoints,
            'swagger_json': swagger_json,
            'api_type': 'swagger_dynamic'
        }
    
    async def extract_general_api_info_pw(self, page: Page) -> Dict:
        """동적 렌더링된 일반 API 정보 추출"""
        general_api_info = {}
        
        # 상세기능 (동적 로드될 수 있음)
        await page.wait_for_selector('#open-api-detail-result', timeout=5000, state='attached')
        detail_div = await page.query_selector('#open-api-detail-result')
        if detail_div:
            desc_elem = await detail_div.query_selector('h4.tit')
            if desc_elem:
                description = await desc_elem.inner_text()
                general_api_info['detail_info'] = {
                    'description': self.clean_text(description)
                }
        
        # AJAX로 로드되는 요청/응답 파라미터 대기
        try:
            await page.wait_for_selector('#request-parameter-table', timeout=3000)
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
        
        return general_api_info
    
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
        
        try:
            # 페이지 로드
            await page.goto(url, wait_until='networkidle', timeout=20000)
            
            # 동적 콘텐츠 로드 대기
            await page.wait_for_timeout(2000)
            
            # API ID 추출
            m = re.search(r'/data/(\d+)/openapi', url)
            api_id = m.group(1) if m else f"api_{url.replace('https://', '').replace('/', '_')}"
            result['api_id'] = api_id
            
            # 테이블 정보 추출
            table_info = await self.extract_table_info_pw(page)
            
            # Swagger JSON 추출 (동적)
            swagger_json = await self.extract_swagger_json_pw(page)
            if swagger_json:
                result['data'] = self.process_swagger_data(
                    swagger_json, api_id, url, table_info
                )
                result['success'] = True
                return result
            
            # 일반 API 정보 추출 (동적)
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
            
            result['errors'].append('동적 추출도 실패')
            
        except Exception as e:
            result['errors'].append(f'Playwright 크롤링 실패: {str(e)}')
        
        return result
    
    async def crawl_single(self, browser: Browser, url: str) -> Dict:
        """단일 URL 크롤링"""
        async with self.semaphore:
            context = await browser.new_context(
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
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
                args=['--disable-blink-features=AutomationControlled']
            )
            
            tasks = [self.crawl_single(browser, url) for url in urls]
            results = await asyncio.gather(*tasks)
            
            await browser.close()
        
        # 데이터 정제
        for result in results:
            if result['success']:
                result['data'] = self.clean_all_text(result['data'])
        
        return results