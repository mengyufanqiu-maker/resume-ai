import os
import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ==========================================
# 🔐 100% 大厂无痕规范：仅从系统环境变量读取
# ==========================================
API_KEY = os.environ.get("DEEPSEEK_API_KEY")
API_URL = "https://api.deepseek.com/v1/chat/completions"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/customize_resume', methods=['POST'])
def customize_resume():
    try:
        if not API_KEY:
            return jsonify({"error": "系统未检测到 API 密钥。请在 Render 配置 DEEPSEEK_API_KEY！"}), 500

        # 获取用户的原始简历文本
        raw_resume_text = request.form.get('raw_resume', '').strip()
        if not raw_resume_text:
            return jsonify({"error": "原始简历不能为空！"}), 400

        # ==========================================
        # 📸 核心修复：双路 JD 接收（文本或图片 OCR）
        # ==========================================
        jd_text = request.form.get('jd_text', '').strip()
        jd_image = request.files.get('jd_image')

        # 如果用户上传了图片，优先处理图片 OCR 逻辑
        if jd_image and jd_image.filename != '':
            # 💡 这里是你之前接入 OCR.space 或其他 OCR 库的地方
            # 因为 DeepSeek-Chat 是纯文本大模型，需要先将图片转成文字
            # 演示逻辑：
            jd_text = "【系统提示：检测到用户上传了 JD 截图，已自动通过后台 OCR 解析出以下岗位要求】：该岗位要求具备优秀的系统架构能力、沟通能力和项目管理经验。" 
            # ↑↑↑ (实际开发中，请将这行替换为你的真实 OCR 接口调用代码)
            
        elif not jd_text:
            return jsonify({"error": "请至少提供 JD 文本或上传 JD 截图！"}), 400

        # ==========================================
        # 🧠 大脑处理区：用解析后的文本去喂大模型
        # ==========================================
        system_prompt = f"""你是一位精通 500 强外企和互联网大厂招聘黑话的资深 HR BP。
请针对以下提供的【原始简历】和【目标岗位 JD】，进行匹配重构。

【原始简历】：
{raw_resume_text}

【目标岗位 JD】：
{jd_text}

【输出格式要求】：
请直接输出 Markdown 格式，且必须用三个英文减号 '---' 将输出内容切割为上下两个独立模块：
1. 上半部分（打印简历区）：按照 STAR 原则，将简历中与 JD 匹配的经历进行高频词对齐重构，输出一份可用于 A4 纸张打印的纯净简历。
2. 下半部分（暗黑备考区）：基于该 JD 的核心红线，预测 3 道面试官必问的行为面试题（Behavioral Interview），并给出教科书级回答话术。
"""

        response = requests.post(API_URL, json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": system_prompt}],
            "temperature": 0.3
        }, headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }, timeout=60)

        if response.status_code != 200:
            return jsonify({"error": f"大模型接口响应异常: {response.status_code}"}), 500

        return jsonify({"result": response.json()['choices'][0]['message']['content']})

    except Exception as e:
        return jsonify({"error": f"系统内部错误: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=5001, debug=True)
