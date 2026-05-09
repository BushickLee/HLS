from fastapi import FastAPI, BackgroundTasks
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
import os
import asyncio
from stream_manager import stream_manager

app = FastAPI(title="HLS Live Streaming Server")

# 모바일 앱(expo-av) 및 프론트엔드가 HLS 파일(.m3u8, .ts)을 원활하게 땡겨갈 수 있도록 CORS 설정 추가
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HLS 파일 서빙을 위한 정적 파일 경로 설정
if not os.path.exists("static"):
    os.makedirs("static")

if not os.path.exists("static/live"):
    os.makedirs("static/live")

if not os.path.exists("static/clips"):
    os.makedirs("static/clips")

# 정적 폴더 전체를 외부에서 직접 접근할 수 있도록 마운트 (/static/live/stream.m3u8)
app.mount("/static", StaticFiles(directory="static"), name="static")

# 기존 클라이언트 하위 호환성을 위해 /live, /clips 마운트도 유지
app.mount("/live", StaticFiles(directory="static/live"), name="live")
app.mount("/clips", StaticFiles(directory="static/clips"), name="clips")

@app.on_event("startup")
async def startup_event():
    # 서버 기동 시 백그라운드에서 스트리밍 시작
    asyncio.create_task(stream_manager.start_streaming())

@app.on_event("shutdown")
async def shutdown_event():
    await stream_manager.stop_streaming()

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>HLS Live Stream & Time Machine</title>
        <link href="https://vjs.zencdn.net/8.10.0/video-js.css" rel="stylesheet" />
        <style>
            body { font-family: sans-serif; display: flex; flex-direction: column; align-items: center; background: #1a1a1a; color: white; }
            .container { margin-top: 50px; width: 80%; max-width: 800px; }
            .vjs-default-skin { margin: 0 auto; }
        </style>
    </head>
    <body>
        <h1>📽️ Real-time HLS Stream</h1>
        <div class="container">
            <video id="my-video" class="video-js vjs-big-play-centered" controls preload="auto" width="800" height="450">
                <source src="/static/live/stream.m3u8" type="application/x-mpegURL">
                <p class="vjs-no-js">To view this video please enable JavaScript, and consider upgrading to a web browser that <a href="https://videojs.com/html5-video-support/" target="_blank">supports HTML5 video</a></p>
            </video>
        </div>

        <div class="container" style="background: #333; padding: 20px; border-radius: 8px;">
            <h2>✂️ Create Clip</h2>
            <div style="display: flex; gap: 10px; margin-bottom: 10px;">
                <input type="text" id="start-time" placeholder="Start (e.g. 00:00:05)" style="padding: 5px;">
                <input type="text" id="duration" placeholder="Duration (e.g. 5)" style="padding: 5px;">
                <input type="text" id="filename" placeholder="Filename" style="padding: 5px;">
                <button onclick="createClip()" style="padding: 5px 15px; cursor: pointer;">Generate Clip</button>
            </div>
            <div id="clip-result"></div>
        </div>

        <script src="https://vjs.zencdn.net/8.10.0/video.min.js"></script>
        <script>
            var player = videojs('my-video', {
                liveui: true,
                liveTracker: {
                    trackingThreshold: 0,
                    liveTolerance: 1 // 1초 정도의 오차만 허용 (최대한 라이브에 붙임)
                }
            });

            // liveTracker가 준비되면 라이브 끝점으로 이동 시도
            player.on('loadedmetadata', function() {
                setTimeout(() => {
                    const liveTracker = player.liveTracker;
                    if (liveTracker && liveTracker.isLive()) {
                        liveTracker.seekToLiveEdge();
                    }
                }, 100);
            });

            // 라이브 버튼 클릭 시 최신 지점으로 강제 이동 로직 보강
            player.on('liveedgechange', function() {
                if (player.liveTracker.atLiveEdge()) {
                    console.log("현재 최신 지점 재생 중");
                }
            });

            async function createClip() {
                const startTime = document.getElementById('start-time').value;
                const duration = document.getElementById('duration').value;
                const filename = document.getElementById('filename').value;
                const resultDiv = document.getElementById('clip-result');
                
                resultDiv.innerText = "Processing...";
                
                const response = await fetch(`/create-clip?start_time=${startTime}&duration=${duration}&output_name=${filename}`, {
                    method: 'POST'
                });
                
                const data = await response.json();
                if (data.status === 'success') {
                    resultDiv.innerHTML = `Clip created! <a href="${data.url}" target="_blank" style="color: #4CAF50;">Download Clip</a>`;
                } else {
                    resultDiv.innerText = "Error: " + data.message;
                }
            }
        </script>
    </body>
    </html>
    """

@app.get("/status")
async def status():
    return {"is_running": stream_manager.is_running}

@app.post("/create-clip")
async def create_clip(start_time: str, duration: str, output_name: str):
    clip_path = await stream_manager.create_clip(start_time, duration, output_name)
    if clip_path:
        return {"status": "success", "url": f"/{clip_path}"}
    return {"status": "failed", "message": "FFmpeg error during clip creation"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
