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

app.post('/api/download', (req, res) => {
  const { videoId, title, bitrate = '64k' } = req.body;

  if (!videoId) {
    return res.status(400).json({ error: 'videoId is required' });
  }

  const safeTitle = (title || 'vegatube_track').replace(/[^a-zA-Z0-9_-]/g, '_');
  const filePath = path.join(tempDir, `${safeTitle}_${Date.now()}.mp3`);

  // 64kbps conversion + thumbnail & tags injection
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
