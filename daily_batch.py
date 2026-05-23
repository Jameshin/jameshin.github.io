import os
import re
import requests
import feedparser
import xml.etree.ElementTree as ET
import urllib.parse
import time
import subprocess
from datetime import datetime, timedelta

# ==========================================
# 1. 설정 (정훈 님의 주소 및 키워드 제어)
# ==========================================
# 🌟 검색하고 싶은 키워드들을 적어줍니다.
KEYWORDS = ["war", "game"] 

# 🌟 여기에 "AND" 또는 "OR"를 입력하여 검색 방식을 언제든 바꿀 수 있습니다!
KEYWORD_MODE = "AND"  

# 로컬 Ollama 모델 이름 및 주소
MODEL_NAME = "gemma4" 
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

# 🌟 정훈 님의 실제 블로그 로컬 저장소 경로 (WSL 형식)
BLOG_DIR = "/mnt/c/Users/Public/jameshin.github.io"

# 🌟 꿈속의 편안함을 주는 자연/도시 풍경 이미지 검색 태그 (Lorem Flickr 전용)
IMAGE_QUERY = "nature,landscape,cityscape,scenery"

# ==========================================
# 2. 🛠️ 감성 이미지 다운로드 함수 (주소 서비스 전면 교체)
# ==========================================
def download_aesthetic_image():
    print("🎨 [Image] 오늘 블로그에 넣을 감성 배경 이미지를 수집하고 있습니다...")
    
    # 🌟 Unsplash 종료로 인해, 안정적인 고해상도 무작위 풍경 서비스로 변경했습니다.
    img_url = f"https://loremflickr.com/1600/900/{IMAGE_QUERY}/all"
    
    img_dir = os.path.join(BLOG_DIR, "images")
    if not os.path.exists(img_dir):
        os.makedirs(img_dir)
        
    today_str = datetime.now().strftime('%Y-%m-%d')
    file_name = f"header-{today_str}.jpg"
    save_path = os.path.join(img_dir, file_name)
    
    try:
        # 브라우저인 척 속이기 위한 헤더 세팅 (차단 방지)
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        # 15초 안에 반응 없으면 에러 처리하고 넘어가도록 timeout 설정 강화
        response = requests.get(img_url, headers=headers, timeout=15)
        if response.status_code == 200:
            with open(save_path, "wb") as f:
                f.write(response.content)
            print(f"✅ 이미지 저장 성공: /images/{file_name}")
            return f"/images/{file_name}"
        else:
            print(f"⚠️ 이미지 서버 응답 실패 (코드: {response.status_code})")
    except Exception as e:
        print(f"⚠️ 이미지 다운로드 중 에러 발생 (기본값 대체): {e}")
    
    return "/images/default-scenery.jpg"

# ==========================================
# 3. 데이터 수집 함수 (arXiv 논문)
# ==========================================
def fetch_arxiv_papers(keywords_list, mode):
    print(f"📡 [arXiv] 논문 검색 시작... (방식: {mode} / 키워드: {keywords_list})")
    papers = []
    
    joined_query = f" {mode} ".join([f'all:"{kw}"' for kw in keywords_list])
    url = f'http://export.arxiv.org/api/query?search_query={urllib.parse.quote(joined_query)}&max_results=6&sortBy=submittedDate&sortOrder=descending'
    
    try:
        response = requests.get(url, timeout=15)
        if response.status_code == 200:
            root = ET.fromstring(response.text)
            for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
                title = entry.find('{http://www.w3.org/2005/Atom}title').text.strip()
                summary = entry.find('{http://www.w3.org/2005/Atom}summary').text.strip()
                paper_url = entry.find('{http://www.w3.org/2005/Atom}id').text.strip()
                
                title = re.sub(r'\s+', ' ', title)
                summary = re.sub(r'\s+', ' ', summary)
                
                papers.append({
                    "title": title,
                    "summary": summary,
                    "url": paper_url
                })
    except Exception as e:
        print(f"⚠️ arXiv 수집 중 오류 발생: {e}")
        
    return papers

