const express = require('express');
const bodyParser = require('body-parser');
const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const app = express();
app.use(bodyParser.json());

// 提供静态文件（调试页面）
app.use(express.static(path.join(__dirname, 'public')));

// 启动一个浏览器实例，复用它
let browser;

async function initializeBrowser() {
    if (!browser) {
        browser = await puppeteer.launch({
            headless: true,
            executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/bin/chromium',
            args: ['--no-sandbox', '--disable-setuid-sandbox']
        });
    }
    return browser;
}

// 使用 Puppeteer 来生成 PDF
async function generatePdf(url, outputFile, format = 'A4') {
    const browser = await initializeBrowser();
    const page = await browser.newPage();
    await page.goto(url, { waitUntil: 'networkidle0', timeout: 120000 });
    await page.pdf({ path: outputFile, format: format });
    await page.close(); // 页面关闭，但浏览器实例不关闭
}

// 定义 PDF 生成的 API
app.post('/pdf', async (req, res) => {
    const url = req.body.url;
    const format = req.body.format || 'A4';  // 从请求中获取格式，默认 A4
    if (!url) {
        return res.status(400).json({ error: 'Missing URL' });
    }

    const outputFile = path.join('/tmp', `output_${Date.now()}.pdf`);

    try {
        await generatePdf(url, outputFile, format);
        res.sendFile(outputFile, (err) => {
            if (err) {
                res.status(500).json({ error: 'Failed to send file' });
            }
            // 删除文件
            fs.unlinkSync(outputFile);
        });
    } catch (e) {
        res.status(500).json({ error: e.message });
    }
});

// 启动服务器
const port = 5000;
app.listen(port, () => {
    console.log(`Server is running on port ${port}`);
});

// 在服务器关闭时关闭浏览器实例
process.on('SIGTERM', async () => {
    if (browser) {
        await browser.close();
    }
    process.exit(0);
});
