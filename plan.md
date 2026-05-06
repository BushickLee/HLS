# 📽️ 실시간 스트리밍 및 클립 서비스 구축 실행 계획

## 1. 프로젝트 개요
* **목적**: 웹캠 영상을 실시간으로 스트리밍하고, 과거 시점 시청(타임머신) 및 특정 구간 클립 추출 기능을 제공하는 경량 서버 구축.
* **핵심 가치**: 빠른 개발 속도, 확장성(AI 연동 가능성), 비동기 처리를 통한 효율적 자원 관리.

---

## 2. 요구사항 정의 (Requirements)

### 2.1 기능적 요구사항
1.  **실시간 스트리밍**: 웹캠 영상을 HLS 프로토콜로 변환하여 지연 시간을 최소화하여 송출.
2.  **타임머신 (DVR)**: 시청 중인 사용자가 재생 바를 뒤로 돌려 과거 영상을 즉시 시청 가능.
3.  **클립 생성**: 사용자가 지정한 시간대(시작~종료)의 영상을 추출하여 MP4 파일로 저장 및 다운로드.
4.  **자동 관리**: 서버 저장 공간 확보를 위해 오래된 영상 조각(.ts) 자동 삭제.

### 2.2 기술적 요구사항
* **비동기 처리**: 영상 인코딩 등 무거운 작업이 API 응답을 차단하지 않아야 함.
* **리소스 분리**: CPU 집약적 작업(인코딩)은 외부 프로세스(FFmpeg)로 분리.

---

## 3. 기술 스택 (Tech Stack)

| 구분 | 선택 기술 | 이유 |
| :--- | :--- | :--- |
| **Framework** | **FastAPI** | 비동기 지원, 빠른 개발 속도, 자동 문서화 |
| **Language** | Python 3.9+ | OpenCV, AI 라이브러리 생태계 활용 |
| **Media Engine** | **FFmpeg** | 업계 표준 영상 처리 도구, HLS 변환 및 클립 병합 |
| **Library** | OpenCV (cv2) | 웹캠 프레임 캡처 및 전처리 |
| **Streaming** | HLS (HTTP Live Streaming) | HTTP 기반 호환성, 타임머신 구현 용이성 |

---

## 4. 시스템 아키텍처 및 흐름

1.  **Ingestion**: FastAPI 서버 시작 시 OpenCV가 웹캠 프레임을 읽어 FFmpeg 파이프에 전송.
2.  **Transformation**: FFmpeg가 영상을 `.ts` 조각으로 쪼개고 `.m3u8` 인덱스 파일 생성.
3.  **Delivery**: FastAPI의 `StaticFiles`가 HLS 파일을 클라이언트에 서빙.
4.  **Interaction**: 사용자가 클립 요청 시 FastAPI가 별도의 FFmpeg 명령어로 파일 병합.

---

## 5. 단계별 실행 계획 (Step-by-Step)

### Phase 1: 개발 환경 및 스트리밍 기초 (완료 ✅)
* [x] FastAPI 기본 보일러플레이트 코드 작성.
* [x] FFmpeg 설치 및 Python `subprocess` 연동 테스트.
* [x] 웹캠 프레임을 FFmpeg로 넘겨 실시간 `.m3u8` 파일 생성 확인.

### Phase 2: 타임머신 및 시청 기능 (완료 ✅)
* [x] FFmpeg HLS 옵션 조정 (`hls_list_size`를 크게 설정하여 과거 조각 유지).
* [x] 프론트엔드 `Video.js`를 연결하여 실시간 재생 및 뒤로 돌려보기 테스트.
* [x] 정적 파일 서빙 경로(`app.mount("/live", ...)`) 보안 및 접근 설정.

### Phase 3: 클립 추출 로직 구현 (완료 ✅)
* [x] 사용자가 요청한 시간대의 `.ts` 파일 리스트를 파악하는 API 개발.
* [x] FFmpeg의 `concat` 기능을 이용하여 무인코딩(Stream Copy) 방식으로 클립 병합 구현.
* [x] 생성된 클립 파일(.mp4) 관리 및 다운로드 엔드포인트 구축.

### Phase 4: 최적화 및 배포 (진행 중 🔄)
* [ ] 서버 종료 시 FFmpeg 서브프로세스가 안전하게 종료되도록 `on_event("shutdown")` 처리. (이미 구현됨)
* [ ] 디스크 용량 관리를 위한 오래된 조각 파일 정리 스케줄러 확인.

---

## 6. 핵심 코드 전략 (Code Snippet)

### FFmpeg 비동기 실행 (Subprocess)
```python
import asyncio

async def run_ffmpeg_task(command: list):
    process = await asyncio.create_subprocess_exec(
        *command,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    # 이벤트 루프를 방해하지 않고 프로세스 완료 대기
    stdout, stderr = await process.communicate()
    return process.returncode
```

### 클립 병합 (Clipping)
```bash
# 재인코딩 없이 빠르게 병합하는 FFmpeg 예시
ffmpeg -f concat -safe 0 -i file_list.txt -c copy output_clip.mp4
```

---

## 7. 트레이드오프 및 주의사항
* **GIL 방어**: 모든 영상 연산은 Python 내부 루프가 아닌 **FFmpeg 외부 프로세스**에서 수행되도록 유지.
* **스토리지**: 타임머신 시간을 길게 잡을수록 디스크 사용량이 선형적으로 증가하므로 모니터링 필요.
* **지연 시간**: HLS 특성상 5~10초의 기본 지연 시간이 발생함 (LL-HLS 적용 검토 가능).