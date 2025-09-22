# WebRTC 本地摄像头流服务

这个项目使用WebRTC将本地摄像头图像从Python服务器发送到网页端显示。

## 架构

系统由三个主要部分组成：

1. **Python WebRTC服务器**：读取摄像头图像并通过WebRTC发送
2. **Node.js代理服务器**：处理信令和提供静态文件服务
3. **浏览器客户端**：显示摄像头流的网页界面

## 安装依赖

### Python依赖

```bash
pip install aiohttp aiortc opencv-python
```

### Node.js依赖

```bash
npm install
```

## 使用方法

### 1. 启动Python WebRTC服务器

```bash
python webrtc_python_server.py
```

这将在 `localhost:8080` 启动Python WebRTC服务器。

### 2. 启动Node.js代理服务器

```bash
npm start
```

这将在 `localhost:3001` 启动Node.js代理服务器。

### 3. 访问Web界面

在浏览器中打开 `http://localhost:3001`，点击"开始连接"按钮开始接收摄像头流。

## 故障排除

### 常见问题

1. **摄像头无法打开**
   - 确保摄像头没有被其他应用程序占用
   - 检查Python控制台的错误消息
   - 修改 `webrtc_python_server.py` 中的摄像头索引（如果有多个摄像头）

2. **网页无法连接到服务器**
   - 确保Python和Node.js服务器都在运行
   - 检查Node.js控制台中的代理错误信息
   - 检查浏览器控制台中的WebRTC连接错误

3. **图像显示但有延迟**
   - 可能是由于本地网络条件导致的
   - 尝试降低 `webrtc_python_server.py` 中的摄像头分辨率

## 定制设置

### 更改Python服务器地址

如果Python服务器不在本地运行，修改 `server.js` 中的 `target` 地址：

```javascript
const proxyOptions = {
  target: "http://你的服务器IP:8080",
  // ...
};
```

### 更改摄像头设置

修改 `webrtc_python_server.py` 中的 `CameraStream` 类：

```python
# 设置摄像头分辨率
self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)  # 更改为你需要的分辨率
self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
```

### 更改摄像头索引

如果你有多个摄像头，修改 `CameraStream` 类的初始化：

```python
self.cap = cv2.VideoCapture(1)  # 使用索引1的摄像头
```

## 安全说明

此项目仅供本地使用。若要部署到生产环境，需要添加：

1. 适当的认证机制
2. HTTPS加密
3. WebRTC TURN服务器配置（用于NAT穿透）