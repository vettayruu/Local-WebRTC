# 环境安装检查脚本
# 运行此脚本以检查是否已安装所有必要的Python依赖

import importlib.util
import sys

# 需要安装的Python包
required_packages = {
    'aiohttp': 'aiohttp',
    'aiortc': 'aiortc',
    'cv2': 'opencv-python',
    'av': 'av'
}

missing_packages = []

print("检查Python环境...")
print(f"Python版本: {sys.version}")
print("检查必要的包:")

for module, package in required_packages.items():
    spec = importlib.util.find_spec(module)
    
    if spec is None:
        print(f"❌ {module} 未安装 (需要安装: {package})")
        missing_packages.append(package)
    else:
        try:
            # 尝试导入模块以确保它正常工作
            lib = importlib.import_module(module)
            # 尝试获取版本信息（不是所有模块都有 __version__）
            version = getattr(lib, "__version__", "未知版本")
            print(f"✅ {module} 已安装 ({version})")
        except Exception as e:
            print(f"❌ {module} 安装损坏: {str(e)}")
            missing_packages.append(package)

if missing_packages:
    print("\n需要安装以下包:")
    print(f"pip install {' '.join(missing_packages)}")
else:
    print("\n✅ 所有必要的Python包已安装。")
    
# 检查摄像头
try:
    import cv2
    cap = cv2.VideoCapture(0)
    if cap.isOpened():
        ret, frame = cap.read()
        if ret:
            print("✅ 摄像头工作正常。")
        else:
            print("❌ 摄像头无法读取图像。")
    else:
        print("❌ 无法打开摄像头。")
    cap.release()
except Exception as e:
    print(f"❌ 摄像头检查失败: {str(e)}")