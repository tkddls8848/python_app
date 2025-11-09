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


def clean_all_text(obj):
    """재귀적으로 모든 텍스트 정제"""
    if isinstance(obj, dict):
        return {k: clean_all_text(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [clean_all_text(v) for v in obj]
    elif isinstance(obj, str):
        return clean_text(obj)
    else:
        return obj
