# Hold'em with AI 


## 빌드/실행 빠른 시작

별도 프론트엔드 빌드나 npm 설치가 필요 없습니다. Python 표준 라이브러리만 사용합니다.

```bash
# 1) Python 버전 확인: 3.10 이상
python3 --version

# 2) 코드 수정 시 문법/테스트 검증
python3 -m py_compile holdem/*.py
python3 -m unittest discover -s tests -v

# 3) 웹 UI 실행(게임 시작)
python3 -m holdem.play
```

`holdem.play`는 로컬 웹 서버를 임시 포트로 띄우고 브라우저를 자동으로 엽니다.

터미널 설정에 따라 자동으로 실행되는 브라우저가 상이할 수 있기 떄문에
수동으로 고정 포트에서 실행하려면 다음과 같이 실행할 수 있습니다
```bash
python3 -m holdem.server
# 원하는 브라우저에서 http://127.0.0.1:8000 접속
```

## 실행: 웹 UI 앱

```bash
python3 -m holdem.play
```

- 내부 로컬 서버를 임시 포트로 띄우고 브라우저를 자동으로 엽니다.
- AI봇, 카드, 그외 이미지는 `assets/*`에 있습니다. 데모용 임시 이미지입니다.
- 봇 턴에는 패 강도(`strength`), 콜 압박(`pressure`), 성격/랜덤성(`roll`)을 섞어 1~5초 사이 thinking 시간을 정합니다.
- 봇은 `check`, `call`, `fold`, `bet`, `raise` 중 유효한 액션을 로컬 스캐폴드로 선택하고 다음 턴으로 넘어갑니다.
- 봇이 행동하면 `CALL`, `RAISE 40` 같은 말풍선이 뜨고, 팟/현재 베팅/각 플레이어의 스택·이번 라운드 베팅액·콜 필요액이 표시됩니다.
- `PREFLOP → FLOP → TURN → RIVER → SHOWDOWN` 단계를 명확히 알 수 있도록 배너를 통해 표현했습니다.
- 현재 액션 차례에는 액션 패널과 해당 봇 좌석 테두리 애니메이션을 통해 명확히 알 수 있도록 합니다.
- 쇼다운은 즉시 승자만 보여주지 않고, 남은 플레이어들의 완성된 패를 순서대로 공개합니다. 족보가 좋을수록 색/애니메이션이 강하고 공개 시간이 더 깁니다.

## 터미널 UI(레거시)

```bash
python3 -m holdem.cli
```

간단한 디버그/텍스트 플레이용입니다.

## 수동 웹 서버 실행(선택)

```bash
python3 -m holdem.server
# http://127.0.0.1:8000
```

## 구성

- `holdem/cards.py` — 카드/덱 유틸리티
- `holdem/evaluator.py` — 7장 중 최고 5장 족보 평가
- `holdem/game.py` — 테이블, 플레이어, 블라인드, 베팅 라운드, 봇 의사결정/생각시간, 쇼다운 족보 공개 메타데이터
- `holdem/play.py` — 웹 UI 앱 런처(브라우저 자동 오픈)
- `holdem/cli.py` — 보조 터미널 UI
- `holdem/store.py` — 선택형 로컬 SQLite 저장소 (`data/holdem.sqlite`)
- `holdem/server.py` — HTTP API + 웹 UI/assets 제공
- `web/index.html` — 웹 UI HTML 골격
- `web/styles.css` — POV 스타일
- `web/app.js` — API 호출과 렌더링 로직
- `assets/*.svg` — 봇 아바타, 칩, 카드 뒷면, 테이블 패턴

## API(선택형 웹 UI용)

- `GET /api/health`
- `POST /api/tables` — `{ "players": 4, "chips": 1000 }`
- `GET /api/tables/{table_id}`
- `POST /api/tables/{table_id}/action` — `{ "player_id": "p1", "action": "call|check|fold|bet|raise", "amount": 20 }`
- `POST /api/tables/{table_id}/bot-action` — 현재 봇 한 명만 행동
- `POST /api/tables/{table_id}/new-hand`

`GET /api/tables/{table_id}`와 액션 응답에는 UI용 필드도 포함됩니다.

- `bot_delay_ms` — 현재 봇의 유동 thinking 시간(1~5초)
- `bot_thought` — `{ strength, pressure, roll }`
- `showdown` — 각 플레이어의 완성 패 `{ label, tier, reveal_ms }`

## 검증

```bash
python3 -m py_compile holdem/*.py
python3 -m unittest discover -s tests -v
```

