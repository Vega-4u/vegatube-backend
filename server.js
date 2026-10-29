const express = require('express');
const cors = require('cors');
const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');

const app = express();
app.use(cors({ origin: '*' }));
app.use(express.json());

const tempDir = path.join(__dirname, 'temp_music');
if (!fs.existsSync(tempDir)) {
  fs.mkdirSync(tempDir, { recursive: true });
}

// Ping / Health check
app.get('/', (req, res) => res.status(200).json({ status: 'ok' }));
app.get('/api/download', (req, res) => res.status(200).json({ status: 'ready' }));

// Ultra-fast streaming download with auto-cleanup (Zero KB Fix)
app.get('/api/stream-download', (req, res) => {
  const { videoId, title, bitrate = '64k' } = req.query;

  if (!videoId) {
    return res.status(400).send('videoId missing');
  }

  const safeTitle = (title || 'Song').replace(/[^a-zA-Z0-9_\-\s]/g, '').trim().replace(/\s+/g, '_') || 'Vegatube_Track';
  const outPath = path.join(tempDir, `${safeTitle}_${Date.now()}.mp3`);

  // Direct fast conversion
  const cmd = `yt-dlp -f "ba/b" -x --audio-format mp3 --audio-quality ${bitrate} --no-playlist --embed-thumbnail --add-metadata -o "${outPath}" "https://www.youtube.com/watch?v=${videoId}"`;

  exec(cmd, { timeout: 120000 }, (err) => {
    if (err || !fs.existsSync(outPath)) {
      console.error('yt-dlp err:', err);
      return res.status(500).send('Conversion error');
    }

    res.download(outPath, `${safeTitle}.mp3`, () => {
      // Delete temporary file after sending
      if (fs.existsSync(outPath)) {
        try { fs.unlinkSync(outPath); } catch (e) {}
      }
    });
  });
});

const PORT = process.env.PORT || 10000;
app.listen(PORT, () => console.log(`Engine running on ${PORT}`));
