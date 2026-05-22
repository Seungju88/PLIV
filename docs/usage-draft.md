# PLIV 주요 사용법 초안

## 1. PLIV는 무엇을 위한 도구인가

PLIV는 PyMOL 3.1 Open Source 안에서 protein-ligand interaction을
시각적으로 점검하기 위한 GUI 플러그인이다. 목표는 Schrödinger Maestro와
유사한 기준과 표현 방식을 참고하되, PyMOL 안에서 바로 구조 검토,
publication 준비, docking pose 점검까지 이어지는 실전형 workflow를
제공하는 것이다.

현재 PLIV는 특히 아래 사용 상황을 염두에 두고 있다.

- X-ray 또는 모델링된 protein-ligand complex에서 interaction 확인
- docking 결과에서 receptor 1개와 ligand object 여러 개를 빠르게 바꿔가며 검토
- publication figure를 만들기 전 interaction 표시를 정리하고 이미지 저장

## 2. 현재 기준 사용 가능한 핵심 기능

- `Complex Object` 모드에서 complex object 내부 ligand instance 선택
- `Docking Receptor + Ligand Objects` 모드에서 receptor object 1개와 ligand object 1개 선택
- interaction family별 on/off
- interaction family별 색상 변경
- `Run Analysis` 후 작업용 visualization 생성
- `Apply Publication Style` / `Restore Working View`
- saved view 5개 저장/복원
- PNG 저장
- PyMOL session 저장/불러오기
- session metadata를 통한 창 크기와 마지막 분석 context 복원

## 3. Analyze 탭 사용법

### 3.1 Selection Mode

`Analyze` 탭의 `Selections` 섹션에서 먼저 `Selection Mode`를 고른다.

- `Complex Object`
  - 하나의 object 안에 protein과 ligand가 함께 들어 있는 경우에 사용
  - 예: X-ray complex, MM/GBSA 구조, cocrystal 구조
- `Docking Receptor + Ligand Objects`
  - receptor object와 ligand object가 분리되어 있는 경우에 사용
  - 예: docking 결과를 PyMOL object들로 불러온 경우

### 3.2 Complex Object 모드

1. 상단 list에서 complex object를 선택한다.
2. 아래 list에서 ligand instance를 `chain:resi:resn` 형식으로 선택한다.
3. 필요하면 `Reload Object List`로 현재 PyMOL object 목록을 다시 읽는다.
4. `Interaction Settings`에서 family와 색상을 정한다.
5. `Run Analysis`를 누른다.

### 3.3 Docking Receptor + Ligand Objects 모드

1. 상단 list에서 receptor object를 선택한다.
2. 아래 list에서 ligand object를 선택한다.
3. `Interaction Settings`에서 family와 색상을 정한다.
4. `Run Analysis`를 누른다.

현재 docking 모드는 `receptor 1개 + ligand 1개`를 한 번에 분석하는 구조다.
즉 ligand object는 여러 개를 보여주지만, 현재 한 번에 하나씩 선택해서 보는
workflow를 기본으로 한다.

## 4. Interaction Settings

### 4.1 Profile

현재 profile은 `Maestro` 하나만 제공한다. 이는 interaction 기준을 잡는
참조 profile이며, GUI에서 다른 profile을 고르는 구조는 아직 열어두지 않았다.

### 4.2 Interaction Families

interaction family는 체크박스로 켜고 끌 수 있다. 각 family 오른쪽의 색상
스와치를 눌러 색을 바꿀 수 있다.

현재 기준으로 가장 안정적으로 쓰는 family는 아래와 같다.

- hydrogen bond
- salt bridge
- pi-pi stacking
- pi-cation

아래 family는 GUI와 색상 스와치는 준비되어 있지만, interaction typing은
아직 prototype 단계이거나 완전 구현 전일 수 있다.

- halogen bond
- hydrophobic contact

색상 변경은 다음처럼 동작한다.

- 색상을 고르면 현재 보이는 해당 family dash 색이 바로 바뀐다.
- 다음 `Run Analysis`에도 같은 색이 사용된다.
- `Reload Config`를 누르면 `interaction_config.json`의 기본값으로 돌아간다.

## 5. Run Analysis 후 화면에서 일어나는 일

`Run Analysis`를 누르면 PLIV가 selection을 정리하고 interaction을 계산한 뒤
작업용 visualization을 만든다.

현재 기본 동작은 아래와 같다.

- protein은 cartoon 중심으로 표시
- ligand는 sticks로 표시
- interaction distance label은 숨김
- protein `lines`는 숨김
- nonpolar hydrogen은 숨김
- `Show Valence`는 자동으로 off
- nearby ion은 유지
- water interaction이 잡히면 관련 water가 표시될 수 있음

하단 `Status Log`에는 아래 정보가 순서대로 누적된다.

- 분석 대상
- pocket atom 수
- ligand atom 수
- nearby water / ion 수
- interaction family별 개수
- prototype 상태나 미구현 family에 대한 note

## 6. Actions 섹션

### 6.1 Run Analysis

현재 selection과 interaction setting을 기준으로 interaction을 계산하고
작업용 visualization을 만든다.

### 6.2 Apply Publication Style

현재 분석 결과를 publication figure에 가까운 형태로 정리한다.

- protein lines는 숨김 유지
- nonpolar hydrogen은 숨김 유지
- ligand와 interaction dashes가 더 깔끔한 상태로 정리됨

