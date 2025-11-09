"""
Swagger JSON 파서
순수 파이썬 기반, 의존성 최소화
BeautifulSoup 및 Playwright 크롤러용 경량 파서
"""

from typing import Dict, List, Optional


class SwaggerParser:
    """Swagger JSON 파싱 유틸리티 클래스"""

    @staticmethod
    def extract_api_info(swagger_json: Optional[Dict]) -> Dict:
        """
        API 기본 정보 추출

        Args:
            swagger_json: Swagger JSON 데이터

        Returns:
            API 기본 정보 딕셔너리 (title, description, version 등)
        """
        if not swagger_json:
            return {}

        info = swagger_json.get('info', {})
        api_info = {
            'title': info.get('title', ''),
            'description': info.get('description', ''),
            'version': info.get('version', '')
        }

        # 확장 정보 추출 (x- 접두사)
        for key, value in info.items():
            if key.startswith('x-'):
                api_info[key.replace('x-', '')] = value

        return api_info

    @staticmethod
    def extract_base_url(swagger_json: Optional[Dict]) -> str:
        """
        Base URL 추출

        Args:
            swagger_json: Swagger JSON 데이터

        Returns:
            Base URL 문자열 (scheme://host/basePath)
        """
        if not swagger_json:
            return ""

        schemes = swagger_json.get('schemes', ['https'])
        host = swagger_json.get('host', '')
        base_path = swagger_json.get('basePath', '')

        if host:
            scheme = schemes[0] if schemes else 'https'
            return f"{scheme}://{host}{base_path}"
        return ""

    @staticmethod
    def extract_endpoints(swagger_json: Optional[Dict]) -> List[Dict]:
        """
        엔드포인트 정보 추출

        Args:
            swagger_json: Swagger JSON 데이터

        Returns:
            엔드포인트 정보 리스트
        """
        if not swagger_json:
            return []

        endpoints = []
        paths = swagger_json.get('paths', {})

        for path, methods in paths.items():
            for method, data in methods.items():
                if method.lower() in ['get', 'post', 'put', 'delete', 'patch', 'options', 'head']:
                    endpoint = {
                        'method': method.upper(),
                        'path': path,
                        'description': data.get('summary', '') or data.get('description', ''),
                        'parameters': SwaggerParser._extract_parameters(data.get('parameters', [])),
                        'responses': SwaggerParser._extract_responses(data.get('responses', {})),
                        'tags': data.get('tags', []),
                        'section': data.get('tags', ['Default'])[0] if data.get('tags') else 'Default'
                    }
                    endpoints.append(endpoint)

        return endpoints

    @staticmethod
    def _extract_parameters(params_list: List[Dict]) -> List[Dict]:
        """
        파라미터 정보 추출 (내부 메서드)

        Args:
            params_list: 파라미터 리스트

        Returns:
            정제된 파라미터 정보 리스트
        """
        parameters = []

        for param in params_list:
            # schema가 있는 경우와 없는 경우 처리
            param_type = param.get('type', '')
            if not param_type and 'schema' in param:
                param_type = param.get('schema', {}).get('type', '')

            parameters.append({
                'name': param.get('name', ''),
                'description': param.get('description', ''),
                'required': param.get('required', False),
                'type': param_type,
                'in': param.get('in', '')  # query, path, body 등
            })

        return parameters

    @staticmethod
    def _extract_responses(responses_dict: Dict) -> List[Dict]:
        """
        응답 정보 추출 (내부 메서드)

        Args:
            responses_dict: 응답 정보 딕셔너리

        Returns:
            정제된 응답 정보 리스트
        """
        responses = []

        for status_code, data in responses_dict.items():
            responses.append({
                'status_code': status_code,
                'description': data.get('description', '')
            })

        return responses

    @staticmethod
    def extract_full_api_data(swagger_json: Optional[Dict]) -> Dict:
        """
        전체 API 데이터 추출 (편의 메서드)

        Args:
            swagger_json: Swagger JSON 데이터

        Returns:
            API 정보, Base URL, 엔드포인트를 포함한 전체 데이터
        """
        if not swagger_json:
            return {
                'api_info': {},
                'base_url': '',
                'endpoints': [],
                'schemes': []
            }

        return {
            'api_info': SwaggerParser.extract_api_info(swagger_json),
            'base_url': SwaggerParser.extract_base_url(swagger_json),
            'endpoints': SwaggerParser.extract_endpoints(swagger_json),
            'schemes': swagger_json.get('schemes', ['https'])
        }
