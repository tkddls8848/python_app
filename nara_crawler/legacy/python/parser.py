import json
import re
from selenium.webdriver.common.by import By
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
import os
from datetime import datetime
import requests
import csv
from functools import lru_cache
import asyncio
import aiohttp
from concurrent.futures import ThreadPoolExecutor

class NaraParser:
    """나라장터 API 파서 클래스"""
    
    def __init__(self, driver):
        self.driver = driver
        self._thread_pool = ThreadPoolExecutor(max_workers=4)
    
    def extract_table_info(self):
        """테이블 정보 추출 - 최우선 실행 (UDDI 값 추출 포함)"""
        try:
            table_info = {}
            
            # 모든 테이블 찾기
            tables = self.driver.find_elements(By.CSS_SELECTOR, "table.dataset-table")
            
            for table in tables:
                # 테이블 내용 추출
                rows = table.find_elements(By.TAG_NAME, "tr")
                
                for row in rows:
                    try:
                        # th와 td 태그 찾기
                        th = row.find_element(By.TAG_NAME, "th")
                        td = row.find_element(By.TAG_NAME, "td")
                        
                        key = th.text.strip()
                        value = td.text.strip()
                        
                        # 전화번호의 경우 JavaScript로 처리된 값을 가져오기
                        if "전화번호" in key:
                            try:
                                tel_no_div = td.find_element(By.ID, "telNoDiv")
                                value = tel_no_div.text.strip()
                            except:
                                pass
                        
                        # 링크가 있는 경우 링크 텍스트만 추출
                        if not value:
                            try:
                                link = td.find_element(By.TAG_NAME, "a")
                                value = link.text.strip()
                            except:
                                pass
                        
                        if key and value:
                            table_info[key] = value
                    except Exception as e:
                        continue
            
            # API 유형 확인 및 로깅
            api_type = table_info.get('API 유형', '')
            if api_type:
                if 'LINK' in api_type.upper():
                    pass
                else:
                    # LINK 타입이 아닌 경우에만 UDDI 값 추출
                    uddi_value = self._extract_uddi_value()
                    if uddi_value:
                        table_info['uddi'] = uddi_value
                        
                        # UDDI 값을 파일에 저장
                        self._save_uddi_to_file(uddi_value, self.driver.current_url)
            
            return table_info
            
        except Exception as e:
            return {}

    def _extract_uddi_value(self):
        """UDDI 값 추출"""
        try:
            # hidden input 요소에서 UDDI 값 찾기
            uddi_input = self.driver.find_element(By.ID, "publicDataDetailPk")
            uddi_value = uddi_input.get_attribute("value")
            
            if uddi_value and uddi_value.strip():
                return uddi_value.strip()
            else:
                return None
                
        except Exception as e:
            # 대안: 모든 hidden input에서 찾기
            try:
                hidden_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='hidden']")
                
                for input_elem in hidden_inputs:
                    input_id = input_elem.get_attribute("id")
                    input_value = input_elem.get_attribute("value")
                    
                    # publicDataDetailPk 또는 유사한 ID 패턴 확인
                    if input_id and ("publicDataDetailPk" in input_id.lower() or 
                                   "uddi" in input_id.lower() or 
                                   "detailpk" in input_id.lower()):
                        if input_value and input_value.strip():
                            return input_value.strip()
                
                return None
                
            except Exception as e2:
                return None

    def _save_uddi_to_file(self, uddi_value, current_url):
        """UDDI 값을 파일에 저장"""
        try:
            # uddi.txt 파일 경로 설정
            uddi_file_path = "uddi.txt"
            
            # 현재 시간 정보
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # 파일에 추가 모드로 저장
            with open(uddi_file_path, 'a', encoding='utf-8') as f:
                f.write(f"{uddi_value}\t{current_url}\t{current_time}\n")
            
        except Exception as e:
            pass

    @lru_cache(maxsize=100)
    def extract_swagger_json(self):
        """Swagger JSON 추출 - 개선된 로직"""
        try:
            # 1. JavaScript 변수에서 직접 추출 시도
            swagger_json = self.driver.execute_script("""
                try {
                    if (typeof swaggerJson !== 'undefined' && swaggerJson !== null) {
                        if (typeof swaggerJson === 'string') {
                            if (swaggerJson.trim() === '') {
                                return null;
                            }
                            return JSON.parse(swaggerJson);
                        } else if (typeof swaggerJson === 'object') {
                            return swaggerJson;
                        }
                    }
                    return null;
                } catch (e) {
                    return null;
                }
            """)
            
            if swagger_json and isinstance(swagger_json, dict) and swagger_json:
                return swagger_json
            
            # 2. script 태그에서 swaggerJson 변수 추출 시도
            scripts = self.driver.find_elements(By.TAG_NAME, "script")
            for script in scripts:
                script_content = script.get_attribute("innerHTML")
                if script_content and 'swaggerJson' in script_content:
                    # 빈 swaggerJson 패턴 먼저 확인
                    empty_patterns = [
                        r'var\s+swaggerJson\s*=\s*[\'\"]\s*[\'\"]\s*[;,]',
                        r'swaggerJson\s*=\s*[\'\"]\s*[\'\"]\s*[;,]',
                        r'var\s+swaggerJson\s*=\s*`\s*`\s*[;,]',
                        r'swaggerJson\s*=\s*`\s*`\s*[;,]'
                    ]
                    
                    for pattern in empty_patterns:
                        if re.search(pattern, script_content):
                            return None
                    
                    # swaggerJson 값 추출 패턴들
                    json_patterns = [
                        r'var\s+swaggerJson\s*=\s*(\{.*?\})\s*[;,]',  # var swaggerJson = {...};
                        r'swaggerJson\s*=\s*(\{.*?\})\s*[;,]',        # swaggerJson = {...};
                        r'swaggerJson\s*:\s*(\{.*?\})',               # swaggerJson: {...}
                        r'var\s+swaggerJson\s*=\s*`(\{.*?\})`',       # var swaggerJson = `{...}`;
                        r'swaggerJson\s*=\s*`(\{.*?\})`'              # swaggerJson = `{...}`;
                    ]
                    
                    for pattern in json_patterns:
                        json_match = re.search(pattern, script_content, re.DOTALL)
                        if json_match:
                            try:
                                json_str = json_match.group(1)
                                # JSON 문자열 정리
                                json_str = json_str.replace('\n', '').replace('\r', '')
                                parsed_json = json.loads(json_str)
                                if parsed_json:  # 빈 객체가 아닌 경우
                                    return parsed_json
                            except Exception as e:
                                continue
            
            # 3. window.swaggerUi 변수에서 추출 시도
            swagger_json = self.driver.execute_script("""
                try {
                    if (window.swaggerUi && window.swaggerUi.spec) {
                        return window.swaggerUi.spec;
                    }
                    return null;
                } catch (e) {
                    return null;
                }
            """)
            
            if swagger_json and isinstance(swagger_json, dict) and swagger_json:
                return swagger_json
            
            # 4. Swagger UI 초기화 코드에서 URL 추출 시도
            for script in scripts:
                script_content = script.get_attribute("innerHTML")
                if script_content and 'SwaggerUIBundle' in script_content:
                    # URL 패턴 찾기
                    url_match = re.search(r'url\s*:\s*[\'"]([^\'"]+)[\'"]', script_content)
                    if url_match:
                        swagger_url = url_match.group(1)
                        if swagger_url.startswith('/'):
                            current_url = self.driver.current_url
                            base_url = '/'.join(current_url.split('/')[:3])
                            swagger_url = base_url + swagger_url
                        
                        try:
                            response = requests.get(swagger_url, timeout=10)
                            if response.status_code == 200:
                                swagger_data = response.json()
                                if swagger_data:
                                    return swagger_data
                        except Exception as e:
                            pass
                    
                    # 인라인 spec 객체 찾기
                    spec_match = re.search(r'spec\s*:\s*(\{.*?\})\s*[,}]', script_content, re.DOTALL)
                    if spec_match:
                        try:
                            spec_str = spec_match.group(1)
                            spec_json = json.loads(spec_str)
                            if spec_json:
                                return spec_json
                        except Exception as e:
                            pass
            
            return None
            
        except Exception as e:
            return None

    def extract_general_api_info(self):
        """일반 API 정보 추출 (Swagger가 없는 경우)"""
        try:
            general_info = {}
            
            # 1. 상세기능 정보 추출
            detail_info = self._extract_detail_info()
            if detail_info:
                general_info['detail_info'] = detail_info
            
            # 2. 요청변수(Request Parameter) 추출
            request_params = self._extract_request_parameters()
            if request_params:
                general_info['request_parameters'] = request_params
            
            # 3. 출력결과(Response Element) 추출
            response_elements = self._extract_response_elements()
            if response_elements:
                general_info['response_elements'] = response_elements
            
            return general_info
            
        except Exception as e:
            return {}
    
    def _extract_detail_info(self):
        """상세기능 정보 추출"""
        try:
            detail_info = {}
            
            # open-api-detail-result div 찾기
            detail_div = self.driver.find_element(By.ID, "open-api-detail-result")
            
            # h4.tit 내용 추출 (API 설명)
            try:
                title_elem = detail_div.find_element(By.CSS_SELECTOR, "h4.tit")
                detail_info['description'] = title_elem.text.strip()
            except:
                detail_info['description'] = ""
            
            # box-gray 하위 리스트 추출
            try:
                box_gray = detail_div.find_element(By.CLASS_NAME, "box-gray")
                list_items = box_gray.find_elements(By.CSS_SELECTOR, "ul.dot-list li")
                
                for item in list_items:
                    item_text = item.text.strip()
                    
                    # 활용승인 절차
                    if "활용승인 절차" in item_text:
                        # 개발단계와 운영단계 정보 추출
                        dev_match = re.search(r'개발단계\s*:\s*([^/]+)', item_text)
                        op_match = re.search(r'운영단계\s*:\s*(.+)', item_text)
                        
                        approval_process = {}
                        if dev_match:
                            approval_process['development'] = dev_match.group(1).strip()
                        if op_match:
                            approval_process['operation'] = op_match.group(1).strip()
                        
                        detail_info['approval_process'] = approval_process
                    
                    # 신청가능 트래픽
                    elif "신청가능 트래픽" in item_text:
                        # 개발계정과 운영계정 정보 추출
                        dev_traffic_match = re.search(r'개발계정\s*:\s*([^/]+)', item_text)
                        op_traffic_match = re.search(r'운영계정\s*:\s*(.+)', item_text)
                        
                        traffic_info = {}
                        if dev_traffic_match:
                            traffic_info['development'] = dev_traffic_match.group(1).strip()
                        if op_traffic_match:
                            traffic_info['operation'] = op_traffic_match.group(1).strip()
                        
                        detail_info['traffic_limit'] = traffic_info
                    
                    # 요청주소
                    elif "요청주소" in item_text:
                        url_match = re.search(r'요청주소\s*(.+)', item_text)
                        if url_match:
                            detail_info['request_url'] = url_match.group(1).strip()
                    
                    # 서비스URL
                    elif "서비스URL" in item_text:
                        service_url_match = re.search(r'서비스URL\s*(.+)', item_text)
                        if service_url_match:
                            detail_info['service_url'] = service_url_match.group(1).strip()
            except Exception as e:
                pass
            
            return detail_info
            
        except Exception as e:
            return {}
    
    def _extract_request_parameters(self):
        """요청변수(Request Parameter) 테이블 추출"""
        try:
            parameters = []
            
            # 요청변수 섹션 찾기
            headers = self.driver.find_elements(By.CSS_SELECTOR, "h4.tit")
            request_header = None
            
            for header in headers:
                if "요청변수" in header.text and "Request Parameter" in header.text:
                    request_header = header
                    break
            
            if not request_header:
                return parameters
            
            # 요청변수 테이블 찾기 (헤더 다음 div.col-table)
            table_div = request_header.find_element(By.XPATH, "following-sibling::div[contains(@class, 'col-table')]")
            table = table_div.find_element(By.TAG_NAME, "table")
            
            # 테이블 행 추출 (헤더 제외)
            tbody = table.find_element(By.TAG_NAME, "tbody")
            rows = tbody.find_elements(By.TAG_NAME, "tr")
            
            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 6:  # 최소 6개 열이 있어야 함
                        parameter = {
                            'name_kor': cells[0].text.strip(),          # 항목명(국문)
                            'name_eng': cells[1].text.strip(),          # 항목명(영문)
                            'size': cells[2].text.strip(),              # 항목크기
                            'required': cells[3].text.strip(),          # 항목구분 (필/옵)
                            'sample_data': cells[4].text.strip(),       # 샘플데이터
                            'description': cells[5].text.strip()        # 항목설명
                        }
                        
                        # 빈 값이 아닌 경우만 추가
                        if parameter['name_eng'] or parameter['name_kor']:
                            parameters.append(parameter)
                            
                except Exception as e:
                    continue
            
            return parameters
            
        except Exception as e:
            return []
    
    def _extract_response_elements(self):
        """출력결과(Response Element) 테이블 추출"""
        try:
            elements = []
            
            # 출력결과 섹션 찾기
            headers = self.driver.find_elements(By.CSS_SELECTOR, "h4.tit")
            response_header = None
            
            for header in headers:
                if "출력결과" in header.text and "Response Element" in header.text:
                    response_header = header
                    break
            
            if not response_header:
                return elements
            
            # 출력결과 테이블 찾기 (헤더 다음 div.col-table)
            table_div = response_header.find_element(By.XPATH, "following-sibling::div[contains(@class, 'col-table')]")
            table = table_div.find_element(By.TAG_NAME, "table")
            
            # 테이블 행 추출 (헤더 제외)
            tbody = table.find_element(By.TAG_NAME, "tbody")
            rows = tbody.find_elements(By.TAG_NAME, "tr")
            
            for row in rows:
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 6:  # 최소 6개 열이 있어야 함
                        element = {
                            'name_kor': cells[0].text.strip(),          # 항목명(국문)
                            'name_eng': cells[1].text.strip(),          # 항목명(영문)
                            'size': cells[2].text.strip(),              # 항목크기
                            'required': cells[3].text.strip(),          # 항목구분 (필/옵)
                            'sample_data': cells[4].text.strip(),       # 샘플데이터
                            'description': cells[5].text.strip()        # 항목설명
                        }
                        
                        # 빈 값이 아닌 경우만 추가
                        if element['name_eng'] or element['name_kor']:
                            elements.append(element)
                            
                except Exception as e:
                    continue
            
            return elements
            
        except Exception as e:
            return []
    
    def extract_api_info(self, swagger_json):
        """API 기본 정보 추출"""
        api_info = {}
        
        if not swagger_json:
            return api_info
            
        # 기본 정보 추출
        info = swagger_json.get('info', {})
        api_info['title'] = info.get('title', '')
        api_info['description'] = info.get('description', '')
        api_info['version'] = info.get('version', '')
        
        # 확장 정보 추출
        if 'x-' in info:
            for key, value in info.items():
                if key.startswith('x-'):
                    api_info[key.replace('x-', '')] = value
        
        return api_info
    
    def extract_base_url(self, swagger_json):
        """Base URL 추출"""
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
        """엔드포인트 정보 추출"""
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
                        'parameters': self._extract_parameters(data.get('parameters', [])),
                        'responses': self._extract_responses(data.get('responses', {})),
                        'tags': data.get('tags', []),
                        'section': data.get('tags', ['Default'])[0] if data.get('tags') else 'Default'
                    }
                    endpoints.append(endpoint)
        
        return endpoints
    
    def _extract_parameters(self, params_list):
        """파라미터 정보 추출"""
        parameters = []
        
        for param in params_list:
            parameters.append({
                'name': param.get('name', ''),
                'description': param.get('description', ''),
                'required': param.get('required', False),
                'type': param.get('type', '') or (param.get('schema', {}).get('type', '') if 'schema' in param else '')
            })
        
        return parameters
    
    def _extract_responses(self, responses_dict):
        """응답 정보 추출"""
        responses = []
        
        for status_code, data in responses_dict.items():
            responses.append({
                'status_code': status_code,
                'description': data.get('description', '')
            })
        
        return responses


