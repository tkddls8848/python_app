import json
import re
import os
import csv
from datetime import datetime
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
from functools import lru_cache

class NaraParser:
    """나라장터 API 파서 클래스 - 크롤러 통합용"""
    
    def __init__(self, driver=None):
        self.driver = driver
    
    def extract_api_info(self, swagger_json):
        """API 기본 정보 추출 - 크롤러 호환용"""
        if not swagger_json:
            return {}
        
        info = swagger_json.get('info', {})
        api_info = {
            'title': info.get('title', ''),
            'description': info.get('description', ''),
            'version': info.get('version', '')
        }
        
        # 확장 정보
        for key, value in info.items():
            if key.startswith('x-'):
                api_info[key.replace('x-', '')] = value
        
        return api_info

    def extract_base_url(self, swagger_json):
        """Base URL 추출 - 크롤러 호환용"""
        if not swagger_json:
            return ""
        
        schemes = swagger_json.get('schemes', ['https'])
        host = swagger_json.get('host', '')
        base_path = swagger_json.get('basePath', '')
        
        if host:
            scheme = schemes[0] if schemes else 'https'
            return f"{scheme}://{host}{base_path}"
        return ""

    def extract_endpoints(self, swagger_json):
        """엔드포인트 정보 추출 - 크롤러 호환용"""
        endpoints = []
        if not swagger_json:
            return endpoints
        
        paths = swagger_json.get('paths', {})
        for path, methods in paths.items():
            for method, data in methods.items():
                if method in ['get', 'post', 'put', 'delete', 'patch']:
                    endpoint = {
                        'method': method.upper(),
                        'path': path,
                        'description': data.get('summary', '') or data.get('description', ''),
                        'parameters': self._extract_swagger_parameters(data.get('parameters', [])),
                        'responses': self._extract_swagger_responses(data.get('responses', {})),
                        'tags': data.get('tags', []),
                        'section': data.get('tags', ['Default'])[0] if data.get('tags') else 'Default'
                    }
                    endpoints.append(endpoint)
        
        return endpoints

    def _extract_swagger_parameters(self, params_list):
        """Swagger 파라미터 추출"""
        return [{
            'name': param.get('name', ''),
            'description': param.get('description', ''),
            'required': param.get('required', False),
            'type': param.get('type', '') or (param.get('schema', {}).get('type', '') if 'schema' in param else '')
        } for param in params_list]

    def _extract_swagger_responses(self, responses_dict):
        """Swagger 응답 추출"""
        return [{
            'status_code': status_code,
            'description': data.get('description', '')
        } for status_code, data in responses_dict.items()]


