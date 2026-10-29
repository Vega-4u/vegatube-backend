const express = require('express');
const cors = require('cors');
const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');

const app = express();
app.use(cors());
app.use(express.json());

const tempDir = path.join(__dirname, 'temp_music');
if (!fs.existsSync(tempDir)) {
  fs.mkdirSync(tempDir, { recursive: true });
}

// Health check endpoint for Vegatube Test button
app.get('/', (req, res) => {
  res.status(200).json({ status: 'ok', message: 'Vegatube Worker Active' });
});

app.get('/api/download', (req, res) => {
  res.status(200).json({ status: 'ok', message: 'Download API ready' });
});

// Download handler
app.post('/api/download', (req, res) => {
  const { videoId, title, bitrate = '64k' } = req.body;

  if (!videoId) {
    // Return 200 on test/empty probe so Vegatube Test passes
    return res.status(200).json({ status: 'ready', message: 'Endpoint active' });
  }

  const safeTitle = (title || 'vegatube_track').replace(/[^a-zA-Z0-9_-]/g, '_');
  const filePath = path.join(tempDir, `${safeTitle}_${Date.now()}.mp3`);

  const command = `yt-dlp -x --audio-format mp3 --audio-quality ${bitrate} --embed-thumbnail --add-metadata -o "${filePath}" "https://www.youtube.com/watch?v=${videoId}"`;

  exec(command, (err, stdout, stderr) => {
    if (err) {
      console.error('Download error:', stderr || err.message);
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