class DataExporter:
    """데이터 내보내기 클래스"""
    
    @staticmethod
    def save_as_json(data, file_path):
        """JSON 형태로 저장"""
        try:
            # 디렉토리가 없으면 생성
            dir_path = os.path.dirname(file_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            return True, None
        except Exception as e:
            return False, f"JSON 저장 실패: {str(e)}"
    
    @staticmethod
    def dict_to_xml(data, root_name="api_documentation"):
        """딕셔너리를 XML로 변환"""
        try:
            def _dict_to_xml_element(d, parent, name=None):
                if name is None:
                    element = parent
                else:
                    # XML 태그명에서 특수문자 제거 및 유효성 검사
                    clean_name = re.sub(r'[^a-zA-Z0-9_-]', '_', str(name))
                    # 숫자로 시작하는 태그명 처리
                    if clean_name and clean_name[0].isdigit():
                        clean_name = f"item_{clean_name}"
                    # 빈 태그명 처리
                    if not clean_name:
                        clean_name = "unnamed_item"
                    
                    element = SubElement(parent, clean_name)
                
                if isinstance(d, dict):
                    for key, value in d.items():
                        _dict_to_xml_element(value, element, key)
                elif isinstance(d, list):
                    for i, item in enumerate(d):
                        if isinstance(item, dict):
                            _dict_to_xml_element(item, element, f"item_{i}")
                        else:
                            item_elem = SubElement(element, f"item_{i}")
                            item_elem.text = str(item) if item is not None else ""
                else:
                    element.text = str(d) if d is not None else ""
            
            root = Element(root_name)
            _dict_to_xml_element(data, root)
            return root, None
        except Exception as e:
            return None, f"XML 변환 실패: {str(e)}"
    
    @staticmethod
    def save_as_xml(data, file_path):
        """XML 형태로 저장"""
        try:
            # 디렉토리가 없으면 생성
            dir_path = os.path.dirname(file_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            # 딕셔너리를 XML로 변환
            root, error = DataExporter.dict_to_xml(data)
            if error:
                return False, error
            
            # 예쁘게 포맷팅
            rough_string = tostring(root, encoding='utf-8')
            reparsed = minidom.parseString(rough_string)
            pretty_xml = reparsed.toprettyxml(indent='  ', encoding='utf-8')
            
            with open(file_path, 'wb') as f:
                f.write(pretty_xml)
            
            return True, None
        except Exception as e:
            return False, f"XML 저장 실패: {str(e)}"
    
    @staticmethod
    def save_as_markdown(data, file_path):
        """Markdown 형태로 저장"""
        try:
            # 디렉토리가 없으면 생성
            dir_path = os.path.dirname(file_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            md_content = DataExporter.dict_to_markdown(data)
            
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(md_content)
            
            return True, None
        except Exception as e:
            return False, f"Markdown 저장 실패: {str(e)}"
    
    @staticmethod
    def dict_to_markdown(data):
        """딕셔너리를 Markdown 형식으로 변환"""
        try:
            md_lines = []
            api_type = data.get('api_type', 'unknown')
            
            # API 타입에 따른 처리 분기
            if api_type == 'swagger':
                return DataExporter._swagger_to_markdown(data, md_lines)
            elif api_type == 'general':
                return DataExporter._general_api_to_markdown(data, md_lines)
            elif api_type == 'link':
                return DataExporter._link_to_markdown(data, md_lines)
            else:
                return "# API 문서\n\n알 수 없는 API 타입입니다."
                
        except Exception as e:
            print(f"⚠️ Markdown 변환 중 오류: {e}")
            return f"# Markdown 변환 오류\n\n변환 중 오류가 발생했습니다: {str(e)}"
    
    @staticmethod
    def _link_to_markdown(data, md_lines):
        """LINK 타입 API를 Markdown으로 변환"""
        md_lines.append("# LINK 타입 API")
        md_lines.append("")
        
        # 크롤링 정보
        if data.get('crawled_time'):
            md_lines.append(f"**크롤링 시간:** {data['crawled_time']}")
        if data.get('crawled_url'):
            md_lines.append(f"**원본 URL:** {data['crawled_url']}")
        md_lines.append("")
        
        md_lines.append("## 📋 API 정보")
        md_lines.append("")
        md_lines.append("이 API는 LINK 타입으로, 외부 링크를 통해 제공됩니다.")
        md_lines.append("")
        
        # 테이블 정보
        table_info = data.get('info', {})
        if table_info:
            md_lines.append("## 📊 상세 정보")
            md_lines.append("")
            for key, value in table_info.items():
                md_lines.append(f"**{key}:** {value}")
            md_lines.append("")
        
        # 건너뛴 이유
        if data.get('skip_reason'):
            md_lines.append("## ℹ️ 처리 정보")
            md_lines.append("")
            md_lines.append(f"**처리 상태:** {data['skip_reason']}")
            md_lines.append("")
        
        # 푸터
        md_lines.append("## 📝 생성 정보")
        md_lines.append("")
        md_lines.append("이 문서는 나라장터 API 크롤러에 의해 자동 생성되었습니다.")
        md_lines.append("**API 타입:** LINK (외부 링크 제공)")
        if data.get('api_id'):
            md_lines.append(f"**API ID:** {data['api_id']}")
        
        return "\n".join(md_lines)   
    
    @staticmethod
    def _swagger_to_markdown(data, md_lines):
        """Swagger API를 Markdown으로 변환"""
        api_info = data.get('api_info', {})
        endpoints = data.get('endpoints', [])
        
        # 제목
        title = api_info.get('title', 'API Documentation')
        md_lines.append(f"# {title}")
        md_lines.append("")
        
        # 크롤링 정보
        if data.get('crawled_time'):
            md_lines.append(f"**크롤링 시간:** {data['crawled_time']}")
        if data.get('crawled_url'):
            md_lines.append(f"**원본 URL:** {data['crawled_url']}")
        md_lines.append("")
        
        # API 기본 정보
        md_lines.append("## 📋 API 정보")
        md_lines.append("")
        
        if api_info.get('description'):
            description = str(api_info['description']).replace('\n', ' ').strip()
            md_lines.append(f"**설명:** {description}")
            md_lines.append("")
        
        # Base URL 정보
        if api_info.get('base_url'):
            md_lines.append(f"**Base URL:** `{api_info['base_url']}`")
            md_lines.append("")
        
        if api_info.get('schemes') and isinstance(api_info['schemes'], list):
            schemes_str = ", ".join(str(s) for s in api_info['schemes'])
            md_lines.append(f"**지원 프로토콜:** {schemes_str}")
            md_lines.append("")
        
        # 엔드포인트 정보
        if endpoints and isinstance(endpoints, list):
            md_lines.append(f"## 🔗 API 엔드포인트 ({len(endpoints)}개)")
            md_lines.append("")
            
            # Base URL이 있으면 완전한 URL 정보 추가
            base_url = api_info.get('base_url', '')
            if base_url:
                md_lines.append(f"**Base URL:** `{base_url}`")
                md_lines.append("")
            
            # 섹션별로 그룹화
            sections = {}
            for endpoint in endpoints:
                if not isinstance(endpoint, dict):
                    continue
                section = endpoint.get('section', 'Default')
                if section not in sections:
                    sections[section] = []
                sections[section].append(endpoint)
            
            for section_name, section_endpoints in sections.items():
                if len(sections) > 1:  # 섹션이 여러 개인 경우만 섹션 제목 표시
                    md_lines.append(f"### {section_name}")
                    md_lines.append("")
                
                for endpoint in section_endpoints:
                    try:
                        # 엔드포인트 제목
                        method = str(endpoint.get('method', 'GET')).upper()
                        path = str(endpoint.get('path', ''))
                        description = str(endpoint.get('description', '')).replace('\n', ' ').strip()
                        
                        # 완전한 URL 생성 (Base URL이 있는 경우)
                        full_url = f"{base_url}{path}" if base_url and path else path
                        
                        md_lines.append(f"#### `{method}` {path}")
                        if base_url:
                            md_lines.append(f"**완전한 URL:** `{full_url}`")
                        md_lines.append("")
                        
                        if description:
                            md_lines.append(f"**설명:** {description}")
                            md_lines.append("")
                        
                        # 파라미터 정보
                        parameters = endpoint.get('parameters', [])
                        if parameters and isinstance(parameters, list):
                            md_lines.append("**파라미터:**")
                            md_lines.append("")
                            md_lines.append("| 이름 | 타입 | 필수 | 설명 |")
                            md_lines.append("|------|------|------|------|")
                            
                            for param in parameters:
                                if not isinstance(param, dict):
                                    continue
                                name = str(param.get('name', '')).replace('|', '\\|')
                                param_type = str(param.get('type', '')).replace('|', '\\|')
                                required = "✅" if param.get('required', False) else "❌"
                                desc = str(param.get('description', '')).replace('\n', ' ').replace('|', '\\|')
                                
                                # 설명이 너무 길면 줄이기
                                if len(desc) > 50:
                                    desc = desc[:50] + "..."
                                
                                md_lines.append(f"| `{name}` | {param_type} | {required} | {desc} |")
                            
                            md_lines.append("")
                        
                        # 응답 정보
                        responses = endpoint.get('responses', [])
                        if responses and isinstance(responses, list):
                            md_lines.append("**응답:**")
                            md_lines.append("")
                            md_lines.append("| 상태 코드 | 설명 |")
                            md_lines.append("|-----------|------|")
                            
                            for response in responses:
                                if not isinstance(response, dict):
                                    continue
                                status_code = str(response.get('status_code', '')).replace('|', '\\|')
                                desc = str(response.get('description', '')).replace('\n', ' ').replace('|', '\\|')
                                
                                # 설명이 너무 길면 줄이기
                                if len(desc) > 80:
                                    desc = desc[:80] + "..."
                                
                                md_lines.append(f"| `{status_code}` | {desc} |")
                            
                            md_lines.append("")
                        
                        md_lines.append("---")
                        md_lines.append("")
                    except Exception as e:
                        print(f"⚠️ 엔드포인트 처리 중 오류: {e}")
                        continue
        
        # 푸터
        md_lines.append("## 📝 생성 정보")
        md_lines.append("")
        md_lines.append("이 문서는 나라장터 API 크롤러에 의해 자동 생성되었습니다.")
        if data.get('api_id'):
            md_lines.append(f"**API ID:** {data['api_id']}")
        if api_info.get('base_url'):
            md_lines.append(f"**Base URL:** {api_info['base_url']}")
        
        return "\n".join(md_lines)
    
    @staticmethod
    def _general_api_to_markdown(data, md_lines):
        """일반 API를 Markdown으로 변환"""
        general_info = data.get('general_api_info', {})
        detail_info = general_info.get('detail_info', {})
        
        # 제목
        title = detail_info.get('description', 'API Documentation')[:50] + "..." if len(detail_info.get('description', '')) > 50 else detail_info.get('description', 'API Documentation')
        md_lines.append(f"# {title}")
        md_lines.append("")
        
        # 크롤링 정보
        if data.get('crawled_time'):
            md_lines.append(f"**크롤링 시간:** {data['crawled_time']}")
        if data.get('crawled_url'):
            md_lines.append(f"**원본 URL:** {data['crawled_url']}")
        md_lines.append("")
        
        # 상세기능 정보
        if detail_info:
            md_lines.append("## 📋 API 상세정보")
            md_lines.append("")
            
            if detail_info.get('description'):
                md_lines.append(f"**기능 설명:**")
                md_lines.append(f"{detail_info['description']}")
                md_lines.append("")
            
            if detail_info.get('request_url'):
                md_lines.append(f"**요청 주소:** `{detail_info['request_url']}`")
                md_lines.append("")
            
            if detail_info.get('service_url'):
                md_lines.append(f"**서비스 URL:** `{detail_info['service_url']}`")
                md_lines.append("")
            
            # 활용승인 절차
            if detail_info.get('approval_process'):
                approval = detail_info['approval_process']
                md_lines.append("**활용승인 절차:**")
                if approval.get('development'):
                    md_lines.append(f"- 개발단계: {approval['development']}")
                if approval.get('operation'):
                    md_lines.append(f"- 운영단계: {approval['operation']}")
                md_lines.append("")
            
            # 신청가능 트래픽
            if detail_info.get('traffic_limit'):
                traffic = detail_info['traffic_limit']
                md_lines.append("**신청가능 트래픽:**")
                if traffic.get('development'):
                    md_lines.append(f"- 개발계정: {traffic['development']}")
                if traffic.get('operation'):
                    md_lines.append(f"- 운영계정: {traffic['operation']}")
                md_lines.append("")
        
        # 요청변수
        request_params = general_info.get('request_parameters', [])
        if request_params:
            md_lines.append(f"## 📤 요청변수 ({len(request_params)}개)")
            md_lines.append("")
            md_lines.append("| 항목명(국문) | 항목명(영문) | 크기 | 필수여부 | 샘플데이터 | 설명 |")
            md_lines.append("|--------------|--------------|------|----------|------------|------|")
            
            for param in request_params:
                name_kor = str(param.get('name_kor', '')).replace('|', '\\|')
                name_eng = str(param.get('name_eng', '')).replace('|', '\\|')
                size = str(param.get('size', '')).replace('|', '\\|')
                required = str(param.get('required', '')).replace('|', '\\|')
                sample = str(param.get('sample_data', '')).replace('|', '\\|')
                desc = str(param.get('description', '')).replace('|', '\\|')
                
                # 긴 텍스트 줄이기
                if len(sample) > 30:
                    sample = sample[:30] + "..."
                if len(desc) > 50:
                    desc = desc[:50] + "..."
                
                md_lines.append(f"| {name_kor} | `{name_eng}` | {size} | {required} | {sample} | {desc} |")
            
            md_lines.append("")
        
        # 출력결과
        response_elements = general_info.get('response_elements', [])
        if response_elements:
            md_lines.append(f"## 📥 출력결과 ({len(response_elements)}개)")
            md_lines.append("")
            md_lines.append("| 항목명(국문) | 항목명(영문) | 크기 | 필수여부 | 샘플데이터 | 설명 |")
            md_lines.append("|--------------|--------------|------|----------|------------|------|")
            
            for element in response_elements:
                name_kor = str(element.get('name_kor', '')).replace('|', '\\|')
                name_eng = str(element.get('name_eng', '')).replace('|', '\\|')
                size = str(element.get('size', '')).replace('|', '\\|')
                required = str(element.get('required', '')).replace('|', '\\|')
                sample = str(element.get('sample_data', '')).replace('|', '\\|')
                desc = str(element.get('description', '')).replace('|', '\\|')
                
                # 긴 텍스트 줄이기
                if len(sample) > 30:
                    sample = sample[:30] + "..."
                if len(desc) > 50:
                    desc = desc[:50] + "..."
                
                md_lines.append(f"| {name_kor} | `{name_eng}` | {size} | {required} | {sample} | {desc} |")
            
            md_lines.append("")
        
        # 푸터
        md_lines.append("## 📝 생성 정보")
        md_lines.append("")
        md_lines.append("이 문서는 나라장터 API 크롤러에 의해 자동 생성되었습니다.")
        md_lines.append("**API 타입:** 일반 API (Swagger 미지원)")
        if data.get('api_id'):
            md_lines.append(f"**API ID:** {data['api_id']}")
        
        return "\n".join(md_lines)
    
    @staticmethod
    def save_as_csv(data, file_path):
        """CSV 형태로 저장 - 모든 문서의 정보를 하나의 파일에 누적"""
        try:
            # 디렉토리가 없으면 생성
            dir_path = os.path.dirname(file_path)
            if dir_path:
                os.makedirs(dir_path, exist_ok=True)
            
            # info 데이터 추출
            info_data = data.get('info', {})
            if not info_data:
                return False, "저장할 테이블 정보가 없습니다."
            
            # 저장할 항목 목록
            target_fields = [
                '분류체계',
                '제공기관',
                '관리부서명',
                '관리부서 전화번호',
                'API 유형',
                '데이터포맷',
                '활용신청',
                '키워드',
                '등록일',
                '수정일',
                '비용부과유무',
                '이용허락범위'
            ]
            
            # 문서 번호와 크롤링 시간 추가
            filtered_data = {
                '문서번호': data.get('api_id', ''),
                '크롤링시간': data.get('crawled_time', ''),
                'URL': data.get('crawled_url', '')
            }
            
            # 지정된 항목만 필터링하여 추가
            for field in target_fields:
                filtered_data[field] = info_data.get(field, '')
            
            # 파일이 존재하는지 확인
            file_exists = os.path.isfile(file_path)
            
            # CSV 파일 작성 (cp949 인코딩 사용 - MS Office 호환)
            with open(file_path, 'a', encoding='cp949', newline='') as f:
                writer = csv.DictWriter(f, fieldnames=filtered_data.keys())
                
                # 파일이 새로 생성되는 경우에만 헤더 작성
                if not file_exists:
                    writer.writeheader()
                
                # 데이터 작성
                writer.writerow(filtered_data)
            
            return True, None
        except Exception as e:
            return False, f"CSV 저장 실패: {str(e)}"

    @staticmethod
    def save_crawling_result(data, output_dir, api_id, formats=['json', 'xml']):
        """크롤링 결과 저장 - 개선된 로직"""
        saved_files = []
        errors = []
        
        # 테이블 정보에서 제공기관과 수정일 추출
        table_info = data.get('info', {})
        org_name = table_info.get('제공기관', 'unknown_org')
        modified_date = table_info.get('수정일', 'unknown_date')
        
        # URL에서 문서번호 추출
        crawled_url = data.get('crawled_url', '')
        doc_num = 'unknown_doc'
        if crawled_url:
            match = re.search(r'/data/(\d+)/openapi\.do', crawled_url)
            if match:
                doc_num = match.group(1)
        
        # 기관명에서 특수문자 제거 및 공백을 언더스코어로 변경
        org_name = re.sub(r'[^\w\s-]', '', org_name)
        org_name = re.sub(r'[\s]+', '_', org_name).strip()
        
        # API 유형 확인
        api_type = data.get('api_type', 'unknown')
        api_category = table_info.get('API 유형', '')
        is_link_type = 'LINK' in api_category.upper() if api_category else False
        
        # API 유형에 따른 상위 디렉토리 설정 (개선된 로직)
        if api_type == 'link' or is_link_type:
            # LINK 타입의 경우
            base_output_dir = os.path.join(output_dir, 'LINK', org_name)
        elif api_type == 'general':
            # 일반 API (Swagger 미지원)의 경우
            base_output_dir = os.path.join(output_dir, '일반API_old', org_name)
        elif api_type == 'swagger':
            # Swagger API의 경우
            base_output_dir = os.path.join(output_dir, '일반API', org_name)
        else:
            # 알 수 없는 타입
            base_output_dir = os.path.join(output_dir, '기타', org_name)
        
        # 파일명 생성
        file_prefix = f"{doc_num}_{modified_date}"
        
        os.makedirs(base_output_dir, exist_ok=True)
        
        # 각 형식별로 저장
        for format_type in formats:
            try:
                if format_type == 'json':
                    file_path = os.path.join(base_output_dir, f"{file_prefix}.json")
                    success, error = DataExporter.save_as_json(data, file_path)
                    if success:
                        saved_files.append(file_path)
                elif format_type == 'xml':
                    file_path = os.path.join(base_output_dir, f"{file_prefix}.xml")
                    success, error = DataExporter.save_as_xml(data, file_path)
                    if success:
                        saved_files.append(file_path)
                elif format_type == 'md':
                    file_path = os.path.join(base_output_dir, f"{file_prefix}.md")
                    success, error = DataExporter.save_as_markdown(data, file_path)
                    if success:
                        saved_files.append(file_path)
                elif format_type == 'csv':
                    # CSV 파일은 CSV 디렉토리에 저장 (단일 파일)
                    csv_dir = os.path.join(output_dir, 'CSV')
                    os.makedirs(csv_dir, exist_ok=True)
                    file_path = os.path.join(csv_dir, "all_table_info.csv")
                    success, error = DataExporter.save_as_csv(data, file_path)
                    if success:
                        saved_files.append(file_path)
            
            except Exception as e:
                error_msg = f"{format_type.upper()} 저장 실패: {str(e)}"
                print(f"❌ {error_msg}")
                errors.append(error_msg)
        
        return saved_files, errors
    
    @staticmethod
    def save_table_info(data, output_dir, api_id):
        """테이블 정보 저장"""
        try:
            # info 디렉토리 생성
            info_dir = os.path.join(output_dir, 'info')
            os.makedirs(info_dir, exist_ok=True)
            
            # 파일명 생성
            file_name = f"{api_id}_table_info.json"
            file_path = os.path.join(info_dir, file_name)
            
            # JSON으로 저장
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            
            return True, file_path
            
        except Exception as e:
            return False, f"테이블 정보 저장 실패: {str(e)}"