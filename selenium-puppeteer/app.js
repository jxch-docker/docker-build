const express = require('express');
const bodyParser = require('body-parser');
const puppeteer = require('puppeteer');
const fs = require('fs');
const path = require('path');

const app = express();
app.use(bodyParser.json());

// 使用 Puppeteer 来生成 PDF
async function generatePdf(url, outputFile) {
  const browser = await puppeteer.launch({
    headless: true,
    executablePath: process.env.PUPPETEER_EXECUTABLE_PATH || '/usr/bin/chromium',
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });
  const page = await browser.newPage();
  await page.goto(url, { waitUntil: 'networkidle0', timeout: 120000 });
  await page.pdf({ path: outputFile, format: 'A4' });
  await browser.close();
}

// 定义 PDF 生成的 API
app.post('/pdf', async (req, res) => {
  const url = req.body.url;
  if (!url) {
    return res.status(400).json({ error: 'Missing URL' });
  }

  const outputFile = path.join('/tmp', `output_${Date.now()}.pdf`);
  
  try {
    await generatePdf(url, outputFile);
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
