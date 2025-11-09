"""
BeautifulSoup 기반 정적 콘텐츠 크롤러
케이스 1: CSV 데이터 (일반 테이블)
케이스 2: LINK 타입 API
케이스 3: 정적 Swagger API
"""

import asyncio
import aiohttp
from bs4 import BeautifulSoup
import re
import json
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import os

class BSCrawler:
    def __init__(self, max_workers: int = 20):
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
    
    async def create_session(self) -> aiohttp.ClientSession:
        """최적화된 HTTP 세션 생성"""
        connector = aiohttp.TCPConnector(
            limit=100,
            limit_per_host=30,
            ttl_dns_cache=300,
            enable_cleanup_closed=True
        )
        timeout = aiohttp.ClientTimeout(total=10, connect=3, sock_read=7)
        return aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            }
        )
    
    async def extract_table_info(self, soup: BeautifulSoup) -> Dict:
        """테이블 정보 추출 (케이스 1, 2 공통)"""
        table_info = {}
        tables = soup.select('table.dataset-table')
        
        for table in tables:
            for row in table.find_all('tr'):
                try:
                    th = row.find('th')
                    td = row.find('td')
                    if th and td:
                        key = self.clean_text(th.get_text())
                        value = self.clean_text(td.get_text())
                        
                        # 전화번호 특별 처리
                        if '전화번호' in key:
                            tel_div = td.find('div', id='telNoDiv')
                            if tel_div:
                                value = self.clean_text(tel_div.get_text())
                        
                        # 링크 처리
                        if not value:
                            link = td.find('a')
                            if link:
                                value = self.clean_text(link.get_text())
                        
                        if key and value:
                            table_info[key] = value
                except Exception:
                    continue
        
        return table_info
    
    def extract_swagger_json(self, soup: BeautifulSoup) -> Optional[Dict]:
        """Swagger JSON 추출 (케이스 3)"""
        swagger_json = None
        scripts = soup.find_all('script')
        
        patterns = [
            (r'var\s+swaggerJson\s*=\s*(\{.*?\})\s*;', re.DOTALL),
            (r'var\s+swaggerJson\s*=\s*`([^`]+)`', re.DOTALL),
            (r'var\s+swaggerJson\s*=\s*"([^"]+)"', 0),
            (r'window\.swaggerJson\s*=\s*(\{.*?\})', re.DOTALL)
        ]
        
        for script in scripts:
            if not script.string:
                continue
                
            content = script.string
            
            for pattern, flags in patterns:
                try:
                    if flags:
                        match = re.search(pattern, content, flags)
                    else:
                        match = re.search(pattern, content)
                    
                    if match:
                        json_str = match.group(1)
                        # 이스케이프 처리
                        json_str = json_str.replace('\\"', '"')
                        json_str = json_str.replace('\\n', '')
                        json_str = json_str.replace('\\r', '')
                        json_str = json_str.replace('\\t', '')
                        
                        swagger_json = json.loads(json_str)
                        if swagger_json and isinstance(swagger_json, dict):
                            return swagger_json
                except (json.JSONDecodeError, AttributeError):
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
            'api_type': 'swagger'
        }
    
    def extract_general_api_info(self, soup: BeautifulSoup) -> Dict:
        """일반 API 정보 추출"""
        general_api_info = {}
        
        # 상세기능
        detail_div = soup.find('div', id='open-api-detail-result')
        if detail_div:
            desc_elem = detail_div.find('h4', class_='tit')
            if desc_elem:
                general_api_info['detail_info'] = {
                    'description': self.clean_text(desc_elem.get_text())
                }
        
        # 요청변수 테이블
        request_table = soup.find('table', id='request-parameter-table')
        if request_table:
            params = []
            for row in request_table.find_all('tr')[1:]:  # 헤더 제외
                cols = row.find_all('td')
                if len(cols) >= 4:
                    params.append({
                        'name': self.clean_text(cols[0].get_text()),
                        'type': self.clean_text(cols[1].get_text()),
                        'required': self.clean_text(cols[2].get_text()),
                        'description': self.clean_text(cols[3].get_text())
                    })
            if params:
                general_api_info['request_parameters'] = params
        
        # 출력결과 테이블
        response_table = soup.find('table', id='response-parameter-table')
        if response_table:
            outputs = []
            for row in response_table.find_all('tr')[1:]:  # 헤더 제외
                cols = row.find_all('td')
                if len(cols) >= 3:
                    outputs.append({
                        'name': self.clean_text(cols[0].get_text()),
                        'type': self.clean_text(cols[1].get_text()),
                        'description': self.clean_text(cols[2].get_text())
                    })
            if outputs:
                general_api_info['response_parameters'] = outputs
        
        return general_api_info
    
    async def extract_api_info(self, session: aiohttp.ClientSession, url: str) -> Dict:
        """메인 추출 함수"""
        result = {
            'success': False,
            'data': None,
            'errors': [],
            'api_id': None,
            'url': url,
            'method': 'beautifulsoup'
        }
        
        try:
            async with self.semaphore:
                async with session.get(url) as response:
                    if response.status != 200:
                        result['errors'].append(f'HTTP {response.status}')
                        return result
                    
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # API ID 추출
                    m = re.search(r'/data/(\d+)/openapi', url)
                    api_id = m.group(1) if m else f"api_{url.replace('https://', '').replace('/', '_')}"
                    result['api_id'] = api_id
                    
                    # 1. 테이블 정보 추출 (모든 케이스 공통)
                    table_info = await self.extract_table_info(soup)
                    
                    if not table_info:
                        result['errors'].append('테이블 정보 없음')
                        return result
                    
                    # 2. LINK 타입 체크 (케이스 2)
                    api_type_field = table_info.get('API 유형', '').upper()
                    if 'LINK' in api_type_field:
                        result['data'] = {
                            'api_id': api_id,
                            'crawled_url': url,
                            'crawled_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'info': table_info,
                            'api_type': 'link',
                            'skip_reason': 'LINK 타입 API는 테이블 정보만 수집'
                        }
                        result['success'] = True
                        return result
                    
                    # 3. Swagger JSON 체크 (케이스 3)
                    swagger_json = self.extract_swagger_json(soup)
                    if swagger_json:
                        result['data'] = self.process_swagger_data(
                            swagger_json, api_id, url, table_info
                        )
                        result['success'] = True
                        return result
                    
                    # 4. 일반 API 정보 추출 (케이스 1)
                    general_api_info = self.extract_general_api_info(soup)
                    if general_api_info:
                        result['data'] = {
                            'api_id': api_id,
                            'crawled_url': url,
                            'crawled_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                            'info': table_info,
                            'general_api_info': general_api_info,
                            'api_type': 'general'
                        }
                        result['success'] = True
                        return result
                    
                    # 정보 부족 - 동적 렌더링 필요 가능성
                    result['errors'].append('정적 추출 실패 - 동적 렌더링 필요')
                    
        except asyncio.TimeoutError:
            result['errors'].append('타임아웃')
        except Exception as e:
            result['errors'].append(f'크롤링 실패: {str(e)}')
        
        return result
    
    async def crawl_batch(self, urls: List[str]) -> Tuple[List[Dict], List[str]]:
        """배치 크롤링"""
        async with await self.create_session() as session:
            tasks = [self.extract_api_info(session, url) for url in urls]
            results = await asyncio.gather(*tasks)
        
        # 성공/실패 분리
        success_results = []
        failed_urls = []
        
        for result in results:
            if result['success']:
                # 데이터 정제
                result['data'] = self.clean_all_text(result['data'])
                success_results.append(result)
            else:
                failed_urls.append(result['url'])
        
        return success_results, failed_urls