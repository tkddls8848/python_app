"""
공통 유틸리티 클래스
크롤러에서 공통으로 사용되는 기능들을 제공
"""
import re
from datetime import datetime
from typing import Dict


class SwaggerProcessor:
    """Swagger 데이터 처리 클래스"""

    @staticmethod
    def process_swagger_data(swagger_json: Dict, api_id: str,
                           url: str, table_info: Dict, api_type: str = 'swagger') -> Dict:
        """
        Swagger JSON을 파싱하여 표준화된 형태로 변환

        Args:
            swagger_json: Swagger JSON 객체
            api_id: API ID
            url: 크롤링한 URL
            table_info: 테이블에서 추출한 정보
            api_type: API 타입 (기본값: 'swagger')

        Returns:
            표준화된 API 정보 딕셔너리
        """
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
            'api_type': api_type
        }


class ApiIdExtractor:
    """API ID 추출 클래스"""

    @staticmethod
    def extract_api_id(url: str) -> str:
        """
        URL에서 API ID 추출

        Args:
            url: API URL

        Returns:
            추출된 API ID 또는 생성된 ID
        """
        m = re.search(r'/data/(\d+)/openapi', url)
        if m:
            return m.group(1)
        else:
            # URL을 기반으로 고유한 ID 생성
            return f"api_{url.replace('https://', '').replace('http://', '').replace('/', '_')}"
