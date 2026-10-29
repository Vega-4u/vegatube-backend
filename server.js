const express = require('express');
const cors = require('cors');
const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');

const app = express();

// Full CORS support for any incoming request from AI Studio
app.use(cors({ origin: '*' }));
app.use(express.json());

const tempDir = path.join(__dirname, 'temp_music');
if (!fs.existsSync(tempDir)) {
  fs.mkdirSync(tempDir, { recursive: true });
}

// 1. Health check for GET requests
app.get('*', (req, res) => {
  return res.status(200).json({ status: 'ok', message: 'Vegatube Worker Active' });
});

// 2. Download and Test Handler
app.post('/api/download', (req, res) => {
  const { videoId, title, bitrate = '64k' } = req.body || {};

  // Agar Vegatube ka Test button bina videoId ke call kare, toh 200 Success bhejo
  if (!videoId) {
    return res.status(200).json({ status: 'success', message: 'Backend connected and ready!' });
  }

  const safeTitle = (title || 'vegatube_track').replace(/[^a-zA-Z0-9_-]/g, '_');
  const filePath = path.join(tempDir, `${safeTitle}_${Date.now()}.mp3`);

  const command = `yt-dlp -x --audio-format mp3 --audio-quality ${bitrate} --embed-thumbnail --add-metadata -o "${filePath}" "https://www.youtube.com/watch?v=${videoId}"`;

  exec(command, (err, stdout, stderr) => {
    if (err) {
      console.error('yt-dlp error:', stderr || err.message);
      return res.status(500).json({ error: 'Audio processing failed' });
    }

    res.download(filePath, `${safeTitle}.mp3`, () => {
      if (fs.existsSync(filePath)) {
        fs.unlinkSync(filePath);
      }
    });
  });
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Worker active on port ${PORT}`));
