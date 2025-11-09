"""조달청 입찰공고 조회 웹 서버"""
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import os
import re
import httpx
from datetime import date
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# FastAPI 앱 생성
app = FastAPI(
    title="조달청 입찰공고 조회",
    description="자연어로 조달청 입찰공고를 조회합니다",
    version="1.0.0"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 정적 파일 & 템플릿 설정
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# 환경변수
SERVICE_KEY = os.getenv("PROCUREMENT_API_KEY", "YOUR_SERVICE_KEY")
BASE_URL = os.getenv("BASE_URL", "https://apis.data.go.kr/1230000/ao/PubDataOpnStdService")
DEFAULT_PAGE_SIZE = int(os.getenv("DEFAULT_PAGE_SIZE", "100"))
ENDPOINT = "/getDataSetOpnStdBidPblancInfo"


# 요청/응답 모델
class SearchRequest(BaseModel):
    query: str
    page_no: int = 1
    num_of_rows: int = None


class BidNoticeItem(BaseModel):
    bidNtceNo: str
    bidNtceOrd: str
    bidNtceNm: str
    bidNtceSttusNm: str
    ntceInsttNm: str
    bidNtceDate: str
    bidClseDate: str
    opengDate: str
    asignBdgtAmt: str
    presmptPrce: str
    bidNtceUrl: str
    bsnsDivNm: str
    cntrctCnclsMthdNm: str


class SearchResponse(BaseModel):
    success: bool
    total_count: int
    items: list[BidNoticeItem]
    query: str
    search_period: dict


def parse_date(query: str) -> tuple[str, str] | None:
    """
    날짜 파싱: "25년 11월" → ("202511010000", "202511302359")
    """
    pattern = r'(\d{2,4})년\s*(\d{1,2})월'
    match = re.search(pattern, query)
    
    if not match:
        return None
    
    year = match.group(1)
    month = match.group(2)
    
    if len(year) == 2:
        year = f"20{year}"
    
    year = int(year)
    month = int(month)
    
    start = date(year, month, 1)
    
    if month == 12:
        end = date(year, 12, 31)
    else:
        if month in [1, 3, 5, 7, 8, 10]:
            end = date(year, month, 31)
        elif month in [4, 6, 9, 11]:
            end = date(year, month, 30)
        else:
            if year % 4 == 0 and (year % 100 != 0 or year % 400 == 0):
                end = date(year, 2, 29)
            else:
                end = date(year, 2, 28)
    
    start_str = start.strftime("%Y%m%d") + "0000"
    end_str = end.strftime("%Y%m%d") + "2359"
    
    return (start_str, end_str)


def format_amount(amount: str) -> str:
    """금액 포맷팅"""
    try:
        num = int(amount)
        if num >= 100000000:  # 1억 이상
            return f"{num // 100000000:,}억 {(num % 100000000) // 10000:,}만원"
        elif num >= 10000:  # 1만 이상
            return f"{num // 10000:,}만원"
        else:
            return f"{num:,}원"
    except:
        return amount


# 라우트: 메인 페이지
@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """메인 페이지"""
    return templates.TemplateResponse("index.html", {
        "request": request,
        "title": "조달청 입찰공고 조회"
    })


# 라우트: API 검색 및 실제 데이터 조회
@app.post("/api/search", response_model=SearchResponse)
async def search_procurement(request: SearchRequest):
    """입찰공고 조회 API"""
    
    if request.num_of_rows is None:
        request.num_of_rows = DEFAULT_PAGE_SIZE
    
    # 날짜 파싱
    date_range = parse_date(request.query)
    
    if not date_range:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "날짜를 찾을 수 없습니다",
                "help": "예시: '25년 11월', '2025년 4월'"
            }
        )
    
    start_date, end_date = date_range
    
    # 조달청 API 호출
    params = {
        "serviceKey": SERVICE_KEY,
        "type": "json",
        "pageNo": str(request.page_no),
        "numOfRows": str(request.num_of_rows),
        "bidNtceBgnDt": start_date,
        "bidNtceEndDt": end_date
    }
    
    api_url = f"{BASE_URL}{ENDPOINT}"
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(api_url, params=params)
            response.raise_for_status()
            data = response.json()
        
        # 응답 파싱
        if "response" not in data:
            raise HTTPException(status_code=500, detail="API 응답 형식이 올바르지 않습니다")
        
        response_data = data["response"]
        header = response_data.get("header", {})
        body = response_data.get("body", {})
        
        # 에러 체크
        if header.get("resultCode") != "00":
            raise HTTPException(
                status_code=400,
                detail=f"API 오류: {header.get('resultMsg', '알 수 없는 오류')}"
            )
        
        # items 추출
        items_data = body.get("items", [])
        if isinstance(items_data, dict):
            items_data = items_data.get("item", [])
        if not isinstance(items_data, list):
            items_data = [items_data] if items_data else []
        
        # BidNoticeItem 객체로 변환
        items = []
        for item in items_data:
            try:
                bid_item = BidNoticeItem(
                    bidNtceNo=item.get("bidNtceNo", ""),
                    bidNtceOrd=item.get("bidNtceOrd", ""),
                    bidNtceNm=item.get("bidNtceNm", ""),
                    bidNtceSttusNm=item.get("bidNtceSttusNm", ""),
                    ntceInsttNm=item.get("ntceInsttNm", ""),
                    bidNtceDate=item.get("bidNtceDate", ""),
                    bidClseDate=item.get("bidClseDate", ""),
                    opengDate=item.get("opengDate", ""),
                    asignBdgtAmt=format_amount(item.get("asignBdgtAmt", "0")),
                    presmptPrce=format_amount(item.get("presmptPrce", "0")),
                    bidNtceUrl=item.get("bidNtceUrl", ""),
                    bsnsDivNm=item.get("bsnsDivNm", ""),
                    cntrctCnclsMthdNm=item.get("cntrctCnclsMthdNm", "")
                )
                items.append(bid_item)
            except Exception as e:
                print(f"항목 파싱 오류: {e}")
                continue
        
        return SearchResponse(
            success=True,
            total_count=len(items),
            items=items,
            query=request.query,
            search_period={
                "start": start_date,
                "end": end_date,
                "start_display": f"{start_date[:4]}년 {start_date[4:6]}월 {start_date[6:8]}일",
                "end_display": f"{end_date[:4]}년 {end_date[4:6]}월 {end_date[6:8]}일"
            }
        )
        
    except httpx.RequestError as e:
        raise HTTPException(status_code=500, detail=f"API 호출 실패: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"처리 중 오류: {str(e)}")


# 라우트: API 정보
@app.get("/api/info")
async def api_info():
    """API 정보 조회"""
    return {
        "api_name": "조달청_나라장터 공공데이터개방표준서비스",
        "endpoint": ENDPOINT,
        "base_url": BASE_URL,
        "method": "GET",
        "description": "실시간으로 조달청 입찰공고 데이터를 조회합니다"
    }


# 라우트: Health Check
@app.get("/health")
async def health_check():
    """서버 상태 확인"""
    return {
        "status": "healthy",
        "service": "조달청 입찰공고 조회 API",
        "version": "1.0.0"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)