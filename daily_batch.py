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
# 1. 설정 (정훈 님의 환경에 최적화)
# ==========================================
KEYWORDS = ["LLM", "RAG"] 
MODEL_NAME = "gemma" 
OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

# 🌟 블로그 로컬 저장소 경로 (WSL 형식)
BLOG_DIR = "/mnt/c/Users/Public/jameshin.github.io"

# ==========================================
# 2. 데이터 수집 함수 (arXiv 논문)
# ==========================================
def fetch_arxiv_papers(keywords_list):
    print(f"📡 [arXiv] 검색 시작... (키워드: {keywords_list})")
    papers = []
    
    # 최근 2일간의 논문만 타겟팅
    start_date = (datetime.now() - timedelta(days=2)).strftime("%Y%M%d")
    
    for kw in keywords_list:
        query = f'all:"{kw}"'
        url = f'http://export.arxiv.org/api/query?search_query={urllib.parse.quote(query)}&max_results=5&sortBy=submittedDate&sortOrder=descending'
        
        for attempt in range(3):
            try:
                response = requests.get(url, timeout=15)
                if response.status_code == 200:
                    root = ET.fromstring(response.text)
                    for entry in root.findall('{http://www.w3.org/2005/Atom}entry'):
                        title = entry.find('{http://www.w3.org/2005/Atom}title').text.strip()
                        summary = entry.find('{http://www.w3.org/2005/Atom}summary').text.strip()
                        paper_url = entry.find('{http://www.w3.org/2005/Atom}id').text.strip()
                        
                        # 중복 제거 및 데이터 저장
                        if not any(p['title'] == title for p in papers):
                            papers.append({
                                "title": title,
                                "summary": summary,
                                "url": paper_url
                            })
                    break
            except Exception as e:
                print(f"⚠️ arXiv 재시도 중... ({attempt+1}/3): {e}")
                time.sleep(2)
    return papers

# ==========================================
# 3. 데이터 수집 함수 (구글 뉴스)
# ==========================================
def fetch_google_news(keywords_list):
    print(f"📡 [News] 검색 시작... (키워드: {keywords_list})")
    news = []
    
    for kw in keywords_list:
        url = f"https://news.google.com/rss/search?q={urllib.parse.quote(kw)}&hl=ko&gl=KR&ceid=KR:ko"
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:3]: # 키워드당 상위 3개 뉴스
                title = entry.title
                link = entry.link
                # 간단한 클리닝
                title = re.sub(r'\s-\s.*$', '', title)
                
                if not any(n['title'] == title for n in news):
                    news.append({
                        "title": title,
                        "summary": title, # 뉴스 피드는 초록이 없으므로 제목을 요약 힌트로 사용
                        "url": link
                    })
        except Exception as e:
            print(f"⚠️ 뉴스 수집 중 오류 발생: {e}")
            
    return news

# ==========================================
# 4. LLM 요약 함수 (Gemma 강제 7건 요약 버전)
# ==========================================
def summarize_with_gemma(context):
    if not context.strip(): return "수집된 데이터가 없습니다."
    
    print(f"🤖 [Gemma] {len(context)}자 데이터를 분석 중... (누락 금지)")
    prompt = (
        f"당신은 꼼꼼한 IT 기술 블로거입니다. 아래 제공된 데이터의 모든 항목을 요약해 주세요.\n\n"
        f"주의사항:\n"
        f"1. 데이터에 포함된 모든 논문과 뉴스를 누락 없이 각각 요약하세요.\n"
        f"2. 각 항목별로 '### [항목 종류] 제목'을 쓰고 그 아래에 2~3문장의 핵심 한글 요약을 작성하세요.\n"
        f"3. 모든 답변은 가독성 좋은 한국어로 작성하세요.\n\n"
        f"[데이터]\n{context[:12000]}"
    )
    try:
        res = requests.post(OLLAMA_URL, json={
            "model": MODEL_NAME, "prompt": prompt, "stream": False,
            "options": {"num_predict": 2048, "temperature": 0.3}
        }, timeout=300)
        return res.json().get('response', "내용 없음")
    except Exception as e:
        return f"요약 실패: {e}"

# ==========================================
# 5. Jekyll Markdown 생성 및 Git 자동 업로드
# ==========================================
def post_to_jekyll(summary, papers, news):
    print(f"📄 [System] Jekyll 포스트 파일 생성 중...")
    
    now = datetime.now()
    today_str = now.strftime('%Y-%m-%d')
    file_name = f"{today_str}-daily-ai-briefing.md"
    file_path = os.path.join(BLOG_DIR, "_posts", file_name)
    
    # Jekyll Front Matter 규격 맞춤 생성
    md_content = f"""---
layout: post
title: "🤖 {today_str} AI & Tech Daily Briefing"
date: {now.strftime('%Y-%m-%d %H:%M:%S')} +0900
categories: [AI, Tech]
tags: [Gemma, arXiv, RAG]
---

## 💡 오늘의 기술 핵심 요약
{summary}

---

### 📚 수집된 원본 논문 리스트
"""
    for p in papers:
        md_content += f"- [{p['title']}]({p['url']})\n"
    
    md_content += "\n### 📰 관련 최신 뉴스\n"
    for n in news:
        md_content += f"- [{n['title']}]({n['url']})\n"

    md_content += "\n\n---\n*본 브리핑 포스팅은 로컬 LLM(Gemma)을 통해 자동으로 생성되었습니다.*"

    try:
        # _posts 폴더가 없으면 자동 생성
        if not os.path.exists(os.path.join(BLOG_DIR, "_posts")):
            os.makedirs(os.path.join(BLOG_DIR, "_posts"))
            
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        print(f"✅ 포스트 파일 생성 완료: {file_name}")
        
        # 🚀 Git 자동 업로드 (Push)
        print("🚀 GitHub 업로드(Push) 시작...")
        subprocess.run(["git", "-C", BLOG_DIR, "add", "."], check=True)
        subprocess.run(["git", "-C", BLOG_DIR, "commit", "-m", f"Daily briefing: {today_str}"], check=True)
        
        # 🌟 기본 브랜치가 main 또는 master 무엇이든 대응하도록 push 실행
        subprocess.run(["git", "-C", BLOG_DIR, "push", "origin", "HEAD"], check=True)
        print("✨ GitHub Pages에 자동 포스팅이 완전히 완료되었습니다!")
        
    except Exception as e:
        print(f"❌ 포스팅 또는 Git 업로드 실패: {e}")

# ==========================================
# 6. 메인 실행 제어
# ==========================================
if __name__ == "__main__":
    # 1. 데이터 가져오기
    p_data = fetch_arxiv_papers(KEYWORDS)
    n_data = fetch_google_news(KEYWORDS)
    
    # 2. Gemma에게 넘겨줄 컨텍스트 조립
    ctx = f"--- [ArXiv 논문 리스트] ---\n"
    for idx, p in enumerate(p_data):
        ctx += f"[{idx+1}] 제목: {p['title']}\n초록: {p['summary']}\n\n"
        
    ctx += f"--- [구글 최신 뉴스] ---\n"
    for idx, n in enumerate(n_data):
        ctx += f"[{idx+1}] 뉴스제목: {n['title']}\n\n"
    
    # 3. Gemma 분석 시작
    final_summary = summarize_with_gemma(ctx)
    
    # 4. 블로그 포스팅 및 깃허브 업로드
    post_to_jekyll(final_summary, p_data, n_data)
