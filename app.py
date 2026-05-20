import os
import requests
import json
import fitz  # PyMuPDF，用于解析 PDF
from flask import Flask, request, jsonify, render_template, Response
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# ==========================================
# 🔐 环境变量与 API 密钥
# ==========================================
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
OCR_SPACE_API_KEY = os.environ.get("OCR_SPACE_API_KEY", "helloworld") 

def extract_text_from_pdf(file_bytes):
    """从上传的 PDF 字节流中提取纯文本"""
    text = ""
    try:
        doc = fitz.open(stream=file_bytes, filetype="pdf")
        for page in doc:
            text += page.get_text()
        return text.strip()
    except Exception as e:
        return f"PDF解析失败: {str(e)}"

def extract_text_from_image(file_bytes):
    """调用 OCR.space 接口识别 JD 截图中的文字"""
    try:
        response = requests.post(
            'https://api.ocr.space/parse/image',
            files={'file': ('image.jpg', file_bytes, 'image/jpeg')},
            data={'apikey': OCR_SPACE_API_KEY, 'language': 'chs', 'isOverlayRequired': False},
            timeout=15
        )
        result = response.json()
        if result.get('IsErroredOnProcessing'):
            return "OCR 识别出错，请确保图片清晰。"
        
        parsed_text = result.get('ParsedResults', [{}])[0].get('ParsedText', '')
        return parsed_text.strip()
    except Exception as e:
        return f"OCR网络请求失败: {str(e)}"

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/api/generate_resume', methods=['POST'])
def generate_resume():
    if not DEEPSEEK_API_KEY:
        return jsonify({"error": "未检测到 DEEPSEEK_API_KEY"}), 500

    # 1. 接收 FormData 数据
    resume_mode = request.form.get('resume_mode', 'text')
    jd_mode = request.form.get('jd_mode', 'text')
    
    # 2. 提取简历文本
    resume_text = ""
    if resume_mode == 'pdf' and 'resume_file' in request.files:
        file = request.files['resume_file']
        resume_text = extract_text_from_pdf(file.read())
    else:
        resume_text = request.form.get('resume_text', '').strip()

    # 3. 提取 JD 文本
    jd_text = ""
    if jd_mode == 'image' and 'jd_file' in request.files:
        file = request.files['jd_file']
        jd_text = extract_text_from_image(file.read())
    else:
        jd_text = request.form.get('jd_text', '').strip()

    if not resume_text or not jd_text:
        return jsonify({"error": "简历或JD内容为空，请检查输入法方式或文件是否成功上传！"}), 400

    # 4. 构造大模型提示词
    system_prompt = f"""你是一位拥有十年大厂经验的高级技术与HR双料专家。当前任务：根据用户提供的目标岗位 JD，对其原有简历进行深度重构与精准对齐。

【输入数据】：
1. 原有简历内容：
{resume_text}

2. 目标岗位 JD (招聘需求)：
{jd_text}

【输出规范】：
1. 关键词对齐：提取 JD 中的核心能力词汇，无缝融入简历经历中。
2. STAR法则：将原有经历改写为“情境-任务-行动-结果”结构，用数据化结果说话。
3. 结构化排版：输出的内容必须包含【个人总结】、【核心技能对齐】、【重构后的项目经历】。
4. 备考预测：在最后，必须提供一个名为【暗黑备考区】的章节，给出 3 道该岗位极大概率会问到的硬核面试题及作答思路。
请直接输出 Markdown 格式，绝不废话。
"""

    # 5. SSE 流式输出
    def generate_stream():
        try:
            response = requests.post(
                "https://api.deepseek.com/v1/chat/completions",
                json={
                    "model": "deepseek-chat",
                    "messages": [{"role": "user", "content": system_prompt}],
                    "temperature": 0.3,
                    "stream": True,
                    "max_tokens": 4096
                },
                headers={
                    "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
                    "Content-Type": "application/json"
                },
                stream=True,
                timeout=60
            )

            # 🚨 拦截器：如果接口欠费或密钥错误，直接把红字吐给前端
            if response.status_code != 200:
                yield f"data: {json.dumps({'error': f'大模型接口拒绝访问，状态码: {response.status_code}'})}\n\n"
                return

            for line in response.iter_lines():
                if line:
                    decoded_line = line.decode('utf-8').strip()
                    if decoded_line.startswith('data: '):
                        data_str = decoded_line[6:].strip()
                        if data_str == '[DONE]' or not data_str:
                            continue
                        try:
                            data_json = json.loads(data_str)
                            chunk = data_json['choices'][0]['delta'].get('content', '')
                            if chunk:
                                yield f"data: {json.dumps({'text': chunk})}\n\n"
                        except:
                            pass
        except Exception as e:
            yield f"data: {json.dumps({'error': f'网络或解析异常: {str(e)}'})}\n\n"

    return Response(generate_stream(), mimetype='text/event-stream')

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get("PORT", 5002), debug=True)
