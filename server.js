const express = require('express');
const cors = require('cors');
const { exec, spawn } = require('child_process');
const path = require('path');
const fs = require('fs');

const app = express();

app.use(cors({ origin: '*' }));
app.use(express.json());

const tempDir = path.join(__dirname, 'temp_music');
if (!fs.existsSync(tempDir)) {
  fs.mkdirSync(tempDir, { recursive: true });
}

// 1. Health check & Ping
app.get('/', (req, res) => {
  return res.status(200).json({ status: 'ok', message: 'Vegatube Engine Ready' });
});

app.get('/api/download', (req, res) => {
  return res.status(200).json({ status: 'ready', message: 'Download API ready' });
});

// 2. Direct Browser Download Endpoint (GET request ensures iOS Safari native download prompt)
app.get('/api/stream-download', (req, res) => {
  const videoId = req.query.videoId;
  const rawTitle = req.query.title || 'Vegatube_Song';
  const bitrate = req.query.bitrate || '64k';

  if (!videoId) {
    return res.status(400).send('videoId is required');
  }

  const cleanTitle = rawTitle.replace(/[^a-zA-Z0-9_\-\s]/g, '').trim().replace(/\s+/g, '_') || 'Vegatube_Track';
  const fileName = `${cleanTitle}.mp3`;

  // Force iOS Safari to trigger the native save prompt
  res.setHeader('Content-Disposition', `attachment; filename="${fileName}"; filename*=UTF-8''${encodeURIComponent(fileName)}`);
  res.setHeader('Content-Type', 'audio/mpeg');

  const ytDlp = spawn('yt-dlp', [
    '-x',
    '--audio-format', 'mp3',
    '--audio-quality', bitrate,
    '--embed-thumbnail',
    '--add-metadata',
    '-o', '-', // Stream directly to stdout
    `https://www.youtube.com/watch?v=${videoId}`
  ]);

  ytDlp.stdout.pipe(res);

  ytDlp.stderr.on('data', (data) => {
    // Log worker progress internally
  });

  ytDlp.on('error', (err) => {
    console.error('yt-dlp error:', err);
    if (!res.headersSent) res.status(500).send('Audio extraction failed');
  });

  req.on('close', () => {
    ytDlp.kill();
  });
});

// Fallback POST endpoint
app.post('/api/download', (req, res) => {
  const { videoId, title, bitrate = '64k' } = req.body || {};
  if (!videoId || videoId === 'test') {
    return res.status(200).json({ status: 'success', message: 'Connected' });
  }
  const cleanTitle = (title || 'track').replace(/[^a-zA-Z0-9_-]/g, '_');
  const downloadUrl = `/api/stream-download?videoId=${encodeURIComponent(videoId)}&title=${encodeURIComponent(cleanTitle)}&bitrate=${bitrate}`;
  return res.status(200).json({ downloadUrl });
});

const PORT = process.env.PORT || 10000;
app.listen(PORT, () => console.log(`Worker active on port ${PORT}`));
