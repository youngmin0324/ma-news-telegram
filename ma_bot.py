"""
M&A 뉴스 리포트 - 연합뉴스 RSS 수집 후 업종별 분류해 텔레그램 전송.
"""
import os
import sys
import datetime
import re
import textwrap

import feedparser
import requests

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
TELEGRAM_CHAT_IDS_STR = os.environ.get("TELEGRAM_CHAT_IDS", "").strip()

if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_IDS_STR:
    print("TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_IDS 환경 변수를 설정하세요.", file=sys.stderr)
    sys.exit(1)

TELEGRAM_CHAT_IDS = [x.strip() for x in TELEGRAM_CHAT_IDS_STR.split(",") if x.strip()]

RSS_URL = "https://www.yna.co.kr/rss/economy.xml"

SECTOR_KEYWORDS = {
    "AI": ["ai", "인공지능", "머신러닝", "딥러닝", "생성형 ai", "gen ai", "챗봇", "computer vision", "자율주행"],
    "반도체": ["반도체", "semiconductor", "칩셋", "chip", "파운드리", "foundry", "메모리", "d-ram", "dram", "nand"],
    "바이오": ["바이오", "bio", "제약", "pharma", "pharmaceutical", "헬스케어", "의료기기", "clinical trial", "임상시험"],
    "2차전지/배터리": ["2차전지", "배터리", "secondary battery", "리튬", "양극재", "음극재"],
    "딜·인수합병": ["인수합병", "지분인수", "포트폴리오 재편", "에너지 인프라", "pe ", " pe ", "pe드라이파우더", "pe 드라이파우더", "딜 구조"],
}


def is_korean_text(text, min_ratio=0.3, min_korean_chars=10):
    if not text:
        return False
    korean_chars = [ch for ch in text if "\uac00" <= ch <= "\ud7a3"]
    total_chars = len(text)
    if len(korean_chars) < min_korean_chars:
        return False
    return len(korean_chars) / max(total_chars, 1) >= min_ratio


def detect_sectors(text):
    if not text:
        return []
    text_lower = text.lower()
    sectors = []
    for sector, keywords in SECTOR_KEYWORDS.items():
        for kw in keywords:
            if kw.lower() in text_lower:
                sectors.append(sector)
                break
    return sectors


def fetch_articles():
    feed = feedparser.parse(RSS_URL)
    articles = []
    for entry in feed.entries:
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        published = entry.get("published", "").strip()
        source = ""
        if "source" in entry and hasattr(entry.source, "title"):
            source = entry.source.title
        summary = entry.get("summary", "").strip()
        articles.append({"title": title, "link": link, "published": published, "source": source, "summary": summary})
    return articles


def filter_and_categorize_articles(articles):
    sector_map = {sector: [] for sector in SECTOR_KEYWORDS.keys()}
    for art in articles:
        combined_text = "%s %s" % (art["title"], art["summary"])
        if not is_korean_text(combined_text):
            continue
        sectors = detect_sectors(combined_text)
        if not sectors:
            continue
        for sec in sectors:
            sector_map[sec].append(art)
    return sector_map


def build_report_text(sector_map):
    today = datetime.date.today()
    header = (
        "[M&A 뉴스 리포트 - 업종별] %s\n\n"
        "공통 조건: 한국어 기사 (금액 기준 없음)\n"
        "출처: 연합뉴스 (https://www.yna.co.kr/rss/economy.xml)\n\n"
    ) % today.isoformat()
    wrapper = textwrap.TextWrapper(width=110, replace_whitespace=False)
    parts = [header]
    any_article = False
    for sector, articles in sector_map.items():
        if not articles:
            continue
        any_article = True
        parts.append("===== [%s] =====\n" % sector)
        for idx, art in enumerate(articles, start=1):
            summary = art["summary"] or "요약 정보 없음."
            summary_wrapped = wrapper.fill(summary)
            block = (
                "%d. %s\n   - 출처: %s\n   - 발행일: %s\n   - 링크: %s\n   - 요약: %s\n\n"
            ) % (idx, art["title"], art["source"] or "알 수 없음", art["published"] or "알 수 없음", art["link"], summary_wrapped)
            parts.append(block)
    if not any_article:
        parts.append("오늘은 조건에 맞는 기사가 없습니다.\n")
    return "".join(parts)


def send_text_to_telegram(text):
    max_len = 3900
    url = "https://api.telegram.org/bot%s/sendMessage" % TELEGRAM_BOT_TOKEN
    chunks = []
    while text:
        chunks.append(text[:max_len])
        text = text[max_len:]
    for chat_id in TELEGRAM_CHAT_IDS:
        for chunk in chunks:
            resp = requests.post(url, json={"chat_id": chat_id, "text": chunk}, timeout=10)
            if not resp.ok:
                print("텔레그램 전송 실패 (chat_id=%s):" % chat_id, resp.status_code, resp.text)


def main():
    articles = fetch_articles()
    sector_map = filter_and_categorize_articles(articles)
    report_text = build_report_text(sector_map)
    send_text_to_telegram(report_text)
    total = sum(len(v) for v in sector_map.values())
    print("업종 분류된 기사 %d건을 텔레그램으로 전송했습니다." % total)


if __name__ == "__main__":
    main()
