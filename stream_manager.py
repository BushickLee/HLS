import cv2
import subprocess
import os
import asyncio
import signal
from typing import Optional

class StreamManager:
    def __init__(self, output_dir: str = "static/live", stream_name: str = "stream"):
        self.output_dir = output_dir
        self.stream_name = stream_name
        self.m3u8_path = os.path.join(self.output_dir, f"{self.stream_name}.m3u8")
        self.process: Optional[subprocess.Popen] = None
        self.cap: Optional[cv2.VideoCapture] = None
        self.is_running = False

        self._ensure_clean_dir()

    def _ensure_clean_dir(self):
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)
        else:
            # 기존 파일들 삭제 (재시작 시 깨끗한 상태 유지)
            for file in os.listdir(self.output_dir):
                file_path = os.path.join(self.output_dir, file)
                try:
                    if os.path.isfile(file_path):
                        os.unlink(file_path)
                except Exception as e:
                    print(f"Error cleaning {file_path}: {e}")

    def _get_ffmpeg_command(self, width: int, height: int, fps: int):
        gop_size = fps  # 1초마다 키프레임 생성

        return [
            'ffmpeg',
            '-y',
            '-f', 'rawvideo',
            '-vcodec', 'rawvideo',
            '-pix_fmt', 'bgr24',
            '-s', f"{width}x{height}",
            '-r', str(fps),
            '-i', '-',
            '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p',
            '-preset', 'ultrafast',   # 속도 우선
            '-tune', 'zerolatency',    # 지연 시간 최소화 (핵심!)
            '-g', str(gop_size),       # GOP 간격 강제
            '-f', 'hls',
            '-hls_time', '1',          # 1초 단위로 쪼개기
            '-hls_list_size', '10',    # 너무 긴 리스트는 클라이언트 부하 유발
            '-hls_flags', 'delete_segments+independent_segments+split_by_time',
            '-hls_segment_filename', os.path.join(self.output_dir, f"{self.stream_name}_%03d.ts"),
            self.m3u8_path
        ]

    async def start_streaming(self):
        if self.is_running:
            return
        

        self.cap = cv2.VideoCapture(0)
        # --- 해상도 조절 코드 추가 ---
        # 예: 640x480 (VGA 해상도)로 낮추기
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        # --------------------------

        if not self.cap.isOpened():
            print("Error: Could not open webcam.")
            return

        width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = int(self.cap.get(cv2.CAP_PROP_FPS)) or 30

        command = self._get_ffmpeg_command(width, height, fps)
        
        self.process = subprocess.Popen(
            command,
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE # 0.46.0 uvicorn doesn't like direct stderr sometimes, but useful for debugging
        )

        self.is_running = True
        
        loop = asyncio.get_event_loop()
        try:
            while self.is_running:
                ret, frame = await loop.run_in_executor(None, self.cap.read)
                if not ret:
                    break
                
                if self.process and self.process.stdin:
                    self.process.stdin.write(frame.tobytes())
                
                await asyncio.sleep(1/fps)
        except Exception as e:
            print(f"Streaming error: {e}")
        finally:
            await self.stop_streaming()

    async def stop_streaming(self):
        self.is_running = False
        if self.cap:
            self.cap.release()
            self.cap = None
        
        if self.process:
            if self.process.stdin:
                self.process.stdin.close()
            self.process.terminate()
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
            self.process = None
        
        print("Streaming stopped.")

    async def create_clip(self, start_time: str, duration: str, output_name: str):
        """
        start_time: "HH:MM:SS" or seconds
        duration: "HH:MM:SS" or seconds
        """
        clip_path = f"static/clips/{output_name}.mp4"
        if not os.path.exists("static/clips"):
            os.makedirs("static/clips")

        command = [
            'ffmpeg',
            '-y',
            '-i', self.m3u8_path,
            '-ss', start_time,
            '-t', duration,
            '-c', 'copy', # 무인코딩 병합
            clip_path
        ]
        
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            return clip_path
        else:
            print(f"Clip creation failed: {stderr.decode()}")
            return None

stream_manager = StreamManager()
