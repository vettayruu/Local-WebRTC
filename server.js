// server.js
const express = require("express");
const { createProxyMiddleware } = require("http-proxy-middleware");
const path = require("path");
const http = require("http");

// 创建Express应用
const app = express();
const PORT = 3001;
const PYTHON_SERVER_PORT = process.env.PYTHON_SERVER_PORT || 8080; // 允许通过环境变量设置

// 解析JSON请求体
app.use(express.json());

// 静态文件服务 (前端 HTML/JS/CSS)
app.use(express.static(path.join(__dirname, "public")));

// 增加更多的日志记录
const proxyOptions = {
  target: `http://localhost:${PYTHON_SERVER_PORT}`, // 使用动态端口
  changeOrigin: true,
  pathRewrite: { "^/offer": "/offer" },
  onProxyReq: (proxyReq, req, res) => {
    console.log(`代理请求: ${req.method} ${req.path} -> ${proxyOptions.target}${req.path}`);
    console.log(`请求头: ${JSON.stringify(req.headers)}`);
    
    // 如果原始请求有请求体但被解析为JSON，需要重写请求体
    if (req.body && Object.keys(req.body).length > 0) {
      console.log(`请求体: ${JSON.stringify(req.body)}`);
      const bodyData = JSON.stringify(req.body);
      // 更新Content-Length头
      proxyReq.setHeader("Content-Length", Buffer.byteLength(bodyData));
      // 写入请求体到代理请求
      proxyReq.write(bodyData);
    }
  },
  onProxyRes: (proxyRes, req, res) => {
    console.log(`代理响应: ${proxyRes.statusCode} ${proxyRes.statusMessage}`);
    console.log(`响应头: ${JSON.stringify(proxyRes.headers)}`);
  },
  onError: (err, req, res) => {
    console.error("代理错误:", err);
    res.status(500).json({
      error: "无法连接到Python WebRTC服务器",
      details: err.message
    });
  },
  logLevel: "debug"
};

// 使用正确的方式设置代理中间件
app.use('/offer', createProxyMiddleware(proxyOptions));

// 健康检查端点
app.get("/health", (req, res) => {
  // 检查Python服务器是否在线
  const pythonServerCheck = http.get(`http://localhost:${PYTHON_SERVER_PORT}/health`, (response) => {
    let data = "";
    response.on("data", (chunk) => {
      data += chunk;
    });
    
    response.on("end", () => {
      res.json({
        status: "ok",
        message: "Node.js代理服务器运行中",
        pythonServer: "连接成功",
        pythonResponse: data
      });
    });
  }).on("error", (err) => {
    res.json({
      status: "warning",
      message: "Node.js代理服务器运行中",
      pythonServer: "未连接",
      error: err.message
    });
  });
  
  pythonServerCheck.end();
});

// 启动服务器
const server = app.listen(PORT, () => {
  console.log(`🚀 WebRTC代理服务器运行在 http://localhost:${PORT}`);
  console.log(`📹 尝试连接Python WebRTC服务器 (localhost:${PYTHON_SERVER_PORT})`);
});

// 优雅地处理关闭
process.on("SIGINT", () => {
  console.log("正在关闭服务器...");
  server.close(() => {
    console.log("服务器已关闭");
    process.exit(0);
  });
});

