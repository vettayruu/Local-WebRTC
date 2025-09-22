import asyncio
import json
import logging
import os
import cv2
import time
import platform
from aiohttp import web
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription, RTCRtpSender
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder, MediaRelay
from aiortc.rtcrtpparameters import RTCRtpCodecParameters

from av import VideoFrame
import pyzed.sl as sl
from fractions import Fraction

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("webrtc_server")

# 全局变量
pcs = set()
relay = MediaRelay()


# 视频轨道类，用于从摄像头捕获图像并转换为WebRTC视频帧
class CameraVideoStreamTrack(MediaStreamTrack):
    """从摄像头捕获视频并发送到WebRTC."""

    kind = "video"

    def __init__(self):
        super().__init__()
        self.zed = sl.Camera()
        self.image_both = sl.Mat()
        self.image_left = sl.Mat()
        self.image_right = sl.Mat()

        self.init_params = sl.InitParameters()
        self.init_params.camera_resolution = sl.RESOLUTION.HD720
        self.init_params.camera_fps = 60
        self.init_params.depth_mode = sl.DEPTH_MODE.NONE  # 禁用深度模式提高性能
        self.init_params.coordinate_units = sl.UNIT.METER

        self.runtime = sl.RuntimeParameters()
        self.runtime.enable_fill_mode = False

        """ZED Initialization"""
        print("ZED Initializing")

        err = self.zed.open(self.init_params)
        if err != sl.ERROR_CODE.SUCCESS:
            print(f"ZED Initialize Error: {err}")
            self.zed.close()

        self.running = True


    async def recv(self):
        # pts, time_base = await self.next_timestamp()

        if self.zed.grab(self.runtime) == sl.ERROR_CODE.SUCCESS:
            # start = time.perf_counter()
            # self.zed.retrieve_image(self.image_left, sl.VIEW.LEFT)
            self.zed.retrieve_image(self.image_both, sl.VIEW.SIDE_BY_SIDE)

            frame = self.image_both.get_data().copy()
            frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)

            # 创建VideoFrame
            video_frame = VideoFrame.from_ndarray(frame, format="rgb24")
            video_frame.time_base = Fraction(1, 75)

            return video_frame

    def __del__(self):
        if hasattr(self, 'cap') and self.cap is not None:
            self.cap.release()
            logger.info("摄像头已释放")


# WebRTC offer处理函数
async def offer(request):
    try:
        params = await request.json()
        offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

        pc = RTCPeerConnection()
        pcs.add(pc)

        logger.info("收到WebRTC offer")

        @pc.on("connectionstatechange")
        async def on_connectionstatechange():
            logger.info(f"连接状态: {pc.connectionState}")
            if pc.connectionState == "failed":
                await pc.close()
                pcs.discard(pc)

        # 添加摄像头视频轨道
        track = CameraVideoStreamTrack()
        sender = pc.addTrack(track)

        # av1_codec = RTCRtpCodecParameters(
        #     mimeType="video/AV1",
        #     clockRate=90000,
        #     parameters={}
        # )
        # sender = pc.addTrack(track)
        # # params = sender.getParameters()
        # params.codecs = [av1_codec]
        # # await sender.setParameters(params)

        # 处理offer并创建answer
        await pc.setRemoteDescription(offer)
        answer = await pc.createAnswer()
        await pc.setLocalDescription(answer)

        response = {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        logger.info("已创建应答")
        return web.Response(
            content_type="application/json",
            text=json.dumps(response),
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "POST, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
            }
        )
    except Exception as e:
        logger.error(f"处理offer时出错: {e}")
        return web.Response(status=500, text=str(e))


# CORS预检请求处理
async def options_handler(request):
    return web.Response(
        status=200,
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type",
        }
    )


# 健康检查端点
async def health_check(request):
    try:
        # 简单测试是否能打开摄像头
        cap = cv2.VideoCapture(0)
        camera_ok = cap.isOpened()
        cap.release()

        return web.json_response({
            "status": "ok",
            "server": "running",
            "camera": "available" if camera_ok else "unavailable",
            "version": "1.0.0",
            "time": time.time()
        })
    except Exception as e:
        logger.error(f"健康检查失败: {e}")
        return web.json_response({
            "status": "error",
            "message": str(e)
        }, status=500)


# 关闭时清理资源
async def on_shutdown(app):
    # 关闭所有WebRTC连接
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()
    logger.info("服务器已关闭，资源已清理")


# 创建aiohttp应用
def create_app():
    app = web.Application()
    app.on_shutdown.append(on_shutdown)

    # 添加路由
    app.router.add_post("/offer", offer)
    app.router.add_options("/offer", options_handler)
    app.router.add_get("/health", health_check)

    return app


if __name__ == "__main__":
    try:
        import numpy as np  # 确保导入numpy

        # 检查环境
        logger.info(f"Python版本: {platform.python_version()}")
        logger.info(f"OpenCV版本: {cv2.__version__}")
        logger.info("开始启动WebRTC服务器...")

        # 修复：使用正确的方式运行应用
        app = create_app()
        web.run_app(app, host="0.0.0.0", port=8080)
    except KeyboardInterrupt:
        logger.info("收到键盘中断，服务器关闭")
    except Exception as e:
        logger.error(f"服务器启动失败: {e}")