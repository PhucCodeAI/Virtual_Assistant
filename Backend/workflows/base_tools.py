from services.graph_engine import GraphEngine

class Tools:
    @staticmethod
    def get_codebase() -> str:
        ...

    def search_knowledge_graph(query: str, graph: GraphEngine) -> str:
        """
        Tìm kiếm thông tin dạng mối quan hệ, thực thể và các tác vụ lịch sử/hiện tại của hệ thống.
        Sử dụng công cụ này khi cần tra cứu thông tin chuyên sâu có tính liên kết logic cao.
        """
        return graph.query_agent(query)

    def search_internet():
        """
        Tìm kiếm thông tin trên Internet.
        Sử dụng công cụ này khi cần tra cứu thông tin tổng quát, cập nhật hoặc không có trong hệ thống.
        """
        pass


import asyncio
import time
import httpx
from selectolax.parser import HTMLParser

# Cấu hình cổng SearXNG Local của bạn
SEARXNG_URL = "http://localhost:8080"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

async def get_search_urls(query: str, limit: int = 3) -> list[dict]:
    """
    Truy vấn SearXNG Local để lấy danh sách URL và tiêu đề.
    """
    url = f"{SEARXNG_URL}/search?q={urllib_parse_quote(query)}&format=json"
    print(f"[1/3] Đang gửi query '{query}' tới SearXNG Local...")
    
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            response = await client.get(url, headers=HEADERS)
            if response.status_code == 200:
                results = response.json().get("results", [])[:limit]
                return [{"title": r.get("title"), "url": r.get("url")} for r in results]
            else:
                print(f"[LỖI] SearXNG phản hồi mã lỗi: {response.status_code}")
        except Exception as e:
            print(f"[LỖI] Không thể kết nối tới SearXNG: {e}")
    return []

async def scrape_clean_text(url: str) -> str:
    """
    Cào mã nguồn HTML thô và bóc tách text siêu tốc bằng selectolax (C-Engine).
    """
    print(f" -> Đang cào: {url}")
    try:
        async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
            response = await client.get(url, headers=HEADERS)
            if response.status_code != 200:
                return f"[Lỗi {response.status_code}]"
            
            # Phân tích cú pháp HTML bằng C-parser
            parser = HTMLParser(response.text)
            
            # Loại bỏ các thẻ rác không chứa thông tin hữu ích
            for tag in parser.css("script, style, iframe, footer, nav, header, noscript, ad"):
                tag.decompose()
            
            # Lấy toàn bộ text thuần và làm sạch khoảng trắng thừa
            raw_text = parser.body.text(separator=" ")
            clean_text = " ".join(raw_text.split())
            
            # Cắt bớt độ dài để chống tràn context của LLM (giới hạn 1000 từ đầu tiên)
            return clean_text[:2000] + "..."
            
    except Exception as e:
        return f"[Lỗi cào dữ liệu: {e}]"

# Hàm helper để encode query
def urllib_parse_quote(text: str) -> str:
    import urllib.parse
    return urllib.parse.quote(text)

async def main():
    query = "tin tức trí tuệ nhân tạo mới nhất 2026"
    print("=== KHỞI ĐỘNG PIPELINE TÌM KIẾM & CÀO DỮ LIỆU LOCAL ===")
    start_time = time.perf_counter()
    
    # Bước 1: Lấy danh sách link từ SearXNG
    links = await get_search_urls(query, limit=3)
    if not links:
        print("[Thất bại] Không lấy được kết quả từ SearXNG. Hãy chắc chắn Docker SearXNG đã chạy!")
        return
        
    print(f"\n[2/3] Tìm thấy {len(links)} liên kết phù hợp. Bắt đầu cào song song...")
    
    # Bước 2: Tạo tác vụ cào song song (Concurrent Tasks)
    tasks = [scrape_clean_text(link["url"]) for link in links]
    contents = await asyncio.gather(*tasks)
    
    # Bước 3: In kết quả thống kê
    print("\n[3/3] === KẾT QUẢ TRÍCH XUẤT ===")
    for i, link in enumerate(links):
        print(f"\n[{i+1}] TIÊU ĐỀ: {link['title']}")
        print(f"    URL: {link['url']}")
        print(f"    NỘI DUNG TRÍCH XUẤT (200 ký tự đầu):\n    {contents[i][:200]}")
        print("-" * 50)
        
    total_time = time.perf_counter() - start_time
    print(f"\n[Metrics] Hoàn thành toàn bộ pipeline trong: {total_time:.2f} giây!")

if __name__ == "__main__":
    asyncio.run(main())
