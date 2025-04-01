from flask import Flask, request, send_file
import os
import threading
from concurrent.futures import ThreadPoolExecutor
import pdfkit

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=4)  # 设置 4 个并发线程

# 创建线程局部存储，用于每个线程独立的 pdfkit 配置
thread_local = threading.local()

def get_pdfkit_config():
    if not hasattr(thread_local, 'pdfkit_config'):
        # 为每个线程创建独立的配置
        thread_local.pdfkit_config = pdfkit.configuration(wkhtmltopdf='/bin/wkhtmltopdf')  # 替换为你的 wkhtmltopdf 路径
    return thread_local.pdfkit_config

def generate_pdf_task(url, output_file):
    try:
        # 获取当前线程的独立配置
        pdfkit_config = get_pdfkit_config()
        
        # 使用 pdfkit 来生成 PDF
        pdfkit.from_url(url, output_file, configuration=pdfkit_config, options={
            'debug-javascript': '',
            'log-level': 'info',
            'no-stop-slow-scripts': '',
            'javascript-delay': 5000,  # 增加等待时间
            'print-media-type': ''  # 强制使用打印媒体类型
        })
    except Exception as e:
        raise RuntimeError(f"PDF generation failed: {str(e)}")

@app.route("/pdf", methods=["POST"])
def generate_pdf():
    url = request.json.get("url")
    if not url:
        return {"error": "Missing URL"}, 400

    output_file = f"/tmp/output_{os.getpid()}.pdf"
    future = executor.submit(generate_pdf_task, url, output_file)

    try:
        future.result()  # 等待执行完成
        return send_file(output_file, as_attachment=True)
    except Exception as e:
        return {"error": str(e)}, 500
    finally:
        if os.path.exists(output_file):
            os.remove(output_file)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, threaded=True)