class DataExporter:
    """데이터 내보내기 클래스 - 크롤러 통합용"""
    
    @staticmethod
    def save_crawling_result(data, output_dir, api_id, formats=['json', 'xml']):
        """크롤링 결과 저장 - 메인 저장 함수"""
        saved_files, errors = [], []
        
        # 기본 정보 추출
        table_info = data.get('info', {})
        org_name = table_info.get('제공기관', 'unknown_org')
        modified_date = table_info.get('수정일', 'unknown_date')
        
        # 문서번호 추출
        crawled_url = data.get('crawled_url', '')
        doc_num = 'unknown_doc'
        if crawled_url:
            match = re.search(r'/data/(\d+)/openapi', crawled_url)
            if match:
                doc_num = match.group(1)
        
        # 기관명 정제
        org_name = re.sub(r'[^\w\s-]', '', org_name)
        org_name = re.sub(r'[\s]+', '_', org_name).strip()

        # data 폴더를 기본 디렉토리로 사용
        data_dir = './data'

        # API 타입에 따른 디렉토리 설정
        api_type = data.get('api_type', 'unknown')
        api_category = table_info.get('API 유형', '')
        is_link_type = 'LINK' in api_category.upper() if api_category else False

        if api_type == 'link' or is_link_type:
            base_dir = os.path.join(data_dir, 'LINK', org_name)
        elif api_type in ['general', 'general_dynamic']:
            base_dir = os.path.join(data_dir, '일반API_old', org_name)
        elif api_type in ['swagger', 'swagger_dynamic']:
            base_dir = os.path.join(data_dir, '일반API', org_name)
        else:
            base_dir = os.path.join(data_dir, '기타', org_name)
        
        file_prefix = f"{doc_num}_{modified_date}"
        os.makedirs(base_dir, exist_ok=True)
        
        # 형식별 저장
        for format_type in formats:
            try:
                if format_type == 'json':
                    file_path = os.path.join(base_dir, f"{file_prefix}.json")
                    success, error = DataExporter._save_as_json(data, file_path)
                    if success:
                        saved_files.append(file_path)
                elif format_type == 'xml':
                    file_path = os.path.join(base_dir, f"{file_prefix}.xml")
                    success, error = DataExporter._save_as_xml(data, file_path)
                    if success:
                        saved_files.append(file_path)
                elif format_type == 'md':
                    file_path = os.path.join(base_dir, f"{file_prefix}.md")
                    success, error = DataExporter._save_as_markdown(data, file_path)
                    if success:
                        saved_files.append(file_path)
                elif format_type == 'csv':
                    # CSV는 data 폴더 바로 하위에 저장
                    os.makedirs('./data', exist_ok=True)
                    file_path = os.path.join('./data', 'TOTAL_RESULT_TABLE.CSV')
                    success, error = DataExporter._save_as_csv(data, file_path)
                    if success:
                        saved_files.append(file_path)
                
                if error:
                    errors.append(error)
            except Exception as e:
                errors.append(f"{format_type.upper()} 저장 실패: {str(e)}")
        
        return saved_files, errors

    @staticmethod
    def _save_as_json(data, file_path):
        """JSON 저장"""
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True, None
        except Exception as e:
            return False, f"JSON 저장 실패: {str(e)}"

    @staticmethod
    def _save_as_xml(data, file_path):
        """XML 저장"""
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            
            def _dict_to_xml(d, parent, name=None):
                if name is None:
                    element = parent
                else:
                    clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', str(name))
                    if clean_name and clean_name[0].isdigit():
                        clean_name = f"item_{clean_name}"
                    if not clean_name:
                        clean_name = "unnamed_item"
                    element = SubElement(parent, clean_name)
                
                if isinstance(d, dict):
                    for key, value in d.items():
                        _dict_to_xml(value, element, key)
                elif isinstance(d, list):
                    for i, item in enumerate(d):
                        if isinstance(item, dict):
                            _dict_to_xml(item, element, f"item_{i}")
                        else:
                            item_elem = SubElement(element, f"item_{i}")
                            item_elem.text = str(item) if item is not None else ""
                else:
                    element.text = str(d) if d is not None else ""
            
            root = Element("api_documentation")
            _dict_to_xml(data, root)
            
            rough_string = tostring(root, encoding='utf-8')
            reparsed = minidom.parseString(rough_string)
            pretty_xml = reparsed.toprettyxml(indent='  ', encoding='utf-8')
            
            with open(file_path, 'wb') as f:
                f.write(pretty_xml)
            
            return True, None
        except Exception as e:
            return False, f"XML 저장 실패: {str(e)}"

    @staticmethod
    def _save_as_markdown(data, file_path):
        """Markdown 저장"""
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            md_content = DataExporter._dict_to_markdown(data)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            return True, None
        except Exception as e:
            return False, f"Markdown 저장 실패: {str(e)}"

    @staticmethod
    def _dict_to_markdown(data):
        """딕셔너리를 Markdown으로 변환"""
        api_type = data.get('api_type', 'unknown')

        if api_type in ['swagger', 'swagger_dynamic']:
            return DataExporter._swagger_to_markdown(data)
        elif api_type in ['general', 'general_dynamic']:
            return DataExporter._general_api_to_markdown(data)
        elif api_type == 'link':
            return DataExporter._link_to_markdown(data)
        else:
            return "# API 문서\n\n알 수 없는 API 타입입니다."

    @staticmethod
    def _swagger_to_markdown(data):
        """Swagger API Markdown 변환"""
        lines = []
        api_info = data.get('api_info', {})
        endpoints = data.get('endpoints', [])
        
        # 헤더
        lines.append(f"# {api_info.get('title', 'API Documentation')}")
        lines.append("")
        if data.get('crawled_time'):
            lines.append(f"**크롤링 시간:** {data['crawled_time']}")
        if data.get('crawled_url'):
            lines.append(f"**원본 URL:** {data['crawled_url']}")
        lines.append("")
        
        # API 정보
        lines.append("## 📋 API 정보")
        lines.append("")
        if api_info.get('description'):
            lines.append(f"**설명:** {api_info['description']}")
            lines.append("")
        if api_info.get('base_url'):
            lines.append(f"**Base URL:** `{api_info['base_url']}`")
            lines.append("")
        
        # 엔드포인트
        if endpoints:
            base_url = api_info.get('base_url', '')
            lines.append(f"## 🔗 API 엔드포인트 ({len(endpoints)}개)")
            lines.append("")
            
            if base_url:
                lines.append(f"**Base URL:** `{base_url}`")
                lines.append("")
            
            for endpoint in endpoints:
                method = endpoint.get('method', 'GET')
                path = endpoint.get('path', '')
                description = endpoint.get('description', '')
                full_url = f"{base_url}{path}" if base_url and path else path
                
                lines.append(f"#### `{method}` {path}")
                if base_url:
                    lines.append(f"**완전한 URL:** `{full_url}`")
                lines.append("")
                if description:
                    lines.append(f"**설명:** {description}")
                lines.append("")
                
                # 파라미터
                parameters = endpoint.get('parameters', [])
                if parameters:
                    lines.append("**파라미터:**")
                    lines.append("")
                    lines.append("| 이름 | 타입 | 필수 | 설명 |")
                    lines.append("|------|------|------|------|")
                    for param in parameters:
                        name = str(param.get('name', '')).replace('|', '\\|')
                        param_type = str(param.get('type', '')).replace('|', '\\|')
                        required = "✅" if param.get('required', False) else "❌"
                        desc = str(param.get('description', '')).replace('|', '\\|')
                        if len(desc) > 50:
                            desc = desc[:50] + "..."
                        lines.append(f"| `{name}` | {param_type} | {required} | {desc} |")
                    lines.append("")
                
                # 응답
                responses = endpoint.get('responses', [])
                if responses:
                    lines.append("**응답:**")
                    lines.append("")
                    lines.append("| 상태 코드 | 설명 |")
                    lines.append("|-----------|------|")
                    for response in responses:
                        status_code = str(response.get('status_code', '')).replace('|', '\\|')
                        desc = str(response.get('description', '')).replace('|', '\\|')
                        if len(desc) > 80:
                            desc = desc[:80] + "..."
                        lines.append(f"| `{status_code}` | {desc} |")
                    lines.append("")
                
                lines.append("---")
                lines.append("")
        
        # 푸터
        lines.append("## 📝 생성 정보")
        lines.append("")
        lines.append("이 문서는 나라장터 API 크롤러에 의해 자동 생성되었습니다.")
        if data.get('api_id'):
            lines.append(f"**API ID:** {data['api_id']}")
        if api_info.get('base_url'):
            lines.append(f"**Base URL:** {api_info['base_url']}")
        
        return "\n".join(lines)

    @staticmethod
    def _general_api_to_markdown(data):
        """일반 API Markdown 변환"""
        lines = []
        general_info = data.get('general_api_info', {})
        detail_info = general_info.get('detail_info', {})
        
        # 헤더
        title = detail_info.get('description', 'API Documentation')
        if len(title) > 50:
            title = title[:50] + "..."
        lines.append(f"# {title}")
        lines.append("")
        if data.get('crawled_time'):
            lines.append(f"**크롤링 시간:** {data['crawled_time']}")
        if data.get('crawled_url'):
            lines.append(f"**원본 URL:** {data['crawled_url']}")
        lines.append("")
        
        # 상세정보
        if detail_info:
            lines.append("## 📋 API 상세정보")
            lines.append("")
            if detail_info.get('description'):
                lines.append(f"**기능 설명:** {detail_info['description']}")
                lines.append("")
            if detail_info.get('request_url'):
                lines.append(f"**요청 주소:** `{detail_info['request_url']}`")
                lines.append("")
            if detail_info.get('service_url'):
                lines.append(f"**서비스 URL:** `{detail_info['service_url']}`")
                lines.append("")
        
        # 푸터
        lines.append("## 📝 생성 정보")
        lines.append("")
        lines.append("이 문서는 나라장터 API 크롤러에 의해 자동 생성되었습니다.")
        lines.append("**API 타입:** 일반 API (Swagger 미지원)")
        if data.get('api_id'):
            lines.append(f"**API ID:** {data['api_id']}")
        
        return "\n".join(lines)

    @staticmethod
    def _link_to_markdown(data):
        """LINK 타입 API Markdown 변환"""
        lines = []
        table_info = data.get('info', {})
        
        lines.append("# LINK 타입 API")
        lines.append("")
        if data.get('crawled_time'):
            lines.append(f"**크롤링 시간:** {data['crawled_time']}")
        if data.get('crawled_url'):
            lines.append(f"**원본 URL:** {data['crawled_url']}")
        lines.append("")
        
        lines.append("## 📋 API 정보")
        lines.append("")
        lines.append("이 API는 LINK 타입으로, 외부 링크를 통해 제공됩니다.")
        lines.append("")
        
        if table_info:
            lines.append("## 📊 상세 정보")
            lines.append("")
            for key, value in table_info.items():
                lines.append(f"**{key}:** {value}")
            lines.append("")
        
        lines.append("## 📝 생성 정보")
        lines.append("")
        lines.append("이 문서는 나라장터 API 크롤러에 의해 자동 생성되었습니다.")
        lines.append("**API 타입:** LINK (외부 링크 제공)")
        if data.get('api_id'):
            lines.append(f"**API ID:** {data['api_id']}")
        
        return "\n".join(lines)

    @staticmethod
    def _save_as_csv(data, file_path):
        """CSV 저장 - 모든 문서 정보 누적"""
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            info_data = data.get('info', {})
            
            if not info_data:
                return False, "저장할 테이블 정보가 없습니다."
            
            target_fields = [
                '분류체계', '제공기관', '관리부서명', '관리부서 전화번호', 'API 유형',
                '데이터포맷', '활용신청', '키워드', '등록일', '수정일', '비용부과유무', '이용허락범위'
            ]
            
            filtered_data = {
                '문서번호': data.get('api_id', ''),
                '크롤링시간': data.get('crawled_time', ''),
                'URL': data.get('crawled_url', '')
            }
            
            for field in target_fields:
                filtered_data[field] = info_data.get(field, '')
            
            file_exists = os.path.isfile(file_path)
            
            with open(file_path, 'a', encoding='cp949', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=filtered_data.keys())
                if not file_exists:
                    writer.writeheader()
                writer.writerow(filtered_data)
            
            return True, None
        except Exception as e:
            return False, f"CSV 저장 실패: {str(e)}"