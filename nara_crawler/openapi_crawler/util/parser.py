import json
import re
import os
import csv
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom

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
        is_link_type = 'Link' in api_category.upper() if api_category else False

        if api_type == 'link' or is_link_type:
            base_dir = os.path.join(data_dir, '01. Link', org_name)
        elif api_type in ['general', 'general_dynamic']:
            base_dir = os.path.join(data_dir, '02. General API', org_name)  # 일반API_old → General API
        elif api_type in ['swagger', 'swagger_dynamic']:
            base_dir = os.path.join(data_dir, '03. Swagger API', org_name)  # 일반API → Swagger API
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
                elif format_type == 'csv':
                    # CSV는 data 폴더 바로 하위에 저장
                    os.makedirs('./data', exist_ok=True)
                    file_path = os.path.join('./data', 'all_result_table.csv')
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