# ==========================================
# 4. 데이터 수집 함수 (구글 뉴스)
# ==========================================
def fetch_google_news(keywords_list, mode):
    print(f"📡 [News] 최신 뉴스 검색 시작... (방식: {mode} / 키워드: {keywords_list})")
    news = []
    
    joined_query = f" {mode} ".join([f'"{kw}"' for kw in keywords_list])
    url = f"https://news.google.com/rss/search?q={urllib.parse.quote(joined_query)}&hl=ko&gl=KR&ceid=KR:ko"
    
    try:
        feed = feedparser.parse(url)
        for entry in feed.entries[:6]:
            title = entry.title
            link = entry.link
            title = re.sub(r'\s-\s.*$', '', title)
            
            news.append({
                "title": title,
                "summary": title,
                "url": link
            })
    except Exception as e:
        print(f"⚠️ 뉴스 수집 중 오류 발생: {e}")
        
    return news

# ==========================================
# 5. LLM 요약 함수 (Gemma)
# ==========================================
def summarize_with_gemma(context):
    if not context.strip(): 
        return "오늘 조건에 맞는 새로운 데이터가 수집되지 않았습니다."
    
    print("🤖 [Gemma] 수집된 기술 정보를 읽고 아침 브리핑을 작성 중입니다...")
    
    prompt = (
        f"당신은 테크 전문 블로그를 운영하는 정교한 AI 에이전트입니다. 아래 제공된 데이터의 모든 항목을 요약해 주세요.\n\n"
        f"주의사항:\n"
        f"1. 누락하는 항목 없이 각각의 논문과 뉴스를 모두 요약하세요.\n"
        f"2. 각 항목별로 '### 제목'을 달고 그 아래에 2~3문장의 핵심 한글 요약을 작성하세요.\n"
        f"3. 전문적이면서도 독자가 읽기 편한 친절한 한국어로 작성하세요.\n\n"
        f"[수집 데이터]\n{context[:12000]}"
    )
    
    try:
        response = requests.post(OLLAMA_URL, json={
            "model": MODEL_NAME, 
            "prompt": prompt, 
            "stream": False,
            "options": {"temperature": 0.3}
        }, timeout=300)
        return response.json().get('response', "요약본 생성에 실패했습니다.")
    except Exception as e:
        return f"연결 실패: {e}"

# ==========================================
# 6. Jekyll 포스팅 생성 및 GitHub 업로드
# ==========================================
def post_to_jekyll(summary, papers, news, image_path, keywords_list, mode):
    print("📄 [System] Jekyll 블로그 Markdown 규격 파일 생성 중...")
    
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    file_name = f"{today_str}-daily-ai-briefing.md"
    file_path = os.path.join(BLOG_DIR, "_posts", file_name)

    # 🌟 [동적 문구 생성 구역] 정훈님이 설정한 키워드들을 이쁘게 문장으로 조립합니다.
    # 예시: "LLM, RAG (AND)"
    keyword_tags = ", ".join(keywords_list)
    dynamic_excerpt = f"오늘 {keyword_tags} 관련 주요 기술 논문과 뉴스를 전해드립니다."

    md_content = f"""---
layout: post
title: "{today_str} Daily AI Tech"
date: {now.strftime('%Y-%m-%d %H:%M:%S')} +0900
excerpt: "{dynamic_excerpt}"
image: "{image_path}"
---

## 💡 오늘의 기술 핵심 요약
{summary}

---

### 📚 오늘 수집된 원본 논문 리스트
"""
    for p in papers:
        md_content += f"- [{p['title']}]({p['url']})\n"
    
    md_content += "\n### 📰 관련 최신 뉴스\n"
    for n in news:
        md_content += f"- [{n['title']}]({n['url']})\n"

