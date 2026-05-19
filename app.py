import os
import requests
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None
try:
    import docx
except ImportError:
    docx = None

app = Flask(__name__)
CORS(app)

# ==========================================
# 你的专属密钥配置
# ==========================================
API_KEY = "sk-48bf10f821904382ae63972a30f5f6db"
API_URL = "https://api.deepseek.com/v1/chat/completions"


def parse_pdf(file_path):
    if fitz is None: return "[错误] 未安装 PyMuPDF"
    text = ""
    with fitz.open(file_path) as doc:
        for page in doc: text += page.get_text()
    return text


def parse_docx(file_path):
    if docx is None: return "[错误] 未安装 python-docx"
    doc = docx.Document(file_path)
    return '\n'.join([para.text for para in doc.paragraphs])


# 调用免费 OCR API 解析全网任意求职详情截图
def parse_image_ocr(file_path):
    try:
        with open(file_path, 'rb') as f:
            response = requests.post(
                'https://api.ocr.space/parse/image',
                files={'file': f},
                data={'apikey': 'helloworld', 'language': 'chs'},
                timeout=20
            )
        result = response.json()
        if not result.get('IsErroredOnProcessing'):
            return result['ParsedResults'][0]['ParsedText']
        else:
            return "[错误] OCR 解析失败，请重试或直接粘贴文本。"
    except Exception as e:
        return f"[错误] 图片提取失败: {str(e)}"


@app.route('/')
def home():
    return render_template('index.html')


@app.route('/api/customize_resume', methods=['POST'])
def customize_resume():
    # 确保临时文件夹存在
    temp_dir = os.path.join(os.getcwd(), "temp_uploads")
    if not os.path.exists(temp_dir): os.makedirs(temp_dir)

    jd_text = ""
    jd_mode = request.form.get('jd_mode', 'text')

    # 1. 深度解析目标岗位 JD (无论是纯文本还是截图)
    if jd_mode == 'text':
        jd_text = request.form.get('jd_text', '').strip()
    else:
        if 'jd_file' not in request.files:
            return jsonify({"error": "没有收到 JD 截图"}), 400
        img_file = request.files['jd_file']
        img_path = os.path.join(temp_dir, "jd_img_" + img_file.filename)
        img_file.save(img_path)
        jd_text = parse_image_ocr(img_path)
        try:
            os.remove(img_path)
        except:
            pass

    if not jd_text or jd_text.startswith("[错误"):
        return jsonify({"error": f"JD 提取失败: {jd_text}"}), 400

    # 2. 深度读取原始简历文件 (PDF/Word)
    if 'resume_file' not in request.files:
        return jsonify({"error": "没有收到简历文件"}), 400

    file = request.files['resume_file']
    file_path = os.path.join(temp_dir, "resume_" + file.filename)
    file.save(file_path)

    resume_text = ""
    if file.filename.lower().endswith('.pdf'):
        resume_text = parse_pdf(file_path)
    elif file.filename.lower().endswith(('.docx', '.doc')):
        resume_text = parse_docx(file_path)
    else:
        return jsonify({"error": "请上传 PDF 或 Word 格式的简历"}), 400

    try:
        os.remove(file_path)
    except:
        pass

    # 3. 终极提示词工程：禁止说废话，强迫 AI 变成 A4 简历打印机
        # 终极提示词工程：纯净简历 + 隐藏面试预测
        system_prompt = f"""你是一位拥有 10 年经验的大厂资深 HR 兼顶级简历优化专家。
    目标岗位 JD:
    {jd_text}

    候选人的原始简历:
    {resume_text}

    【你的终极任务】：
    请你完成两个步骤，且中间必须用三个短横线 `---` 严格隔开！

    ### 步骤一：重写简历正文（在 `---` 之前输出）
    直接以候选人的第一人称视角，重写一份完整、完美对齐 JD 且可以直接投递的简历正文。不要有任何多余的客套话。
    格式必须如下：
    # [姓名]
    📱 [电话] | ✉️ [邮箱] | 🎯 意向岗位：[根据JD提取岗位名]

    ## 💡 核心优势 (Summary)
    [结合JD写 3-4 行的极强个人亮点总结]

    ## 💼 核心经历 (Experience)
    ### [公司/项目名称] | [重写后的专业职位名称] | [时间段]
    - **业务背景**: [一句话描述]
    - **核心行动**: [强力植入 JD 关键词，STAR原则]
    - **量化成果**: [合理推算或优化业务数据]

    ---

    ### 步骤二：面试神预测（必须在 `---` 之后输出）
    根据这份 JD 的要求和候选人简历的薄弱环节，预测 3 道最可能被问到的刁钻面试题。
    格式必须如下：
    ## 🎯 高频面试题神预测与反杀话术
    **Q1: [面试题 1]**
    - **HR考察意图**: ...
    - **反杀话术思路**: ...

    **Q2: [面试题 2]**...
    **Q3: [面试题 3]**...
    """

    try:
        response = requests.post(API_URL, json={
            "model": "deepseek-chat",
            "messages": [{"role": "user", "content": system_prompt}],
            "temperature": 0.3
        }, headers={
            "Authorization": f"Bearer {API_KEY}",
            "Content-Type": "application/json"
        }, timeout=60)

        if response.status_code != 200:
            return jsonify({"error": "大模型调用失败"}), 500

        res_data = response.json()
        return jsonify({"result": res_data['choices'][0]['message']['content']})

    except Exception as e:
        return jsonify({"error": f"内部错误: {str(e)}"}), 500


if __name__ == '__main__':
    # 使用 5001 端口防冲突
    app.run(host='127.0.0.1', port=5001, debug=True)