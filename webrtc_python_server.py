import asyncio
import json
import logging
import os
import cv2
import time
import platform
from aiohttp import web
from aiortc import MediaStreamTrack, RTCPeerConnection, RTCSessionDescription
from aiortc.contrib.media import MediaBlackhole, MediaPlayer, MediaRecorder, MediaRelay
from aiortc.rtcrtpsender import RTCRtpSendParameters
from aiortc.rtcrtpparameters import RTCRtpCodecParameters, RTCRtcpParameters
from av import VideoFrame

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
        self.cap = cv2.VideoCapture(0)  # 打开默认摄像头
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

        # 检查摄像头是否成功打开
        if not self.cap.isOpened():
            logger.error("无法打开摄像头")
            raise RuntimeError("无法打开摄像头")

        logger.info("摄像头初始化成功")
        self.last_log = time.time()
        self.frame_count = 0

    async def recv(self):
        # 读取摄像头帧
        ret, frame = self.cap.read()
        if not ret:
            logger.error("无法从摄像头读取图像")
            # 尝试重新打开摄像头
            self.cap.release()
            self.cap = cv2.VideoCapture(0)
            if not self.cap.isOpened():
                raise RuntimeError("无法重新打开摄像头")
            ret, frame = self.cap.read()
            if not ret:
                # 如果还是失败，返回黑色帧
                import numpy as np
                frame = np.zeros((1920, 1080, 3), dtype=np.uint8)

        # 将OpenCV的BGR格式转换为RGB格式
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # 创建VideoFrame
        video_frame = VideoFrame.from_ndarray(frame, format="rgb24")
        # video_frame.pts = video_frame.time = int(time.time() * 1000000)

        # 计算并打印FPS
        # self.frame_count += 1
        # current_time = time.time()
        # if current_time - self.last_log > 5:  # 每5秒打印一次
        #     fps = self.frame_count / (current_time - self.last_log)
        #     logger.info(f"相机FPS: {fps:.2f}")
        #     self.frame_count = 0
        #     self.last_log = current_time

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
        video_sender = pc.addTrack(CameraVideoStreamTrack())
        logger.info("已添加相机视频轨道")

        encoder_parameters = RTCRtpSendParameters(
            codecs=[
                RTCRtpCodecParameters(
                    mimeType="video/AV1",  # 使用 AV1 编码器
                    clockRate=90000,
                    parameters={},  # AV1 通常不需要额外参数
                ),
                # 添加 H.264 作为备选，防止浏览器不支持 AV1
                RTCRtpCodecParameters(
                    mimeType="video/H264",
                    clockRate=90000,
                    parameters={"packetization-mode": "1", "profile-level-id": "42e01f"},
                )
            ],
            headerExtensions=[],
            rtcp=RTCRtcpParameters(
                cname="video0",
                # reducedSize=True,
            ),
        )

        # await video_sender.setParameters(encoder_parameters)


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