# 🌟 [정훈님 맞춤 추가] 본문 맨 하단에 실시간 채팅창으로 갈 수 있는 세련된 테두리 버튼 박스를 생성합니다.
    md_content += f"""

---

<div style="background-color: #1e293b; border-left: 5px solid #deff9a; padding: 20px; border-radius: 8px; margin-top: 40px; color: #f8fafc;">
    <h4 style="margin-top: 0; color: #deff9a; font-size: 18px;"> Agent Assistant와 더 깊은 대화를 나누세요.</h4>
    <p style="font-size: 14px; color: #cbd5e1; margin-bottom: 15px;">
        방금 읽으신 오늘자 {keyword_tags} 논문이나 기술 동향에 대해 더 깊은 분석이나 궁금한 점이 있으신가요? 
        지금 실시간으로 학습된 AI 에이전트와 직접 질문을 주거니 받거니 하며 토론해 보세요!
    </p>
    <a href="https://agent.dudejoy.com" target="_blank" style="display: inline-block; background-color: #deff9a; color: #0f172a; font-weight: bold; padding: 10px 20px; border-radius: 6px; text-decoration: none; font-size: 14px; transition: 0.3s;">
        👉 AI 에이전트와 실시간 채팅하기
    </a>
</div>

<br>
    *본 브리핑 포스팅은 Local LLM (Gemma4)과 자동화 에이전트를 통해 생성되었습니다.*"""

    try:
        if not os.path.exists(os.path.join(BLOG_DIR, "_posts")):
            os.makedirs(os.path.join(BLOG_DIR, "_posts"))
            
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"✅ 블로그 파일 생성 완료: {file_name}")
        
        # 🚀 [안전장치 수리 구역] 
        # 무조건 Push하기 전, GitHub 서버에 있는 최신 변경사항을 가져와서 내 컴퓨터와 먼저 합칩니다(Pull).
        # 업데이트 히스토리가 엇갈려도 자동으로 합치도록 `--rebase`와 `rebase.autostash` 옵션을 동원합니다.
        print("🔄 GitHub 서버로부터 최신 정보 동기화 중 (Pull)...")
        subprocess.run(["git", "-C", BLOG_DIR, "config", "rebase.autostash", "true"], check=True)
        subprocess.run(["git", "-C", BLOG_DIR, "pull", "--rebase", "origin", "master"], check=False) # 혹시 마스터 브랜치 이름이 master가 아닌 main이면 알아서 맞춰 돌도록 유연하게 예외처리
        
        print("🚀 GitHub 업로드(Push)를 시작합니다...")
        subprocess.run(["git", "-C", BLOG_DIR, "add", "."], check=True)
        subprocess.run(["git", "-C", BLOG_DIR, "commit", "-m", f"Daily update with chat button: {today_str}"], check=True)
        subprocess.run(["git", "-C", BLOG_DIR, "push", "origin", "HEAD"], check=True)
        print("✨ GitHub Pages 클라우드 서버에 성공적으로 배포되었습니다!")        

    except Exception as e:
        print(f"❌ 포스팅 파일 저장 또는 Git 업로드 중 실패: {e}")

# ==========================================
# 7. 메인 제어 흐름
# ==========================================
if __name__ == "__main__":
    print(f"=== 에이전트 가동 (현재 모드: {KEYWORD_MODE}) ===")
    
    # 1단계: 분위기 있는 이미지 다운로드
    saved_img_path = download_aesthetic_image()
    
    # 2단계: 키워드 모드에 맞춘 데이터 수집
    p_data = fetch_arxiv_papers(KEYWORDS, KEYWORD_MODE)
    n_data = fetch_google_news(KEYWORDS, KEYWORD_MODE)
    
    # 3단계: Gemma에게 줄 컨텍스트 조립
    ctx = "--- [ArXiv 논문 리스트] ---\n"
    for idx, p in enumerate(p_data):
        ctx += f"[{idx+1}] 제목: {p['title']}\n초록: {p['summary']}\n\n"
        
    ctx += f"--- [구글 최신 뉴스] ---\n"
    for idx, n in enumerate(n_data):
        ctx += f"[{idx+1}] 뉴스제목: {n['title']}\n\n"
    
    # 4단계: LLM 분석 및 요약
    final_summary = summarize_with_gemma(ctx)
    
    # 5단계: 이미지 경로를 Front Matter에 포함하여 최종 포스팅 및 푸시
    post_to_jekyll(final_summary, p_data, n_data, saved_img_path, KEYWORDS, KEYWORD_MODE)