### 6.3 Restore Working View

`Apply Publication Style`를 누르기 직전의 작업 뷰로 복원한다.

### 6.4 Clear Plugin Objects

PLIV가 만든 helper selection, dash object, temporary object를 지운다.
원본 protein / ligand object 자체를 삭제하는 용도는 아니다.

## 7. Capture 탭

### 7.1 Saved Views

`Saved Views`는 camera position과 zoom을 저장하는 기능이다.

- `Save View 1~5`
- `Load View 1~5`

주의할 점은 이것이 full scene restore는 아니라는 것이다.

- saved view: 카메라와 zoom 중심
- restore working view: publication 적용 전 visualization 복원

두 기능은 목적이 다르다.

### 7.2 Save Image

현재 PyMOL 화면을 PNG로 저장한다.

### 7.3 Batch Export

저장된 `Saved View 1~5`를 이용해 현재 PLIV visualization state를 여러 장의 PNG로
일괄 저장한다.

현재 1차 구현에서 지원하는 항목은 다음과 같다.

- 사용할 view slot 선택
- `Current visible state`, `Working view`, `Publication style` 선택
- `ray trace`, width, height, dpi 지정
- output folder 선택
- 실행 시 output folder 아래에 전용 디렉토리 자동 생성
- export manifest JSON 저장

### 7.4 Report Export

`Report Export`는 현재 batch export 설정과 saved view를 그대로 재사용해 문서를 만든다.

- `Save DOCX Report`로 batch 결과를 Word 보고서로 정리
- `Save PPTX Report`로 batch 결과를 PowerPoint 슬라이드로 정리

DOCX 보고서는 batch export에서 생성된 PNG 세트를 문서에 삽입하는 방식으로 만들어진다.
현재 구현은 `python-docx`가 PyMOL이 사용하는 Python 환경에 설치되어 있을 때 동작한다.
설치되어 있지 않으면 PLIV가 의존성 안내 메시지를 표시한다.

PPTX 보고서는 같은 batch PNG 세트를 ligand target 단위 슬라이드로 정리한다.
현재 구현은 `python-pptx`가 PyMOL이 사용하는 Python 환경에 설치되어 있을 때 동작한다.
설치되어 있지 않으면 PLIV가 의존성 안내 메시지를 표시한다.

이제 DOCX와 PPTX는 템플릿 기반으로도 동작할 수 있다.
- `interaction_config.json`의 `reporting.docx.template`
- `interaction_config.json`의 `reporting.pptx.template`

에 템플릿 경로를 넣으면 해당 템플릿을 기준으로 보고서를 생성한다.
경로는 절대경로 또는 `pliv_plugin/resources/` 기준 상대경로를 사용할 수 있다.
세부 예시는 `pliv_plugin/resources/report_templates/README.md`를 참고한다.

또한 Batch Export, DOCX, PPTX 출력은 실행할 때마다 전용 디렉토리를 하나 만들고, 그 안에 PNG / manifest / report 파일을 함께 저장하도록 동작한다.

## 8. Session 탭

### 8.1 Save Session

PyMOL session 파일을 저장한다. 동시에 아래 정보도 sidecar metadata에 함께
저장한다.

- PyMOL 창 크기
- 창 위치
- viewport 크기
- 마지막 분석 request
- 마지막 분석 summary
- saved view 1~5 정보

### 8.2 Load Session

저장한 PyMOL session을 불러온다. PLIV metadata가 함께 있으면 아래 정보도
복원된다.

- 창 크기
- viewport
- 마지막 분석 context
- selection mode
- saved views

즉 `Load Session` 뒤에도 `Apply Publication Style` 같은 기능이 바로 이어질 수
있도록 설계되어 있다.

## 9. 권장 사용 시나리오

### 9.1 X-ray complex 검토

1. `Complex Object` 모드 선택
2. complex 선택
3. ligand instance 선택
4. hydrogen bond / salt bridge / pi 계열 중심으로 체크
5. `Run Analysis`
6. 필요하면 색상 조정
7. `Apply Publication Style`
8. 필요하면 `Save View`로 시점을 저장
9. `Batch Export`로 saved view 기반 PNG 세트 출력
10. 필요하면 `Save DOCX Report` 또는 `Save PPTX Report`로 이미지 세트를 문서로 정리

### 9.2 Docking pose 검토

1. `Docking Receptor + Ligand Objects` 모드 선택
2. receptor object 선택
3. ligand object 하나 선택
4. `Run Analysis`
5. 다른 ligand object를 선택해 같은 과정을 반복
6. 필요하면 `Save View`를 사용해 같은 시점에서 pose 비교

## 10. 현재 한계와 주의사항

- docking 모드는 현재 `one receptor + one ligand object at a time` 구조다
- 일부 interaction family는 UI는 준비되어 있어도 typing logic이 완전하지 않을 수 있다
- profile은 현재 `Maestro` 하나만 제공한다
- 내부 패키지 폴더명은 `pliv_plugin`이고, 표시 이름은 `PLIV`를 사용한다

## 11. 다음 확장 후보

- docking mode에서 ligand multi-select
- `Run All` 또는 `Next / Previous ligand`
- interaction 결과 table export
- water bridge / metal coordination 확장
- metalloenzyme 전용 표시 규칙 보강
