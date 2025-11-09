"""조달청 입찰공고 조회 MCP 서버"""
import os
import re
import sys
from datetime import date
from fastmcp import FastMCP
from dotenv import load_dotenv

# 디버깅 로그 (stderr로 출력)
def debug_log(message):
    print(f"[DEBUG] {message}", file=sys.stderr, flush=True)

debug_log("서버 초기화 시작")

# .env 파일 로드
load_dotenv()
debug_log(".env 파일 로드 완료")

# MCP 서버 생성
mcp = FastMCP("조달청 입찰공고 조회")
debug_log("MCP 인스턴스 생성 완료")

# 환경변수에서 설정 가져오기
SERVICE_KEY = os.getenv("PROCUREMENT_API_KEY", "YOUR_SERVICE_KEY")
BASE_URL = os.getenv("BASE_URL", "https://apis.data.go.kr/1230000/ao/PubDataOpnStdService")
DEFAULT_PAGE_SIZE = int(os.getenv("DEFAULT_PAGE_SIZE", "100"))

debug_log(f"서비스키: {SERVICE_KEY[:20]}...")
debug_log(f"Base URL: {BASE_URL}")

# 엔드포인트
ENDPOINT = "/getDataSetOpnStdBidPblancInfo"


def parse_date(query: str) -> tuple[str, str] | None:
    """
    "25년 4월" → ("202504010000", "202504302359")
    """
    pattern = r'(\d{2,4})년\s*(\d{1,2})월'
    match = re.search(pattern, query)
    
    if not match:
        return None
    
    year = match.group(1)
    month = match.group(2)
    
    # 2자리 연도 보정
    if len(year) == 2:
        year = f"20{year}"
    
    year = int(year)
    month = int(month)
    
    # 시작일: 해당 월 1일 00:00
    start = date(year, month, 1)
    
    # 종료일: 해당 월 마지막날 23:59
    if month == 12:
        end = date(year, 12, 31)
    else:
        # 다음 달 첫날에서 하루 빼기
        if month == 1:
            end = date(year, 1, 31)
        elif month == 2:
            # 윤년 체크
            if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
                end = date(year, 2, 29)
            else:
                end = date(year, 2, 28)
        elif month in [4, 6, 9, 11]:
            end = date(year, month, 30)
        else:
            end = date(year, month, 31)
    
    # YYYYMMDDHHMM 포맷
    start_str = start.strftime("%Y%m%d") + "0000"
    end_str = end.strftime("%Y%m%d") + "2359"
    
    return (start_str, end_str)


@mcp.tool()
def get_procurement_bid_notice_url(
    query: str,
    page_no: int = 1,
    num_of_rows: int = None
) -> dict:
    """조달청 입찰공고 조회 URL 생성
    
    자연어로 입찰공고 조회 기간을 입력하면 API 호출 URL을 생성합니다.
    
    Args:
        query: "25년 4월 입찰공고" 또는 "2025년 4월 공고 조회"
        page_no: 페이지 번호 (기본값: 1)
        num_of_rows: 한 페이지 결과 수 (기본값: .env의 DEFAULT_PAGE_SIZE)
    
    Returns:
        API URL과 파라미터 정보
    
    Examples:
        >>> get_procurement_bid_notice_url("25년 4월")
        >>> get_procurement_bid_notice_url("2025년 4월 입찰공고")
    """
    debug_log(f"Tool 호출: query={query}")
    
    # 기본값 설정
    if num_of_rows is None:
        num_of_rows = DEFAULT_PAGE_SIZE
    
    # 날짜 파싱
    date_range = parse_date(query)
    
    if not date_range:
        return {
            "error": "날짜를 찾을 수 없습니다",
            "help": "예시: '25년 4월', '2025년 4월'",
            "query": query
        }
    
    start_date, end_date = date_range
    
    # 파라미터 구성
    params = {
        "serviceKey": SERVICE_KEY,
        "type": "json",
        "pageNo": str(page_no),
        "numOfRows": str(num_of_rows),
        "bidNtceBgnDt": start_date,
        "bidNtceEndDt": end_date
    }
    
    # URL 생성
    query_string = "&".join([f"{k}={v}" for k, v in params.items()])
    full_url = f"{BASE_URL}{ENDPOINT}?{query_string}"
    
    return {
        "url": full_url,
        "description": "조달청 나라장터 입찰공고정보 조회",
        "parameters": {
            "입찰공고일시_시작": start_date,
            "입찰공고일시_종료": end_date,
            "페이지번호": page_no,
            "결과수": num_of_rows
        },
        "usage": {
            "curl": f"curl '{full_url}'",
            "python": f"""
import requests

response = requests.get(
    "{BASE_URL}{ENDPOINT}",
    params={{
        "serviceKey": "{SERVICE_KEY[:20]}...",
        "type": "json",
        "bidNtceBgnDt": "{start_date}",
        "bidNtceEndDt": "{end_date}",
        "pageNo": {page_no},
        "numOfRows": {num_of_rows}
    }}
)
data = response.json()
print(data)
"""
        },
        "query": query,
        "note": "서비스키가 자동으로 .env 파일에서 로드되었습니다"
    }


@mcp.tool()
def explain_procurement_api() -> dict:
    """조달청 입찰공고 API 설명
    
    API의 상세 정보와 사용법을 반환합니다.
    """
    debug_log("API 설명 Tool 호출")
    
    return {
        "api_name": "조달청_나라장터 공공데이터개방표준서비스",
        "endpoint": ENDPOINT,
        "description": "입찰공고번호, 입찰공고차수, 입찰공고명 등 나라장터에 등록된 입찰공고정보 조회",
        "base_url": BASE_URL,
        "method": "GET",
        "current_settings": {
            "service_key": f"{SERVICE_KEY[:20]}... (loaded from .env)",
            "default_page_size": DEFAULT_PAGE_SIZE,
            "base_url": BASE_URL
        },
        "parameters": {
            "필수": {
                "serviceKey": "공공데이터포털 인증키"
            },
            "선택": {
                "pageNo": "페이지번호 (기본값: 1)",
                "numOfRows": f"한 페이지 결과 수 (기본값: {DEFAULT_PAGE_SIZE})",
                "type": "응답 포맷 (json 또는 xml)",
                "bidNtceBgnDt": "입찰공고일시 시작 (YYYYMMDDHHMM)",
                "bidNtceEndDt": "입찰공고일시 종료 (YYYYMMDDHHMM)"
            }
        },
        "notes": [
            "입찰공고일시 범위는 1개월로 제한됩니다",
            "날짜 형식은 YYYYMMDDHHMM (예: 202504010000)",
            "서비스키는 .env 파일에서 자동으로 로드됩니다"
        ],
        "example_response_fields": {
            "bidNtceNo": "입찰공고번호",
            "bidNtceNm": "입찰공고명",
            "ntceInsttNm": "공고기관명",
            "dmndInsttNm": "수요기관명",
            "bidNtceDate": "입찰공고일자",
            "asignBdgtAmt": "배정예산액",
            "presmptPrce": "추정가격",
            "opengDate": "개찰일자",
            "bidNtceUrl": "입찰공고 URL"
        }
    }


debug_log("Tool 등록 완료")

if __name__ == "__main__":
    try:
        debug_log("MCP 서버 시작 준비")
        # MCP 서버 실행 (stdio 모드)
        mcp.run()
        debug_log("MCP 서버 정상 시작")
    except Exception as e:
        debug_log(f"오류 발생: {str(e)}")
        import traceback
        debug_log(traceback.format_exc())
        sys.exit(1)