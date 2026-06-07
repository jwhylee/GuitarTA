# GuitarTA v1.10

macOS에서 개인 연습용으로 쓰는 기타/베이스 트레이닝 앱입니다. Python + Flet으로 동작하며, 유튜브 링크를 로컬 영상으로 저장해 배속 조절과 노트별 메트로놈 구간 관리를 제공합니다.

## 실행

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install .
flet run src/guitarta/main.py
```

설치된 명령으로 실행할 수도 있습니다.

```bash
source .venv/bin/activate
guitarta
```

앞으로 UI/기능 업데이트는 `v1.1`, `v1.2`처럼 앱 화면과 패키지 버전에 함께 표시합니다.

## 데이터 위치

- DB: `~/Library/Application Support/GuitarTA/guitarta.db`
- 영상: `~/Library/Application Support/GuitarTA/media/`

## 주요 기능

- 유튜브 링크 다운로드 및 노트 생성
- 카테고리별 노트 관리
- 로컬 영상 재생과 `0.10x` - `2.00x` 배속 제어
- 노트별 여러 메트로놈 구간 저장
- BPM, 박자, 강조박 설정

## 다운로드 방식

v1.2부터 영상 다운로드는 YtCD와 같은 구조를 사용합니다.

- `bestvideo + bestaudio` 최고 화질 조합을 우선 선택합니다.
- `/opt/homebrew/bin/ffmpeg` 등을 자동 탐색해 MP4로 병합합니다.
- 파일은 GuitarTA 내부 media 폴더에 저장됩니다.
- 현재 이 컴퓨터에서는 `/Users/jylee/JYLee/CS/Vibe Coding/YtCD/.venv/bin/yt-dlp`를 우선 사용해 최신 YouTube extractor로 다운로드합니다.
