# 리포트 템플릿 안내

PLIV는 `DOCX`와 `PPTX` 리포트 출력 시 사용자 템플릿을 사용할 수 있다.

## 1. 동작 방식

템플릿 경로는 `pliv_plugin/resources/interaction_config.json`의 아래 항목에서 설정한다.

- `reporting.docx.template`
- `reporting.pptx.template`

설정값 규칙은 다음과 같다.

- 값을 비워두면: PLIV의 기본 내장 포맷 사용
- 절대경로를 넣으면: 해당 위치의 `.docx` 또는 `.pptx` 템플릿 사용
- 상대경로를 넣으면: `pliv_plugin/resources/` 기준으로 해석

## 2. 권장 사용 방법

1. Word에서 원하는 글꼴, 제목 스타일, 로고, 여백이 반영된 `.docx` 템플릿을 만든다.
2. PowerPoint에서 원하는 테마와 슬라이드 레이아웃이 반영된 `.pptx` 템플릿을 만든다.
3. 템플릿 파일을 이 폴더에 저장한다. 예시:
   - `report_templates/custom_report.docx`
   - `report_templates/custom_report.pptx`
4. `interaction_config.json`을 다음과 같이 수정한다.

```json
"reporting": {
  "docx": {
    "template": "report_templates/custom_report.docx"
  },
  "pptx": {
    "template": "report_templates/custom_report.pptx",
    "title_slide_layout": 0,
    "content_slide_layout": 5
  }
}
```

## 3. 함께 조절할 수 있는 기본 포맷 옵션

### DOCX
- `title`
- `image_width_inches`
- `page_break_between_targets`

### PPTX
- `title`
- `title_slide_layout`
- `content_slide_layout`
- `images_per_slide`
- `slide_width_inches`
- `slide_height_inches`

## 4. 주의사항

- DOCX 템플릿에 `List Bullet` 스타일이 없어도 PLIV는 일반 문단으로 fallback 하도록 처리되어 있다.
- PPTX 템플릿에 기본 title/subtitle placeholder가 없어도 textbox를 사용해 fallback 한다.
- 지정한 템플릿 경로가 존재하지 않으면, PLIV는 기본 내장 포맷으로 자동 복귀하고 로그에 이유를 남긴다.

## 5. 출력 폴더 구조

Batch Export, DOCX, PPTX 출력은 이제 실행마다 전용 디렉토리를 하나 생성한 뒤, 그 안에 결과 파일을 저장한다.

예를 들면 다음과 같다.

- `GDP_201_A_batch_export_20260522_143000/`
  - PNG 이미지들
  - manifest JSON
- `GDP_201_A_batch_report_20260522_143000/`
  - PNG 이미지들
  - manifest JSON
  - `GDP_201_A_batch_report_20260522_143000.docx`
