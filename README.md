# GuitarTA v2.0

개인 연습용으로 쓰는 기타/베이스 트레이닝 앱입니다. Python + Flet으로 동작하며, 유튜브 링크를 로컬 영상으로 저장해 배속 조절, 노트별 메트로놈 구간 관리, 베이스/기타 제거 음원 전환을 제공합니다.

## 실행

```bash
python3.10 -m venv .venv
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
- 음원: `~/Library/Application Support/GuitarTA/audio/`

앱 아이콘이나 macOS 앱 번들을 다시 빌드해도 위 데이터 위치는 바뀌지 않습니다.

## macOS 앱 아이콘

앱 아이콘 원본은 `assets/icon.png`에 저장되어 있고, macOS 빌드용 아이콘은 `assets/icon_macos.png`를 사용합니다. Flet macOS 빌드는 `assets/icon_macos.png`를 자동으로 찾아 앱 아이콘으로 반영합니다.

```bash
source .venv/bin/activate
flet build macos . --product GuitarTA --bundle-id com.guitarta.app
```

## 주요 기능

- 유튜브 링크 다운로드 및 노트 생성
- 다운로드된 영상에서 원본 음원 추출
- Demucs 6-source 모델을 사용한 베이스 제거/기타 제거 음원 생성
- 원본, 베이스 제거, 기타 제거 음원을 선택해 영상과 함께 재생
- 카테고리별 노트 관리
- 로컬 영상 재생과 `0.10x` - `2.00x` 배속 제어
- 노트별 여러 메트로놈 구간 저장
- BPM, 박자, 강조박 설정

## 다운로드 방식

v1.2부터 영상 다운로드는 YtCD와 같은 구조를 사용합니다.

- `bestvideo + bestaudio` 최고 화질 조합을 우선 선택합니다.
- 설치된 `ffmpeg`를 자동 탐색해 MP4로 병합합니다.
- 파일은 GuitarTA 내부 media 폴더에 저장됩니다.
- 현재 이 컴퓨터에서는 `/Users/jylee/JYLee/CS/Vibe Coding/YtCD/.venv/bin/yt-dlp`를 우선 사용해 최신 YouTube extractor로 다운로드합니다.

## v2.0 음원 처리

새 노트는 영상 다운로드 후 원본 WAV, 베이스 제거 WAV, 기타 제거 WAV를 자동 생성합니다. 기존 노트는 앱 시작 후 누락된 음원을 백그라운드에서 순차 생성합니다.

Demucs는 Python 3.10 이상이 필요합니다. 기존 Python 3.9 venv를 쓰고 있다면 venv를 새로 만든 뒤 설치하세요.

앱은 일반 Demucs의 `htdemucs_6s` 모델을 사용합니다. macOS, Windows, Linux에서 같은 분리 경로를 사용하며, FFmpeg로 추출한 PCM WAV를 Demucs에 전달해 stem을 생성합니다.
