"""
텍스트 정제 유틸리티
"""
import re


def clean_text(text):
    """텍스트 정제"""
    if not isinstance(text, str):
        return text
    text = re.sub(r'[\n\r\t]+', ' ', text)
    text = re.sub(r'<[^>]+>', '', text)
    text = re.sub(r' +', ' ', text)
    return text.strip()


def clean_text_preserve_tags(text):
    """HTML 태그를 보존하면서 공백 문자만 정리"""
    if not isinstance(text, str):
        return text
    # 개행, 캐리지 리턴, 탭 문자 제거
    text = re.sub(r'[\n\r\t]+', '', text)
    # 연속된 공백을 하나로
    text = re.sub(r' +', ' ', text)
    return text.strip()


def clean_all_text(obj, skip_keys=None):
    """재귀적으로 모든 텍스트 정제

    Args:
        obj: 정제할 객체 (dict, list, str 등)
        skip_keys: HTML 태그를 보존할 키 이름 목록 (set 또는 list)
                  이 키들의 값은 태그를 보존하고 공백 문자만 정리
    """
    if skip_keys is None:
        skip_keys = set()
    elif not isinstance(skip_keys, set):
        skip_keys = set(skip_keys)

    if isinstance(obj, dict):
        result = {}
        for k, v in obj.items():
            if k in skip_keys:
                # skip_keys에 해당하는 키는 태그 보존하면서 공백만 정리
                if isinstance(v, str):
                    result[k] = clean_text_preserve_tags(v)
                elif isinstance(v, (dict, list)):
                    result[k] = clean_all_text(v, skip_keys)
                else:
                    result[k] = v
            else:
                # 일반 키는 태그 제거
                result[k] = clean_all_text(v, skip_keys)
        return result
    elif isinstance(obj, list):
        return [clean_all_text(v, skip_keys) for v in obj]
    elif isinstance(obj, str):
        return clean_text(obj)
    else:
        return obj