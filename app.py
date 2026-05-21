import streamlit as st
import requests
import os
import glob
from datetime import datetime

# ==========================================
# 1. 설정 (블로그 경로 및 Ollama 연동)
# ==========================================
BLOG_DIR = "/mnt/c/Users/Public/jameshin.github.io"
MODEL_NAME = "gemma4"
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

st.set_page_config(page_title="Cybernote AI Agent", page_icon="🤖", layout="centered")

# ==========================================
# 2. 최신 지식(Markdown 파일) 자동 로드 함수
# ==========================================
def load_latest_knowledge():
    posts_path = os.path.join(BLOG_DIR, "_posts", "*.md")
    files = glob.glob(posts_path)
    
    if not files:
        return "현재 블로그에 축적된 최신 AI/Tech 동향 데이터가 없습니다."
        
    # 가장 최근에 생성된 파일 찾기
    latest_file = max(files, key=os.path.getmtime)
    filename = os.path.basename(latest_file)
    
    try:
        with open(latest_file, "r", encoding="utf-8") as f:
            content = f.read()
            # Jekyll Front Matter(머릿말) 부분을 제외한 실제 본문만 추출
            body = content.split("---")[-1].strip()
            return f"[{filename} 내용]\n{body}"
    except Exception as e:
        return f"지식 베이스 로드 실패: {e}"

# ==========================================
# 3. 화면 UI 구상 (세련된 다크/화이트 톤)
# ==========================================
st.title("Cybernote AI 지식 에이전트")
st.subheader("오늘 수집된 최신 동향을 기반으로 실시간 대화를 나눕니다.")

# 오늘 자 지식 베이스 미리 읽어두기
if "knowledge" not in st.session_state:
    st.session_state.knowledge = load_latest_knowledge()

# 채팅 기록 초기화
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "안녕하세요, 정훈 님! 오늘 분석된 Data/AI & Engineering 최신 동향에 대해 궁금한 점이 있으신가요?"}
    ]

# 화면에 기존 대화 기록 출력
for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.write(message["content"])

# ==========================================
# 4. 실시간 채팅 제어 및 Ollama API 호출
# ==========================================
if user_input := st.chat_input("오늘 아침 논문이나 뉴스에 대해 물어보세요!"):
    # 유저 메시지 화면 표시 및 저장
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.write(user_input)

    # 에이전트 답변 생성 구역
    with st.chat_message("assistant"):
        with st.spinner("Gemma가 오늘 자 지식을 바탕으로 생각하는 중..."):
            
            # 🌟 핵심 RAG 프롬프트: 오늘 수집한 지식을 Gemma의 머릿속에 강제로 주입!
            system_prompt = (
                f"당신은 정훈 님의 개인 AI 지식 비서입니다. 아래 제공된 [오늘의 최신 지식]을 반드시 바탕으로 삼아 사용자의 질문에 답변하세요.\n"
                f"만약 지식에 없는 내용이라면 자신이 원래 알고 있던 지식을 활용하되, 가급적 오늘 자 동향과 연결지어 친절한 한국어로 설명하세요.\n\n"
                f"[오늘의 최신 지식]\n{st.session_state.knowledge}\n\n"
                f"사용자 질문: {user_input}"
            )
            
            try:
                response = requests.post(OLLAMA_URL, json={
                    "model": MODEL_NAME,
                    "prompt": system_prompt,
                    "stream": False,
                    "options": {"temperature": 0.5}
                }, timeout=120)
                
                ai_response = response.json().get('response', "죄송합니다. 답변을 생성하지 못했습니다.")
                
            except Exception as e:
                ai_response = f"⚠️ 로컬 Ollama(Gemma) 서버와 통신 중 오류가 발생했습니다: {e}"
            
            # 결과 출력 및 저장
            st.write(ai_response)
            st.session_state.messages.append({"role": "assistant", "content": ai_response})
