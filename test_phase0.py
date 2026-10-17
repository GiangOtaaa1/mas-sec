# test_phase0.py
from langchain_core.messages import HumanMessage
from config import Config, get_llm

def test_qwen_connection():
    print(f"Đang khởi tạo kết nối tới Ollama ({Config.MODEL_NAME}) tại {Config.OLLAMA_BASE_URL}...")
    
    llm = get_llm(temperature=0.7)
    
    # Tạo câu prompt test
    messages = [
        HumanMessage(content="Xin chào, bạn là ai và bạn có thể làm gì? Hãy trả lời ngắn gọn trong 2 câu.")
    ]
    
    print("Đang gửi request...")
    try:
        response = llm.invoke(messages)
        print("\n=== KẾT QUẢ TỪ QWEN 2.5:7B ===")
        print(response.content)
        print("===============================\n")
        print("TEST: OK - Hệ thống đã sẵn sàng cho Phase 1.")
    except Exception as e:
        print(f"TEST FAILED: Lỗi kết nối - {e}")

if __name__ == "__main__":
    test_qwen_connection()